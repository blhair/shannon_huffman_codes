"""Tokenizer 集合：把文本切成 token 序列，喂给 ShannonCode。

三种模式：
* char        ：每个 Unicode 字符一个 token（基线）。
* singleton   ：全文出现次数为 1 的字符若相邻，合并成一个 token。
                  作用：把多个长码字合并成一个，省下一份"长码字"开销。
* ngram       ：把高频 n-gram（默认 2-gram）作为新 token 加入字母表。
                  其余位置仍按字符切。贪婪最长匹配解析。

注意：编码端必须使用与构建码表时**完全相同**的 tokenizer，
否则 token 序列对不上、码表查不到。
"""

from __future__ import annotations

from collections import Counter
from typing import Iterable, List, Set, Tuple


# ---------------- 单字 ----------------
def tokenize_chars(text: str) -> List[str]:
    return list(text)


# ---------------- Singleton 合并 ----------------
def tokenize_singletons(text: str) -> List[str]:
    """连续的、全文只出现 1 次的字符合并成一个 token。"""
    counts = Counter(text)
    singletons = {c for c, n in counts.items() if n == 1}

    tokens: List[str] = []
    i, n = 0, len(text)
    while i < n:
        if text[i] in singletons:
            j = i + 1
            while j < n and text[j] in singletons:
                j += 1
            tokens.append(text[i:j])
            i = j
        else:
            tokens.append(text[i])
            i += 1
    return tokens


# ---------------- Top-K n-gram ----------------
def select_top_k_ngrams(text: str, k: int, n: int = 2) -> List[str]:
    """挑出现频率最高的前 k 个 n-gram。

    返回时按"长度降序、然后频次降序"排，便于后续贪婪最长匹配。
    """
    if k <= 0 or n < 2:
        return []
    counts = Counter(text[i:i + n] for i in range(len(text) - n + 1))
    top = counts.most_common(k)
    return [g for g, _ in top]


def tokenize_ngrams(text: str, ngram_set: Set[str]) -> List[str]:
    """贪婪最长匹配：能匹配 n-gram 就匹配，否则按单字符切。"""
    if not ngram_set:
        return list(text)
    max_n = max(len(g) for g in ngram_set)

    tokens: List[str] = []
    i, n = 0, len(text)
    while i < n:
        matched = False
        # 从长到短试，保证最长匹配
        for L in range(min(max_n, n - i), 1, -1):
            if text[i:i + L] in ngram_set:
                tokens.append(text[i:i + L])
                i += L
                matched = True
                break
        if not matched:
            tokens.append(text[i])
            i += 1
    return tokens


# ---------------- 统一入口 ----------------
def tokenize(text: str, mode: str, *, k: int = 0, n: int = 2) -> Tuple[List[str], dict]:
    """统一 tokenizer 入口。

    返回 (tokens, meta)。meta 里记录"重建 tokenizer 所需的最少信息"。
    对 char/singleton 模式，meta 是 {"mode": ...}，足够确定。
    对 ngram 模式，meta 包含挑出的 n-gram 列表——解码端不需要 meta，
    因为 token 直接从码表恢复；编码端再 tokenize 时才需要。
    """
    if mode == "char":
        return tokenize_chars(text), {"mode": "char"}
    if mode == "singleton":
        return tokenize_singletons(text), {"mode": "singleton"}
    if mode == "ngram":
        ngrams = select_top_k_ngrams(text, k=k, n=n)
        return tokenize_ngrams(text, set(ngrams)), {
            "mode": "ngram", "k": k, "n": n, "ngrams": ngrams,
        }
    raise ValueError(f"unknown mode: {mode!r}")
