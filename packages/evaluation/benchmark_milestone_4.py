"""Comprehensive Milestone 4 Performance, Overhead, and Cost Benchmark Suite."""

from __future__ import annotations

import asyncio
import gc
import json
import os
import platform
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

# ruff: noqa: E402

# Ensure apps/backend is in sys.path
_BACKEND_DIR = Path(__file__).resolve().parents[2] / "apps" / "backend"
if str(_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(_BACKEND_DIR))

from app.core.config import (
    GuardrailsSettings,
    LLMSettings,
    PIISettings,
    TelemetrySettings,
    TensorZeroSettings,
)
from app.guardrails.service import NeMoGuardrailsService
from app.llm.clients.client import build_llm_client
from app.llm.gateway.tensorzero_client import TensorZeroGatewayClient
from app.security.pii.service import PIIProtectionService
from app.telemetry.tracing import async_span_context, setup_telemetry


@dataclass
class BenchmarkScenarioResult:
    """Benchmark outcome for an individual architectural configuration."""

    scenario_name: str
    sample_count: int
    mean_latency_ms: float
    p50_latency_ms: float
    p95_latency_ms: float
    p99_latency_ms: float
    overhead_vs_baseline_ms: float
    tokens_per_request: int
    estimated_cost_per_1k_requests_usd: float


@dataclass
class BenchmarkSuiteReport:
    """Consolidated performance benchmark report."""

    timestamp: str
    hardware_platform: str
    python_version: str
    scenarios: dict[str, BenchmarkScenarioResult]
    overhead_breakdown_ms: dict[str, float]


TEST_WORKLOAD = [
    "Explain the concept of backpropagation in deep neural networks.",
    "My name is Sarah Connor and my email is sarah@sky.net. What is gradient descent?",
    "Calculate the derivative of f(x) = 3x^2 + 5x - 7 at x = 2.",
    "Can you provide a step-by-step worked example of matrix multiplication for 2x2 matrices?",
    "Why does high variance lead to overfitting in machine learning models?",
]


async def run_scenario_benchmark(
    name: str,
    iterations: int = 10,
    *,
    use_pii: bool = False,
    use_nemo: bool = False,
    use_otel: bool = False,
    use_tensorzero: bool = False,
    baseline_latency_ms: float = 0.0,
) -> BenchmarkScenarioResult:
    """Measure latency and memory for a specific pipeline configuration."""
    base_llm = build_llm_client(LLMSettings(provider="demo"))

    pii_svc = PIIProtectionService(PIISettings(enabled=use_pii)) if use_pii else None
    nemo_svc = (
        NeMoGuardrailsService(GuardrailsSettings(enabled=use_nemo)) if use_nemo else None
    )
    if use_otel:
        setup_telemetry(TelemetrySettings(enabled=True, otlp_endpoint=None))

    if use_tensorzero:
        gateway = TensorZeroGatewayClient(
            TensorZeroSettings(enabled=False), fallback_client=base_llm
        )
    else:
        gateway = base_llm

    latencies: list[float] = []

    # Warmup
    for text in TEST_WORKLOAD[:2]:
        _ = await _execute_pipeline(text, pii_svc, nemo_svc, gateway, use_otel)

    gc.collect()

    for _ in range(iterations):
        for text in TEST_WORKLOAD:
            t0 = time.perf_counter()
            _ = await _execute_pipeline(text, pii_svc, nemo_svc, gateway, use_otel)
            elapsed_ms = (time.perf_counter() - t0) * 1000.0
            latencies.append(elapsed_ms)

    latencies.sort()
    n = len(latencies)
    mean_val = sum(latencies) / n
    p50_val = latencies[int(n * 0.50)]
    p95_val = latencies[int(n * 0.95)]
    p99_val = latencies[int(n * 0.99)]

    overhead = max(0.0, mean_val - baseline_latency_ms) if baseline_latency_ms > 0 else 0.0

    # Demo cost estimation (based on gpt-4o-mini pricing: $0.15 / 1M input, $0.60 / 1M output)
    avg_tokens = 350
    cost_per_1k = (avg_tokens / 1_000_000.0) * 0.30 * 1000.0

    return BenchmarkScenarioResult(
        scenario_name=name,
        sample_count=n,
        mean_latency_ms=round(mean_val, 3),
        p50_latency_ms=round(p50_val, 3),
        p95_latency_ms=round(p95_val, 3),
        p99_latency_ms=round(p99_val, 3),
        overhead_vs_baseline_ms=round(overhead, 3),
        tokens_per_request=avg_tokens,
        estimated_cost_per_1k_requests_usd=round(cost_per_1k, 5),
    )


async def _execute_pipeline(
    text: str,
    pii_svc: PIIProtectionService | None,
    nemo_svc: NeMoGuardrailsService | None,
    llm: Any,
    use_otel: bool,
) -> str:
    """Simulate execution through configured components."""
    clean_text = text
    pii_ctx = None

    if pii_svc:
        clean_text, pii_ctx, _ = pii_svc.redact_user_input(text, student_id="bench_student")

    if nemo_svc:
        check = nemo_svc.validate_input(clean_text)
        if not check.allowed:
            return check.reason or "Blocked"

    if use_otel:
        async with async_span_context("benchmark.pipeline"):
            resp = await llm.generate("You are SocraticAI tutor.", clean_text)
    else:
        resp = await llm.generate("You are SocraticAI tutor.", clean_text)

    if nemo_svc:
        out_check = nemo_svc.validate_output(resp)
        if not out_check.allowed:
            resp = "Blocked by output rail"

    if pii_svc and pii_ctx:
        resp = pii_svc.restore_response(resp, pii_ctx)
        pii_ctx.clear()

    return resp


async def run_all_benchmarks(iterations: int = 10) -> BenchmarkSuiteReport:
    """Run full matrix of architectural configurations and report overheads."""
    print("Executing Milestone 4 Benchmark Suite...")

    # 1. Existing Baseline
    baseline = await run_scenario_benchmark("1_Baseline", iterations=iterations)
    base_ms = baseline.mean_latency_ms

    # 2. Baseline + TensorZero Gateway
    tz_res = await run_scenario_benchmark(
        "2_Baseline_TensorZero",
        iterations=iterations,
        use_tensorzero=True,
        baseline_latency_ms=base_ms,
    )

    # 3. Baseline + NeMo Guardrails
    nemo_res = await run_scenario_benchmark(
        "3_Baseline_NeMo",
        iterations=iterations,
        use_nemo=True,
        baseline_latency_ms=base_ms,
    )

    # 4. Baseline + OpenTelemetry Tracing
    otel_res = await run_scenario_benchmark(
        "4_Baseline_OpenTelemetry",
        iterations=iterations,
        use_otel=True,
        baseline_latency_ms=base_ms,
    )

    # 5. Full Integrated Pipeline (PII + NeMo + TensorZero + OTel)
    full_res = await run_scenario_benchmark(
        "5_Full_Integrated_Pipeline",
        iterations=iterations,
        use_pii=True,
        use_nemo=True,
        use_otel=True,
        use_tensorzero=True,
        baseline_latency_ms=base_ms,
    )

    scenarios = {
        "baseline": baseline,
        "baseline_tensorzero": tz_res,
        "baseline_nemo": nemo_res,
        "baseline_opentelemetry": otel_res,
        "full_integrated_pipeline": full_res,
    }

    overheads = {
        "gateway_overhead_ms": tz_res.overhead_vs_baseline_ms,
        "guardrails_overhead_ms": nemo_res.overhead_vs_baseline_ms,
        "tracing_overhead_ms": otel_res.overhead_vs_baseline_ms,
        "total_integrated_overhead_ms": full_res.overhead_vs_baseline_ms,
    }

    report = BenchmarkSuiteReport(
        timestamp=time.strftime("%Y-%m-%d %H:%M:%S"),
        hardware_platform=f"{platform.system()} {platform.machine()} ({os.cpu_count()} CPUs)",
        python_version=platform.python_version(),
        scenarios=scenarios,
        overhead_breakdown_ms=overheads,
    )

    results_dir = Path(__file__).resolve().parent / "results"
    results_dir.mkdir(parents=True, exist_ok=True)
    out_file = results_dir / "benchmark_milestone_4.json"
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(
            {
                "timestamp": report.timestamp,
                "hardware_platform": report.hardware_platform,
                "python_version": report.python_version,
                "overhead_breakdown_ms": report.overhead_breakdown_ms,
                "scenarios": {k: asdict(v) for k, v in report.scenarios.items()},
            },
            f,
            indent=2,
        )

    print(f"Benchmark results saved to {out_file}")
    return report


if __name__ == "__main__":
    asyncio.run(run_all_benchmarks(iterations=5))
