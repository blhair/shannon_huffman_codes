# Shannon Codes & Q-ary Huffman Codes

信息论课程作业（Project 1-B）：用 Python 实现 **Shannon 编码** 与 **Q-ary Huffman 编码**，支持中英文文本（~3000 字）的自动编/解码、组间互测与 PK。

- Shannon 部分在基线之上叠加三层优化：**字节流位运算 / canonical 码表 / 多种 tokenizer（singleton 合并 + top-K n-gram）**。
- Huffman 部分目前是**初版**：核心算法 + 老格式 CLI（JSON 码表 + q 进制码流），支持 q ∈ [2, 10]。

## 目录结构

```
shannon_codes/
├── README.md                 本文档
├── shannon.py                核心库：ShannonCode（编码/解码/熵/前缀码自检）
├── shannon_bytes.py          字节流位运算版编/解码 (#1 #2)
├── shannon_tokens.py         Tokenizer：char / singleton / top-K n-gram (#4 #5)
├── shannon_codec.py          canonical 码表 + 端到端 .shc 单文件格式 (#3)
├── cli.py                    Shannon 命令行入口
├── huffman.py                核心库：HuffmanCode（Q-ary，q ∈ [2,10]）
├── huffman_cli.py            Huffman 命令行入口
├── demos/
│   ├── demo_string.py        码表、手工对照前几位编码
│   ├── demo_bytes.py         字符串版 vs 字节版差异、(code,length) 冲突
│   └── demo_advanced.py      5 种模式压缩率对比 + roundtrip 校验
├── samples/                  测试文本
├── out/                      生成产物
└── docs/                     课程任务说明、扩展优化笔记
```

## 编码程序 / 解码程序

| 用途 | 模块 / 函数 | CLI 子命令 |
|---|---|---|
| 老格式：编码 → JSON 码表 + ASCII 比特流 | `ShannonCode.from_text` + `.encode` | `cli.py encode` |
| 老格式：解码 | `ShannonCode.decode` | `cli.py decode` |
| 字节流：编/解码 | `shannon_bytes.encode_to_bytes` / `decode_from_bytes` | （demo） |
| **新格式：压缩 → 单文件 .shc** | `shannon_codec.save_compressed` | `cli.py compress` |
| **新格式：解压** | `shannon_codec.load_compressed` | `cli.py decompress` |
| 对比 5 种模式 | — | `cli.py compare` |

### 编码算法（Shannon, 1948）

1. 统计每个符号 $s_i$ 的概率 $p_i$。
2. 按概率从大到小排序：$p_1 \ge p_2 \ge \dots \ge p_n$。
3. 累积概率 $F_i = \sum_{k<i} p_k$，其中 $F_1 = 0$。
4. 码长 $l_i = \lceil -\log_2 p_i \rceil$。
5. 码字 $c_i = F_i$ 的二进制小数展开取前 $l_i$ 位。

可证：得到的是前缀码，满足 Shannon 第一定理 $H(X) \le L < H(X) + 1$。

## Q-ary Huffman 编码（初版）

实现位置：[huffman.py](huffman.py) + [huffman_cli.py](huffman_cli.py)。算法（Huffman, 1952 的 q 进制推广）：

1. 统计每个符号 $s_i$ 的概率 $p_i$。
2. 若符号数 $n$ 不满足 $(n - 1) \bmod (q - 1) = 0$，补若干个概率为 0 的"虚拟符号"凑齐；二进制 ($q=2$) 时不需要补。
3. 反复从最小堆里取出 q 个概率最小的节点，合成一个父节点（概率 = 子节点概率之和），放回堆。
4. 从根向叶分配码字：父节点到 q 个子节点的边分别标 $0, 1, \dots, q-1$（实现里高概率子节点拿小数字，让高频符号倾向于以 '0' 开头）。

得到的码是 q-ary 前缀码，且**在所有 q-ary 前缀码里平均码长最小**（与 Shannon 码相比是最优的）。满足
$H_q(X) \le L < H_q(X) + 1$，其中 $H_q(X) = -\sum p_i \log_q p_i$。

### 用法

```powershell
# 1. 二进制 Huffman（默认 q=2）
python huffman_cli.py roundtrip samples/zh_sample.txt
python huffman_cli.py roundtrip samples/en_sample.txt

# 2. 三进制 / 更高进制
python huffman_cli.py roundtrip samples/zh_sample.txt --q 3
python huffman_cli.py roundtrip samples/en_sample.txt --q 4

# 3. 单独编码 / 解码
python huffman_cli.py encode samples/zh_sample.txt --out out/zh_huf
python huffman_cli.py decode out/zh_huf.bits out/zh_huf.codebook.json --out out/zh_huf.decoded.txt
```

### 初版当前结果（与 Shannon 同输入对照）

| 输入 | 方法 | q | H_q | L | 效率 |
|---|---|---:|---:|---:|---:|
| en_sample.txt (320 字符) | Shannon | 2 | 4.211 | 4.725 | 89.13% |
| en_sample.txt | **Huffman** | 2 | 4.211 | **4.247** | **99.16%** |
| zh_sample.txt (100 字符) | Shannon | 2 | 5.888 | 6.330 | 93.02% |
| zh_sample.txt | **Huffman** | 2 | 5.888 | **5.950** | **98.96%** |
| zh_sample.txt | Huffman | 3 | 3.715 | 3.780 | 98.28% |

> **预期**：3000 字测试信源上 Huffman 在中英文都应稳定 >99% 效率；Shannon 因 $l_i = \lceil -\log_2 p_i \rceil$ 的向上取整，效率天然差一截。

### 初版尚未做的

- 字节流位运算打包（当前仅老格式 ASCII 码流，便于人眼检查）。
- canonical 码表 + 单文件 `.huf` 容器。
- 与 Shannon 共用 tokenizer（singleton / top-K n-gram）。
- 与 `cli.py compare` 合并成统一的对比子命令。

## 五条优化路径

| # | 优化 | 实现位置 | 主要受益 |
|---|---|---|---|
| 1 | 位运算 + 字节流打包 | `shannon_bytes.py` | 速度 + 真实压缩比 |
| 2 | 解码字典按长度分组 | `shannon_bytes.build_decode_dict` | 解码速度 3-5× |
| 3 | canonical 码表（只存 token+count） | `shannon_codec.py` | 码表开销 ↓10× |
| 4 | Singleton 相邻合并 | `shannon_tokens.tokenize_singletons` | 压缩率 +15-30%（中文显著） |
| 5 | Selective top-K n-gram | `shannon_tokens.tokenize_ngrams` | 压缩率 +10-25% |

### .shc 文件格式

```
[4B] MAGIC = 'SHCB'
[1B] version = 1
[1B] pad_bits
[4B] N = token 总数
[N entries]:
    [2B] utf-8 字节长度 m
    [m B] token 的 utf-8 字节
    [4B] count (uint32)
[剩余字节] 位流 payload (MSB-first)
```

解码端只需读 `(token, count)` 表，用同一份 Shannon 算法重建码字——**根本不存储码字、码长、概率**。所以码表从 JSON 的 6282 B 缩到 ~600 B（10× 缩减）。

> **关键约束**：解压必须用一致的 Shannon 实现（排序规则、tie-breaking、ceil 行为、log2(1) 单符号特例）。本仓库的 `shannon.py` 和 `shannon_codec.py` 已对齐，编/解端走完全一样的浮点路径。

## 快速上手

环境：Python ≥ 3.9，无第三方依赖。Windows PowerShell 下若中文乱码：`$env:PYTHONIOENCODING="utf-8"`。

```powershell
# 1. 五种模式压缩率对比（推荐先跑）
python cli.py compare samples/zh_sample.txt
python cli.py compare samples/en_sample.txt

# 2. 用某种模式压缩 -> .shc 单文件
python cli.py compress samples/zh_sample.txt --out out/zh.shc --mode singleton
python cli.py compress samples/zh_sample.txt --out out/zh.shc --mode ngram --k 64

# 3. 解压回原文
python cli.py decompress out/zh.shc --out out/zh.decoded.txt

# 4. 一键基线 roundtrip（老格式，便于人眼检查中间产物）
python cli.py roundtrip samples/zh_sample.txt

# 5. 完整 demo：五种模式比对 + roundtrip 校验
python demos/demo_advanced.py
```

## 当前测试结果

**中文样例 (298 B UTF-8, 100 字符)**

| 模式 | tokens | 字母表 | H | L | payload | 码表 | total | vs UTF-8 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| char | 100 | 74 | 5.888 | 6.330 | 80 | 674 | 754 | 2.530 |
| **singleton** | 65 | 39 | 4.860 | 5.708 | 47 | 464 | **511** | **1.715** |
| ngram(K=128) | 50 | 50 | 5.644 | 6.000 | 38 | 608 | 646 | 2.168 |

**英文样例 (320 B UTF-8, 320 字符)**

| 模式 | tokens | 字母表 | H | L | payload | 码表 | total | vs UTF-8 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| **char** | 320 | 30 | 4.211 | 4.725 | 189 | 220 | **409** | **1.278** |
| singleton | 320 | 30 | 4.211 | 4.725 | 189 | 220 | 409 | 1.278 |
| ngram(K=16) | 247 | 45 | 5.147 | 5.482 | 170 | 341 | 511 | 1.597 |

**所有模式 roundtrip 全部通过 ✓**。

### 几个值得讲的现象

- **中文 singleton 模式**收益最大（35% 字符是 singleton，合并掉 35 个 token）。
- **英文 singleton 无效**：少数 singleton 字符（如大写字母、罕见标点）通常被高频字符隔开，没有"连续 singleton 串"可合并。
- **英文 n-gram 反而变差**：原文太短、字母表本来就小（30），加入 n-gram 后码表膨胀超过 payload 节省。3000 字以上时此问题会缓解。
- **所有模式总 size 都 > UTF-8**：因为样例太短，码表开销占绝对大头。3000 字时码表占比会从 60-90% 摊薄到 10-20%。

## 设计要点

* 符号粒度按 Unicode 字符（不是字节）—— 熵的物理意义清晰，码表条目数可控。
* JSON 老格式仅保留用于人眼检查中间产物。生产用走 `.shc`。
* 三层正交可叠加：tokenizer 决定 token 序列，ShannonCode 把 token 序列编成位流，codec 把"码表 + 位流"打包到一个文件。
* `--mode` 切换 tokenizer，对编/解端透明（解端通过码表自动恢复多字符 token）。

## 下一步

1. 准备约 3000 字的中英文测试信源，码表占比应大幅下降。
2. 给 PK 对手交付：`.shc` 单文件 + Huffman 同款字节容器 + `README.md` + 算法约定文档。
3. 把 Huffman 也接入：字节流打包、canonical 码表、`.huf` 单文件、复用 tokenizer。
4. 写测试报告：对自己代码 + 对手代码的客观分析（Shannon vs Huffman 在中/英、不同 q 下的效率对比）。
5. （可选）`singleton + ngram` 组合 tokenizer。
6. （可选）BWT + MTF 预处理——压缩率显著提升，但超出"对 Shannon/Huffman 码本身优化"的范畴。

## 参考

- C. E. Shannon, "A Mathematical Theory of Communication," 1948.
- D. A. Huffman, "A Method for the Construction of Minimum-Redundancy Codes," 1952.
- `docs/扩展说明`：进一步的优化方向与文本特性分析。
