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

- **[New Restructured Architecture](docs/architecture/NEW_ARCHITECTURE.md)**: In-depth technical architecture, state machines, and RAG pipelines.
- **[Directory Structure Guide](docs/architecture/DIRECTORY_STRUCTURE.md)**: Comprehensive tour of packages, modules, and directories.
- **[Existing Architecture Audit](docs/architecture/EXISTING_ARCHITECTURE.md)**: Pre-restructuring analysis and baseline dependency mapping.
- **[Local Development Setup](docs/development/SETUP.md)**: Environment configuration and step-by-step startup guide.
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
| **Dynamic Practice Quizzes** | Generates mixed-format assessments (MCQ, numerical, subjective) targeting weak concepts. |
| **Deterministic & Hybrid Grading** | Objective questions graded deterministically via code; subjective questions evaluated via LLM with rubrics. |
| **Long-Term Memory** | Extracts persistent facts (strengths, goals, misconceptions) to personalize future sessions across turns. |
| **Contextual Note Grounding (RAG)**| Ingests PDFs/TXTs into ChromaDB using token-aware chunking and sentence-transformers; provides exact page citations. |
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

SocraticAI runs out of the box in **offline demo mode** (`LLM_PROVIDER=demo`). To use live models, update your `.env`:

```env
# For OpenAI
LLM_PROVIDER=openai
LLM_OPENAI_API_KEY=sk-...

# Or for Google Gemini
LLM_PROVIDER=gemini
LLM_GEMINI_API_KEY=AIza...
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

# Terminal 2: Frontend Dashboard (Streamlit)
make run-frontend
# Runs at http://localhost:8501
```

### 4. Running with Docker Compose

Run the entire platform with a single command:

```bash
docker compose up --build
```

---

## 🧪 Testing & Verification

SocraticAI includes a comprehensive suite of 102 automated unit and integration tests:

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

# Run end-to-end subsystem verification
make verify
```

---

## 📊 Evaluation Benchmarks

To benchmark pedagogical accuracy, hallucination resistance, latency, and memory recall:

```bash
uv run python packages/evaluation/run_all.py
```
Benchmark reports and metrics are saved to `packages/evaluation/results/`.

---

## 📄 License

This project is licensed under the MIT License. See [LICENSE](LICENSE) for details.
