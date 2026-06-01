"""完整的 Shannon 压缩 / 解压"封装"层：

* canonical 码表：只存 (token, count)，解码端用同一份 Shannon 算法重建码字。
* 端到端文件格式：把码表 + pad + 位流打包进一个 .shc 文件。

文件布局
--------
[4B] MAGIC = b'SHCB'
[1B] version = 1
[1B] pad_bits        (末字节填充的 0 的个数)
[4B] N               (token 总数)
[N entries]:
    [2B] utf-8 字节长度 m   (uint16, little-endian)
    [m B] token 的 utf-8 字节
    [4B] count             (uint32, little-endian)
[剩余字节] 位流 payload     (MSB-first 比特对应字节高位)

设计取舍
--------
* count 用 uint32 -> 支持非常长的文本，且与对端约定简单
* token UTF-8 长度用 uint16 -> singleton 合并后 token 可能很长，1B 不够保险
* 没有显式存"模式"字段：解码端不需要知道 tokenizer 类型，
  因为 token 直接就是解码字典的键，解码出来 join 即可还原文本。
"""

from __future__ import annotations

import struct
from pathlib import Path
from typing import Dict, Iterable, List, Tuple

from shannon import ShannonCode
from shannon_bytes import encode_to_bytes, decode_from_bytes

MAGIC = b"SHCB"
VERSION = 1
_HEADER = struct.Struct("<4sBBI")          # magic, version, pad, N
_LEN = struct.Struct("<H")                 # token utf-8 length
_CNT = struct.Struct("<I")                 # count


# ---------------- 端到端编码 ----------------
def encode_tokens(tokens: List[str]) -> Tuple[bytes, ShannonCode, int]:
    """token 序列 -> (字节流, 码表, pad_bits)。"""
    if not tokens:
        raise ValueError("token 序列为空")
    code = ShannonCode.from_text(tokens)   # Counter(list) 按元素计数，恰好就是 token 计数
    data, pad = encode_to_bytes(tokens, code)
    return data, code, pad


def save_compressed(path: Path, tokens: List[str]) -> Tuple[ShannonCode, int, int]:
    """编码并写到一个完整的 .shc 文件。返回 (码表, 压缩字节数, 码表字节数)。"""
    data, code, pad = encode_tokens(tokens)

    # 按 token 第一次出现的顺序保存——保证两端 Counter 顺序一致
    # 实际只要 (token, count) 集合一致即可，from_text 内部会再排序
    counts = {}
    for t in tokens:
        counts[t] = counts.get(t, 0) + 1

    body = bytearray()
    body += _HEADER.pack(MAGIC, VERSION, pad, len(counts))
    codebook_bytes = len(body)
    for tok, cnt in counts.items():
        b = tok.encode("utf-8")
        body += _LEN.pack(len(b))
        body += b
        body += _CNT.pack(cnt)
    codebook_bytes = len(body) - codebook_bytes + _HEADER.size  # 头 + 表
    body += data

    path.parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_bytes(bytes(body))
    return code, len(data), codebook_bytes


# ---------------- 端到端解码 ----------------
def load_compressed(path: Path) -> Tuple[List[str], ShannonCode]:
    """读 .shc，重建码表并解码出 token 列表。"""
    raw = Path(path).read_bytes()
    magic, version, pad, n = _HEADER.unpack_from(raw, 0)
    if magic != MAGIC:
        raise ValueError(f"非 .shc 文件 (magic={magic!r})")
    if version != VERSION:
        raise ValueError(f"不支持的版本 {version}")

    off = _HEADER.size
    counts: Dict[str, int] = {}
    for _ in range(n):
        (m,) = _LEN.unpack_from(raw, off); off += _LEN.size
        tok = raw[off:off + m].decode("utf-8"); off += m
        (c,) = _CNT.unpack_from(raw, off); off += _CNT.size
        counts[tok] = c

    payload = raw[off:]
    # 必须和 from_text 的浮点路径一致，避免 FP 漂移导致码长边界翻转：
    # from_text 内部先做 c/total -> 再交给 from_probabilities 二次归一化。
    total = sum(counts.values())
    probs = {t: c / total for t, c in counts.items()}
    code = ShannonCode.from_probabilities(probs)
    # 解码字节流回 token 序列（注意：decode_from_bytes 返回 str；
    # 当 token 多字符时，逐 token append 的结果 join 起来也是 str，
    # 但我们想拿回 token 列表来对账，于是这里直接用 ShannonCode.decode 的方式重写）
    tokens = _decode_to_token_list(payload, pad, code)
    return tokens, code


def _decode_to_token_list(data: bytes, pad_bits: int, code: ShannonCode) -> List[str]:
    """字节流 -> token 列表（不 join）。逻辑与 shannon_bytes.decode_from_bytes 一致。"""
    by_len: Dict[int, Dict[int, str]] = {}
    for sym, codestr in code.code_table.items():
        L = code.lengths[sym]
        c = int(codestr, 2) if codestr else 0
        by_len.setdefault(L, {})[c] = sym
    lengths = sorted(by_len.keys())
    max_len = lengths[-1]

    total_bits = len(data) * 8 - pad_bits
    out: List[str] = []
    window = 0
    window_bits = 0
    byte_idx = 0
    bits_consumed = 0

    while bits_consumed < total_bits:
        while window_bits < max_len and byte_idx < len(data):
            window = (window << 8) | data[byte_idx]
            window_bits += 8
            byte_idx += 1

        usable = min(window_bits, total_bits - bits_consumed)
        matched = False
        for L in lengths:
            if L > usable:
                break
            cand = (window >> (window_bits - L)) & ((1 << L) - 1)
            if cand in by_len[L]:
                out.append(by_len[L][cand])
                window_bits -= L
                window &= (1 << window_bits) - 1 if window_bits > 0 else 0
                bits_consumed += L
                matched = True
                break
        if not matched:
            raise ValueError(f"解码失败：第 {bits_consumed} 位")
    return out


def decompress_to_text(path: Path) -> str:
    tokens, _ = load_compressed(path)
    return "".join(tokens)
