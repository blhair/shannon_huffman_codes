---
name: project-shannon-codes
description: 信息论课程作业 1-B：实现 Shannon 编码 + Q-ary Huffman 编码，并与他组 PK 互测
metadata:
  type: project
---

课程任务（docs/image.png 截图，Course Project 1-B）：2 人组队，组间 PK。要求**分别**用 **Shannon codes** 和 **Q-ary Huffman codes** 对一段中英文文本（~3000 字）做编/解码。需提交：（1）Shannon 可运行源码 + readme；（2）Huffman 可运行源码 + readme；（3）测试报告：对自己代码的测试结果、对 PK 对手代码的测试结果、两份实现的客观分析（优势与不足）。

**Why:** 这是评分作业；交付物是双算法可演示代码 + 中英两套测试信源 + 测试报告。

**How to apply:**
- Shannon 部分：根目录 `shannon.py` (核心)、`cli.py` (encode/decode/roundtrip + compress/decompress/compare)、`shannon_bytes.py` / `shannon_tokens.py` / `shannon_codec.py`（三层优化已落地）。
- Huffman 部分：根目录 `huffman.py`（核心 HuffmanCode，支持 q ∈ [2,10]）+ `huffman_cli.py`（encode/decode/roundtrip，老格式 JSON 码表 + q 进制 ASCII 码流）。**初版**，尚未做字节流打包、canonical 码表、`.huf` 容器，也还没接 tokenizer。
- 已用 samples/zh_sample.txt 和 en_sample.txt 验证 q=2 / q=3 roundtrip 通过，q=2 效率 ~99%。
- 仍未做：（1）准备真正约 3000 字的中英文测试信源；（2）把 Huffman 接入字节容器（对齐 Shannon 的 `.shc`）；（3）写测试报告（含与对手互测结果）。
- 用户母语中文，作业说明和讲解都用中文。
