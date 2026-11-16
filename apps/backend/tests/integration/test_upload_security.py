"""Integration tests for document upload security, size ceilings, and content validation."""

from __future__ import annotations


class TestUploadSecurity:
    def test_valid_pdf_magic_bytes_accepted(self, client, auth_header):
        # Construct minimal valid PDF binary
        valid_pdf_bytes = (
            b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n"
            b"2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n"
            b"3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R >>\nendobj\n"
            b"4 0 obj\n<< /Length 44 >>\nstream\nBT /F1 12 Tf 72 712 Td (Hello World PDF) Tj ET\nendstream\nendobj\n"
            b"xref\n0 5\n0000000000 65535 f \n0000000009 00000 n \n0000000058 00000 n \n0000000115 00000 n \n0000000210 00000 n \n"
            b"trailer\n<< /Size 5 /Root 1 0 R >>\nstartxref\n304\n%%EOF"
        )
        resp = client.post(
            "/api/v1/documents/student_pdf",
            files={"file": ("syllabus.pdf", valid_pdf_bytes, "application/pdf")},
            headers=auth_header("student_pdf"),
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "ingested"

    def test_disguised_pdf_rejected(self, client, auth_header):
        # File named .pdf but containing plain text or malicious script
        fake_pdf_content = b"<html><script>alert('malicious')</script></html>"
        resp = client.post(
            "/api/v1/documents/student_sec",
            files={"file": ("fake_report.pdf", fake_pdf_content, "application/pdf")},
            headers=auth_header("student_sec"),
        )
        assert resp.status_code == 415
        assert resp.json()["error"] == "UNSUPPORTED_MEDIA_TYPE"
        assert "valid PDF header" in resp.json()["message"]

    def test_unsupported_extensions_rejected(self, client, auth_header):
        for bad_ext in ["virus.exe", "script.sh", "archive.zip", "image.jpeg"]:
            resp = client.post(
                "/api/v1/documents/student_sec",
                files={"file": (bad_ext, b"binary content", "application/octet-stream")},
                headers=auth_header("student_sec"),
            )
            assert resp.status_code == 415
            assert resp.json()["error"] == "UNSUPPORTED_MEDIA_TYPE"

    def test_empty_file_rejected(self, client, auth_header):
        resp = client.post(
            "/api/v1/documents/student_sec",
            files={"file": ("empty.txt", b"", "text/plain")},
            headers=auth_header("student_sec"),
        )
        assert resp.status_code == 415
        assert "empty" in resp.json()["message"].lower()

    def test_oversized_file_rejected_with_413(self, client, auth_header, container):
        # Configure a small 1 MB limit to test threshold cleanly
        container.settings.api.max_upload_size_bytes = 100 * 1024  # 100 KB limit
        oversized_data = b"A" * (150 * 1024)  # 150 KB

        resp = client.post(
            "/api/v1/documents/student_sec",
            files={"file": ("large_notes.txt", oversized_data, "text/plain")},
            headers=auth_header("student_sec"),
        )
        assert resp.status_code == 413
        assert resp.json()["error"] == "PAYLOAD_TOO_LARGE"

    def test_filename_path_traversal_sanitized(self, client, auth_header):
        # Attempt path traversal in filename
        malicious_filename = "../../../etc/passwd.txt"
        resp = client.post(
            "/api/v1/documents/student_sec",
            files={"file": (malicious_filename, b"safe text content", "text/plain")},
            headers=auth_header("student_sec"),
        )
        assert resp.status_code == 200
        # The stored filename should strip all directory path separators
        stored_name = resp.json()["filename"]
        assert "../" not in stored_name
        assert "/" not in stored_name
        assert "\\" not in stored_name
        assert stored_name == "passwd.txt"
