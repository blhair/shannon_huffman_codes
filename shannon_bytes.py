"""字节流版本的 Shannon 编/解码，配套 shannon.py 的 ShannonCode。

关键点
------
* 码字用整数表示，单独记录长度。
* 比特按 MSB-first 写入字节；末尾不足 8 位补 0，单独返回 pad 位数。
* 解码字典按码字长度分组：{L: {code_int: symbol}}。
  这样从短到长尝试，命中即消费 L 个比特——必须同时匹配 `(code, length)`，
  因为整数 1 既可以是长度 1 的码字 "1"，也可以是长度 2 的码字 "01"，
  仅用整数会冲突。
"""

from __future__ import annotations

from typing import Dict, List, Tuple

from shannon import ShannonCode


# ---------- 编码 ----------
def encode_to_bytes(text: str, code: ShannonCode) -> Tuple[bytes, int]:
    """返回 (字节流, pad_bits)。pad_bits 是最后一个字节里填充的 0 的个数。"""
    out = bytearray()
    buf = 0          # 比特缓冲区（整数）
    buf_bits = 0     # 缓冲区里现存的比特数

    for ch in text:
        codestr = code.code_table[ch]
        L = code.lengths[ch]
        c = int(codestr, 2) if codestr else 0
        # 把 L 位写到缓冲区低端（buf 已有的位整体左移 L）
        buf = (buf << L) | c
        buf_bits += L
        # 缓冲区每满 8 位输出一个字节（取高位）
        while buf_bits >= 8:
            buf_bits -= 8
            out.append((buf >> buf_bits) & 0xFF)
            buf &= (1 << buf_bits) - 1  # 砍掉已输出的高位

    # 尾部 flush：不足 8 位的部分左移到字节高位，低位补 0
    pad = 0
    if buf_bits > 0:
        pad = 8 - buf_bits
        out.append((buf << pad) & 0xFF)
    return bytes(out), pad


# ---------- 构建按长度分组的解码字典 ----------
def build_decode_dict(code: ShannonCode) -> Tuple[Dict[int, Dict[int, str]], List[int]]:
    by_len: Dict[int, Dict[int, str]] = {}
    for sym, codestr in code.code_table.items():
        L = code.lengths[sym]
        c = int(codestr, 2) if codestr else 0
        by_len.setdefault(L, {})[c] = sym
    return by_len, sorted(by_len.keys())


# ---------- 解码 ----------
def decode_from_bytes(data: bytes, pad_bits: int, code: ShannonCode) -> str:
    """字节流 -> 文本。pad_bits 是末字节里需要丢弃的低位个数。"""
    by_len, lengths = build_decode_dict(code)
    max_len = lengths[-1]

    total_bits = len(data) * 8 - pad_bits
    out: List[str] = []

    # 用一个滑动比特缓冲区：buf 的低位存"待消费"的比特，最低位 = 当前最旧待匹配位
    # 为简化代码，这里改成：维护一个高位对齐的窗口 (window, window_bits)，
    # 每次按长度 L 从 window 的最高位取 L 位。
    window = 0
    window_bits = 0
    byte_idx = 0

    bits_consumed = 0  # 已经成功解码消耗的比特数
    while bits_consumed < total_bits:
        # 把字节往 window 里塞，直到窗口里至少有 max_len 位或者字节用完
        while window_bits < max_len and byte_idx < len(data):
            window = (window << 8) | data[byte_idx]
            window_bits += 8
            byte_idx += 1

        # 剩余可用比特数（窗口里 + 还没看到字节里的）= 总比特 - 已消费
        remain = total_bits - bits_consumed
        usable = min(window_bits, remain)

        matched = False
        # 从短到长尝试；前缀码保证最先命中的就是正确的
        for L in lengths:
            if L > usable:
                break
            # 取 window 最高 L 位
            cand = (window >> (window_bits - L)) & ((1 << L) - 1)
            if cand in by_len[L]:
                out.append(by_len[L][cand])
                # 从 window 里"消费"掉这 L 位
                window_bits -= L
                window &= (1 << window_bits) - 1 if window_bits > 0 else 0
                bits_consumed += L
                matched = True
                break
        if not matched:
            raise ValueError(
                f"解码失败：在比特位 {bits_consumed}，剩余 window={window:0{window_bits}b}"
            )
    return "".join(out)


# ---------- 演示：(code, length) 匹配冲突 ----------
def demo_code_length_collision() -> None:
    """展示为什么解码字典必须以 (code, length) 联合作键。

    取两个码字 "1"（整数 1，长度 1）和 "01"（整数 1，长度 2）。
    它们整数值都是 1，仅用整数做键会互相覆盖。
    """
    pairs = [("A", "1"), ("B", "01")]
    print("码字 -> 整数：")
    for s, c in pairs:
        print(f"  {s}: '{c}' -> int={int(c, 2)}, len={len(c)}")

    bad: Dict[int, str] = {}
    for s, c in pairs:
        bad[int(c, 2)] = s
    print(f"仅用整数做键：{bad}    <-- A 被 B 覆盖，丢失")

    good: Dict[Tuple[int, int], str] = {}
    for s, c in pairs:
        good[(int(c, 2), len(c))] = s
    print(f"用 (int, len)：{good}    <-- 区分开了")


if __name__ == "__main__":
    demo_code_length_collision()
