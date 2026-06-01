"""命令行入口：读入文本文件，构建 Shannon 码表，编解码并输出结果。

老格式（JSON 码表 + ASCII 比特流，便于人眼检查）：
    python cli.py encode samples/zh_sample.txt --out out/zh
    python cli.py decode out/zh.bits out/zh.codebook.json --out out/zh.decoded.txt
    python cli.py roundtrip samples/en_sample.txt

新格式（canonical 码表 + 字节流，单文件 .shc）：
    python cli.py compress   samples/zh_sample.txt --out out/zh.shc --mode singleton
    python cli.py compress   samples/zh_sample.txt --out out/zh.shc --mode ngram --k 64
    python cli.py decompress out/zh.shc --out out/zh.decoded.txt
    python cli.py compare    samples/zh_sample.txt   # 对比 char / singleton / ngram(K=...)
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from shannon import ShannonCode
from shannon_tokens import tokenize
from shannon_codec import save_compressed, load_compressed, decompress_to_text


# ---------------- 通用 IO ----------------
def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _dump_codebook(code: ShannonCode, path: Path) -> None:
    data = {
        "code_table": code.code_table,
        "probabilities": code.probabilities,
        "lengths": code.lengths,
        "order": code.order,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _load_codebook(path: Path) -> ShannonCode:
    data = json.loads(path.read_text(encoding="utf-8"))
    return ShannonCode(
        code_table=data["code_table"],
        probabilities=data["probabilities"],
        lengths=data["lengths"],
        cumulative={},
        order=data.get("order", list(data["code_table"].keys())),
    )


def _print_table(code: ShannonCode, top: int = 20) -> None:
    print(f"{'symbol':<8}{'p':>12}{'F':>14}{'l':>5}  codeword")
    print("-" * 60)
    for i, (s, p, F, L, c) in enumerate(code.table_rows()):
        if i >= top:
            print(f"... 还有 {len(code.order) - top} 个符号未显示")
            break
        disp = repr(s) if (s.isspace() or not s.isprintable()) else s
        print(f"{disp:<8}{p:>12.6f}{F:>14.6f}{L:>5}  {c}")


def _print_metrics(code: ShannonCode, text_or_tokens=None) -> None:
    H = code.entropy()
    L = code.average_length()
    eta = code.efficiency()
    print(f"符号数  : {len(code.order)}")
    print(f"熵 H(X) : {H:.4f} bit/符号")
    print(f"平均码长: {L:.4f} bit/符号")
    print(f"编码效率: {eta:.4%}")
    print(f"是否前缀码: {code.is_prefix_code()}")
    if text_or_tokens is not None:
        total_bits = sum(code.lengths[t] for t in text_or_tokens)
        print(f"序列长度: {len(text_or_tokens)} token")
        print(f"编码总长: {total_bits} bit (≈ {total_bits/8:.1f} byte)")


# ---------------- 老格式：encode / decode / roundtrip ----------------
def cmd_encode(args: argparse.Namespace) -> int:
    in_path = Path(args.input)
    out_prefix = Path(args.out)
    text = _read_text(in_path)

    code = ShannonCode.from_text(text)
    bits = code.encode(text)

    _write_text(out_prefix.with_suffix(".bits"), bits)
    _dump_codebook(code, out_prefix.with_suffix(".codebook.json"))

    print(f"[encode] 输入  : {in_path}")
    print(f"[encode] 比特流: {out_prefix.with_suffix('.bits')}")
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
    code = ShannonCode.from_text(text)
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


# ---------------- 新格式：compress / decompress / compare ----------------
def _tokenize_for_mode(text: str, mode: str, k: int):
    return tokenize(text, mode, k=k)


def cmd_compress(args: argparse.Namespace) -> int:
    text = _read_text(Path(args.input))
    tokens, meta = _tokenize_for_mode(text, args.mode, args.k)
    out_path = Path(args.out)

    code, payload_bytes, codebook_bytes = save_compressed(out_path, tokens)
    total = out_path.stat().st_size
    src_bytes = len(text.encode("utf-8"))

    print(f"[compress] 输入  : {args.input} ({src_bytes} byte UTF-8)")
    print(f"[compress] 输出  : {out_path} ({total} byte)")
    print(f"[compress] 模式  : {meta}")
    print(f"  token 数        : {len(tokens)}")
    print(f"  码表条目        : {len(code.order)}")
    print(f"  payload 字节    : {payload_bytes}")
    print(f"  码表(含 header) : {codebook_bytes}")
    print(f"  总压缩比 vs UTF-8: {total / src_bytes:.3f}")
    _print_metrics(code, tokens)
    return 0


def cmd_decompress(args: argparse.Namespace) -> int:
    text = decompress_to_text(Path(args.input))
    out_path = Path(args.out)
    _write_text(out_path, text)
    print(f"[decompress] 已写入: {out_path}（{len(text)} 字符）")
    return 0


def cmd_compare(args: argparse.Namespace) -> int:
    text = _read_text(Path(args.input))
    src_bytes = len(text.encode("utf-8"))
    print(f"输入: {args.input}  原文 UTF-8: {src_bytes} byte")
    print()
    header = f"{'mode':<22}{'tokens':>8}{'alpha':>7}{'H':>9}{'L':>9}{'payload':>10}{'codebook':>10}{'total':>9}{'vs UTF-8':>10}"
    print(header)
    print("-" * len(header))

    configs = [
        ("char", {}),
        ("singleton", {}),
    ]
    for k in args.k_list:
        configs.append((f"ngram(K={k})", {"mode_override": "ngram", "k": k}))

    tmp_dir = Path("out/_compare")
    tmp_dir.mkdir(parents=True, exist_ok=True)

    for label, cfg in configs:
        mode = cfg.get("mode_override", label)
        k = cfg.get("k", 0)
        tokens, _ = tokenize(text, mode, k=k)
        path = tmp_dir / f"{label}.shc"
        code, payload, codebook = save_compressed(path, tokens)
        total = path.stat().st_size
        # 校验可逆
        restored = decompress_to_text(path)
        ok = "✓" if restored == text else "✗"
        print(
            f"{label:<22}{len(tokens):>8}{len(code.order):>7}"
            f"{code.entropy():>9.3f}{code.average_length():>9.3f}"
            f"{payload:>10}{codebook:>10}{total:>9}{total/src_bytes:>9.3f} {ok}"
        )
    return 0


# ---------------- 入口 ----------------
def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Shannon 编解码工具")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_enc = sub.add_parser("encode", help="老格式：JSON 码表 + ASCII 比特流")
    p_enc.add_argument("input"); p_enc.add_argument("--out", default="out/result")
    p_enc.set_defaults(func=cmd_encode)

    p_dec = sub.add_parser("decode", help="老格式：读 .bits + .codebook.json")
    p_dec.add_argument("bits"); p_dec.add_argument("codebook")
    p_dec.add_argument("--out", default="out/decoded.txt")
    p_dec.set_defaults(func=cmd_decode)

    p_rt = sub.add_parser("roundtrip", help="老格式：一键编/解码并校验可逆")
    p_rt.add_argument("input")
    p_rt.set_defaults(func=cmd_roundtrip)

    p_cmp = sub.add_parser("compress", help="新格式：canonical 码表 + 字节流，单文件 .shc")
    p_cmp.add_argument("input")
    p_cmp.add_argument("--out", required=True)
    p_cmp.add_argument("--mode", choices=("char", "singleton", "ngram"), default="char")
    p_cmp.add_argument("--k", type=int, default=64, help="ngram 模式下的 top-K 大小")
    p_cmp.set_defaults(func=cmd_compress)

    p_dcp = sub.add_parser("decompress", help="新格式：解压 .shc")
    p_dcp.add_argument("input")
    p_dcp.add_argument("--out", required=True)
    p_dcp.set_defaults(func=cmd_decompress)

    p_cmpr = sub.add_parser("compare", help="对比 char / singleton / 不同 K 的 ngram")
    p_cmpr.add_argument("input")
    p_cmpr.add_argument("--k-list", nargs="+", type=int, default=[16, 64, 128, 256],
                        help="对比时尝试的若干 K 值")
    p_cmpr.set_defaults(func=cmd_compare)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
