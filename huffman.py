"""Q-ary Huffman 编码 / 解码核心模块。

经典 Huffman 算法（Huffman, 1952）的 q 进制推广：
    1. 统计每个符号 s_i 的概率 p_i。
    2. 若符号数 n 不满足 (n - 1) mod (q - 1) == 0，
       补若干个概率为 0 的"虚拟符号"使其满足；二进制时不需要补。
    3. 反复从堆里取出 q 个最小概率的节点，合成一个父节点；
       父节点概率为子节点概率之和。
    4. 给父节点到子节点的 q 条边分别标号 0, 1, ..., q-1，
       叶子的码字就是从根到该叶子路径上的边标号序列。

得到的码是 q-ary 前缀码（即时码），平均码长 L（以 q-ary 符号为单位）满足
    H_q(X) <= L < H_q(X) + 1, 其中 H_q(X) = -sum p_i log_q p_i 。
"""

from __future__ import annotations

import heapq
import math
from collections import Counter
from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Optional, Tuple


# 初版限制：码字用单字符数字表示，便于和 Shannon 模块对齐、人眼检查
_MIN_Q = 2
_MAX_Q = 10


@dataclass(order=True)
class _Node:
    """堆里的节点。weight + seq 提供严格全序，避免比较到 symbol/children。"""
    weight: float
    seq: int
    symbol: Optional[str] = field(default=None, compare=False)
    children: List["_Node"] = field(default_factory=list, compare=False)
    is_dummy: bool = field(default=False, compare=False)


@dataclass
class HuffmanCode:
    """一次构建好的 q-ary Huffman 码表。"""

    code_table: Dict[str, str]          # symbol -> codeword (digits '0'..'q-1')
    probabilities: Dict[str, float]     # symbol -> p_i
    lengths: Dict[str, int]             # symbol -> l_i (以 q-ary 符号计)
    q: int                              # 进制
    order: List[str] = field(default_factory=list)  # 按概率降序排列的符号

    # ---------- 构造 ----------
    @classmethod
    def from_text(cls, text: str, q: int = 2) -> "HuffmanCode":
        if not text:
            raise ValueError("文本为空，无法构建 Huffman 码")
        counts = Counter(text)
        total = sum(counts.values())
        probs = {s: c / total for s, c in counts.items()}
        return cls.from_probabilities(probs, q)

    @classmethod
    def from_probabilities(cls, probs: Dict[str, float], q: int = 2) -> "HuffmanCode":
        if not (_MIN_Q <= q <= _MAX_Q):
            raise ValueError(f"初版仅支持 {_MIN_Q} <= q <= {_MAX_Q}，收到 q={q}")

        total = sum(probs.values())
        if total <= 0:
            raise ValueError("所有概率之和必须为正")
        probs = {s: p / total for s, p in probs.items()}

        # 单符号特例：直接给一位码字
        if len(probs) == 1:
            sym = next(iter(probs))
            return cls(
                code_table={sym: "0"},
                probabilities=probs,
                lengths={sym: 1},
                q=q,
                order=[sym],
            )

        # q-ary 需要补虚拟符号（dummy），让 (n + dummy - 1) 是 (q-1) 的倍数
        n = len(probs)
        if q == 2:
            dummy_count = 0
        else:
            r = (n - 1) % (q - 1)
            dummy_count = 0 if r == 0 else (q - 1) - r

        # 入堆：稳定 tie-breaking 用 (符号 ascii, 插入序)
        # 同概率时倾向把"插入早 = 频次大的先合并"，影响码字形态但不影响平均码长
        heap: List[_Node] = []
        seq = 0
        # 按 (-p, symbol) 升序入堆，让确定性可复现
        for sym, p in sorted(probs.items(), key=lambda kv: (-kv[1], kv[0])):
            heapq.heappush(heap, _Node(p, seq, symbol=sym))
            seq += 1
        for _ in range(dummy_count):
            # dummy 概率 0，放在堆里只是凑数
            heapq.heappush(heap, _Node(0.0, seq, is_dummy=True))
            seq += 1

        # 反复合并 q 个最小
        while len(heap) > 1:
            children = [heapq.heappop(heap) for _ in range(q)]
            new_weight = sum(c.weight for c in children)
            parent = _Node(new_weight, seq, children=children)
            seq += 1
            heapq.heappush(heap, parent)

        root = heap[0]

        # 由根向叶分配码字：第 i 个子节点（按弹出顺序 = 概率升序）拿到数字 i
        # 反过来等价于"概率最大的子节点拿 0"，这样高频符号往往以 '0' 开头
        code_table: Dict[str, str] = {}

        def assign(node: _Node, prefix: str) -> None:
            if node.symbol is not None:
                code_table[node.symbol] = prefix
                return
            if node.is_dummy:
                return  # dummy 不分配码字
            # children 当前是按弹出顺序（升序）排的；反过来让大概率拿小数字
            for i, child in enumerate(reversed(node.children)):
                assign(child, prefix + str(i))

        assign(root, "")

        lengths = {s: len(c) for s, c in code_table.items()}
        order = sorted(probs.keys(), key=lambda s: (-probs[s], s))

        return cls(
            code_table=code_table,
            probabilities=probs,
            lengths=lengths,
            q=q,
            order=order,
        )

    # ---------- 编码 / 解码 ----------
    def encode(self, text: str) -> str:
        """返回编码后的 q 进制串（字符 '0'..'(q-1)'）。"""
        try:
            return "".join(self.code_table[ch] for ch in text)
        except KeyError as e:
            raise ValueError(f"符号 {e.args[0]!r} 不在码表中") from None

    def decode(self, code: str) -> str:
        """前缀码解码：贪心匹配。"""
        inv = {c: s for s, c in self.code_table.items()}
        max_len = max(self.lengths.values()) if self.lengths else 0

        out: List[str] = []
        i, n = 0, len(code)
        while i < n:
            matched = False
            for L in range(1, max_len + 1):
                if i + L > n:
                    break
                chunk = code[i:i + L]
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
        """信源熵 H_q(X) = -sum p_i log_q p_i (q-ary 符号/原符号)。"""
        if self.q == 2:
            return -sum(p * math.log2(p) for p in self.probabilities.values() if p > 0)
        log_q = math.log(self.q)
        return -sum(p * (math.log(p) / log_q) for p in self.probabilities.values() if p > 0)

    def average_length(self) -> float:
        """平均码长 L = sum p_i * l_i (q-ary 符号/原符号)。"""
        return sum(self.probabilities[s] * self.lengths[s] for s in self.probabilities)

    def efficiency(self) -> float:
        """编码效率 eta = H_q(X) / L。"""
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
    def table_rows(self) -> Iterable[Tuple[str, float, int, str]]:
        """按 order 返回 (symbol, p, l, codeword)，便于打印。"""
        for s in self.order:
            yield s, self.probabilities[s], self.lengths[s], self.code_table[s]
