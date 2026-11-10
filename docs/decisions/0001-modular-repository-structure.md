# ADR 0001: Modular Repository Structure

## Status
Accepted

## Context
The original EduAgent repository organized all backend code, frontend scripts, prompts, tests, and configuration at the root directory level. As the project expands to support multi-agent orchestration, diverse LLM providers, and sophisticated RAG pipelines, this monolithic layout posed several issues:
1. Tight coupling between the Streamlit UI and FastAPI backend models/services.
2. Root-level clutter with multiple competing responsibilities.
3. Difficulties in packaging, containerization, and independent testing of backend vs. frontend components.
4. Risk of accidental circular dependencies between services, agents, and API routers.

## Decision
We restructured the repository into a modular, multi-package layout following standard production Python patterns:

- `apps/backend/`: Encapsulates all backend source code under `app/` and test suites under `tests/`.
- `apps/frontend/`: Encapsulates the Streamlit presentation tier, modularized into reusable components, pages, state management, and an HTTP API client.
- `packages/`: Contains reusable libraries (`shared`, `evaluation`, `experiments`) isolated from core backend runtime.
- `configs/`: Externalizes prompt templates, agent hyperparameters, and RAG configuration.
- `data/`: Designates explicit subdirectories for user uploads (`uploads/`), processed artifacts (`processed/`), and sample payloads (`sample/`).
- `scripts/`: Isolates automation scripts by purpose (`setup/`, `migration/`, `development/`).
- `docs/`: Centralizes architectural documentation, development guides, and architecture decision records.

## Consequences
### Positive
- Strict separation of concerns between API/agents and user interface.
- Independent deployability of backend and frontend containers.
- Clean import namespaces (`from app.agents...`, `from app.core...`).
- Clear guidelines for where new capabilities and tests should reside.

### Negative / Trade-offs
- Requires updating legacy import paths across tests and scripts.
- Shim forwarders retained at project root (`main.py`, `pytest.ini`) to maintain backward compatibility during the transition.

