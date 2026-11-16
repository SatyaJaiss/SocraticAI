"""Unit tests for QueryProcessor and multi-part question decomposition."""

from __future__ import annotations

import pytest
from app.core.config import QueryRewritingSettings
from app.rag.retrieval.query_processor import QueryProcessor


class TestQueryProcessor:
    @pytest.fixture
    def processor(self):
        settings = QueryRewritingSettings(enabled=True, max_subqueries=3)
        return QueryProcessor(settings)

    def test_simple_question_not_decomposed(self, processor):
        plan = processor.process("What is backpropagation?")
        assert plan.is_compound is False
        assert len(plan.subqueries) == 1
        assert "backpropagation" in plan.cleaned_retrieval_query

    def test_comparative_question_decomposed(self, processor):
        query = "Explain the difference between CNN and RNN and when should I use each?"
        plan = processor.process(query)
        assert plan.is_compound is True
        assert len(plan.subqueries) >= 2
        assert any("CNN" in sq for sq in plan.subqueries)
        assert any("RNN" in sq for sq in plan.subqueries)

    def test_conversational_prefix_stripped(self, processor):
        query = "Can you please explain according to my uploaded notes what is entropy?"
        plan = processor.process(query)
        assert "can you please explain" not in plan.cleaned_retrieval_query.lower()
        assert "uploaded notes" not in plan.cleaned_retrieval_query.lower()
        assert "entropy" in plan.cleaned_retrieval_query.lower()
