"""Token-aware context assembly with strict section budgets and source traceability."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from app.core.config import ContextBudgetSettings
from app.schemas.domain import EpisodicMemory, RetrievedChunk

logger = logging.getLogger(__name__)

try:
    import tiktoken

    _TIKTOKEN_AVAILABLE = True
except ImportError:  # pragma: no cover
    tiktoken = None
    _TIKTOKEN_AVAILABLE = False


@dataclass
class AssembledContext:
    """Detailed result of context assembly with token accounting."""

    system_prompt: str
    user_message: str
    history_messages: list[dict[str, Any]] = field(default_factory=list)
    episodic_context: str = ""
    semantic_context: str = ""
    rag_context: str = ""
    assembled_prompt: str = ""
    token_counts: dict[str, int] = field(default_factory=dict)
    sources_included: list[str] = field(default_factory=list)
    truncated_sections: list[str] = field(default_factory=list)


class ContextBuilder:
    """Assembles prompt contexts respecting token allocations and preserving grounding."""

    def __init__(self, settings: ContextBudgetSettings) -> None:
        self.settings = settings
        self._encoder = None
        if _TIKTOKEN_AVAILABLE:
            try:
                self._encoder = tiktoken.get_encoding(settings.tokenizer_encoding)
            except Exception as exc:  # pragma: no cover
                logger.warning(
                    "Failed to load tokenizer %r: %s; using character estimation",
                    settings.tokenizer_encoding,
                    exc,
                )

    def count_tokens(self, text: str) -> int:
        """Count tokens using tiktoken if available, else approximate via character ratio."""
        if not text:
            return 0
        if self._encoder is not None:
            try:
                return len(self._encoder.encode(text))
            except Exception:  # pragma: no cover
                pass
        # Fallback ratio: ~4 characters per token
        return max(1, len(text) // 4)

    def truncate_to_tokens(self, text: str, max_tokens: int) -> tuple[str, bool]:
        """Truncate text to fit within max_tokens, returning (truncated_text, was_truncated)."""
        tokens = self.count_tokens(text)
        if tokens <= max_tokens:
            return text, False
        if max_tokens <= 0:
            return "", True

        if self._encoder is not None:
            try:
                encoded = self._encoder.encode(text)
                truncated_text = self._encoder.decode(encoded[:max_tokens])
                return truncated_text, True
            except Exception:  # pragma: no cover
                pass

        # Fallback char truncation
        char_limit = max_tokens * 4
        return text[:char_limit], True

    def build_context(
        self,
        *,
        system_prompt: str = "",
        user_message: str = "",
        history_messages: list[dict[str, Any]] | None = None,
        episodic_memories: list[EpisodicMemory] | None = None,
        semantic_profile: dict[str, Any] | None = None,
        rag_chunks: list[RetrievedChunk] | None = None,
    ) -> AssembledContext:
        """Assemble all prompt sections according to token budgets."""
        truncated_sections: list[str] = []
        sources_included: list[str] = []
        token_breakdown: dict[str, int] = {}

        # 1. System Prompt
        sys_text = system_prompt.strip()
        sys_tokens = self.count_tokens(sys_text)
        if sys_tokens > self.settings.system_prompt_budget:
            sys_text, _ = self.truncate_to_tokens(sys_text, self.settings.system_prompt_budget)
            truncated_sections.append("system_prompt")
            sys_tokens = self.count_tokens(sys_text)
        token_breakdown["system_prompt"] = sys_tokens

        # 2. User Message
        user_text = user_message.strip()
        token_breakdown["user_message"] = self.count_tokens(user_text)

        # 3. Working Memory (Recent Conversation History)
        # Assemble backwards from newest to oldest
        history_msgs = history_messages or []
        budget_hist = self.settings.history_budget
        included_history: list[dict[str, Any]] = []
        hist_tokens_used = 0

        for msg in reversed(history_msgs):
            content = msg.get("content", "")
            role = msg.get("role", "user")
            formatted = f"{role.capitalize()}: {content}"
            t_count = self.count_tokens(formatted)
            if hist_tokens_used + t_count <= budget_hist:
                included_history.insert(0, msg)
                hist_tokens_used += t_count
            else:
                truncated_sections.append("history")
                break

        token_breakdown["history"] = hist_tokens_used

        # 4. Episodic Memory (Cross-session narrative memories)
        episodic_text = ""
        episodic_tokens_used = 0
        if episodic_memories:
            episodic_lines = []
            budget_epi = self.settings.episodic_memory_budget
            for mem in episodic_memories:
                line = f"- [{mem.topic or 'Session'}]: {mem.summary}"
                t_count = self.count_tokens(line)
                if episodic_tokens_used + t_count <= budget_epi:
                    episodic_lines.append(line)
                    episodic_tokens_used += t_count
                    sources_included.append(f"episodic_memory:{mem.id}")
                else:
                    truncated_sections.append("episodic_memory")
                    break
            if episodic_lines:
                episodic_text = "Prior Learning Context:\n" + "\n".join(episodic_lines)
                if self.count_tokens(episodic_text) > self.settings.episodic_memory_budget:
                    episodic_text, _ = self.truncate_to_tokens(
                        episodic_text, self.settings.episodic_memory_budget
                    )
                episodic_tokens_used = self.count_tokens(episodic_text)

        token_breakdown["episodic_memory"] = episodic_tokens_used

        # 5. Semantic Profile (Student Level, Misconceptions, Weak/Strong concepts)
        semantic_text = ""
        semantic_tokens_used = 0
        if semantic_profile:
            sem_lines = []
            level = semantic_profile.get("level", "beginner")
            sem_lines.append(f"- Student Level: {level}")

            misconceptions = semantic_profile.get("active_misconceptions") or []
            if misconceptions:
                sem_lines.append("Active Misconceptions to Address:")
                for m in misconceptions:
                    sem_lines.append(f"  * {m.get('concept')}: {m.get('description')}")
                    sources_included.append(f"misconception:{m.get('concept')}")

            weak = semantic_profile.get("weak_concepts") or []
            if weak:
                sem_lines.append(f"- Areas Needing Reinforcement: {', '.join(weak[:5])}")

            formatted_sem = "Student Learning Profile:\n" + "\n".join(sem_lines)
            sem_t = self.count_tokens(formatted_sem)
            if sem_t > self.settings.semantic_profile_budget:
                formatted_sem, _ = self.truncate_to_tokens(
                    formatted_sem, self.settings.semantic_profile_budget
                )
                truncated_sections.append("semantic_profile")
                sem_t = self.count_tokens(formatted_sem)

            semantic_text = formatted_sem
            semantic_tokens_used = sem_t

        token_breakdown["semantic_profile"] = semantic_tokens_used

        # 6. RAG Grounding Context
        rag_text = ""
        rag_tokens_used = 0
        if rag_chunks:
            rag_lines = []
            budget_rag = self.settings.rag_budget
            for chunk in rag_chunks:
                source_label = f"{chunk.source}" + (f" (p.{chunk.page})" if chunk.page else "")
                block = f"--- Source: {source_label} ---\n{chunk.content}"
                t_count = self.count_tokens(block)
                if rag_tokens_used + t_count <= budget_rag:
                    rag_lines.append(block)
                    rag_tokens_used += t_count
                    sources_included.append(f"doc:{source_label}")
                elif not rag_lines:
                    # Truncate first chunk to fit available budget
                    remaining = budget_rag - rag_tokens_used
                    if remaining > 10:
                        truncated_block, _ = self.truncate_to_tokens(block, remaining)
                        rag_lines.append(truncated_block)
                        rag_tokens_used += self.count_tokens(truncated_block)
                        sources_included.append(f"doc:{source_label}")
                        truncated_sections.append("rag")
                    break
                else:
                    truncated_sections.append("rag")
                    break
            if rag_lines:
                rag_text = "Grounding Course Material:\n" + "\n\n".join(rag_lines)
                if self.count_tokens(rag_text) > self.settings.rag_budget:
                    rag_text, _ = self.truncate_to_tokens(rag_text, self.settings.rag_budget)
                rag_tokens_used = self.count_tokens(rag_text)

        token_breakdown["rag"] = rag_tokens_used

        # 7. Final Assembled Prompt Formulation
        prompt_sections = []
        if semantic_text:
            prompt_sections.append(semantic_text)
        if episodic_text:
            prompt_sections.append(episodic_text)
        if rag_text:
            prompt_sections.append(rag_text)

        if included_history:
            hist_formatted = "\n".join(
                f"{m.get('role', 'user').capitalize()}: {m.get('content', '')}"
                for m in included_history
            )
            prompt_sections.append(f"Recent Conversation:\n{hist_formatted}")

        prompt_sections.append(f"Student: {user_text}")

        assembled = "\n\n".join(s for s in prompt_sections if s)
        total_tokens = sys_tokens + self.count_tokens(assembled)
        token_breakdown["total"] = total_tokens

        return AssembledContext(
            system_prompt=sys_text,
            user_message=user_text,
            history_messages=included_history,
            episodic_context=episodic_text,
            semantic_context=semantic_text,
            rag_context=rag_text,
            assembled_prompt=assembled,
            token_counts=token_breakdown,
            sources_included=sources_included,
            truncated_sections=list(dict.fromkeys(truncated_sections)),
        )
