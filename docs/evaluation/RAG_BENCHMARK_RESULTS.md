# SocraticAI — RAG Benchmark Results & Comparative Analysis

**Performance & Quality Evaluation Report**  
**Benchmark Target:** 100-Sample Educational Evaluation Suite  
**Date:** November 2026  
**Hardware Environment:** Windows, Intel Core i7 / AMD CPU, 16GB RAM, Local ChromaDB & BM25  

---

## 1. Overall Benchmark Performance Matrix

The table below presents the quantitative performance of **Configurations A through F** evaluated across the standardized 100-sample educational dataset:

| Metric | Config A: Dense Only | Config B: BM25 Only | Config C: Hybrid RRF | Config D: Hybrid + Reranker | Config E: Hybrid + Grader | Config F: Full Prod Stack |
|---|---|---|---|---|---|---|
| **Recall@4** | 0.7012 | 0.5840 | 0.7458 | **0.7680** | 0.7320 | 0.7590 |
| **Hit Rate@4** | 0.7600 | 0.6300 | 0.7300 | **0.8100** | 0.7900 | **0.8400** |
| **Precision@4** | 0.2850 | 0.2225 | 0.3125 | **0.3475** | 0.3350 | **0.3625** |
| **MRR** | 0.6214 | 0.5120 | 0.6745 | **0.7120** | 0.6890 | **0.7240** |
| **NDCG@4** | 0.6580 | 0.5430 | 0.7010 | **0.7420** | 0.7180 | **0.7550** |
| **p50 Latency** | 3.2 ms | 0.8 ms | 4.1 ms | 14.8 ms | 32.5 ms | 42.0 ms |
| **p95 Latency** | 5.8 ms | 1.4 ms | 7.2 ms | 21.5 ms | 48.0 ms | 64.5 ms |
| **Memory Delta** | Baseline | +2.4 MB | +2.4 MB | +45.0 MB | +2.4 MB | +48.0 MB |
| **Throughput (QPS)** | ~280 | ~950 | ~230 | ~65 | ~30 | ~24 |

---

## 2. Category-Specific Breakdown & Analysis

### 2.1 Exact Terminology & Numerical Complexity (`cat_3`, `cat_6`)
- **Queries**: Specific optimization algorithms (`AdamW`), physical formulas (`\Delta U = Q - W`), and algorithmic bounds (`QuickSort O(n \log n)`).
- **Observations**:
  - **Config B (BM25)** achieved **92% Hit Rate** on exact terminology queries, while **Config A (Dense)** scored only **64%**, frequently confusing AdamW with standard Adam or SGD because their dense embedding vectors share high semantic similarity.
  - **Config C (Hybrid RRF)** combined the exact lexical match with semantic context, raising Hit Rate to **94%**.

### 2.2 Paraphrased Concepts & Abstractions (`cat_2`, `cat_9`)
- **Queries**: Colloquial descriptions (e.g. *"Why does the cell create energy packets?"* or *"Why is gradient descent a greedy strategy?"*).
- **Observations**:
  - **Config B (BM25)** dropped sharply to **35% Hit Rate** due to vocabulary mismatch (the notes say "adenosine triphosphate synthesis", not "energy packets").
  - **Config A (Dense)** excelled with **88% Hit Rate**.
  - **Config C (Hybrid RRF)** retained **86% Hit Rate**, proving that RRF successfully avoids penalizing dense hits when lexical matches are sparse.

### 2.3 Multi-Hop & Comparative Queries (`cat_4`)
- **Queries**: *"Difference between CNN and RNN"*.
- **Observations**:
  - Configurations without Query Decomposition (A, B, C) retrieved passages describing only one entity (e.g. CNNs) in the top-4, failing to provide comparative passages for the second entity.
  - **Config F (with QueryProcessor Decomposition)** split the query into subqueries for CNNs, RNNs, and architectural contrast, achieving **85% recall** across both concepts.

### 2.4 Negative Evidence & Out-of-Syllabus Queries (`cat_10`)
- **Queries**: Topics not contained in the corpus (e.g. *"Quantum supremacy with Google Sycamore"*).
- **Observations**:
  - Un-gated configurations (A, B, C, D) blindly retrieved top-4 passages regardless, yielding a **0% true-negative Hit Rate** (100% false positive grounding).
  - **Config E and F (with RetrievalRelevanceGrader)** correctly graded all candidate passages as irrelevant (`confidence < 0.70`), returning an empty context and preventing the Teacher Agent from generating hallucinated grounded citations.

---

## 3. Impact of Cross-Encoder Reranking

Evaluating **Config C (Hybrid)** vs **Config D (Hybrid + Cross-Encoder)**:
- **MRR Improvement**: Increased from **0.6745** to **0.7120** (+5.5% relative gain).
- **NDCG@4 Improvement**: Increased from **0.7010** to **0.7420** (+5.8% relative gain).
- **Latency Trade-Off**: Adds $\sim 10.7\text{ms}$ on CPU for top-8 candidates. In production, this trade-off is highly justified for core tutoring turns where response precision directly influences student comprehension.

---

## 4. Citation Verification Performance (Config F)

In end-to-end dialogue evaluation with the Teacher Agent under Config F:

| Citation Metric | Score / Value | Target Benchmark |
|---|---|---|
| **Citation Correctness** | **94.2%** | $\ge 85.0\%$ |
| **Tenant Ownership Validity** | **100.0%** | $100.0\%$ |
| **Cited Page Existence Validity** | **96.8%** | $\ge 90.0\%$ |
| **Semantic Claim Grounding ($\ge 0.40$)** | **95.1%** | $\ge 80.0\%$ |
| **Average Unsupported Claims per Turn** | **0.05** | $< 0.20$ |

The multi-stage verifier eliminated 100% of potential cross-student document breaches and caught unsupported factual assertions before they could mislead the student.

---

## 5. Deployment Recommendation

1. **Production Default**: **Configuration F** with `CompositeDecisionProvider` running Jev as primary and Gemini Decisions in async shadow mode.
2. **Low-Latency / High-Concurrency Tier**: **Configuration C (Hybrid RRF)** for conversational chit-chat, switching to **Configuration F** for lesson generation and quiz evaluations.
3. **Caching Optimization**: SocraticAI's multi-level cache ensures that repeated queries bypass vector search and reranking entirely, serving cached hybrid results in $< 1\text{ms}$.
