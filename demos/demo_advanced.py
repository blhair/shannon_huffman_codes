"""演示三大优化叠加效果：
* #3 canonical 码表
* #4 singleton 相邻合并
* #5 top-K n-gram

输出：每种模式的码表/payload/总文件大小，并校验 roundtrip。
"""

import os, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)

from shannon_tokens import tokenize
from shannon_codec import save_compressed, decompress_to_text


def run(label: str, mode: str, src: str, k: int = 0) -> None:
    text = Path(src).read_text(encoding="utf-8")
    src_bytes = len(text.encode("utf-8"))

    tokens, meta = tokenize(text, mode, k=k)
    out = Path("out/_demo_adv") / f"{Path(src).stem}.{label}.shc"
    code, payload, codebook = save_compressed(out, tokens)
    total = out.stat().st_size
    restored = decompress_to_text(out)
    ok = restored == text

    print(
        f"{label:<18} tokens={len(tokens):<5} alpha={len(code.order):<5}"
        f" H={code.entropy():6.3f} L={code.average_length():6.3f}"
        f" payload={payload:<5} codebook={codebook:<5} total={total:<5}"
        f" ratio={total/src_bytes:.3f} {'✓' if ok else '✗ FAIL'}"
    )


def main() -> None:
    for src in ["samples/en_sample.txt", "samples/zh_sample.txt"]:
        text = Path(src).read_text(encoding="utf-8")
        print(f"\n=== {src} (UTF-8 {len(text.encode('utf-8'))} byte, {len(text)} 字符) ===")
        run("char",          "char",      src)
        run("singleton",     "singleton", src)
        for k in (16, 32, 64, 128, 256):
            run(f"ngram(K={k})", "ngram", src, k=k)


if __name__ == "__main__":
    main()
