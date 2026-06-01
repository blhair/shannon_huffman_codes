"""命令行入口：读入文本文件，构建 Q-ary Huffman 码表，编/解码并输出结果。

用法（默认 q=2，二进制 Huffman）：
    python huffman_cli.py encode samples/zh_sample.txt --out out/zh_huf
    python huffman_cli.py decode out/zh_huf.bits out/zh_huf.codebook.json --out out/zh_huf.decoded.txt
    python huffman_cli.py roundtrip samples/en_sample.txt
    python huffman_cli.py roundtrip samples/zh_sample.txt --q 3

输出格式（老格式，便于人眼检查）：
    .bits           q 进制字符串（'0'..'(q-1)'）
    .codebook.json  码表 + 概率 + q
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from huffman import HuffmanCode


# ---------------- 通用 IO ----------------
def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _dump_codebook(code: HuffmanCode, path: Path) -> None:
    data = {
        "q": code.q,
        "code_table": code.code_table,
        "probabilities": code.probabilities,
        "lengths": code.lengths,
        "order": code.order,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _load_codebook(path: Path) -> HuffmanCode:
    data = json.loads(path.read_text(encoding="utf-8"))
    return HuffmanCode(
        code_table=data["code_table"],
        probabilities=data["probabilities"],
        lengths=data["lengths"],
        q=data.get("q", 2),
        order=data.get("order", list(data["code_table"].keys())),
    )


def _print_table(code: HuffmanCode, top: int = 20) -> None:
    print(f"{'symbol':<8}{'p':>12}{'l':>5}  codeword (base-{code.q})")
    print("-" * 60)
    for i, (s, p, L, c) in enumerate(code.table_rows()):
        if i >= top:
            print(f"... 还有 {len(code.order) - top} 个符号未显示")
            break
        disp = repr(s) if (s.isspace() or not s.isprintable()) else s
        print(f"{disp:<8}{p:>12.6f}{L:>5}  {c}")


def _print_metrics(code: HuffmanCode, text=None) -> None:
    H = code.entropy()
    L = code.average_length()
    eta = code.efficiency()
    unit = "bit" if code.q == 2 else f"{code.q}-ary 符号"
    print(f"进制 q   : {code.q}")
    print(f"符号数   : {len(code.order)}")
    print(f"熵 H_q(X): {H:.4f} {unit}/符号")
    print(f"平均码长 : {L:.4f} {unit}/符号")
    print(f"编码效率 : {eta:.4%}")
    print(f"是否前缀码: {code.is_prefix_code()}")
    if text is not None:
        total = sum(code.lengths[t] for t in text)
        print(f"序列长度 : {len(text)} 个原符号")
        print(f"编码总长 : {total} {unit}")
        if code.q == 2:
            print(f"          ≈ {total/8:.1f} byte")


# ---------------- 子命令 ----------------
def cmd_encode(args: argparse.Namespace) -> int:
    in_path = Path(args.input)
    out_prefix = Path(args.out)
    text = _read_text(in_path)

    code = HuffmanCode.from_text(text, q=args.q)
    bits = code.encode(text)

    _write_text(out_prefix.with_suffix(".bits"), bits)
    _dump_codebook(code, out_prefix.with_suffix(".codebook.json"))

    print(f"[encode] 输入  : {in_path}")
    print(f"[encode] 码流  : {out_prefix.with_suffix('.bits')}")
    print(f"[encode] 码表  : {out_prefix.with_suffix('.codebook.json')}")
    _print_metrics(code, text)
    print()
    _print_table(code)
    return 0


def cmd_decode(args: argparse.Namespace) -> int:
    bits = Path(args.bits).read_text(encoding="utf-8").strip()
    code = _load_codebook(Path(args.codebook))
    text = code.decode(bits)
    _write_text(Path(args.out), text)
    print(f"[decode] 已写入: {args.out}（{len(text)} 个符号）")
    return 0


def cmd_roundtrip(args: argparse.Namespace) -> int:
    text = _read_text(Path(args.input))
    code = HuffmanCode.from_text(text, q=args.q)
    bits = code.encode(text)
    restored = code.decode(bits)
    ok = restored == text
    print(f"[roundtrip] 输入: {args.input}")
    _print_metrics(code, text)
    print(f"解码是否完全还原: {ok}")
    if not ok:
        for i, (a, b) in enumerate(zip(text, restored)):
            if a != b:
                print(f"  第 {i} 个符号不同: 原 {a!r} -> 解 {b!r}")
                break
        return 1
    print()
    _print_table(code)
    return 0


# ---------------- 入口 ----------------
def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Q-ary Huffman 编解码工具")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_enc = sub.add_parser("encode", help="编码并输出 .bits + .codebook.json")
    p_enc.add_argument("input")
    p_enc.add_argument("--out", default="out/huf_result")
    p_enc.add_argument("--q", type=int, default=2, help="码字进制 (2..10)，默认 2")
    p_enc.set_defaults(func=cmd_encode)

    p_dec = sub.add_parser("decode", help="读 .bits + .codebook.json 解码")
    p_dec.add_argument("bits")
    p_dec.add_argument("codebook")
    p_dec.add_argument("--out", default="out/huf_decoded.txt")
    p_dec.set_defaults(func=cmd_decode)

    p_rt = sub.add_parser("roundtrip", help="一键编/解码并校验可逆")
    p_rt.add_argument("input")
    p_rt.add_argument("--q", type=int, default=2, help="码字进制 (2..10)，默认 2")
    p_rt.set_defaults(func=cmd_roundtrip)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
