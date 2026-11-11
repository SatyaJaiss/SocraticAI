"""Security utilities: password hashing and JWT token handling.

Design rationale
----------------
* Uses standard bcrypt for password hashing with cost factor (work factor) 12.
* Uses HMAC-SHA256 with constant-time comparison for signing and verifying JWTs,
  leveraging Python's standard library and cryptography module without extraneous
  auth frameworks.
* Strictly validates token expiration, signature integrity, and claims.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import logging
import time
from typing import Any

import bcrypt

from app.core.exceptions import AuthenticationError

logger = logging.getLogger(__name__)


# --------------------------------------------------------------------------- #
# Password Hashing
# --------------------------------------------------------------------------- #
def hash_password(password: str) -> str:
    """Hash a plaintext password using bcrypt.

    Returns a UTF-8 decoded bcrypt hash string with embedded salt.
    """
    if not password:
        raise ValueError("Password cannot be empty")
    # Truncate at 72 bytes (bcrypt max key length limit) to prevent errors
    pw_bytes = password.encode("utf-8")[:72]
    salt = bcrypt.gensalt(rounds=12)
    hashed = bcrypt.hashpw(pw_bytes, salt)
    return hashed.decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plaintext password against a bcrypt hash string."""
    if not plain_password or not hashed_password:
        return False
    try:
        pw_bytes = plain_password.encode("utf-8")[:72]
        hash_bytes = hashed_password.encode("utf-8")
        return bcrypt.checkpw(pw_bytes, hash_bytes)
    except Exception as exc:
        logger.warning("Password verification failed with error: %s", exc)
        return False


# --------------------------------------------------------------------------- #
# JWT Token Handling (HS256)
# --------------------------------------------------------------------------- #
def _b64url_encode(data: bytes) -> str:
    """URL-safe base64 encoding without padding."""
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _b64url_decode(data: str) -> bytes:
    """URL-safe base64 decoding with restored padding."""
    padding = 4 - (len(data) % 4)
    if padding and padding != 4:
        data += "=" * padding
    return base64.urlsafe_b64decode(data.encode("ascii"))


def create_access_token(
    subject: str,
    secret_key: str,
    *,
    expires_delta_seconds: int = 86400,  # 24 hours default
    additional_claims: dict[str, Any] | None = None,
) -> str:
    """Generate a signed HMAC-SHA256 JWT access token.

    :param subject: The student ID or unique principal.
    :param secret_key: Secret key used for signing.
    :param expires_delta_seconds: Token lifetime in seconds.
    :param additional_claims: Optional extra claims to embed in payload.
    """
    if not secret_key:
        raise ValueError("JWT secret key must not be empty")

    now = int(time.time())
    payload = {
        "sub": str(subject),
        "iat": now,
        "exp": now + expires_delta_seconds,
        "type": "access",
    }
    if additional_claims:
        payload.update(additional_claims)

    header = {"alg": "HS256", "typ": "JWT"}

    header_b64 = _b64url_encode(json.dumps(header, separators=(",", ":")).encode("utf-8"))
    payload_b64 = _b64url_encode(json.dumps(payload, separators=(",", ":")).encode("utf-8"))

    signing_input = f"{header_b64}.{payload_b64}".encode("ascii")
    signature = hmac.new(secret_key.encode("utf-8"), signing_input, hashlib.sha256).digest()
    signature_b64 = _b64url_encode(signature)

    return f"{header_b64}.{payload_b64}.{signature_b64}"


def decode_access_token(token: str, secret_key: str) -> dict[str, Any]:
    """Decode and strictly validate a signed JWT token.

    Raises :class:`AuthenticationError` if token is expired, malformed, or
    signature is invalid.
    """
    if not token or not secret_key:
        raise AuthenticationError("Invalid token or secret key")

    parts = token.strip().split(".")
    if len(parts) != 3:
        raise AuthenticationError("Malformed authentication token format")

    header_b64, payload_b64, signature_b64 = parts

    # 1. Verify Signature
    signing_input = f"{header_b64}.{payload_b64}".encode("ascii")
    expected_sig = hmac.new(secret_key.encode("utf-8"), signing_input, hashlib.sha256).digest()

    try:
        actual_sig = _b64url_decode(signature_b64)
    except Exception as exc:
        raise AuthenticationError("Invalid token signature encoding") from exc

    if not hmac.compare_digest(expected_sig, actual_sig):
        raise AuthenticationError("Token signature verification failed")

    # 2. Decode Header & Payload
    try:
        header = json.loads(_b64url_decode(header_b64).decode("utf-8"))
        payload = json.loads(_b64url_decode(payload_b64).decode("utf-8"))
    except Exception as exc:
        raise AuthenticationError("Malformed token payload") from exc

    if header.get("alg") != "HS256":
        raise AuthenticationError(f"Unsupported token algorithm: {header.get('alg')}")

    # 3. Verify Expiry & Claims
    now = int(time.time())
    exp = payload.get("exp")
    if exp is None or not isinstance(exp, (int, float)):
        raise AuthenticationError("Token is missing expiration claim ('exp')")

    if now > exp:
        raise AuthenticationError("Authentication token has expired")

    sub = payload.get("sub")
    if not sub:
        raise AuthenticationError("Token is missing subject claim ('sub')")

    return payload

