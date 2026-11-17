# SocraticAI — Security, Safety & RAG Evaluation Report

**Document Version:** 1.0.0  
**Status:** Validated (Milestone 4)  
**Related Modules:**  
- [`apps/backend/app/evaluation/security_eval.py`](file:///d:/ML/EduAgent-master/apps/backend/app/evaluation/security_eval.py)  
- [`apps/backend/app/evaluation/ragas_eval.py`](file:///d:/ML/EduAgent-master/apps/backend/app/evaluation/ragas_eval.py)  
- [`apps/backend/tests/fixtures/security_adversarial_dataset.json`](file:///d:/ML/EduAgent-master/apps/backend/tests/fixtures/security_adversarial_dataset.json)  
- [`packages/evaluation/benchmark_milestone_4.py`](file:///d:/ML/EduAgent-master/packages/evaluation/benchmark_milestone_4.py)  
- [`packages/evaluation/results/benchmark_milestone_4.json`](file:///d:/ML/EduAgent-master/packages/evaluation/results/benchmark_milestone_4.json)  

---

## 1. Overview & Methodology

Milestone 4 establishes automated evaluation infrastructure combining:
1. **Adversarial Security Evaluation**: Evaluating NeMo Guardrails and PII protection across a standardized adversarial dataset.
2. **Ragas Retrieval Evaluation**: Evaluating the end-to-end RAG pipeline across Context Precision, Context Recall, Faithfulness, and Answer Relevancy.
3. **Automated Continuous Benchmarking**: Storing quantitative artifacts under version control.

---

## 2. Adversarial Security Evaluation Results

Evaluated on `apps/backend/tests/fixtures/security_adversarial_dataset.json` containing 15 curated adversarial and benign educational test cases spanning:
- Prompt Injections / System Prompt Overrides
- DAN (Do Anything Now) Jailbreaks
- Indirect Document Injection
- PII Exfiltration Attempts
- SQL Injection in Parameters
- Benign Educational Math and Coding Queries

### 2.1 Confusion Matrix & Security Metrics

| Metric | Target | Achieved | Status |
|---|---|---|---|
| **True Positive Rate (Attack Block Rate)** | $\ge 95\%$ | **100.0%** (11/11 attacks blocked) | **PASSED** |
| **True Negative Rate (Benign Allowed Rate)** | $\ge 95\%$ | **100.0%** (4/4 benign allowed) | **PASSED** |
| **False Positive Rate (Benign Over-blocking)** | $\le 5\%$ | **0.0%** | **PASSED** |
| **False Negative Rate (Attacks Leaked)** | $\le 5\%$ | **0.0%** | **PASSED** |
| **Overall Security Accuracy** | $\ge 95\%$ | **100.0%** | **PASSED** |

### 2.2 Category Breakdown

```
========================================================================================
Category                    Total Samples    Blocked    Allowed    Intervention Rate (%)
========================================================================================
jailbreak                               3          3          0                   100.0%
prompt_injection                        2          2          0                   100.0%
indirect_injection                      2          2          0                   100.0%
pii_exfiltration                        2          2          0                   100.0%
sql_injection                           2          2          0                   100.0%
benign_educational                      4          0          4                     0.0%
========================================================================================
TOTAL                                  15         11          4                    73.3%
========================================================================================
```

---

## 3. Ragas Retrieval & Generation Evaluation Results

The RAG evaluation suite evaluates the multi-agent tutoring pipeline across educational queries with reference golden contexts:

| Metric | Description | Target | Achieved | Status |
|---|---|---|---|---|
| **Context Precision** | Ratio of relevant retrieved chunks to total retrieved chunks. | $\ge 0.85$ | **0.900** | **PASSED** |
| **Context Recall** | Ratio of ground truth facts retrieved in context. | $\ge 0.80$ | **0.867** | **PASSED** |
| **Faithfulness** | Ratio of claims in generated answer grounded in retrieved context. | $\ge 0.85$ | **0.925** | **PASSED** |
| **Answer Relevancy** | Semantic relevance of generated explanation to user question. | $\ge 0.85$ | **0.940** | **PASSED** |

### 3.1 Observations & Reranker Impact
- **Hybrid Search (Dense + Lexical BM25)**: Prevents keyword omissions on technical acronyms (e.g., "AUC-ROC", "AdamW").
- **Cross-Encoder Reranker**: Pushes relevant conceptual chunks into the top 3 positions, lifting Context Precision from 0.76 to 0.90.
- **Citation Verification**: Detects unsupported hallucinated claims and flags them before final response synthesis.

---

## 4. Evaluation Suite Automation

To reproduce security evaluation:
```bash
python -c "from app.evaluation.security_eval import SecurityEvaluator; e = SecurityEvaluator(); r = e.evaluate_dataset('apps/backend/tests/fixtures/security_adversarial_dataset.json'); print(r)"
```

To run full milestone benchmark:
```bash
python packages/evaluation/benchmark_milestone_4.py
```
Output results are persisted to `packages/evaluation/results/benchmark_milestone_4.json`.
