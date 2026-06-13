# -*- coding: utf-8 -*-
"""Project 1-B 组间 PK 基准脚本。

同时加载【本组(我)】根目录实现 与【对手(同学)】info_project_1B 实现，
在同一组中英文文本上跑 Shannon / Q-ary Huffman 编解码，统一口径采集：
  - 正确性（无损 roundtrip、是否前缀码）
  - 平均码长 L、编码效率 eta（算法级，口径统一）
  - 纯码流字节数（把码字按 ceil(log2 q) bit 打包后的净载荷，跨实现可比）
  - 自包含文件字节数（各自的容器格式，反映工程封装）
  - 编/解码耗时

不修改任何一方源码，只 import 调用。结果写入 pk_results.json。
"""
from __future__ import annotations

import importlib.util
import math
import os
import sys
import time
from collections import Counter
from pathlib import Path

ROOT = os.path.dirname(os.path.abspath(__file__))
OPP = os.path.join(ROOT, "info_project_1B")


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


# 我的实现（根目录）
sys.path.insert(0, ROOT)
import shannon as my_shannon            # noqa: E402
import huffman as my_huffman            # noqa: E402
import shannon_bytes as my_sbytes       # noqa: E402
import shannon_codec as my_scodec       # noqa: E402

# 对手实现（info_project_1B），用独立模块名避免覆盖
opp_shannon = _load("opp_shannon", os.path.join(OPP, "shannon.py"))
opp_huffman = _load("opp_huffman", os.path.join(OPP, "huffman.py"))

TEXTS = [
    ("badminton.txt", "中文", os.path.join(OPP, "badminton.txt")),
    ("beethoven_en.txt", "英文", os.path.join(OPP, "beethoven_en.txt")),
]


# ---------- 统一口径的算法级指标 ----------
def entropy_q(text, q):
    freq = Counter(text); n = len(text)
    Hb = -sum((c / n) * math.log2(c / n) for c in freq.values())
    return Hb if q == 2 else Hb / math.log2(q)


def avg_len(text, code_table):
    freq = Counter(text); n = len(text)
    return sum((c / n) * len(code_table[s]) for s, c in freq.items())


def stream_bytes(text, code_table, q):
    """把 q 进制码流按 ceil(log2 q) bit/数字 打包后的净字节数。"""
    bits_per_digit = max(1, (q - 1).bit_length())
    total_digits = sum(len(code_table[ch]) for ch in text)
    return math.ceil(total_digits * bits_per_digit / 8)


def is_prefix(code_table):
    codes = list(code_table.values())
    for i, a in enumerate(codes):
        for j, b in enumerate(codes):
            if i != j and b.startswith(a):
                return False
    return True


def timed(fn, repeat=5):
    best = math.inf; out = None
    for _ in range(repeat):
        t0 = time.perf_counter(); out = fn(); dt = time.perf_counter() - t0
        best = min(best, dt)
    return out, best


# ---------- 我的实现适配 ----------
def my_shannon_run(text):
    code = my_shannon.ShannonCode.from_text(text)
    ct = code.code_table
    (bits, _), t_enc = timed(lambda: (code.encode(text), None))
    restored, t_dec = timed(lambda: code.decode(bits))
    # 自包含 .shc 文件
    tmp = Path(ROOT) / "out" / "_pk_my.shc"
    _, payload_bytes, codebook_bytes = my_scodec.save_compressed(tmp, list(text))
    shc_size = os.path.getsize(tmp)
    return dict(L=avg_len(text, ct), eta=entropy_q(text, 2) / avg_len(text, ct),
                stream=stream_bytes(text, ct, 2), container=shc_size,
                container_name=".shc(自包含: canonical码表+位流)",
                prefix=is_prefix(ct), lossless=(restored == text),
                t_enc=t_enc, t_dec=t_dec, note="")


def my_huffman_run(text, q):
    code = my_huffman.HuffmanCode.from_text(text, q)
    ct = code.code_table
    (qs, _), t_enc = timed(lambda: (code.encode(text), None))
    restored, t_dec = timed(lambda: code.decode(qs))
    return dict(L=avg_len(text, ct), eta=entropy_q(text, q) / avg_len(text, ct),
                stream=stream_bytes(text, ct, q), container=None,
                container_name=".bits + .codebook.json(非紧凑)",
                prefix=is_prefix(ct), lossless=(restored == text),
                t_enc=t_enc, t_dec=t_dec, note="初版无紧凑二进制容器")


# ---------- 对手实现适配 ----------
def opp_shannon_run(text):
    (enc, codebook), t_enc = timed(lambda: opp_shannon.shannon_encode(text))
    ct = {ch: code for ch, (f, code) in codebook.items()}
    # 解码（可能因 ceil 破坏前缀而抛异常）
    try:
        restored, t_dec = timed(lambda: opp_shannon.shannon_decode(enc, ct))
        lossless = (restored == text); note = "" if lossless else "解码与原文不一致"
    except Exception as e:
        lossless = False; t_dec = math.nan; note = f"解码崩溃: {e}"
    # 外置文本码表大小
    import io
    buf = io.StringIO()
    for ch, (f, code) in codebook.items():
        cp = ord(ch)
        sym = ch if 0x20 <= cp <= 0x7E and ch not in ("\t", "\n", "\r") else f"<U+{cp:04X}>"
        buf.write(f"{sym}\t{f}\t{code}\n")
    cb_bytes = len(buf.getvalue().encode("utf-8"))
    container = len(enc) + cb_bytes  # 位流 + 外置码表（合起来才能解码）
    return dict(L=avg_len(text, ct), eta=entropy_q(text, 2) / avg_len(text, ct),
                stream=len(enc), container=container,
                container_name="位流(.bin)+外置文本码表",
                prefix=is_prefix(ct), lossless=lossless,
                t_enc=t_enc, t_dec=t_dec, note=note)


def opp_huffman_run(text, q):
    root = opp_huffman.build_qary_huffman_tree_heap(text, q)
    ct = opp_huffman.generate_codes(root, q=q)
    comp, t_enc = timed(lambda: opp_huffman.huffman_encode_text(text, q))
    restored, t_dec = timed(lambda: opp_huffman.huffman_decode_bytes(comp))
    return dict(L=avg_len(text, ct), eta=entropy_q(text, q) / avg_len(text, ct),
                stream=stream_bytes(text, ct, q), container=len(comp),
                container_name=".huff(自包含: 头+序列化树+CRC32+位流)",
                prefix=is_prefix(ct), lossless=(restored == text),
                t_enc=t_enc, t_dec=t_dec, note="")


def main():
    out = []
    for fname, kind, path in TEXTS:
        text = open(path, encoding="utf-8").read()
        rec = {"file": fname, "kind": kind, "chars": len(text),
               "orig_bytes": len(text.encode("utf-8")),
               "alphabet": len(set(text)), "H_bits": entropy_q(text, 2),
               "rows": []}
        rec["rows"].append(("我", "Shannon", 2, my_shannon_run(text)))
        rec["rows"].append(("对手", "Shannon", 2, opp_shannon_run(text)))
        for q in (2, 3, 4):
            rec["rows"].append(("我", "Huffman", q, my_huffman_run(text, q)))
            rec["rows"].append(("对手", "Huffman", q, opp_huffman_run(text, q)))
        out.append(rec)

        print(f"\n===== {fname} ({kind})  字符={rec['chars']} "
              f"UTF-8={rec['orig_bytes']}B  字母表={rec['alphabet']} "
              f"H={rec['H_bits']:.4f} =====")
        print(f"{'方':<4}{'方法':<9}{'q':>2}{'L':>9}{'eta':>8}"
              f"{'码流B':>8}{'容器B':>9}{'前缀':>5}{'无损':>5}{'编ms':>8}{'解ms':>8}")
        for who, name, q, m in rec["rows"]:
            dec = "-" if (m["t_dec"] != m["t_dec"]) else f"{m['t_dec']*1000:.3f}"
            cont = "-" if m["container"] is None else str(m["container"])
            print(f"{who:<4}{name:<9}{q:>2}{m['L']:>9.4f}{m['eta']*100:>7.2f}%"
                  f"{m['stream']:>8}{cont:>9}{str(m['prefix']):>5}"
                  f"{('OK' if m['lossless'] else 'X'):>5}"
                  f"{m['t_enc']*1000:>8.3f}{dec:>8}"
                  + (f"  <-{m['note']}" if m['note'] else ""))

    import json
    with open(os.path.join(ROOT, "pk_results.json"), "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2, default=str)
    print("\n结果已写入 pk_results.json")


if __name__ == "__main__":
    main()
