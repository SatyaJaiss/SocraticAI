"""Query analysis, decomposition, and retrieval-oriented preprocessing.

Design rationale
----------------
* Simple direct questions (e.g. "What is backpropagation?") require zero decomposition.
* Compound, comparative, or multi-topic questions (e.g. "Compare CNN and RNN and when
  to use each") dilute embedding vectors if searched as a single string.
* Deterministic rule-based decomposition splits multi-part questions into targeted
  subqueries without adding LLM latency or token overhead.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import ClassVar

from app.core.config import QueryRewritingSettings

logger = logging.getLogger(__name__)


@dataclass
class QueryPlan:
    """Analysis and decomposition of a student's search query."""

    original_query: str
    is_compound: bool
    subqueries: list[str] = field(default_factory=list)
    cleaned_retrieval_query: str = ""


class QueryProcessor:
    """Preprocesses user queries for retrieval, decomposing multi-part questions."""

    # Phrasing to strip from retrieval queries (keeps the core subject clear)
    CONVERSATIONAL_PREFIXES: ClassVar[list[re.Pattern]] = [
        re.compile(
            r"^(?:can you\s+)?(?:please\s+)?(?:tell me|explain)(?:\s+to me)?(?:\s+(?:about|what\s+is|how))?[,\s]*",
            re.IGNORECASE,
        ),
        re.compile(
            r"^(?:according to\s+(?:the\s+|my\s+|our\s+)?(?:uploaded\s+)?(?:notes|pdf|document|textbook)[,\s]*)",
            re.IGNORECASE,
        ),
        re.compile(
            r"^(?:what\s+does\s+(?:the\s+|my\s+)?(?:textbook|pdf|notes)\s+say\s+about\s+)",
            re.IGNORECASE,
        ),
        re.compile(
            r"^(?:what\s+is\s+|what\s+are\s+|how\s+does\s+|how\s+do\s+)",
            re.IGNORECASE,
        ),
        re.compile(
            r"^(?:tell me\s+(?:about\s+)?|i\s+want\s+to\s+know\s+about\s+)",
            re.IGNORECASE,
        ),
    ]

    # Comparative / Multi-part patterns
    COMPARISON_PATTERN = re.compile(
        r"(?:difference between|compare|contrast|versus|\bvs\b)\s+([A-Za-z0-9_\-\s]+?)\s+(?:and|with|to|\bvs\b)\s+([A-Za-z0-9_\-\s\?]+)",
        re.IGNORECASE,
    )
    MULTI_PART_SPLIT = re.compile(
        r"\s+(?:and also|as well as|and when should i use each|and which one is better)\b",
        re.IGNORECASE,
    )

    def __init__(self, settings: QueryRewritingSettings) -> None:
        self.settings = settings

    def clean_query(self, query: str) -> str:
        """Strip conversational wrappers to isolate the semantic topic."""
        cleaned = query.strip()
        changed = True
        iterations = 0
        while changed and iterations < 5:
            changed = False
            iterations += 1
            for pat in self.CONVERSATIONAL_PREFIXES:
                new_cleaned = pat.sub("", cleaned).strip()
                if new_cleaned != cleaned:
                    cleaned = new_cleaned
                    changed = True
        cleaned = re.sub(r"[\?\.\!]+$", "", cleaned).strip()
        return cleaned or query.strip()

    def is_simple_query(self, query: str) -> bool:
        """Check whether the query is a simple single-topic question."""
        words = query.strip().split()
        if len(words) <= 5 and not any(
            k in query.lower() for k in ["difference", "compare", "vs", "versus", "between"]
        ):
            return True
        return False

    def process(self, query: str) -> QueryPlan:
        """Analyze query and return a QueryPlan with primary and optional subqueries."""
        q = query.strip()
        if not self.settings.enabled or not q:
            return QueryPlan(
                original_query=q,
                is_compound=False,
                subqueries=[q] if q else [],
                cleaned_retrieval_query=q,
            )

        cleaned = self.clean_query(q)

        # 1. Simple queries -> no decomposition needed
        if self.is_simple_query(q):
            return QueryPlan(
                original_query=q,
                is_compound=False,
                subqueries=[cleaned],
                cleaned_retrieval_query=cleaned,
            )

        # 2. Check for comparative questions: "difference between X and Y"
        comp_match = self.COMPARISON_PATTERN.search(cleaned)
        if comp_match:
            entity_a = comp_match.group(1).strip()
            entity_b = comp_match.group(2).strip()
            # Clean entity names
            entity_b = self.MULTI_PART_SPLIT.split(entity_b)[0].strip()

            subqueries = [
                f"{entity_a} definition and properties",
                f"{entity_b} definition and properties",
                f"{entity_a} versus {entity_b} comparison",
            ]
            return QueryPlan(
                original_query=q,
                is_compound=True,
                subqueries=subqueries[: self.settings.max_subqueries],
                cleaned_retrieval_query=cleaned,
            )

        # 3. Standard queries
        return QueryPlan(
            original_query=q,
            is_compound=False,
            subqueries=[cleaned],
            cleaned_retrieval_query=cleaned,
        )
