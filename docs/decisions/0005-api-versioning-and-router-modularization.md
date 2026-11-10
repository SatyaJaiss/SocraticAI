# ADR 0005: API Versioning and Router Modularization

## Status
Accepted

## Context
The initial implementation housed API endpoints in `api/routers/` mounted directly under `/api/v1` via string concatenation in `api/main.py`. Mixing exception handlers, dependency injections, and routers in a flat directory made API versioning and endpoint isolation challenging as new endpoints or agent services are added.

## Decision
1. **Versioned Route Hierarchy:** Placed all v1 endpoints under `apps/backend/app/api/v1/routes/`:
   - `health.py`: Liveness, readiness, and runtime metadata checks.
   - `students.py`: Student registration and profile management.
   - `chat.py`: Interactive tutoring chat and agent dispatch.
   - `quizzes.py`: Quiz generation, submission, and grading.
   - `documents.py`: Document upload, RAG ingestion, and retrieval test endpoints.
   - `dashboard.py`: Analytics and student progress metrics.
2. **Aggregated API Router:** Assembled all v1 route modules in `apps/backend/app/api/v1/router.py` using `APIRouter(prefix="/api/v1")`.
3. **Core Dependency Injection:** Fast-API dependency providers (`get_db_session`, `get_container_dep`) were placed in `apps/backend/app/core/dependencies.py` to decouple routing from service construction.
4. **Custom Exceptions & Handlers:** Unified exception classes in `apps/backend/app/core/exceptions.py` with registered handlers mapping domain errors to appropriate HTTP status codes (e.g. 404 for `ResourceNotFoundError`, 422 for `ValidationError`).

## Consequences
### Positive
- Clear path for future API revisions (e.g., adding `api/v2/` alongside `api/v1/` without touching existing clients).
- Routes have clean, single responsibilities.
- Testing is simplified with dependency override capabilities in FastAPI.

### Negative / Trade-offs
- Endpoint consumers must target the versioned prefix `/api/v1`, which is now standard across frontend and integration tests.

