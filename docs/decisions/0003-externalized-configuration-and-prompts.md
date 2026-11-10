# ADR 0003: Externalized Configuration and Prompts

## Status
Accepted

## Context
Prompts in the original architecture were stored in a root-level `prompts/` directory, loaded via `prompts/loader.py`, while agent configs were scattered between settings and hardcoded defaults in node logic. In addition, when restructuring the codebase, the relative path resolution `Path(__file__).resolve().parent` within `app.llm.prompts.loader` would have looked inside `apps/backend/app/llm/prompts/` rather than the centralized `configs/prompts/` location.

## Decision
1. **Central Config Directory:** Moved all YAML prompt templates (`planner.yaml`, `teacher.yaml`, `quiz.yaml`, `evaluation.yaml`, `memory.yaml`, `recommendation.yaml`) to `configs/prompts/`.
2. **Additional Configuration Files:** Introduced `configs/agents/agents.yaml` and `configs/rag/rag.yaml` to specify default agent parameters, chunking sizes, and vector retrieval thresholds without requiring code edits.
3. **Multi-Location Prompt Resolution:** Updated `app.llm.prompts.loader.PromptLoader` to search multiple candidate paths:
   - Root `configs/prompts/`
   - Config-relative `prompts/`
   - Packaged fallback directory
4. **Pydantic Settings Isolation:** Centralized application and database settings into `apps/backend/app/core/config.py` using `pydantic-settings`, reading environment variables with graceful defaults.

## Consequences
### Positive
- Prompt engineers and domain specialists can refine prompts in `configs/prompts/` without touching Python source code.
- Works consistently whether run locally via `uvicorn`, via test harnesses (`pytest`), or inside containerized Docker environments.
- Protects API keys and sensitive settings by ensuring no credentials or secrets are committed.

### Negative / Trade-offs
- File I/O required on prompt loading, mitigated by in-memory LRU caching in `PromptLoader`.

