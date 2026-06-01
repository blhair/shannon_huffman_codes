"""一次性演示脚本：对比文件大小、校验可逆、手工对照前几位编码。

在仓库根目录运行：python demos/demo_string.py
（必须先跑过 `python cli.py encode samples/*.txt --out out/*`）
"""
import json, os, sys
from pathlib import Path

# 允许从仓库根目录 import shannon
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)

samples = {
    "en": ("samples/en_sample.txt", "out/en.bits", "out/en.codebook.json"),
    "zh": ("samples/zh_sample.txt", "out/zh.bits", "out/zh.codebook.json"),
}

print(f"{'sample':<6}{'utf8 bytes':>12}{'bits (chars)':>14}{'codebook':>10}{'bit/byte':>12}")
print("-" * 60)
for name, (src, bits, cb) in samples.items():
    s = os.path.getsize(src)
    b = os.path.getsize(bits)           # 这里 bits 是 '0'/'1' 字符流，1 char ≈ 1 bit
    c = os.path.getsize(cb)
    print(f"{name:<6}{s:>12}{b:>14}{c:>10}{b/s:>12.3f}")

print("\n== 编解码可逆校验 ==")
for name, (src, bits, cb) in samples.items():
    orig = Path(src).read_text(encoding="utf-8")
    dec = Path(f"out/{name}.decoded.txt").read_text(encoding="utf-8")
    print(f"  {name}: original == decoded ?  {orig == dec}")

print("\n== 手工对照：英文前 12 个字符的编码 ==")
cb = json.loads(Path("out/en.codebook.json").read_text(encoding="utf-8"))
table = cb["code_table"]
orig = Path("samples/en_sample.txt").read_text(encoding="utf-8")
acc = ""
for ch in orig[:12]:
    code = table[ch]
    acc += code
    print(f"  {ch!r:>5} -> {code}")
print(f"  拼接 {len(acc)} 位: {acc}")
print(f"  bits 文件前 {len(acc)} 位: {Path('out/en.bits').read_text(encoding='utf-8')[:len(acc)]}")

print("\n== 手工对照：中文前 8 个字符的编码 ==")
cb = json.loads(Path("out/zh.codebook.json").read_text(encoding="utf-8"))
table = cb["code_table"]
orig = Path("samples/zh_sample.txt").read_text(encoding="utf-8")
acc = ""
for ch in orig[:8]:
    code = table[ch]
    acc += code
    print(f"  {ch!r:>5} -> {code}")
print(f"  拼接 {len(acc)} 位: {acc}")
print(f"  bits 文件前 {len(acc)} 位: {Path('out/zh.bits').read_text(encoding='utf-8')[:len(acc)]}")
