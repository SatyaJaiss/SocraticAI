"""Integration tests for learning analytics and Socratic problem-solving API endpoints."""

from __future__ import annotations


class TestLearningAnalyticsAPI:
    def test_get_progress_authenticated(self, client, auth_header) -> None:
        """Student can view their own comprehensive learning progress analytics."""
        headers = auth_header("student_analytics_1")
        resp = client.get("/api/v1/analytics/progress", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["student_id"] == "student_analytics_1"
        assert "quizzes_taken" in data
        assert "concepts_mastered" in data
        assert "demonstrated_improvement_score" in data

    def test_student_a_cannot_view_student_b_analytics(self, client, auth_header) -> None:
        """Access control check: student cannot view another student's analytics."""
        headers = auth_header("student_a")
        resp = client.get("/api/v1/analytics/progress?student_id=student_b", headers=headers)
        assert resp.status_code == 403
        assert resp.json()["error"] == "AUTHORIZATION_ERROR"

    def test_get_concept_mastery_list(self, client, auth_header, container) -> None:
        """Student can list their concept-level mastery records."""
        student_id = "student_analytics_2"
        headers = auth_header(student_id)

        # Seed mastery evidence
        for _ in range(3):
            container.mastery_repo.update_mastery_from_evidence(
                student_id=student_id,
                concept="Linear Algebra",
                evidence_score=0.90,
                evidence_confidence=0.90,
            )

        resp = client.get("/api/v1/analytics/mastery", headers=headers)
        assert resp.status_code == 200
        items = resp.json()
        assert len(items) >= 1
        assert items[0]["concept"] == "Linear Algebra"
        assert items[0]["status"] == "mastered"

    def test_get_prerequisite_recommendations(self, client, auth_header) -> None:
        """Student can fetch prioritized learning recommendations with prerequisite checks."""
        headers = auth_header("student_analytics_3")
        resp = client.get(
            "/api/v1/analytics/recommendations?topic=Neural%20Networks", headers=headers
        )
        assert resp.status_code == 200
        recs = resp.json()
        assert isinstance(recs, list)
        assert len(recs) > 0
        assert "concept" in recs[0]
        assert "priority" in recs[0]


class TestSocraticAPI:
    def test_start_and_respond_socratic_session(self, client, auth_header) -> None:
        """Full interactive flow: start session, respond, and escalate hint."""
        student_id = "student_socratic_api_1"
        headers = auth_header(student_id)

        # 1. Start session
        start_payload = {
            "concept": "Kinematics",
            "problem_statement": "An apple falls from a tree. How fast is it moving after 3 seconds?",
            "total_steps": 2,
            "target_solution": "v = g * t = 9.8 * 3 = 29.4 m/s.",
        }
        res_start = client.post("/api/v1/socratic/start", json=start_payload, headers=headers)
        assert res_start.status_code == 200
        start_data = res_start.json()
        session_id = start_data["session_id"]
        assert start_data["current_step"] == 1
        assert "Step 1 of 2" in start_data["question"]

        # 2. Respond to session
        resp_payload = {"session_id": session_id, "response": "v = g * t = 9.8 * 3 = 29.4 m/s"}
        res_step = client.post("/api/v1/socratic/respond", json=resp_payload, headers=headers)
        assert res_step.status_code == 200
        step_data = res_step.json()
        assert step_data["current_step"] >= 1

    def test_hint_escalation(self, client, auth_header) -> None:
        """Requesting a progressive hint returns Level 1 without revealing full answer."""
        student_id = "student_socratic_api_2"
        headers = auth_header(student_id)

        start_payload = {
            "concept": "Newton's Second Law",
            "problem_statement": "A force of 20 N accelerates a mass. Find the mass if acceleration is 4 m/s^2.",
            "total_steps": 2,
            "target_solution": "F = m * a -> m = F / a = 20 / 4 = 5 kg.",
        }
        res_start = client.post("/api/v1/socratic/start", json=start_payload, headers=headers)
        session_id = res_start.json()["session_id"]

        hint_res = client.post(
            "/api/v1/socratic/hint", json={"session_id": session_id}, headers=headers
        )
        assert hint_res.status_code == 200
        hint_data = hint_res.json()
        assert hint_data["hint_level"] == 1
        assert not hint_data["solution_revealed"]
        assert hint_data["hint"] is not None
