# SocraticAI — Directory Structure Reference

This document details the file and directory layout of the reorganized SocraticAI codebase, explaining the architectural purpose and responsibility of each directory.

```text
SocraticAI/
├── apps/
│   ├── backend/
│   │   ├── app/
│   │   │   ├── api/
│   │   │   │   └── v1/
│   │   │   │       ├── routes/
│   │   │   │       │   ├── health.py
│   │   │   │       │   ├── chat.py
│   │   │   │       │   ├── quizzes.py
│   │   │   │       │   ├── documents.py
│   │   │   │       │   ├── dashboard.py
│   │   │   │       │   └── students.py
│   │   │   │       └── router.py
│   │   │   │
│   │   │   ├── core/
│   │   │   │   ├── config.py
│   │   │   │   ├── logging.py
│   │   │   │   ├── exceptions.py
│   │   │   │   └── dependencies.py
│   │   │   │
│   │   │   ├── agents/
│   │   │   │   ├── base.py
│   │   │   │   ├── context.py
│   │   │   │   ├── planner/
│   │   │   │   ├── teacher/
│   │   │   │   ├── quiz/
│   │   │   │   ├── evaluation/
│   │   │   │   ├── memory/
│   │   │   │   ├── recommendation/
│   │   │   │   └── rag/
│   │   │   │
│   │   │   ├── graphs/
│   │   │   │   ├── states/
│   │   │   │   │   └── state.py
│   │   │   │   ├── routing/
│   │   │   │   │   └── router.py
│   │   │   │   ├── tutoring/
│   │   │   │   │   └── workflow.py
│   │   │   │   └── evaluation/
│   │   │   │       └── workflow.py
│   │   │   │
│   │   │   ├── rag/
│   │   │   │   ├── chunking/
│   │   │   │   │   └── chunker.py
│   │   │   │   ├── embeddings/
│   │   │   │   │   └── provider.py
│   │   │   │   ├── ingestion/
│   │   │   │   │   └── pipeline.py
│   │   │   │   ├── retrieval/
│   │   │   │   │   └── vector_store.py
│   │   │   │   └── pipelines/
│   │   │   │       └── service.py
│   │   │   │
│   │   │   ├── llm/
│   │   │   │   ├── clients/
│   │   │   │   │   └── client.py
│   │   │   │   ├── providers/
│   │   │   │   │   └── demo.py
│   │   │   │   └── prompts/
│   │   │   │       └── loader.py
│   │   │   │
│   │   │   ├── services/
│   │   │   │   └── container.py
│   │   │   ├── repositories/
│   │   │   │   ├── base_repository.py
│   │   │   │   ├── student_repository.py
│   │   │   │   ├── conversation_repository.py
│   │   │   │   ├── document_repository.py
│   │   │   │   ├── lesson_repository.py
│   │   │   │   ├── memory_repository.py
│   │   │   │   ├── progress_repository.py
│   │   │   │   └── quiz_repository.py
│   │   │   ├── models/
│   │   │   │   └── orm.py
│   │   │   ├── schemas/
│   │   │   │   ├── domain.py
│   │   │   │   └── enums.py
│   │   │   ├── db/
│   │   │   │   └── connection.py
│   │   │   ├── utils/
│   │   │   │   ├── async_utils.py
│   │   │   │   ├── helpers.py
│   │   │   │   └── logging.py
│   │   │   └── main.py
│   │   │
│   │   ├── tests/
│   │   │   ├── fixtures/
│   │   │   │   ├── conftest.py
│   │   │   │   └── fakes.py
│   │   │   ├── integration/
│   │   │   │   ├── test_api.py
│   │   │   │   ├── test_documents_api.py
│   │   │   │   ├── test_graphs.py
│   │   │   │   └── test_rag.py
│   │   │   └── unit/
│   │   │       ├── test_agents.py
│   │   │       ├── test_chunking.py
│   │   │       ├── test_llm_demo.py
│   │   │       ├── test_repositories.py
│   │   │       └── test_vector_store.py
│   │   └── Dockerfile
│   │
│   └── frontend/
│       ├── app.py
│       ├── pages/
│       │   ├── chat.py
│       │   ├── quiz.py
│       │   ├── dashboard.py
│       │   └── documents.py
│       ├── components/
│       │   └── sidebar.py
│       ├── services/
│       │   └── api_client.py
│       ├── utils/
│       │   └── state.py
│       └── Dockerfile
│
├── packages/
│   ├── shared/
│   │   └── __init__.py
│   ├── evaluation/
│   │   ├── benchmark_accuracy.py
│   │   ├── benchmark_agents.py
│   │   ├── benchmark_e2e.py
│   │   ├── benchmark_hallucination.py
│   │   ├── benchmark_latency.py
│   │   ├── benchmark_memory.py
│   │   ├── benchmark_quiz.py
│   │   ├── benchmark_rag.py
│   │   ├── common.py
│   │   └── run_all.py
│   └── experiments/
│       ├── chunkers.py
│       ├── make_corpus.py
│       └── run_experiments.py
│
├── configs/
│   ├── agents/
│   │   └── agents.yaml
│   ├── rag/
│   │   └── rag.yaml
│   └── prompts/
│       ├── planner.yaml
│       ├── teacher.yaml
│       ├── quiz.yaml
│       ├── evaluation.yaml
│       ├── memory.yaml
│       └── recommendation.yaml
│
├── data/
│   ├── uploads/
│   ├── processed/
│   ├── sample/
│   │   ├── chat_demo.json
│   │   ├── eval_demo.json
│   │   ├── quiz_submit.json
│   │   └── rag_demo.json
│   └── chroma/
│
├── scripts/
│   ├── setup/
│   │   └── setup_env.py
│   ├── migration/
│   │   └── init_db.py
│   └── development/
│       ├── e2e_verify.py
│       └── make_sample_doc.py
│
├── docs/
│   ├── architecture/
│   │   ├── EXISTING_ARCHITECTURE.md
│   │   ├── NEW_ARCHITECTURE.md
│   │   └── DIRECTORY_STRUCTURE.md
│   ├── development/
│   │   ├── SETUP.md
│   │   └── TESTING.md
│   └── decisions/
│       ├── 0001-modular-repository-structure.md
│       ├── 0002-decoupled-langgraph-state-and-routing.md
│       ├── 0003-externalized-configuration-and-prompts.md
│       ├── 0004-database-and-vector-store-abstraction.md
│       └── 0005-api-versioning-and-router-modularization.md
│
├── .env.example
├── .gitignore
├── pyproject.toml
├── README.md
├── Makefile
└── docker-compose.yml
```

---

## Directory Descriptions

### `apps/backend/app/`
Contains the FastAPI backend application.
- `api/v1/`: Version 1 HTTP endpoints and router aggregation.
- `core/`: Application settings, logging configuration, custom domain exceptions, and FastAPI dependency providers.
- `agents/`: Independent implementations of specialized tutoring agents (`planner`, `teacher`, `quiz`, `evaluation`, `memory`, `recommendation`, `rag`), inheriting from `BaseAgent`.
- `graphs/`: LangGraph orchestration workflows, decoupled state definitions (`states/state.py`), and conditional routing logic (`routing/router.py`).
- `rag/`: Composable document ingestion, token-aware chunking, embeddings providers, vector store retrieval, and high-level RAG pipeline service.
- `llm/`: Unified `LLMClient` supporting OpenAI, Gemini, and offline `DemoLLMProvider`, alongside external YAML prompt loader.
- `services/`: Global service container providing singleton instances of repositories, database connections, and agents.
- `repositories/`: Database abstraction layer encapsulating all SQLAlchemy queries.
- `models/`: Declarative SQLAlchemy ORM database models.
- `schemas/`: Pydantic request/response schemas, DTOs, and enumeration definitions.
- `db/`: Database engine, connection lifecycle, and transaction scopes.
- `utils/`: Common utilities for asynchronous helpers, logging formatters, and sanitizers.

### `apps/backend/tests/`
Automated test suite for the backend application.
- `fixtures/`: Shared test fixtures, mock embeddings, and fake LLM implementations (`fakes.py`, `conftest.py`).
- `integration/`: Integration tests testing full API routers, LangGraph workflow execution, and RAG document ingestion.
- `unit/`: Unit tests testing isolated agent reasoning, token chunking, demo LLM behavior, repositories, and vector stores.

### `apps/frontend/`
Modular Streamlit user interface.
- `app.py`: Main dashboard entry point and multi-page routing.
- `pages/`: Individual view controllers for Chat, Quizzes, Analytics Dashboard, and Document Management.
- `components/`: Reusable Streamlit UI widgets (sidebar navigation, health indicators).
- `services/`: Typed HTTP client (`api_client.py`) connecting the frontend to the backend.
- `utils/`: Frontend session state initializers and guards.

### `packages/`
Shared and standalone tooling packages.
- `packages/shared/`: Shared cross-application models, type definitions, and common constants.
- `packages/evaluation/`: Benchmark suite measuring agent accuracy, hallucination, latency, quiz quality, and retrieval accuracy.
- `packages/experiments/`: Experimental research scripts exploring chunking boundaries and embeddings.

### `configs/`
Externalized configuration files.
- `agents/`: Agent configuration files (`agents.yaml`).
- `rag/`: RAG hyperparameter configuration (`rag.yaml`).
- `prompts/`: System and user prompt YAML files for each specialized agent.

### `data/`
File storage and persistence targets.
- `uploads/`: Raw user-uploaded PDF and text files.
- `processed/`: Ingested and chunked intermediate documents.
- `sample/`: Sample JSON payloads for testing and demonstration.
- `chroma/`: Local ChromaDB vector database directory.

### `scripts/`
Operational and development scripts.
- `setup/`: Environment bootstrap scripts (`setup_env.py`).
- `migration/`: Database initialization and schema management (`init_db.py`).
- `development/`: End-to-end subsystem verification scripts (`e2e_verify.py`, `make_sample_doc.py`).

### `docs/`
Complete project documentation.
- `architecture/`: Architecture audits and target specifications.
- `development/`: Local setup and testing guides.
- `decisions/`: Architectural Decision Records (ADRs).

