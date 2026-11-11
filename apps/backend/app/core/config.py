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

    model_config = SettingsConfigDict(
        env_prefix="APP_", extra="ignore", env_file=_ENV_FILE
    )

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

    model_config = SettingsConfigDict(
        env_prefix="LLM_", extra="ignore", env_file=_ENV_FILE
    )

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

    model_config = SettingsConfigDict(
        env_prefix="DATABASE_", extra="ignore", env_file=_ENV_FILE
    )

    url: str = "sqlite:///./data/socraticai.db"
    echo: bool = False
    create_on_startup: bool = True


class VectorStoreSettings(BaseSettings):
    """ChromaDB + embedding model settings."""

    model_config = SettingsConfigDict(
        env_prefix="VECTOR_", extra="ignore", env_file=_ENV_FILE
    )

    persist_directory: str = "./data/chroma"
    collection_name: str = "socraticai_notes"
    embedding_model: str = "all-MiniLM-L6-v2"
    chunk_size: int = 600
    chunk_overlap: int = 100
    top_k: int = 4


class ApiSettings(BaseSettings):
    """REST API surface settings."""

    model_config = SettingsConfigDict(
        env_prefix="API_", extra="ignore", env_file=_ENV_FILE
    )

    prefix: str = "/api/v1"
    upload_dir: str = "./data/uploads"
    pagination_default_size: int = 20
    max_upload_size_bytes: int = 25 * 1024 * 1024  # 25 MB


class AuthSettings(BaseSettings):
    """Authentication and JWT token configuration."""

    model_config = SettingsConfigDict(
        env_prefix="AUTH_", extra="ignore", env_file=_ENV_FILE
    )

    secret_key: str = "socraticai-dev-insecure-secret-key-32b-min!!"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 60 * 24  # 24 hours


class LoggingSettings(BaseSettings):
    """Centralised logging behaviour."""

    model_config = SettingsConfigDict(
        env_prefix="LOGGING_", extra="ignore", env_file=_ENV_FILE
    )

    level: str = "INFO"
    json_format: bool = False
    log_dir: str = "./logs"
    rotation_bytes: int = 5 * 1024 * 1024  # 5 MB
    backup_count: int = 3


class FrontendSettings(BaseSettings):
    """Where the Streamlit dashboard reaches the API."""

    model_config = SettingsConfigDict(
        env_prefix="FRONTEND_", extra="ignore", env_file=_ENV_FILE
    )

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

    model_config = SettingsConfigDict(
        env_prefix="MEMORY_", extra="ignore", env_file=_ENV_FILE
    )

    episodic_collection_name: str = "socraticai_episodic_memory"
    episodic_top_k: int = 4
    memory_similarity_threshold: float = 0.55
    max_memory_context_tokens: int = 600
    consolidation_message_trigger: int = 10
    concept_ema_alpha: float = 0.6


class RoutingSettings(BaseSettings):
    """Jev (TypeSafe AI) and deterministic routing configuration."""

    model_config = SettingsConfigDict(
        env_prefix="ROUTING_", extra="ignore", env_file=_ENV_FILE
    )

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

    model_config = SettingsConfigDict(
        env_prefix="CACHE_", extra="ignore", env_file=_ENV_FILE
    )

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

    model_config = SettingsConfigDict(
        env_prefix="CONTEXT_", extra="ignore", env_file=_ENV_FILE
    )

    total_budget: int = 4000
    system_prompt_budget: int = 600
    history_budget: int = 1500
    episodic_memory_budget: int = 600
    semantic_profile_budget: int = 400
    rag_budget: int = 900
    tokenizer_encoding: str = "cl100k_base"


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
    prompts_dir: Path = Field(default_factory=lambda: _PROJECT_ROOT / "configs" / "prompts")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the process-wide ``Settings`` instance (cached)."""
    return Settings()
