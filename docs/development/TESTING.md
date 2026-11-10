# SocraticAI — Testing and Quality Assurance Guide

This document describes the testing strategy, test structure, benchmark suites, and commands for SocraticAI.

---

## 1. Test Architecture

The backend test suite is located in `apps/backend/tests/` and structured into three distinct directories:

```text
apps/backend/tests/
├── fixtures/
│   ├── conftest.py       # Global fixtures (test DB session, test container, settings)
│   └── fakes.py          # Deterministic in-memory fakes (FakeEmbedder, FakeLLMClient, etc.)
│
├── unit/
│   ├── test_agents.py        # Isolated agent logic, reasoning nodes, and fallbacks
│   ├── test_chunking.py      # Token-aware sliding window splitting and text sanitization
│   ├── test_llm_demo.py      # Offline DemoLLMProvider responses, intent parsing, quiz JSON
│   ├── test_repositories.py  # SQLite repository CRUD, session rollback, integrity checks
│   └── test_vector_store.py  # ChromaDB collection creation, similarity search, filtering
│
└── integration/
    ├── test_api.py           # FastAPI v1 endpoints (chat, quiz, students, dashboard, health)
    ├── test_documents_api.py # File upload, document ingestion, and retrieval endpoints
    ├── test_graphs.py        # LangGraph tutoring and evaluation workflow compilation & execution
    └── test_rag.py           # End-to-end RAG pipeline from PDF ingestion to context retrieval
```

---

## 2. Running Automated Tests

All tests can be executed via `pytest` or through `Makefile` shortcuts.

### 2.1 Complete Test Suite

Run the full suite of unit and integration tests:

```bash
# Using Makefile
make test

# Or using pytest with uv
uv run pytest
```

### 2.2 Running by Category

- **Unit tests only**:
  ```bash
  make test-unit
  # Or:
  uv run pytest apps/backend/tests/unit
  ```

- **Integration tests only**:
  ```bash
  make test-integration
  # Or:
  uv run pytest apps/backend/tests/integration
  ```

- **Specific test module**:
  ```bash
  uv run pytest apps/backend/tests/unit/test_agents.py -k "test_planner"
  ```

### 2.3 Test Coverage Reporting

To calculate test coverage:

```bash
make test-cov
# Or:
uv run pytest --cov=apps/backend/app --cov-report=term-missing
```

---

## 3. Linting and Code Quality

SocraticAI uses [Ruff](https://docs.astral.sh/ruff/) for high-performance linting and formatting.

- **Check for lint violations**:
  ```bash
  make lint
  # Or:
  uv run ruff check apps/backend/app apps/frontend apps/backend/tests
  ```

- **Auto-format code**:
  ```bash
  make format
  # Or:
  uv run ruff format apps/backend/app apps/frontend apps/backend/tests
  ```

---

## 4. Test Isolation and Mocking Principles

1. **In-Memory SQLite Database**: Tests use an isolated in-memory or ephemeral SQLite database created per test session, ensuring no leftover artifacts contaminate the main database.
2. **Deterministic Fakes**:
   - `FakeEmbedder`: Generates deterministic float vectors based on character trigrams, bypassing GPU requirements and heavy neural network downloads during tests.
   - `DemoLLMProvider`: Produces structured JSON output matching real LLM schemas for intent recognition, pedagogical answers, and quiz questions.
3. **Dependency Injection Overrides**: The FastAPI test client uses `app.dependency_overrides` configured in `conftest.py` to inject test database sessions and mock containers seamlessly.

---

## 5. Evaluation Benchmarks (`packages/evaluation/`)

The evaluation package contains benchmarks assessing agent performance across multiple dimensions:

- `benchmark_accuracy.py`: Pedagogical answer correctness.
- `benchmark_hallucination.py`: Groundedness against retrieved RAG context.
- `benchmark_latency.py`: End-to-end response timing breakdown across nodes.
- `benchmark_memory.py`: Fact extraction precision and recall across sessions.
- `benchmark_quiz.py`: Question validity, distractor quality, and rubric grading accuracy.
- `benchmark_rag.py`: Retrieval precision and recall on synthetic corpora.

To run all evaluation benchmarks:
```bash
uv run python packages/evaluation/run_all.py
```
*Results and metric summaries are generated under `packages/evaluation/results/`.*

---

## 6. RAG Experiments (`packages/experiments/`)

To compare chunking strategies (fixed-size vs. sentence-aware vs. token-sliding):

```bash
uv run python packages/experiments/run_experiments.py
```
*Generated reports and plots are saved to `packages/experiments/results/`.*

