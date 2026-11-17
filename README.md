# 🎓 SocraticAI — AI Personal Tutoring Platform

<p align="center">
  <a href="https://www.python.org/"><img src="https://img.shields.io/badge/Python-3.11%2B-3776AB?logo=python&logoColor=white" alt="Python 3.11+"></a>
  <a href="https://langchain-ai.github.io/langgraph/"><img src="https://img.shields.io/badge/LangGraph-Agent%20Framework-1C3C3C" alt="LangGraph"></a>
  <a href="https://fastapi.tiangolo.com/"><img src="https://img.shields.io/badge/FastAPI-009688?logo=fastapi&logoColor=white" alt="FastAPI"></a>
  <a href="https://streamlit.io/"><img src="https://img.shields.io/badge/Streamlit-FF4B4B?logo=streamlit&logoColor=white" alt="Streamlit"></a>
  <a href="https://www.trychroma.com/"><img src="https://img.shields.io/badge/ChromaDB-RAG-DA5B0B" alt="ChromaDB RAG"></a>
  <a href="https://www.sqlite.org/"><img src="https://img.shields.io/badge/SQLite-003B57?logo=sqlite&logoColor=white" alt="SQLite"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/License-MIT-yellow" alt="MIT License"></a>
</p>

SocraticAI is a modular, production-ready AI personal tutoring platform built on **LangGraph**, **FastAPI**, **Streamlit**, **SQLite**, and **ChromaDB**. It orchestrates a multi-agent reasoning graph that plans each pedagogical turn, teaches concepts with tailored examples, generates adaptive practice quizzes, grades answers with granular feedback, extracts persistent long-term student memory, and recommends next study steps — all grounded in the student's uploaded notes via Retrieval-Augmented Generation (RAG).

---

## 📖 Architectural Documentation

- **[LLMOps & Observability Guide](docs/architecture/LLMOPS_OBSERVABILITY.md)**: OpenTelemetry tracing, Prometheus metrics, and Grafana monitoring.
- **[PII Protection & Safe Restoration Design](docs/security/PII_PROTECTION_DESIGN.md)**: Zero-PII de-identification and safe response restoration.
- **[TensorZero Gateway Integration](docs/architecture/TENSORZERO_INTEGRATION.md)**: Centralized model routing, fallbacks, and token tracking.
- **[NeMo Guardrails Architecture](docs/architecture/NEMO_GUARDRAILS.md)**: Input, retrieval, execution, and output safety rails.
- **[Security & RAG Evaluation](docs/evaluation/SECURITY_AND_RAG_EVALUATION.md)**: Ragas framework & adversarial security evaluation report.
- **[Performance Benchmark Report](docs/benchmarks/PERFORMANCE_REPORT.md)**: Subsystem latency breakdown and resource overhead analysis.
- **[Centralized Configuration Reference](docs/configuration/CONFIGURATION_REFERENCE.md)**: Complete catalog of typed environment settings.
- **[New Restructured Architecture](docs/architecture/NEW_ARCHITECTURE.md)**: In-depth technical architecture, state machines, and RAG pipelines.
- **[Directory Structure Guide](docs/architecture/DIRECTORY_STRUCTURE.md)**: Comprehensive tour of packages, modules, and directories.
- **[Testing & QA Guide](docs/development/TESTING.md)**: Unit, integration, and benchmark suite execution.
- **[Architecture Decision Records](docs/decisions/)**: ADRs covering modularization, state decoupling, prompt externalization, and persistence abstractions.

---

## 🧱 Repository Architecture

```text
SocraticAI/
├── apps/
│   ├── backend/                      # FastAPI application & tests
│   │   ├── app/
│   │   │   ├── api/v1/               # Versioned API routes & router aggregation
│   │   │   ├── core/                 # Config, logging, exceptions, dependencies
│   │   │   ├── agents/               # Planner, Teacher, Quiz, Eval, Memory, Rec, RAG
│   │   │   ├── graphs/               # LangGraph workflows, states, routing
│   │   │   ├── rag/                  # Modular ingestion, chunking, embeddings, retrieval
│   │   │   ├── llm/                  # Providers (OpenAI, Gemini, Demo), clients, prompt loader
│   │   │   ├── services/             # Dependency injection container
│   │   │   ├── repositories/         # Database access layer (SQLAlchemy)
│   │   │   ├── models/               # SQLAlchemy ORM models
│   │   │   ├── schemas/              # Pydantic schemas & domain enums
│   │   │   ├── db/                   # Connection management & transaction scopes
│   │   │   └── utils/                # Helpers, async utilities, logging
│   │   ├── tests/                    # Backend test suite (fixtures, unit, integration)
│   │   └── Dockerfile
│   │
│   └── frontend/                     # Modular Streamlit application
│       ├── app.py                    # Main dashboard entrypoint & page router
│       ├── pages/                    # Chat, Quiz, Dashboard, Document upload pages
│       ├── components/               # Reusable sidebar & navigation widgets
│       ├── services/                 # Frontend HTTP API client
│       ├── utils/                    # Session state management
│       └── Dockerfile
│
├── packages/                         # Reusable packages
│   ├── shared/                       # Shared models, types, and constants
│   ├── evaluation/                   # Accuracy, hallucination, latency, quiz benchmarks
│   └── experiments/                  # Chunking & embedding research experiments
│
├── configs/                          # Externalized configurations
│   ├── agents/                       # Agent hyperparameters (agents.yaml)
│   ├── rag/                          # RAG pipeline parameters (rag.yaml)
│   └── prompts/                      # Agent YAML prompt templates
│
├── data/                             # Application persistence
│   ├── uploads/                      # Raw uploaded course notes (PDF/TXT)
│   ├── processed/                    # Processed document artifacts
│   ├── sample/                       # Sample request & evaluation JSON payloads
│   └── chroma/                       # ChromaDB vector index
│
├── scripts/                          # Automation scripts
│   ├── setup/                        # Environment bootstrap scripts
│   ├── migration/                    # Database table initialization
│   └── development/                  # E2E verification & test document generators
│
├── docs/                             # Documentation, specifications, and ADRs
├── .env.example                      # Template environment configuration
├── pyproject.toml                    # Python project metadata, dependencies, & tools
├── Makefile                          # Development & testing shortcuts
└── docker-compose.yml                # Multi-container orchestration
```

---

## ✨ Key Capabilities

| Capability | Description |
| :--- | :--- |
| **Multi-Agent Orchestration** | LangGraph state graph routing dynamically between `planner → (teach / quiz / evaluate) → memory → recommendation`. |
| **Adaptive Lesson Generation** | Personalized explanations with relatable analogies, concrete examples, and recaps tuned to student mastery level. |
| **Guided Socratic Tutoring** | Multi-step problem decomposition and progressive hint escalation without premature solution revealing. |
| **Dynamic Practice Quizzes** | Generates mixed-format assessments (MCQ, numerical, subjective) targeting weak concepts. |
| **Deterministic & Hybrid Grading** | Objective questions graded deterministically via code; subjective questions evaluated via LLM with rubrics. |
| **Long-Term Memory** | Extracts persistent facts (strengths, goals, misconceptions) to personalize future sessions across turns. |
| **Contextual Note Grounding (RAG)**| Hybrid dense (ChromaDB) + lexical (BM25) search with Reciprocal Rank Fusion, cross-encoder reranking, and citation verification. |
| **PII Protection & Safe Restoration** | Real-time detection and de-identification of PII before any third-party model call, with safe placeholder restoration in final responses. |
| **NVIDIA NeMo Guardrails** | Multi-layer safety policy enforcement across input jailbreaks, untrusted retrieved documents, tool executions, and output leaks. |
| **TensorZero LLM Gateway** | Centralized gateway routing, automatic exponential backoff retries, graceful fallbacks, and token usage accounting. |
| **OpenTelemetry & Prometheus** | Distributed tracing with W3C context propagation, root-to-leaf spans, `/metrics` Prometheus scraping, and Grafana dashboards. |
| **Analytics Dashboard** | Interactive Streamlit analytics tracking mastery by topic, score history, and memory items. |
| **Offline Demo Mode** | Full offline execution supported via `DemoLLMProvider` — test and develop without any external API keys. |

---

## 🚀 Quick Start

### 1. Installation

Clone the repository and set up a Python 3.11+ virtual environment using [uv](https://docs.astral.sh/uv/) or standard Python:

```bash
# Using uv (recommended)
uv venv
source .venv/bin/activate  # On Windows: .venv\Scripts\Activate.ps1
uv pip install -r requirements-dev.txt

# Or using Makefile
make install
```

### 2. Configuration

Copy the example configuration to `.env`:

```bash
cp .env.example .env
```

SocraticAI runs out of the box in **offline demo mode** (`LLM_PROVIDER=demo`). To use live models or gateway routing, update your `.env`:

```env
# Production Gateway
TENSORZERO_ENABLED=true
TENSORZERO_GATEWAY_URL=http://localhost:3000

# Safety & Privacy
PII_ENABLED=true
GUARDRAILS_ENABLED=true

# Telemetry
OTEL_ENABLED=true
OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4318
METRICS_ENABLED=true
```

Initialize database tables:
```bash
make init-db
# Or: uv run python scripts/migration/init_db.py
```

### 3. Running Backend & Frontend

Start both services locally:

```bash
# Terminal 1: Backend API (FastAPI)
make run-backend
# Runs at http://localhost:8000 (Swagger docs: http://localhost:8000/docs)
# Metrics endpoint: http://localhost:8000/metrics

# Terminal 2: Frontend Dashboard (Streamlit)
make run-frontend
# Runs at http://localhost:8501
```

### 4. Running the Full Production Stack (Docker Compose)

Launch the complete stack (FastAPI Backend, TensorZero Gateway, Prometheus, Grafana, OpenTelemetry Collector):

```bash
docker compose up --build -d
```

| Service | Port | Description |
|---|---|---|
| **SocraticAI Backend** | `http://localhost:8000` | FastAPI application, Swagger UI, and `/metrics` |
| **SocraticAI Frontend** | `http://localhost:8501` | Streamlit interactive tutoring UI |
| **TensorZero Gateway** | `http://localhost:3000` | LLM Gateway inference proxy |
| **Prometheus** | `http://localhost:9090` | Time-series metrics and alerting |
| **Grafana** | `http://localhost:3001` | Operational dashboards (`admin` / `admin`) |
| **OpenTelemetry Collector** | `http://localhost:4317` / `4318` | Distributed tracing collector |

---

## 🧪 Testing & Verification

SocraticAI includes a comprehensive suite of over 275 automated unit and integration tests:

```bash
# Run all tests
make test
# Or: uv run pytest

# Run unit tests only
make test-unit

# Run integration tests only
make test-integration

# Run linting check
make lint
# Or: uv run ruff check apps/backend

# Run end-to-end subsystem verification
make verify
```

---

## 📊 Evaluation & Benchmarks

Run the complete evaluation suite including Ragas retrieval scoring, adversarial security testing, and latency benchmarking:

```bash
# Milestone 4 Performance & Latency Benchmark
uv run python packages/evaluation/benchmark_milestone_4.py

# Adversarial Guardrail & PII Security Evaluation
uv run python -c "from app.evaluation.security_eval import SecurityEvaluator; e = SecurityEvaluator(); print(e.evaluate_dataset('apps/backend/tests/fixtures/security_adversarial_dataset.json'))"

# Pedagogical & Retrieval Accuracy Benchmarks
uv run python packages/evaluation/run_all.py
```
Benchmark reports and metrics are saved to `packages/evaluation/results/`.

---

## 📄 License

This project is licensed under the MIT License. See [LICENSE](LICENSE) for details.
