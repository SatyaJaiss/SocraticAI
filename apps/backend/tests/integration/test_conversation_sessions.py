"""Integration tests for conversation session management, history persistence, and multi-turn continuity."""

from __future__ import annotations


class TestConversationSessions:
    def test_create_and_list_sessions(self, client, auth_header):
        # Create two distinct sessions for student_alpha
        s1 = client.post(
            "/api/v1/conversations",
            json={"title": "Physics Mechanics"},
            headers=auth_header("student_alpha"),
        )
        assert s1.status_code == 201
        session_1_id = s1.json()["id"]
        assert s1.json()["title"] == "Physics Mechanics"

        s2 = client.post(
            "/api/v1/conversations",
            json={"title": "Organic Chemistry"},
            headers=auth_header("student_alpha"),
        )
        assert s2.status_code == 201
        session_2_id = s2.json()["id"]

        # List sessions
        list_resp = client.get(
            "/api/v1/conversations",
            headers=auth_header("student_alpha"),
        )
        assert list_resp.status_code == 200
        sessions = list_resp.json()
        ids = [s["id"] for s in sessions]
        assert session_1_id in ids
        assert session_2_id in ids

    async def test_multi_turn_conversation_continuity(self, client, auth_header, container):
        # 1. Turn 1: Start a new conversation on Thermodynamics
        resp1 = client.post(
            "/api/v1/chat",
            json={
                "student_id": "student_multi",
                "message": "Explain the First Law of Thermodynamics",
                "topic": "Thermodynamics",
            },
            headers=auth_header("student_multi"),
        )
        assert resp1.status_code == 200
        data1 = resp1.json()
        cid = data1["conversation_id"]
        assert cid, "A valid conversation_id should be returned"

        # Check that messages were persisted in this session
        msg_resp1 = client.get(
            f"/api/v1/conversations/{cid}/messages",
            headers=auth_header("student_multi"),
        )
        assert msg_resp1.status_code == 200
        messages_turn_1 = msg_resp1.json()
        assert len(messages_turn_1) >= 2  # user + assistant

        # 2. Turn 2: Continue the SAME conversation with conversation_id
        resp2 = client.post(
            "/api/v1/chat",
            json={
                "student_id": "student_multi",
                "conversation_id": cid,
                "message": "Can you give me a real-world example of that?",
                "topic": "Thermodynamics",
            },
            headers=auth_header("student_multi"),
        )
        assert resp2.status_code == 200
        data2 = resp2.json()
        assert data2["conversation_id"] == cid

        # Verify that messages now reflect both turns in chronological order
        msg_resp2 = client.get(
            f"/api/v1/conversations/{cid}/messages",
            headers=auth_header("student_multi"),
        )
        assert msg_resp2.status_code == 200
        messages_turn_2 = msg_resp2.json()
        assert len(messages_turn_2) > len(messages_turn_1)
        # Check roles alternate or match user/assistant
        assert messages_turn_2[0]["role"] == "user"
        assert messages_turn_2[1]["role"] == "assistant"

    def test_conversation_isolation_between_students(self, client, auth_header):
        # Student A creates a session
        create_resp = client.post(
            "/api/v1/conversations",
            json={"title": "Private Math Session"},
            headers=auth_header("student_alice"),
        )
        alice_cid = create_resp.json()["id"]

        # Student B tries to read Alice's messages
        read_resp = client.get(
            f"/api/v1/conversations/{alice_cid}/messages",
            headers=auth_header("student_bob"),
        )
        assert read_resp.status_code == 403
        assert read_resp.json()["error"] == "AUTHORIZATION_ERROR"

        # Student B tries to delete Alice's session
        del_resp = client.delete(
            f"/api/v1/conversations/{alice_cid}",
            headers=auth_header("student_bob"),
        )
        assert del_resp.status_code == 403
        assert del_resp.json()["error"] == "AUTHORIZATION_ERROR"

    def test_delete_own_conversation(self, client, auth_header):
        create_resp = client.post(
            "/api/v1/conversations",
            json={"title": "Session to be deleted"},
            headers=auth_header("student_deleter"),
        )
        cid = create_resp.json()["id"]

        del_resp = client.delete(
            f"/api/v1/conversations/{cid}",
            headers=auth_header("student_deleter"),
        )
        assert del_resp.status_code == 200
        assert del_resp.json()["status"] == "deleted"

        # Reading deleted conversation returns 404
        read_resp = client.get(
            f"/api/v1/conversations/{cid}/messages",
            headers=auth_header("student_deleter"),
        )
        assert read_resp.status_code == 404
