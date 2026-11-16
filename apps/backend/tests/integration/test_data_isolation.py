"""Multi-tenant data isolation and vector retrieval boundaries between distinct students."""

from __future__ import annotations


class TestMultiTenantDataIsolation:
    def test_cross_student_vector_isolation(self, client, auth_header, container):
        # Student A uploads Quantum Computing notes
        doc_a_content = (
            "Quantum entanglement is a phenomenon where quantum particles become inextricably linked. "
            "Qubits can exist in a superposition of zero and one states simultaneously."
        ) * 3
        upload_a = client.post(
            "/api/v1/documents/student_quantum",
            files={"file": ("quantum_notes.txt", doc_a_content.encode("utf-8"), "text/plain")},
            headers=auth_header("student_quantum"),
        )
        assert upload_a.status_code == 200
        doc_a_id = upload_a.json()["doc_id"]

        # Student B uploads Medieval History notes
        doc_b_content = (
            "The Magna Carta was signed in 1215 at Runnymede by King John of England. "
            "It established that everyone, even the king, was subject to the law."
        ) * 3
        upload_b = client.post(
            "/api/v1/documents/student_history",
            files={"file": ("history_notes.txt", doc_b_content.encode("utf-8"), "text/plain")},
            headers=auth_header("student_history"),
        )
        assert upload_b.status_code == 200
        assert upload_b.json()["doc_id"]

        # 1. Direct RAG Service Verification
        # Student A queries for 'Magna Carta' -> MUST NOT retrieve Student B's notes
        chunks_for_a = container.rag.search(
            "Magna Carta 1215 King John", student_id="student_quantum"
        )
        assert all("history" not in c.source for c in chunks_for_a), (
            "Student Quantum must never receive Student History's notes!"
        )

        # Student B queries for 'Qubits superposition' -> MUST NOT retrieve Student A's notes
        chunks_for_b = container.rag.search(
            "Qubits superposition entanglement", student_id="student_history"
        )
        assert all("quantum" not in c.source for c in chunks_for_b), (
            "Student History must never receive Student Quantum's notes!"
        )

        # 2. Student retrieves their own documents correctly
        own_a = container.rag.search("superposition qubits", student_id="student_quantum")
        assert len(own_a) >= 1
        assert "quantum_notes.txt" in own_a[0].source

        own_b = container.rag.search("Magna Carta 1215", student_id="student_history")
        assert len(own_b) >= 1
        assert "history_notes.txt" in own_b[0].source

        # 3. Document deletion removes vector embeddings
        del_resp = client.delete(
            f"/api/v1/documents/{doc_a_id}",
            headers=auth_header("student_quantum"),
        )
        assert del_resp.status_code == 200

        # After deletion, search for Student A returns nothing
        assert container.rag.search("superposition qubits", student_id="student_quantum") == []
        # But Student B's notes are unaffected
        assert len(container.rag.search("Magna Carta 1215", student_id="student_history")) >= 1
