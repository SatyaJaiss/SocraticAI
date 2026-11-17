# SocraticAI — Milestone 4 Pre-Implementation Audit & Verification

**Document Version:** 1.0.0  
**Audit Timestamp:** 2026-11-17  
**Scope:** Milestone 4: Production Engineering, LLMOps, Observability, Security and Evaluation Infrastructure

---

## 1. Executive Summary & Verification of Prior Milestones

A comprehensive codebase audit was conducted prior to implementing Milestone 4. The repository was inspected to verify that all foundational, memory, retrieval, and adaptive tutoring capabilities from Milestones 1, 1.5, 2, and 3 are present, operational, and free of regressions.

### Status of Previous Milestones:
- **Milestone 1 (Foundation & Reliability)**: Confirmed. JWT authentication, student isolation, conversation session persistence, and LangGraph lifecycle are fully operational.
- **Milestone 1.5 (Conversational Memory & Routing)**: Confirmed. Episodic/semantic memory, Jev/Gemini decision providers, token-budget context assembly, and multi-tier caching are present and tested.
- **Milestone 2 (Advanced RAG & Retrieval Intelligence)**: Confirmed. Section-aware chunking, dense + BM25 hybrid retrieval (RRF), cross-encoder reranking, and citation verification are integrated.
- **Milestone 3 (Adaptive Tutoring & Learning Intelligence)**: Confirmed. Concept-level learning state, asymptotic Bayesian confidence modeling ($C(n) = 1.0 - e^{-0.45n}$), bounded Socratic dialogue, misconception tracking, adaptive explanation modes, tolerance-aware quiz grading, and prerequisite DAG recommendation are active.
- **Test Baseline**: 248/248 unit and integration tests passing (`100%` pass rate).

---

## 2. Milestone 4 Target Capabilities & Gap Analysis

| Capability | Current State in Repository | Identified Gap / Requirement for Milestone 4 |
| :--- | :--- | :--- |
| **LLM Gateway** | Direct `LLMClient` invoking LangChain OpenAI / Gemini / Demo. | Need centralized **TensorZero Gateway** integration supporting provider configuration, retries, fallback behavior, timeout handling, token usage, latency tracking, and offline/demo failover. |
| **Guardrails** | Basic validation in Pydantic models; citation verification. | Need **NVIDIA NeMo Guardrails** integration (Input, Retrieval, Execution, Output rails) without replacing LangGraph or duplicating workflows in Colang. |
| **PII Protection & Redaction** | No dedicated redaction before external model/decision calls. | **CRITICAL SECURITY REQUIREMENT**: Build dedicated PII protection service with local deterministic detection, request-scoped placeholder generation (`[PERSON_1]`, `[EMAIL_1]`, etc.), strict isolation, redaction *before* any model/decision call, and safe response restoration. |
| **Distributed Tracing** | Partial basic logging; `opentelemetry` installed but unconfigured. | Full **OpenTelemetry** distributed tracing across FastAPI routes, LangGraph agent nodes, RAG retrieval/reranking, NeMo rails, and TensorZero calls, with W3C propagation. Ensure zero PII or credentials in trace attributes. |
| **Metrics & Monitoring** | No Prometheus `/metrics` endpoint; no Grafana dashboards. | Implement **Prometheus** metrics collection (`http_requests`, `llm_gateway`, `rag_latency`, `guardrails_blocked`, `pii_redacted_total`), `/metrics` route, and Grafana dashboard provisioning. |
| **Evaluation Infrastructure** | Deterministic unit tests; educational benchmark dataset. | Implement **Ragas** RAG evaluation (Context Precision/Recall, Faithfulness, Relevancy) and adversarial security evaluation datasets. |
| **Benchmarking** | Ad-hoc latency scripts in `packages/benchmarks/`. | Implement unified Milestone 4 performance & cost benchmarking suite comparing Baseline, Gateway, Guardrails, Telemetry, and Full Pipeline. |
| **Deployment & Ops** | Basic `docker-compose.yml` for backend/frontend only. | Updated `docker-compose.yml` orchestrating FastAPI backend, TensorZero gateway, Prometheus, Grafana, and OTel Collector with health checks. |

---

## 3. Mandatory Architectural Boundaries & Non-Negotiables

1. **Agent Orchestration**: LangGraph remains the sole orchestrator. NeMo Guardrails acts as a safety perimeter around inputs, retrieval, execution, and outputs; it must NOT replace LangGraph nodes or duplicate tutoring logic in Colang.
2. **Decision Providers**: Jev and Gemini Decisions remain behind the existing `DecisionProvider` abstraction and are NOT forced into generative chat interfaces. However, all inputs to decision providers MUST pass through the PII redaction boundary.
3. **PII Security Boundary**:
   $$\text{User Input} \longrightarrow \text{PII Redaction} \longrightarrow \text{NeMo Guardrails} \longrightarrow \text{LangGraph / External APIs (LLM, Jev, Gemini)} \longrightarrow \text{Output Rails} \longrightarrow \text{Controlled PII Restoration}$$
   Original PII must never reach external LLM endpoints, embeddings, decision APIs, logs, or traces.
4. **Offline Testability**: All unit, integration, and security tests must run offline with zero dependency on paid third-party APIs.
5. **No Destructive Migrations**: Do not migrate to Qdrant, Next.js, Celery, Redis, Kubernetes, or alternative application databases.

---

## 4. Implementation Plan & Execution Sequence

1. **Security & PII Subsystem**:
   - `apps/backend/app/security/pii/`: `detector.py`, `redactor.py`, `mapping.py`, `restorer.py`, `service.py`.
2. **NVIDIA NeMo Guardrails Subsystem**:
   - `configs/guardrails/`: `config.yml`, `prompts.yml`, `actions.py`, `rails.co`.
   - `apps/backend/app/guardrails/`: `service.py`, `input_rails.py`, `retrieval_rails.py`, `execution_rails.py`, `output_rails.py`.
3. **TensorZero Gateway Subsystem**:
   - `apps/backend/app/llm/gateway/`: `tensorzero_client.py`, `router.py`, `models.py`.
   - Integration into `apps/backend/app/llm/clients/client.py` and `services/container.py`.
4. **OpenTelemetry Distributed Tracing**:
   - `apps/backend/app/telemetry/tracing.py`: Tracer provider, W3C context, span decorators, FastAPI & HTTPX instrumentation, LangGraph instrumentation.
5. **Prometheus & Grafana Monitoring**:
   - `apps/backend/app/telemetry/metrics.py`: Counters, Histograms, Gauges, `/metrics` endpoint.
   - `configs/prometheus/prometheus.yml`, `configs/grafana/dashboards/`, `configs/grafana/provisioning/`.
6. **Centralized Configuration**:
   - Extend `apps/backend/app/core/config.py` with `PIISettings`, `GuardrailsSettings`, `TensorZeroSettings`, `TelemetrySettings`, `MetricsSettings`.
   - Update `.env.example`.
7. **Evaluation & Benchmarks**:
   - `apps/backend/app/evaluation/`: `ragas_eval.py`, `security_eval.py`, `benchmark_runner.py`.
   - `apps/backend/tests/fixtures/security_adversarial_dataset.json`.
8. **Deployment & Reliability**:
   - Update `docker-compose.yml` with health checks, Prometheus, Grafana, TensorZero, and OTel Collector.
9. **Automated Test Suite**:
   - Tests for PII redaction and restoration, NeMo rails, TensorZero gateway, OpenTelemetry spans, Prometheus metrics, and adversarial security scenarios.
   - Full regression verification across all existing tests.
