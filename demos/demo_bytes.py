"""演示字节流编/解码 vs 字符串版编/解码：
1. 两版结果一致
2. 字节流真实大小（vs 用字符串保存的 .bits）
3. (code, length) 联合键的必要性

在仓库根目录运行：python demos/demo_bytes.py
"""
import os, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)

from shannon import ShannonCode
from shannon_bytes import (
    encode_to_bytes, decode_from_bytes, demo_code_length_collision,
)


def test_one(name: str, path: str) -> None:
    text = Path(path).read_text(encoding="utf-8")
    code = ShannonCode.from_text(text)

    # 字符串版（旧）
    bits_str = code.encode(text)
    text_back_str = code.decode(bits_str)

    # 字节流版（新）
    data, pad = encode_to_bytes(text, code)
    text_back_bytes = decode_from_bytes(data, pad, code)

    # 一致性
    assert bits_str == "".join(f"{b:08b}" for b in data)[:len(bits_str)], "比特流不一致"
    assert text_back_str == text, "字符串版解码不还原"
    assert text_back_bytes == text, "字节流版解码不还原"

    print(f"[{name}]")
    print(f"  原文 UTF-8 大小  : {len(text.encode('utf-8'))} byte")
    print(f"  '.bits' 字符串大小: {len(bits_str)} byte  (每比特占 1 字节，浪费 8x)")
    print(f"  真实字节流大小    : {len(data)} byte  (末字节 pad={pad} 位)")
    print(f"  压缩比 vs UTF-8   : {len(data) / len(text.encode('utf-8')):.3f}")
    print(f"  字符串版/字节版结果一致 ✓ 解码还原 ✓")
    print()


if __name__ == "__main__":
    test_one("英文", "samples/en_sample.txt")
    test_one("中文", "samples/zh_sample.txt")

    print("=" * 50)
    print("演示 (code, length) 必须联合做键：")
    print("=" * 50)
    demo_code_length_collision()
