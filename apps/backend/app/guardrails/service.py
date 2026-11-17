"""Unified NVIDIA NeMo Guardrails service coordinating input, retrieval, execution, and output rails."""

from __future__ import annotations

import logging
import os
import time
from typing import TYPE_CHECKING, Any

from app.guardrails.execution_rails import ExecutionRails
from app.guardrails.input_rails import InputRails
from app.guardrails.models import RailCheckResult, RailType
from app.guardrails.output_rails import OutputRails
from app.guardrails.retrieval_rails import RetrievalRails

if TYPE_CHECKING:
    from app.core.config import GuardrailsSettings

logger = logging.getLogger(__name__)


class NeMoGuardrailsService:
    """Production service coordinating NeMo Guardrails and deterministic safety boundaries."""

    def __init__(self, settings: GuardrailsSettings | None = None) -> None:
        self.settings = settings
        max_len = settings.max_input_length if settings else 4000
        self.input_rails = InputRails(max_length=max_len)
        self.retrieval_rails = RetrievalRails()
        self.execution_rails = ExecutionRails()
        self.output_rails = OutputRails()

        self._llm_rails: Any | None = None
        self._nemo_initialized = False

        if settings and settings.enabled:
            self._try_init_nemo(settings.config_path)

    def _try_init_nemo(self, config_path: str) -> None:
        """Attempt to load official NeMo LLMRails configuration if available."""
        if not os.path.exists(config_path):
            logger.info(
                "NeMo Guardrails config path not found at %s. Using deterministic rails.",
                config_path,
            )
            return

        try:
            from nemoguardrails import LLMRails, RailsConfig

            rails_config = RailsConfig.from_path(config_path)
            self._llm_rails = LLMRails(rails_config)
            self._nemo_initialized = True
            logger.info("NeMo Guardrails LLMRails initialized from %s.", config_path)
        except Exception as exc:
            logger.warning("NeMo Guardrails initialization deferred/fallback: %s", exc)

    def validate_input(self, text: str) -> RailCheckResult:
        """Evaluate input message through input rails."""
        start_time = time.perf_counter()
        result = self.input_rails.validate(text)
        duration = time.perf_counter() - start_time

        self._record_metrics(RailType.INPUT, result, duration)
        return result

    def validate_retrieval(
        self,
        passages: list[dict[str, Any]],
        querying_student_id: str | None = None,
    ) -> list[dict[str, Any]]:
        """Filter retrieved passages using retrieval rails."""
        start_time = time.perf_counter()
        safe_passages = self.retrieval_rails.filter_passages(
            passages, querying_student_id=querying_student_id
        )
        duration = time.perf_counter() - start_time

        # Track if any passage was blocked
        blocked = len(passages) - len(safe_passages)
        res = RailCheckResult(
            allowed=(blocked == 0),
            rail_type=RailType.RETRIEVAL,
            reason=f"Blocked {blocked} unsafe retrieved passages." if blocked > 0 else None,
        )
        self._record_metrics(RailType.RETRIEVAL, res, duration)
        return safe_passages

    def validate_tool_execution(
        self,
        tool_name: str,
        tool_args: dict[str, Any],
        student_id: str,
    ) -> RailCheckResult:
        """Verify tool authorization and student isolation before execution."""
        start_time = time.perf_counter()
        result = self.execution_rails.validate_tool_invocation(
            tool_name=tool_name,
            tool_args=tool_args,
            student_id=student_id,
        )
        duration = time.perf_counter() - start_time

        self._record_metrics(RailType.EXECUTION, result, duration)
        return result

    def validate_output(self, text: str) -> RailCheckResult:
        """Evaluate generated model output before presenting to student."""
        start_time = time.perf_counter()
        result = self.output_rails.validate(text)
        duration = time.perf_counter() - start_time

        self._record_metrics(RailType.OUTPUT, result, duration)
        return result

    def _record_metrics(
        self, rail_type: RailType, result: RailCheckResult, duration: float
    ) -> None:
        """Record Prometheus metrics for guardrail executions."""
        try:
            from app.telemetry.metrics import record_guardrail_event

            record_guardrail_event(
                rail_type=rail_type.value,
                allowed=result.allowed,
                duration=duration,
            )
        except Exception:
            pass
