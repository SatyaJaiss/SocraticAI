"""Unit tests for password hashing and JWT token handling."""

from __future__ import annotations

import time

import pytest
from app.core.exceptions import AuthenticationError
from app.core.security import (
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)

SECRET = "super-secret-test-key-minimum-32-chars-long!"


class TestPasswordHashing:
    def test_hash_and_verify_success(self):
        pw = "CorrectHorseBatteryStaple123!"
        hashed = hash_password(pw)
        assert hashed != pw
        assert hashed.startswith("$2b$")
        assert verify_password(pw, hashed) is True

    def test_verify_failure_wrong_password(self):
        hashed = hash_password("secret123")
        assert verify_password("wrongpassword", hashed) is False

    def test_empty_password_raises(self):
        with pytest.raises(ValueError):
            hash_password("")

    def test_verify_empty_inputs(self):
        assert verify_password("", "somehash") is False
        assert verify_password("secret", "") is False
        assert verify_password("secret", "invalid-hash-format") is False


class TestJWTToken:
    def test_create_and_decode_valid_token(self):
        token = create_access_token(
            subject="student_42",
            secret_key=SECRET,
            expires_delta_seconds=3600,
            additional_claims={"role": "learner"},
        )
        assert isinstance(token, str)
        assert len(token.split(".")) == 3

        payload = decode_access_token(token, SECRET)
        assert payload["sub"] == "student_42"
        assert payload["type"] == "access"
        assert payload["role"] == "learner"
        assert payload["exp"] > int(time.time())

    def test_expired_token_raises_authentication_error(self):
        # Create token that expired 10 seconds ago
        token = create_access_token(
            subject="student_old",
            secret_key=SECRET,
            expires_delta_seconds=-10,
        )
        with pytest.raises(AuthenticationError, match="has expired"):
            decode_access_token(token, SECRET)

    def test_invalid_signature_raises_authentication_error(self):
        token = create_access_token(subject="student_42", secret_key=SECRET)
        wrong_secret = "completely-different-secret-key-32-chars!"
        with pytest.raises(AuthenticationError, match="signature verification failed"):
            decode_access_token(token, wrong_secret)

    def test_tampered_payload_raises_authentication_error(self):
        token = create_access_token(subject="student_42", secret_key=SECRET)
        header, payload, sig = token.split(".")
        # Tamper payload by altering a byte
        tampered_payload = payload[:-1] + ("A" if payload[-1] != "A" else "B")
        tampered_token = f"{header}.{tampered_payload}.{sig}"
        with pytest.raises(AuthenticationError):
            decode_access_token(tampered_token, SECRET)

    def test_malformed_token_format_raises(self):
        with pytest.raises(AuthenticationError, match="Malformed"):
            decode_access_token("not-a-token", SECRET)

        with pytest.raises(AuthenticationError, match="Malformed"):
            decode_access_token("part1.part2", SECRET)

    def test_empty_token_or_secret_raises(self):
        with pytest.raises(AuthenticationError):
            decode_access_token("", SECRET)

        with pytest.raises(AuthenticationError):
            decode_access_token("a.b.c", "")

