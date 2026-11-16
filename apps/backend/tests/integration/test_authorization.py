"""Integration tests for authorization boundaries (preventing IDOR and privilege escalation)."""

from __future__ import annotations

from app.schemas.domain import Quiz, QuizQuestion
from app.schemas.enums import DifficultyLevel, QuestionType


class TestAuthorizationBoundaries:
    def test_student_a_cannot_read_student_b_profile(self, client, auth_header):
        # Authenticated as student_a, attempting to access student_b's profile
        resp = client.get(
            "/api/v1/students/student_b",
            headers=auth_header("student_a"),
        )
        assert resp.status_code == 403
        assert resp.json()["error"] == "AUTHORIZATION_ERROR"
        assert "Access denied" in resp.json()["message"]

    def test_student_a_cannot_update_student_b_profile(self, client, auth_header):
        resp = client.put(
            "/api/v1/students/student_b",
            json={"name": "Hacked Name"},
            headers=auth_header("student_a"),
        )
        assert resp.status_code == 403
        assert resp.json()["error"] == "AUTHORIZATION_ERROR"

    def test_student_a_cannot_view_student_b_dashboard(self, client, auth_header):
        resp = client.get(
            "/api/v1/dashboard/student_b",
            headers=auth_header("student_a"),
        )
        assert resp.status_code == 403
        assert resp.json()["error"] == "AUTHORIZATION_ERROR"

    def test_student_a_cannot_list_student_b_quizzes(self, client, auth_header):
        resp = client.get(
            "/api/v1/quizzes/student_b",
            headers=auth_header("student_a"),
        )
        assert resp.status_code == 403
        assert resp.json()["error"] == "AUTHORIZATION_ERROR"

    def test_student_a_cannot_view_student_b_quiz_by_id(self, client, auth_header, container):
        # Create a quiz owned by student_b
        quiz = Quiz(
            id="quiz_b_private",
            topic="Calculus",
            difficulty=DifficultyLevel.INTERMEDIATE,
            questions=[
                QuizQuestion(
                    id="q1",
                    type=QuestionType.MCQ,
                    topic="Calculus",
                    question="d/dx(x^2) = ?",
                    options=["2x", "x^2", "x"],
                    correct_answer="2x",
                )
            ],
        )
        container.student_repo.get_or_create("student_b")
        container.quiz_repo.create_quiz(quiz, "student_b")

        # Student A attempts to read it
        resp = client.get(
            f"/api/v1/quiz/{quiz.id}",
            headers=auth_header("student_a"),
        )
        assert resp.status_code == 403
        assert resp.json()["error"] == "AUTHORIZATION_ERROR"

    def test_student_a_cannot_submit_quiz_as_student_b(self, client, auth_header, container):
        quiz = Quiz(
            id="quiz_b_submit",
            topic="Algebra",
            difficulty=DifficultyLevel.BEGINNER,
            questions=[
                QuizQuestion(
                    id="q1",
                    type=QuestionType.NUMERICAL,
                    topic="Algebra",
                    question="2+2=?",
                    options=[],
                    correct_answer="4",
                )
            ],
        )
        container.student_repo.get_or_create("student_b")
        container.quiz_repo.create_quiz(quiz, "student_b")

        resp = client.post(
            "/api/v1/chat/submit-quiz",
            json={
                "quiz_id": quiz.id,
                "student_id": "student_b",  # Pretending to be student_b
                "answers": [{"question_id": f"{quiz.id}q1", "answer": "4"}],
            },
            headers=auth_header("student_a"),  # Authenticated as student_a
        )
        assert resp.status_code == 403
        assert resp.json()["error"] == "AUTHORIZATION_ERROR"

    def test_student_a_cannot_upload_document_for_student_b(self, client, auth_header):
        resp = client.post(
            "/api/v1/documents/student_b",
            files={"file": ("notes.txt", b"Student B notes", "text/plain")},
            headers=auth_header("student_a"),
        )
        assert resp.status_code == 403
        assert resp.json()["error"] == "AUTHORIZATION_ERROR"

    def test_student_a_cannot_list_student_b_documents(self, client, auth_header):
        resp = client.get(
            "/api/v1/documents/student_b",
            headers=auth_header("student_a"),
        )
        assert resp.status_code == 403
        assert resp.json()["error"] == "AUTHORIZATION_ERROR"

    def test_student_a_cannot_delete_student_b_document(self, client, auth_header):
        # 1. Student B uploads a document
        upload = client.post(
            "/api/v1/documents/student_b",
            files={"file": ("confidential.txt", b"Student B Secret Notes", "text/plain")},
            headers=auth_header("student_b"),
        )
        assert upload.status_code == 200
        doc_id = upload.json()["doc_id"]

        # 2. Student A tries to delete it
        resp = client.delete(
            f"/api/v1/documents/{doc_id}",
            headers=auth_header("student_a"),
        )
        assert resp.status_code == 403
        assert resp.json()["error"] == "AUTHORIZATION_ERROR"

    def test_student_a_cannot_impersonate_student_b_in_chat(self, client, auth_header):
        resp = client.post(
            "/api/v1/chat",
            json={
                "student_id": "student_b",
                "message": "Teach me something secret",
            },
            headers=auth_header("student_a"),
        )
        assert resp.status_code == 403
        assert resp.json()["error"] == "AUTHORIZATION_ERROR"
