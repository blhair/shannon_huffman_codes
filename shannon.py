"""Shannon 编码 / 解码核心模块。

经典 Shannon 编码算法（Shannon, 1948）：
    1. 统计每个符号 s_i 的概率 p_i。
    2. 按概率从大到小排序：p_1 >= p_2 >= ... >= p_n。
    3. 累积概率 F_i = sum_{k<i} p_k，其中 F_1 = 0。
    4. 码长 l_i = ceil(-log2(p_i))。
    5. 码字 c_i = F_i 的二进制展开的前 l_i 位。

可以证明这样得到的码是前缀码（即时码），平均码长满足
    H(X) <= L < H(X) + 1。
"""

from __future__ import annotations

import math
from collections import Counter
from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Tuple


def _frac_to_binary(frac: float, length: int) -> str:
    """把 0 <= frac < 1 展开为长度为 length 的二进制小数串。"""
    bits = []
    x = frac
    for _ in range(length):
        x *= 2
        if x >= 1.0:
            bits.append("1")
            x -= 1.0
        else:
            bits.append("0")
    return "".join(bits)


@dataclass
class ShannonCode:
    """一次构建好的 Shannon 码表。"""

    code_table: Dict[str, str]          # symbol -> codeword (bit string)
    probabilities: Dict[str, float]     # symbol -> p_i
    lengths: Dict[str, int]             # symbol -> l_i
    cumulative: Dict[str, float]        # symbol -> F_i
    order: List[str] = field(default_factory=list)  # 按概率降序排列的符号

    # ---------- 构造 ----------
    @classmethod
    def from_text(cls, text: str) -> "ShannonCode":
        if not text:
            raise ValueError("文本为空，无法构建 Shannon 码")
        counts = Counter(text)
        total = sum(counts.values())
        probs = {s: c / total for s, c in counts.items()}
        return cls.from_probabilities(probs)

    @classmethod
    def from_probabilities(cls, probs: Dict[str, float]) -> "ShannonCode":
        # 归一化，防御性处理浮点误差
        total = sum(probs.values())
        if total <= 0:
            raise ValueError("所有概率之和必须为正")
        probs = {s: p / total for s, p in probs.items()}

        # 按 p 降序；同概率时用符号本身做次级排序，保证确定性
        ordered = sorted(probs.items(), key=lambda kv: (-kv[1], kv[0]))

        code_table: Dict[str, str] = {}
        lengths: Dict[str, int] = {}
        cumulative: Dict[str, float] = {}
        order: List[str] = []

        F = 0.0
        for symbol, p in ordered:
            # 单符号特例：-log2(1)=0，强制至少 1 位
            length = max(1, math.ceil(-math.log2(p)))
            codeword = _frac_to_binary(F, length)
            code_table[symbol] = codeword
            lengths[symbol] = length
            cumulative[symbol] = F
            order.append(symbol)
            F += p

        return cls(
            code_table=code_table,
            probabilities=probs,
            lengths=lengths,
            cumulative=cumulative,
            order=order,
        )

    # ---------- 编码 / 解码 ----------
    def encode(self, text: str) -> str:
        """返回编码后的比特串（'0'/'1' 字符）。"""
        try:
            return "".join(self.code_table[ch] for ch in text)
        except KeyError as e:
            raise ValueError(f"符号 {e.args[0]!r} 不在码表中") from None

    def decode(self, bits: str) -> str:
        """前缀码解码：贪心匹配。"""
        # code -> symbol 反查表
        inv = {code: sym for sym, code in self.code_table.items()}
        max_len = max(self.lengths.values()) if self.lengths else 0

        out: List[str] = []
        i, n = 0, len(bits)
        while i < n:
            matched = False
            # 由于是前缀码，从短到长第一次匹配即可
            for L in range(1, max_len + 1):
                if i + L > n:
                    break
                chunk = bits[i:i + L]
                if chunk in inv:
                    out.append(inv[chunk])
                    i += L
                    matched = True
                    break
            if not matched:
                raise ValueError(f"解码失败：在位置 {i} 无法匹配任何码字")
        return "".join(out)

    # ---------- 指标 ----------
    def entropy(self) -> float:
        """信源熵 H(X) = -sum p_i log2 p_i (bit/符号)。"""
        return -sum(p * math.log2(p) for p in self.probabilities.values() if p > 0)

    def average_length(self) -> float:
        """平均码长 L = sum p_i * l_i。"""
        return sum(self.probabilities[s] * self.lengths[s] for s in self.probabilities)

    def efficiency(self) -> float:
        """编码效率 eta = H(X) / L。"""
        L = self.average_length()
        return self.entropy() / L if L > 0 else 0.0

    # ---------- 自检 ----------
    def is_prefix_code(self) -> bool:
        """暴力检查任何码字都不是另一个的前缀。"""
        codes = list(self.code_table.values())
        for i, a in enumerate(codes):
            for j, b in enumerate(codes):
                if i != j and b.startswith(a):
                    return False
        return True

    # ---------- 展示 ----------
    def table_rows(self) -> Iterable[Tuple[str, float, float, int, str]]:
        """按 order 返回 (symbol, p, F, l, codeword)，便于打印。"""
        for s in self.order:
            yield s, self.probabilities[s], self.cumulative[s], self.lengths[s], self.code_table[s]
