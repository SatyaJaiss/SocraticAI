# ADR 0002: Decoupled LangGraph State and Routing

## Status
Accepted

## Context
In the baseline implementation, the LangGraph workflows (`graphs/workflow.py`) directly imported agent nodes, while agent nodes imported the global state and agent context, and some agents referenced workflows. Furthermore, `models/state.py` conflated Pydantic models with LangGraph state types. When reorganizing into package submodules, eager imports of `app.graphs` triggered circular import errors (`ImportError: cannot import name 'EduAgentState' from partially initialized module 'app.graphs'`).

## Decision
1. **Isolated State Definitions:** State representations are strictly isolated into `apps/backend/app/graphs/states/state.py`.
2. **Dedicated Routing Logic:** Conditional edges, branch decisions, and route determination logic are isolated into `apps/backend/app/graphs/routing/router.py`.
3. **Workflow Implementations:** Workflows are separated by domain into `apps/backend/app/graphs/tutoring/workflow.py` and `apps/backend/app/graphs/evaluation/workflow.py`.
4. **Lazy Graph Factory Loading:** In `apps/backend/app/graphs/__init__.py`, graph instances (`tutoring_workflow`, `eval_workflow`) are compiled via lazy accessors or factory functions, preventing module-level circular references during agent initialization.

## Consequences
### Positive
- Completely eliminates circular dependency loops between agents, state, and graph definitions.
- Allows agent implementations to depend solely on state definitions (`app.graphs.states`) without pulling in the entire workflow compiler.
- Enables individual agent nodes and routing conditional functions to be tested in isolation.

### Negative / Trade-offs
- Slight indirection in workflow building (e.g., calling `get_tutoring_graph()` or building upon demand).

