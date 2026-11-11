"""Typed exception hierarchy and HTTP exception handlers for SocraticAI.

Design rationale
----------------
A small, purpose-built exception tree lets every layer raise domain-meaningful
errors and lets the API layer translate them to HTTP responses with a single
registry. Each exception carries an HTTPStatus-compatible ``status_code`` and
a stable machine-readable ``code`` so clients can branch without string-matching.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from fastapi import FastAPI, Request
    from fastapi.responses import JSONResponse


class SocraticAIError(Exception):
    """Base class for all SocraticAI-specific exceptions."""

    status_code: int = 500
    code: str = "SOCRATICAI_ERROR"

    def __init__(self, message: str, *, detail: dict | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.detail = detail or {}


# Backward-compatibility alias
EduAgentError = SocraticAIError


class ConfigurationError(SocraticAIError):
    """Missing/invalid runtime configuration (e.g. no LLM API key set)."""

    status_code = 500
    code = "CONFIGURATION_ERROR"


class ProviderConfigurationError(ConfigurationError):
    """The selected LLM provider is unsupported or misconfigured."""

    code = "LLM_PROVIDER_CONFIG"


class DatabaseError(SocraticAIError):
    """Any persistence failure (connection, integrity, constraint)."""

    status_code = 500
    code = "DATABASE_ERROR"


class LLMError(SocraticAIError):
    """Failure while calling the LLM provider (upstream / network)."""

    status_code = 502
    code = "LLM_ERROR"


class LLMTimeoutError(LLMError):
    """The LLM call exceeded the configured timeout window."""

    code = "LLM_TIMEOUT"


class LLMOutputParsingError(LLMError):
    """The model returned output that could not be validated/parsed."""

    code = "LLM_OUTPUT_PARSE"


class IngestionError(SocraticAIError):
    """A document could not be loaded, chunked or embedded."""

    status_code = 422
    code = "INGESTION_ERROR"


class RetrievalError(SocraticAIError):
    """Semantic retrieval failed (collection missing, embedder error)."""

    status_code = 500
    code = "RETRIEVAL_ERROR"


class ResourceNotFoundError(SocraticAIError):
    """Requested entity (student, quiz, document, ...) does not exist."""

    status_code = 404
    code = "NOT_FOUND"


class AuthenticationError(SocraticAIError):
    """Missing, invalid or expired authentication credentials."""

    status_code = 401
    code = "AUTHENTICATION_ERROR"


class AuthorizationError(SocraticAIError):
    """Authenticated caller does not have permission to access this resource."""

    status_code = 403
    code = "AUTHORIZATION_ERROR"


class PayloadTooLargeError(SocraticAIError):
    """Uploaded content exceeds maximum permitted size."""

    status_code = 413
    code = "PAYLOAD_TOO_LARGE"


class UnsupportedMediaTypeError(SocraticAIError):
    """Uploaded file type or MIME type is not supported."""

    status_code = 415
    code = "UNSUPPORTED_MEDIA_TYPE"


class ValidationError(SocraticAIError):
    """Input payload failed domain validation."""

    status_code = 422
    code = "VALIDATION_ERROR"


def register_exception_handlers(app: FastAPI) -> None:
    """Attach the error-to-HTTP mapper to ``app``."""
    from fastapi.responses import JSONResponse

    @app.exception_handler(SocraticAIError)
    async def socraticai_error_handler(
        request: Request, exc: SocraticAIError
    ) -> JSONResponse:
        headers = {}
        if isinstance(exc, AuthenticationError):
            headers["WWW-Authenticate"] = "Bearer"

        return JSONResponse(
            status_code=exc.status_code,
            headers=headers if headers else None,
            content={
                "error": exc.code,
                "message": str(exc.message),
                "detail": exc.detail,
            },
        )
