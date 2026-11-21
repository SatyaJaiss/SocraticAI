"""TensorZero Gateway client providing centralized generative LLM inference, routing, and observability."""

from __future__ import annotations

import logging
import time
from typing import TYPE_CHECKING, Any, TypeVar

from pydantic import BaseModel, ValidationError

from app.core.exceptions import (
    LLMError,
    LLMOutputParsingError,
)
from app.llm.gateway.models import GatewayInferenceResult
from app.telemetry.metrics import (
    record_llm_failure,
    record_llm_fallback,
    record_llm_inference,
)
from app.telemetry.tracing import async_span_context, inject_trace_context
from app.utils.helpers import safe_json_parse

if TYPE_CHECKING:
    from app.core.config import Settings, TensorZeroSettings
    from app.llm.clients.client import LLMClient

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)


class TensorZeroGatewayClient:
    """Async client routing generative inference through the TensorZero Gateway

    with automatic fallbacks, telemetry, retries, and token tracking.
    """

    def __init__(
        self,
        settings: TensorZeroSettings,
        fallback_client: LLMClient | None = None,
        full_settings: Settings | None = None,
    ) -> None:
        self.settings = settings
        self.fallback_client = fallback_client
        self.full_settings = full_settings
        self._gateway: Any | None = None
        self._gateway_initialized = False

        if self.settings.enabled and self.settings.gateway_url:
            self._try_init_gateway()

    def _try_init_gateway(self) -> None:
        """Attempt to construct the TensorZero HTTP gateway client."""
        try:
            from tensorzero import AsyncTensorZeroGateway

            self._gateway = AsyncTensorZeroGateway.build_http(
                gateway_url=self.settings.gateway_url,
                timeout=self.settings.timeout_seconds,
            )
            self._gateway_initialized = True
            logger.info("TensorZero gateway client connected at %s", self.settings.gateway_url)
        except Exception as exc:
            logger.warning("TensorZero gateway client initialization deferred/failed: %s", exc)

    async def generate(
        self,
        system: str,
        user: str,
        *,
        temperature: float | None = None,
        function_name: str | None = None,
        variant_name: str | None = None,
        episode_id: str | None = None,
    ) -> str:
        """Generate response text via TensorZero gateway or fallback client."""
        func = function_name or self.settings.default_chat_function
        variant = variant_name or self.settings.default_variant

        span_attrs = {
            "llm.function": func,
            "llm.variant": variant,
            "llm.gateway_enabled": self.settings.enabled,
        }

        async with async_span_context("tensorzero.generate", span_attrs) as span:
            start_time = time.perf_counter()

            # If gateway is enabled and initialized, attempt gateway inference
            if self.settings.enabled and self._gateway_initialized and self._gateway is not None:
                try:
                    result = await self._call_gateway_inference(
                        system=system,
                        user=user,
                        function_name=func,
                        variant_name=variant,
                        episode_id=episode_id,
                    )
                    duration = time.perf_counter() - start_time
                    record_llm_inference(
                        provider="tensorzero",
                        model=result.model,
                        function_name=func,
                        duration=duration,
                        prompt_tokens=result.prompt_tokens,
                        completion_tokens=result.completion_tokens,
                    )
                    span.set_attribute("llm.provider", "tensorzero")
                    span.set_attribute("llm.model", result.model)
                    span.set_attribute("llm.prompt_tokens", result.prompt_tokens)
                    span.set_attribute("llm.completion_tokens", result.completion_tokens)
                    return result.text
                except Exception as exc:
                    logger.warning(
                        "TensorZero gateway call failed (%s); triggering resilient fallback.",
                        exc,
                    )
                    record_llm_failure(provider="tensorzero", error_type=type(exc).__name__)
                    record_llm_fallback(reason=f"tensorzero_error_{type(exc).__name__}")

            # Fallback path (internal LangChain or Demo provider)
            if self.fallback_client is not None:
                logger.debug(
                    "Executing LLM inference via fallback client (%s)",
                    self.fallback_client.provider,
                )
                fallback_start = time.perf_counter()
                try:
                    output = await self.fallback_client.generate(
                        system, user, temperature=temperature
                    )
                    duration = time.perf_counter() - fallback_start
                    record_llm_inference(
                        provider=self.fallback_client.provider,
                        model=getattr(
                            self.fallback_client.settings,
                            f"{self.fallback_client.provider}_model",
                            "default",
                        ),
                        function_name=func,
                        duration=duration,
                    )
                    span.set_attribute("llm.provider", self.fallback_client.provider)
                    span.set_attribute("llm.fallback", True)
                    return output
                except Exception as exc:
                    record_llm_failure(
                        provider=self.fallback_client.provider, error_type=type(exc).__name__
                    )
                    raise

            raise LLMError("Neither TensorZero gateway nor fallback client is operational.")

    async def generate_json(
        self,
        system: str,
        user: str,
        *,
        model_class: type[T],
        temperature: float | None = None,
        function_name: str | None = None,
        variant_name: str | None = None,
        episode_id: str | None = None,
    ) -> T:
        """Generate structured JSON via TensorZero gateway or fallback, validating with Pydantic."""
        func = function_name or self.settings.default_json_function
        variant = variant_name or self.settings.default_variant

        # 1. Attempt structured generation through TensorZero gateway if operational
        if self.settings.enabled and self._gateway_initialized and self._gateway is not None:
            try:
                res = await self._call_gateway_inference(
                    system=system,
                    user=user,
                    function_name=func,
                    variant_name=variant,
                    episode_id=episode_id,
                )
                payload = safe_json_parse(res.text)
                if payload is not None:
                    try:
                        return model_class.model_validate(payload)
                    except ValidationError as val_err:
                        logger.warning(
                            "TensorZero gateway output failed %s validation (%s); falling back.",
                            model_class.__name__,
                            val_err,
                        )
                else:
                    logger.warning(
                        "TensorZero gateway output was not parseable JSON; falling back."
                    )
            except Exception as exc:
                logger.warning(
                    "TensorZero gateway JSON call failed (%s); triggering resilient fallback.",
                    exc,
                )
                record_llm_failure(provider="tensorzero", error_type=type(exc).__name__)
                record_llm_fallback(reason=f"tensorzero_json_error_{type(exc).__name__}")

        # 2. Resilient fallback path directly to fallback client's generate_json
        if self.fallback_client is not None:
            logger.debug(
                "Executing LLM JSON inference via fallback client (%s)",
                self.fallback_client.provider,
            )
            return await self.fallback_client.generate_json(
                system, user, model_class=model_class, temperature=temperature
            )

        raise LLMError("Neither TensorZero gateway nor fallback client is operational for JSON generation.")

    async def _call_gateway_inference(
        self,
        system: str,
        user: str,
        function_name: str,
        variant_name: str | None = None,
        episode_id: str | None = None,
    ) -> GatewayInferenceResult:
        """Format messages and invoke TensorZero gateway via SDK."""
        from tensorzero import Input, InputMessage, Text

        # Inject OpenTelemetry trace context headers into gateway call
        trace_headers = inject_trace_context({})

        messages = [
            InputMessage(role="system", content=[Text(text=system)]),
            InputMessage(role="user", content=[Text(text=user)]),
        ]
        gateway_input = Input(messages=messages)

        response = await self._gateway.inference(
            function_name=function_name,
            input=gateway_input,
            variant_name=variant_name,
            episode_id=episode_id,
            gateway_http_headers=trace_headers,
        )

        # Extract text and token usage from TensorZero response
        extracted_text = ""
        model_used = "tensorzero-model"
        prompt_tokens = 0
        completion_tokens = 0

        # Handle chat response content blocks
        content_blocks = getattr(response, "content", [])
        if content_blocks:
            parts = [
                getattr(block, "text", "") for block in content_blocks if hasattr(block, "text")
            ]
            extracted_text = "".join(parts)
        elif hasattr(response, "output"):
            output = response.output
            if hasattr(output, "text"):
                extracted_text = str(output.text)
            elif isinstance(output, str):
                extracted_text = output
            elif isinstance(output, dict):
                import json

                extracted_text = json.dumps(output)

        usage = getattr(response, "usage", None)
        if usage:
            prompt_tokens = (
                getattr(usage, "input_tokens", 0) or getattr(usage, "prompt_tokens", 0) or 0
            )
            completion_tokens = (
                getattr(usage, "output_tokens", 0) or getattr(usage, "completion_tokens", 0) or 0
            )

        if hasattr(response, "model_name"):
            model_used = str(response.model_name)

        return GatewayInferenceResult(
            text=extracted_text,
            raw_response=response,
            model=model_used,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
        )

    @property
    def provider(self) -> str:
        """Identify provider abstraction."""
        if self.settings.enabled and self._gateway_initialized:
            return "tensorzero"
        if self.fallback_client:
            return self.fallback_client.provider
        return "tensorzero"
