# SocraticAI — RAG Evaluation Methodology & Dataset Specification

**Evaluation Framework Specification**  
**Module:** RAG Benchmarking & Quality Assurance  
**Author:** SocraticAI LLM Systems Engineering Team  
**Status:** Active Benchmark Specification  

---

## 1. Overview & Objective

To systematically measure, validate, and compare retrieval architectures, SocraticAI establishes a standardized RAG Evaluation Framework. The objective is to replace qualitative impressions with rigorous quantitative metrics across diverse pedagogical query patterns, testing precision, recall, ranking quality, and latency.

The evaluation suite tests **Configurations A through F** against a curated 100-question ground-truth evaluation corpus.

---

## 2. Curated 100-Sample Evaluation Dataset

The dataset is stored in [`apps/backend/tests/fixtures/rag_evaluation_dataset.json`](file:///d:/ML/EduAgent-master/apps/backend/tests/fixtures/rag_evaluation_dataset.json). It contains exactly **100 questions** evenly distributed across **10 distinct educational query categories** (10 questions each):

| Category ID | Category Name | Description & Pedagogical Intent | Example Query |
|---|---|---|---|
| `cat_1` | **Direct Factual** | Simple, explicit factual queries with high literal correspondence. | *"What is the primary function of mitochondria?"* |
| `cat_2` | **Paraphrased Concept** | Questions expressing textbook ideas using colloquial or alternate phrasings. | *"Why does the cell create energy packets?"* |
| `cat_3` | **Exact Terminology** | Queries containing rare symbols, formula names, algorithm titles, or codes. | *"How does AdamW decouple weight decay from gradient updates?"* |
| `cat_4` | **Multi-Hop / Comparative** | Multi-concept questions comparing two entities or requiring joint synthesis. | *"What is the difference between CNN and RNN architectures?"* |
| `cat_5` | **Definition & Formulation** | Formal mathematical definitions and theorem statements. | *"State the First Law of Thermodynamics and write its equation."* |
| `cat_6` | **Numerical / Algorithmic** | Computational complexity, asymptotic bounds, and step-by-step algorithms. | *"What is the time complexity of QuickSort in the average and worst case?"* |
| `cat_7` | **Section-Specific** | Questions targeting a narrow subsection within a nested document hierarchy. | *"In Section 3.2 on Neural Network Regularization, what is Dropout?"* |
| `cat_8` | **Cross-Section Synthesis** | Queries requiring evidence spanning multiple sections of the same syllabus. | *"How do Light Reactions and the Calvin Cycle interact in photosynthesis?"* |
| `cat_9` | **Concept Abstraction** | High-level philosophical or conceptual questions testing abstract semantic mapping. | *"Why is gradient descent considered a greedy optimization algorithm?"* |
| `cat_10` | **Negative Evidence** | Unanswerable / out-of-syllabus questions with zero supporting corpus evidence. | *"What is quantum supremacy and how does Google Sycamore work?"* |

### Dataset Item Schema:
```json
{
  "id": "q001",
  "category": "direct_factual",
  "query": "What is the primary function of mitochondria in eukaryotic cells?",
  "document": "biology_notes.pdf",
  "expected_passages": [
    "Mitochondria are membrane-bound cell organelles that generate most of the chemical energy needed to power the cell's biochemical reactions, stored in adenosine triphosphate (ATP)."
  ],
  "expected_pages": [2],
  "relevant_chunk_ids": ["doc_bio::c2::mitochondria"]
}
```

---

## 3. Mathematical Metric Formulations

### 3.1 Hit Rate@k
Measures whether at least one ground-truth passage appears in the top-$k$ retrieved candidates:

$$\text{HitRate@}k = \begin{cases} 
1.0 & \text{if } \exists d \in \text{Retrieved}_{1..k} \text{ such that } d \in \text{GroundTruth} \\
0.0 & \text{otherwise}
\end{cases}$$

*(For negative evidence queries where $\text{GroundTruth} = \emptyset$, Hit Rate is $1.0$ if no passages are retrieved or passed through gating, and $0.0$ if irrelevant passages are retrieved).*

### 3.2 Recall@k
Proportion of all relevant ground-truth passages retrieved within the top-$k$ slots:

$$\text{Recall@}k = \frac{|\text{Retrieved}_{1..k} \cap \text{GroundTruth}|}{|\text{GroundTruth}|}$$

### 3.3 Precision@k
Proportion of top-$k$ retrieved candidate passages that are genuinely relevant:

$$\text{Precision@}k = \frac{|\text{Retrieved}_{1..k} \cap \text{GroundTruth}|}{k}$$

### 3.4 Mean Reciprocal Rank (MRR)
Evaluates where the first relevant passage appears in the ranked candidate list:

$$\text{MRR} = \frac{1}{|Q|} \sum_{q \in Q} \frac{1}{\text{rank}_1(q)}$$

Where $\text{rank}_1(q)$ is the rank position of the first relevant chunk for query $q$, or $0.0$ if no relevant chunk is retrieved.

### 3.5 Normalized Discounted Cumulative Gain (NDCG@k)
Accounts for graded position decay, penalizing relevant items retrieved at lower ranks:

$$\text{DCG@}k = \sum_{i=1}^k \frac{\mathbb{I}(d_i \in \text{GroundTruth})}{\log_2(i + 1)}$$

$$\text{NDCG@}k = \frac{\text{DCG@}k}{\text{IDCG@}k}$$

Where $\text{IDCG@}k$ is the ideal DCG score if all relevant items were ranked at the very top.

---

## 4. Evaluated Architecture Configurations

The benchmark evaluates six architectural configurations:

- **Configuration A (Dense-Only Baseline)**: ChromaDB embedding search with top-$k=4$.
- **Configuration B (Lexical-Only Baseline)**: BM25Okapi lexical token matching with top-$k=4$.
- **Configuration C (Hybrid RRF)**: Multi-Modal fusion combining Dense (top-20) + BM25 (top-20) with Reciprocal Rank Fusion ($k=60$), yielding top-$k=4$.
- **Configuration D (Hybrid + Cross-Encoder Reranking)**: Hybrid RRF candidate generation (top-8) followed by `cross-encoder/ms-marco-MiniLM-L-6-v2` neural reranking down to top-$k=4$.
- **Configuration E (Hybrid + Decision Relevance Grading)**: Hybrid RRF candidate generation filtered through `RetrievalRelevanceGrader` (binary relevance classification with confidence gating $\ge 0.70$).
- **Configuration F (Full Production Stack)**: Query decomposition + Hybrid RRF + Cross-Encoder Reranker + Decision Relevance Grader + Citation Verification.
