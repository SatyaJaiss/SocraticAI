"""Centralised, typed configuration for SocraticAI backend.

Design rationale
----------------
* One ``Settings`` object is built once per process from environment variables
  (with ``.env`` support) and passed around via dependency injection.
* Each concern gets its own nested settings model with an ``env_prefix`` so the
  env namespace is flat (e.g. ``LLM_OPENAI_API_KEY``) while the Python objects
  stay grouped.
* Safe defaults mean the project boots without a real API key — useful for the
  test-suite and for demo mode.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Annotated, Any

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

_ENV_FILE = ".env"

# Root project directory lookup
_PROJECT_ROOT = Path(__file__).resolve().parents[4]


class Agents:
    """Canonical names for every graph node / agent."""

    PLANNER = "planner"
    TEACHER = "teacher"
    QUIZ = "quiz"
    EVALUATION = "evaluation"
    MEMORY = "memory"
    RECOMMENDATION = "recommendation"
    RAG = "rag"
    DASHBOARD = "dashboard"

    ALL = (
        PLANNER,
        TEACHER,
        QUIZ,
        EVALUATION,
        MEMORY,
        RECOMMENDATION,
        RAG,
        DASHBOARD,
    )


class Routes:
    """Stable node names and routing keys for LangGraph workflows."""

    TEACH = "teach"
    ANSWER_QUESTION = "answer_question"
    QUIZ = "quiz"
    RAG_ONLY = "rag_only"
    GREETING = "greeting"
    SMALL_TALK = "small_talk"
    MEMORY_QUERY = "memory_query"
    PROGRESS = "progress"
    OFF_TOPIC = "off_topic"
    CLARIFICATION = "clarification"
    TUTORING = "tutoring"
    SOCRATIC = "socratic"
    END = "end"


class QuizComposition:
    """Fixed composition of a generated quiz."""

    MCQ_COUNT = 5
    NUMERICAL_COUNT = 2
    SUBJECTIVE_COUNT = 1
    TOTAL = MCQ_COUNT + NUMERICAL_COUNT + SUBJECTIVE_COUNT


SUPPORTED_DOCUMENT_EXTENSIONS = frozenset({".pdf", ".txt", ".md"})
DEFAULT_STUDENT_NAME = "Learner"
MAX_CHUNKS_PER_DOCUMENT = 2000


class AppSettings(BaseSettings):
    """Application-level metadata and runtime behaviour."""

    model_config = SettingsConfigDict(env_prefix="APP_", extra="ignore", env_file=_ENV_FILE)

    name: str = "SocraticAI"
    version: str = "1.0.0"
    environment: str = "development"
    host: str = "0.0.0.0"
    port: int = 8000
    debug: bool = True
    allowed_origins: Annotated[list[str], NoDecode] = Field(
        default_factory=lambda: ["http://localhost:8501", "http://localhost:8000"]
    )

    @field_validator("allowed_origins", mode="before")
    @classmethod
    def _split_csv(cls, value: Any) -> Any:
        """Allow CORS origins to be supplied as a CSV env var."""
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
        return value


class LLMSettings(BaseSettings):
    """LLM provider selection. Provider is ``openai``, ``gemini``, or ``demo``."""

    model_config = SettingsConfigDict(env_prefix="LLM_", extra="ignore", env_file=_ENV_FILE)

    provider: str = "openai"
    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"
    openai_temperature: float = 0.4
    gemini_api_key: str = ""
    gemini_model: str = "gemini-1.5-flash"
    gemini_temperature: float = 0.4
    timeout_seconds: float = 60.0
    max_retries: int = 2


class DatabaseSettings(BaseSettings):
    """SQLAlchemy connection settings."""

    model_config = SettingsConfigDict(env_prefix="DATABASE_", extra="ignore", env_file=_ENV_FILE)

    url: str = "sqlite:///./data/socraticai.db"
    echo: bool = False
    create_on_startup: bool = True


class VectorStoreSettings(BaseSettings):
    """ChromaDB + embedding model settings."""

    model_config = SettingsConfigDict(env_prefix="VECTOR_", extra="ignore", env_file=_ENV_FILE)

    persist_directory: str = "./data/chroma"
    collection_name: str = "socraticai_notes"
    embedding_model: str = "all-MiniLM-L6-v2"
    chunk_size: int = 600
    chunk_overlap: int = 100
    top_k: int = 4


class ApiSettings(BaseSettings):
    """REST API surface settings."""

    model_config = SettingsConfigDict(env_prefix="API_", extra="ignore", env_file=_ENV_FILE)

    prefix: str = "/api/v1"
    upload_dir: str = "./data/uploads"
    pagination_default_size: int = 20
    max_upload_size_bytes: int = 25 * 1024 * 1024  # 25 MB


class AuthSettings(BaseSettings):
    """Authentication and JWT token configuration."""

    model_config = SettingsConfigDict(env_prefix="AUTH_", extra="ignore", env_file=_ENV_FILE)

    secret_key: str = "socraticai-dev-insecure-secret-key-32b-min!!"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 60 * 24  # 24 hours


class LoggingSettings(BaseSettings):
    """Centralised logging behaviour."""

    model_config = SettingsConfigDict(env_prefix="LOGGING_", extra="ignore", env_file=_ENV_FILE)

    level: str = "INFO"
    json_format: bool = False
    log_dir: str = "./logs"
    rotation_bytes: int = 5 * 1024 * 1024  # 5 MB
    backup_count: int = 3


class FrontendSettings(BaseSettings):
    """Where the Streamlit dashboard reaches the API."""

    model_config = SettingsConfigDict(env_prefix="FRONTEND_", extra="ignore", env_file=_ENV_FILE)

    api_base_url: str = "http://localhost:8000"


class ConversationSettings(BaseSettings):
    """Conversational history and working memory limits."""

    model_config = SettingsConfigDict(
        env_prefix="CONVERSATION_", extra="ignore", env_file=_ENV_FILE
    )

    history_limit: int = 10
    context_token_budget: int = 1500
    max_message_length: int = 8000
    summary_trigger_turns: int = 6


class MemorySettings(BaseSettings):
    """Episodic and semantic memory configuration."""

    model_config = SettingsConfigDict(env_prefix="MEMORY_", extra="ignore", env_file=_ENV_FILE)

    episodic_collection_name: str = "socraticai_episodic_memory"
    episodic_top_k: int = 4
    memory_similarity_threshold: float = 0.55
    max_memory_context_tokens: int = 600
    consolidation_message_trigger: int = 10
    concept_ema_alpha: float = 0.6


class RoutingSettings(BaseSettings):
    """Jev (TypeSafe AI) and deterministic routing configuration."""

    model_config = SettingsConfigDict(env_prefix="ROUTING_", extra="ignore", env_file=_ENV_FILE)

    jev_enabled: bool = False
    jev_api_key: str = ""
    jev_model: str = "jev-latest"
    jev_timeout_seconds: float = 5.0
    jev_retry_count: int = 2
    confidence_high_threshold: float = 0.70
    confidence_low_threshold: float = 0.40
    fallback_strategy: str = "deterministic"


class CachingSettings(BaseSettings):
    """Caching configuration for embeddings, retrieval, and LLM responses."""

    model_config = SettingsConfigDict(env_prefix="CACHE_", extra="ignore", env_file=_ENV_FILE)

    enabled: bool = True
    backend: str = "memory"
    max_size: int = 10000
    default_ttl_seconds: int = 3600
    embedding_cache_ttl_seconds: int = 86400
    retrieval_cache_ttl_seconds: int = 1800
    response_cache_enabled: bool = False
    response_cache_ttl_seconds: int = 3600


class ContextBudgetSettings(BaseSettings):
    """Token budget allocations across prompt segments."""

    model_config = SettingsConfigDict(env_prefix="CONTEXT_", extra="ignore", env_file=_ENV_FILE)

    total_budget: int = 4000
    system_prompt_budget: int = 600
    history_budget: int = 1500
    episodic_memory_budget: int = 600
    semantic_profile_budget: int = 400
    rag_budget: int = 900
    tokenizer_encoding: str = "cl100k_base"


class ChunkingSettings(BaseSettings):
    """Document chunking and section-awareness settings."""

    model_config = SettingsConfigDict(env_prefix="CHUNKING_", extra="ignore", env_file=_ENV_FILE)

    chunk_size: int = 600
    chunk_overlap: int = 100
    strategy: str = "section_aware"  # "fixed", "section_aware"
    max_section_size: int = 1200


class BM25Settings(BaseSettings):
    """BM25 lexical retrieval settings."""

    model_config = SettingsConfigDict(env_prefix="BM25_", extra="ignore", env_file=_ENV_FILE)

    enabled: bool = True
    candidate_count: int = 10
    index_dir: str = "./data/bm25_indices"
    k1: float = 1.5
    b: float = 0.75


class HybridRetrievalSettings(BaseSettings):
    """Hybrid retrieval (Dense + BM25 + Reciprocal Rank Fusion) settings."""

    model_config = SettingsConfigDict(env_prefix="HYBRID_", extra="ignore", env_file=_ENV_FILE)

    enabled: bool = True
    rrf_k: int = 60
    dense_candidates: int = 10
    bm25_candidates: int = 10
    final_top_k: int = 4


class RerankerSettings(BaseSettings):
    """Cross-Encoder reranking settings."""

    model_config = SettingsConfigDict(env_prefix="RERANKER_", extra="ignore", env_file=_ENV_FILE)

    enabled: bool = False
    model_name: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"
    top_k: int = 4
    max_length: int = 512
    device: str = "auto"  # "auto", "cpu", "cuda"
    batch_size: int = 16


class DecisionModelSettings(BaseSettings):
    """Unified decision-model settings for Jev and Gemini Decisions API."""

    model_config = SettingsConfigDict(env_prefix="DECISION_", extra="ignore", env_file=_ENV_FILE)

    primary_provider: str = "jev"  # "jev", "gemini_decisions", "shadow", "disabled"
    fallback_provider: str = "disabled"
    gemini_model: str = "gemini-decision-1"
    gemini_api_key: str = ""
    jev_model: str = "jev-latest"
    jev_api_key: str = ""
    timeout_seconds: float = 5.0
    confidence_threshold: float = 0.65
    relevance_threshold: float = 0.50
    shadow_mode: bool = False
    candidate_grading_limit: int = 6
    relevance_gating_enabled: bool = False


class CitationSettings(BaseSettings):
    """Citation generation and verification pipeline settings."""

    model_config = SettingsConfigDict(env_prefix="CITATION_", extra="ignore", env_file=_ENV_FILE)

    enabled: bool = True
    verification_threshold: float = 0.60
    max_claims_per_verification: int = 8
    require_ownership_check: bool = True


class QueryRewritingSettings(BaseSettings):
    """Query analysis and multi-part decomposition settings."""

    model_config = SettingsConfigDict(
        env_prefix="QUERY_REWRITE_", extra="ignore", env_file=_ENV_FILE
    )

    enabled: bool = True
    max_subqueries: int = 3


class TutoringSettings(BaseSettings):
    """Adaptive tutoring and Socratic dialogue configuration."""

    model_config = SettingsConfigDict(env_prefix="TUTORING_", extra="ignore", env_file=_ENV_FILE)

    default_strategy: str = "direct_explanation"
    max_dialogue_turns: int = 10
    max_hint_level: int = 4
    default_explanation_mode: str = "intermediate"
    socratic_enabled: bool = True
    adaptive_depth_enabled: bool = True


class MasterySettings(BaseSettings):
    """Concept-level learning state and evidence-based mastery configuration."""

    model_config = SettingsConfigDict(env_prefix="MASTERY_", extra="ignore", env_file=_ENV_FILE)

    mastery_threshold: float = 0.80
    confidence_threshold: float = 0.70
    min_evidence_count: int = 3
    evidence_weight: float = 0.35
    decay_days: int = 30
    partial_understanding_threshold: float = 0.50


class AssessmentSettings(BaseSettings):
    """Adaptive quiz generation and deterministic evaluation configuration."""

    model_config = SettingsConfigDict(env_prefix="ASSESSMENT_", extra="ignore", env_file=_ENV_FILE)

    default_question_count: int = 5
    numerical_relative_tolerance: float = 0.01
    numerical_absolute_tolerance: float = 1e-4
    subjective_passing_score: float = 0.70
    max_retries: int = 2
    require_document_grounding: bool = True


class AdaptiveRecommendationSettings(BaseSettings):
    """Prerequisite-aware recommendation engine configuration."""

    model_config = SettingsConfigDict(
        env_prefix="RECOMMENDATION_", extra="ignore", env_file=_ENV_FILE
    )

    max_recommendations: int = 5
    prerequisite_threshold: float = 0.70


class MisconceptionSettings(BaseSettings):
    """Evidence-based misconception detection and tracking configuration."""

    model_config = SettingsConfigDict(
        env_prefix="MISCONCEPTION_", extra="ignore", env_file=_ENV_FILE
    )

    detection_confidence_threshold: float = 0.75
    resolution_attempts_required: int = 2
    prevent_duplicate_active: bool = True


class PIISettings(BaseSettings):
    """Personal Identifiable Information (PII) protection and redaction settings."""

    model_config = SettingsConfigDict(env_prefix="PII_", extra="ignore", env_file=_ENV_FILE)

    enabled: bool = True
    enabled_categories: Annotated[list[str], NoDecode] = Field(
        default_factory=lambda: [
            "PERSON",
            "EMAIL",
            "PHONE",
            "ADDRESS",
            "GOVERNMENT_ID",
            "FINANCIAL",
            "SENSITIVE_ID",
        ]
    )
    escape_html: bool = True
    strict_restoration: bool = False

    @field_validator("enabled_categories", mode="before")
    @classmethod
    def _split_csv(cls, value: Any) -> Any:
        if isinstance(value, str):
            if value.startswith("[") and value.endswith("]"):
                import json
                try:
                    return json.loads(value)
                except Exception:
                    pass
            return [cat.strip() for cat in value.split(",") if cat.strip()]
        return value


class GuardrailsSettings(BaseSettings):
    """NVIDIA NeMo Guardrails configuration settings."""

    model_config = SettingsConfigDict(env_prefix="GUARDRAILS_", extra="ignore", env_file=_ENV_FILE)

    enabled: bool = True
    config_path: str = "configs/guardrails"
    max_input_length: int = 4000
    check_retrieval: bool = True
    check_execution: bool = True
    check_output: bool = True


class TensorZeroSettings(BaseSettings):
    """TensorZero LLM gateway configuration settings."""

    model_config = SettingsConfigDict(env_prefix="TENSORZERO_", extra="ignore", env_file=_ENV_FILE)

    enabled: bool = False
    gateway_url: str = "http://localhost:3000"
    timeout_seconds: float = 30.0
    default_chat_function: str = "tutor_chat"
    default_json_function: str = "tutor_json"
    default_variant: str = "default"
    max_retries: int = 2


class TelemetrySettings(BaseSettings):
    """OpenTelemetry distributed tracing configuration settings."""

    model_config = SettingsConfigDict(env_prefix="OTEL_", extra="ignore", env_file=_ENV_FILE)

    enabled: bool = True
    service_name: str = "socraticai"
    service_version: str = "1.0.0"
    environment: str = "development"
    otlp_endpoint: str | None = None
    debug_console: bool = False


class MetricsSettings(BaseSettings):
    """Prometheus metrics configuration settings."""

    model_config = SettingsConfigDict(env_prefix="METRICS_", extra="ignore", env_file=_ENV_FILE)

    enabled: bool = True
    endpoint: str = "/metrics"


class Settings(BaseSettings):
    """Aggregate settings object injected across the whole application."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    app: AppSettings = Field(default_factory=AppSettings)
    llm: LLMSettings = Field(default_factory=LLMSettings)
    database: DatabaseSettings = Field(default_factory=DatabaseSettings)
    vector_store: VectorStoreSettings = Field(default_factory=VectorStoreSettings)
    api: ApiSettings = Field(default_factory=ApiSettings)
    auth: AuthSettings = Field(default_factory=AuthSettings)
    logging: LoggingSettings = Field(default_factory=LoggingSettings)
    frontend: FrontendSettings = Field(default_factory=FrontendSettings)
    conversation: ConversationSettings = Field(default_factory=ConversationSettings)
    memory: MemorySettings = Field(default_factory=MemorySettings)
    routing: RoutingSettings = Field(default_factory=RoutingSettings)
    cache: CachingSettings = Field(default_factory=CachingSettings)
    context: ContextBudgetSettings = Field(default_factory=ContextBudgetSettings)
    chunking: ChunkingSettings = Field(default_factory=ChunkingSettings)
    bm25: BM25Settings = Field(default_factory=BM25Settings)
    hybrid: HybridRetrievalSettings = Field(default_factory=HybridRetrievalSettings)
    reranker: RerankerSettings = Field(default_factory=RerankerSettings)
    decision: DecisionModelSettings = Field(default_factory=DecisionModelSettings)
    citation: CitationSettings = Field(default_factory=CitationSettings)
    query_rewrite: QueryRewritingSettings = Field(default_factory=QueryRewritingSettings)
    tutoring: TutoringSettings = Field(default_factory=TutoringSettings)
    mastery: MasterySettings = Field(default_factory=MasterySettings)
    assessment: AssessmentSettings = Field(default_factory=AssessmentSettings)
    recommendation: AdaptiveRecommendationSettings = Field(
        default_factory=AdaptiveRecommendationSettings
    )
    adaptive_recommendation: AdaptiveRecommendationSettings = Field(
        default_factory=AdaptiveRecommendationSettings
    )
    misconception: MisconceptionSettings = Field(default_factory=MisconceptionSettings)
    pii: PIISettings = Field(default_factory=PIISettings)
    guardrails: GuardrailsSettings = Field(default_factory=GuardrailsSettings)
    tensorzero: TensorZeroSettings = Field(default_factory=TensorZeroSettings)
    telemetry: TelemetrySettings = Field(default_factory=TelemetrySettings)
    metrics: MetricsSettings = Field(default_factory=MetricsSettings)
    prompts_dir: Path = Field(default_factory=lambda: _PROJECT_ROOT / "configs" / "prompts")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the process-wide ``Settings`` instance (cached)."""
    return Settings()
