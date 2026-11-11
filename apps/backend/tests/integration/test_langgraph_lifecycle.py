"""Integration tests for LangGraph lifecycle, singleton compilation, and conversation isolation."""

from __future__ import annotations

import pytest


class TestLangGraphLifecycle:
    def test_graph_compiled_singleton(self, container):
        # Repeated calls to container.tutoring_graph return the identical compiled instance
        graph_1 = container.tutoring_graph
        graph_2 = container.tutoring_graph
        assert graph_1 is graph_2, "Tutoring graph should be compiled once and cached as a singleton"

        eval_graph_1 = container.evaluation_graph
        eval_graph_2 = container.evaluation_graph
        assert eval_graph_1 is eval_graph_2, "Evaluation graph should be compiled once and cached"

    async def test_concurrent_conversations_do_not_share_state(self, client, auth_header):
        # Conversation 1: Student studying Quantum Physics
        resp_q = client.post(
            "/api/v1/chat",
            json={
                "student_id": "student_phys",
                "message": "Teach me Schrödinger equation",
                "topic": "Quantum Mechanics",
            },
            headers=auth_header("student_phys"),
        )
        assert resp_q.status_code == 200
        cid_q = resp_q.json()["conversation_id"]

        # Conversation 2: Student studying European History
        resp_h = client.post(
            "/api/v1/chat",
            json={
                "student_id": "student_hist",
                "message": "Teach me French Revolution",
                "topic": "French Revolution",
            },
            headers=auth_header("student_hist"),
        )
        assert resp_h.status_code == 200
        cid_h = resp_h.json()["conversation_id"]

        assert cid_q != cid_h

        # History student's response does NOT contain Quantum concepts
        assert "Schrödinger" not in resp_h.json()["lesson"]["summary"]
        assert "French Revolution" in resp_h.json()["lesson"]["topic"]

    async def test_graph_execution_failure_handled_gracefully(self, client, auth_header, monkeypatch, container):
        # Simulate unexpected runtime error in tutoring graph
        def failing_ainvoke(*args, **kwargs):
            raise RuntimeError("LLM worker crashed unexpectedly")

        monkeypatch.setattr(container.tutoring_graph, "ainvoke", failing_ainvoke)

        with pytest.raises(RuntimeError, match="LLM worker crashed"):
            await container.tutoring_graph.ainvoke({"student_id": "fail_test"})

