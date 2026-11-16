# SocraticAI — Configuration Reference

## Centralized, Typed Application Settings & Environment Variables

**Document Version:** 1.0.0  
**Source Module:** [`apps/backend/app/core/config.py`](file:///d:/ML/EduAgent-master/apps/backend/app/core/config.py)  
**Template File:** [`.env.example`](file:///d:/ML/EduAgent-master/.env.example)

---

## 1. Overview

SocraticAI utilizes Pydantic `BaseSettings` models to enforce strict typing, validation, default fallbacks, and zero-magic-number configuration. Settings are hierarchically grouped into specialized sub-models and mounted under the primary `Settings` class.

All variables can be overridden using environment variables or a `.env` file at the repository root.

---

## 2. Configuration Settings Catalog

### 2.1 Core Application & Security Settings

| Variable Name | Type | Default Value | Description | Subsystem |
|---|---|---|---|---|
| `APP_NAME` | `str` | `SocraticAI` | Canonical display name of the application. | Global / Logging |
| `APP_ENV` | `str` | `development` | Deployment environment: `development`, `testing`, `production`. | Global |
| `DEBUG` | `bool` | `false` | Enables verbose stack traces and reloaders. | Global |
| `LOG_LEVEL` | `str` | `INFO` | Logging threshold: `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL`. | Core Logging |
| `SECRET_KEY` | `str` | `insecure-dev-secret-key...` | Cryptographic secret for signing JWT access tokens (min 32 chars). | Auth & Security |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `int` | `1440` (24h) | JWT access token expiration duration in minutes. | Auth & Security |
| `PASSWORD_MIN_LENGTH` | `int` | `8` | Minimum password length for student registration. | Auth & Security |

---

### 2.2 Conversational & History Settings (`ConversationSettings`)

| Variable Name | Type | Default Value | Description | Subsystem |
|---|---|---|---|---|
| `CONVERSATION_WORKING_MEMORY_TURNS` | `int` | `10` | Number of recent user/assistant turns (20 messages) loaded into working memory. | Working Memory |
| `CONVERSATION_MAX_HISTORY_MESSAGES` | `int` | `50` | Hard upper limit on dialogue messages retrieved during deep history review. | Working Memory |
| `CONVERSATION_SESSION_IDLE_TIMEOUT_MINUTES` | `int` | `60` | Inactivity threshold before a dialogue session is considered inactive. | Session Management |
| `CONVERSATION_CONSOLIDATE_THRESHOLD_TURNS` | `int` | `10` | Number of dialogue turns between automatic episodic consolidation triggers. | Memory Consolidation |

---

### 2.3 Memory Subsystem Settings (`MemorySettings`)

| Variable Name | Type | Default Value | Description | Subsystem |
|---|---|---|---|---|
| `MEMORY_EPISODIC_ENABLED` | `bool` | `true` | Enables cross-session episodic memory persistence and vector indexing. | Episodic Memory |
| `MEMORY_SEMANTIC_ENABLED` | `bool` | `true` | Enables longitudinal concept score tracking and misconception detection. | Semantic Memory |
| `MEMORY_EPISODIC_RETRIEVAL_LIMIT` | `int` | `5` | Maximum number of episodic memories retrieved per context build. | Episodic Memory |
| `MEMORY_EPISODIC_SIMILARITY_THRESHOLD` | `float` | `0.6` | Minimum cosine similarity required to inject an episodic memory. | Episodic Memory |
| `MEMORY_EPISODIC_DECAY_HALF_LIFE_DAYS` | `float` | `30.0` | Exponential temporal decay half-life in days for episodic importance weighting. | Episodic Memory |
| `MEMORY_EMA_ALPHA` | `float` | `0.3` | Alpha weighting factor for Exponential Moving Average of concept proficiency. | Semantic Memory |
| `MEMORY_CHROMA_COLLECTION` | `str` | `socraticai_episodic_memory` | ChromaDB collection name for storing episodic memory embeddings. | Vector Storage |

---

### 2.4 Intent Classification & Routing Settings (`RoutingSettings`)

| Variable Name | Type | Default Value | Description | Subsystem |
|---|---|---|---|---|
| `ROUTING_PROVIDER` | `str` | `jev` | Primary intent routing engine: `jev`, `deterministic`. | Routing Engine |
| `TYPESAFE_API_KEY` | `str` | `""` | API key for TypeSafe AI Jev System One classification. | Jev Client |
| `TYPESAFE_ENDPOINT` | `str` | `https://api.typesafe.ai/v1/decisions` | API endpoint URL for Jev System One decisions. | Jev Client |
| `ROUTING_FALLBACK_ON_ERROR` | `bool` | `true` | Automatically failover to deterministic pattern classifier if Jev fails. | Router Failover |
| `ROUTING_CONFIDENCE_THRESHOLD` | `float` | `0.65` | Confidence score below which the router activates deterministic fallback. | Intent Router |
| `ROUTING_JEV_TIMEOUT_SECONDS` | `float` | `3.0` | HTTP client timeout in seconds for Jev decision requests. | Jev Client |
| `ROUTING_MAX_RETRIES` | `int` | `2` | Number of retry attempts on network error when calling Jev. | Jev Client |

---

### 2.5 Multi-Tier Caching Settings (`CachingSettings`)

| Variable Name | Type | Default Value | Description | Subsystem |
|---|---|---|---|---|
| `CACHING_ENABLED` | `bool` | `true` | Global switch enabling or disabling all caching layers. | Caching System |
| `CACHE_EMBEDDING_MAX_SIZE` | `int` | `50000` | Maximum number of text embedding vectors stored in memory. | Embedding Cache |
| `CACHE_EMBEDDING_TTL` | `int` | `86400` (24h) | Time-To-Live in seconds for cached embedding vectors. | Embedding Cache |
| `CACHE_RETRIEVAL_MAX_SIZE` | `int` | `5000` | Maximum number of top-$k$ retrieved chunk queries stored in memory. | Retrieval Cache |
| `CACHE_RETRIEVAL_TTL` | `int` | `3600` (1h) | Time-To-Live in seconds for cached document chunk retrievals. | Retrieval Cache |
| `CACHE_RESPONSE_MAX_SIZE` | `int` | `2000` | Maximum number of deterministic agent responses stored in memory. | Response Cache |
| `CACHE_RESPONSE_TTL` | `int` | `1800` (30m) | Time-To-Live in seconds for cached deterministic responses. | Response Cache |

---

### 2.6 Token Budget Settings (`ContextBudgetSettings`)

| Variable Name | Type | Default Value | Description | Subsystem |
|---|---|---|---|---|
| `CONTEXT_TOTAL_BUDGET` | `int` | `4000` | Total maximum token budget for prompt context assembly. | ContextBuilder |
| `CONTEXT_SYSTEM_PROMPT_BUDGET` | `int` | `500` | Token allocation reserved for static persona instructions. | ContextBuilder |
| `CONTEXT_SEMANTIC_PROFILE_BUDGET` | `int` | `400` | Token allocation reserved for student mastery scores and misconceptions. | ContextBuilder |
| `CONTEXT_EPISODIC_MEMORY_BUDGET` | `int` | `600` | Token allocation reserved for retrieved past session summaries. | ContextBuilder |
| `CONTEXT_RAG_CHUNKS_BUDGET` | `int` | `1500` | Token allocation reserved for retrieved syllabus/document excerpts. | ContextBuilder |
| `CONTEXT_WORKING_HISTORY_BUDGET` | `int` | `1000` | Token allocation reserved for recent conversation dialogue history. | ContextBuilder |
| `CONTEXT_ENCODING_MODEL` | `str` | `cl100k_base` | Tiktoken encoding tokenizer for calculating accurate token counts. | ContextBuilder |

---

### 2.7 Advanced Chunking & Ingestion Settings (`ChunkingSettings`)

| Variable Name | Type | Default Value | Description | Subsystem |
|---|---|---|---|---|
| `CHUNKING_CHUNK_SIZE` | `int` | `400` | Target token/character chunk size for section-aware splitting. | Chunker |
| `CHUNKING_OVERLAP_SIZE` | `int` | `60` | Token/character overlap between adjacent passage chunks. | Chunker |
| `CHUNKING_MIN_CHUNK_SIZE` | `int` | `50` | Minimum token threshold before a chunk is merged into its parent. | Chunker |
| `CHUNKING_PRESERVE_HEADINGS` | `bool` | `true` | Retain section headings and hierarchy in chunk metadata. | Chunker |
| `CHUNKING_MAX_HEADING_LEVEL` | `int` | `4` | Maximum Markdown/PDF heading depth tracked in section path. | Chunker |

---

### 2.8 BM25 Lexical Retrieval Settings (`BM25Settings`)

| Variable Name | Type | Default Value | Description | Subsystem |
|---|---|---|---|---|
| `BM25_ENABLED` | `bool` | `true` | Enables student-partitioned BM25Okapi lexical retrieval. | Lexical Index |
| `BM25_INDEX_DIR` | `str` | `data/bm25` | Directory path for disk-persisted student BM25 index files. | Storage |
| `BM25_K1` | `float` | `1.5` | BM25 term frequency saturation parameter. | Lexical Index |
| `BM25_B` | `float` | `0.75` | BM25 document length normalization parameter. | Lexical Index |
| `BM25_CANDIDATE_COUNT` | `int` | `20` | Number of candidate chunks retrieved during lexical ranking phase. | Retrieval Pipeline |

---

### 2.9 Hybrid Retrieval & Reciprocal Rank Fusion (`HybridRetrievalSettings`)

| Variable Name | Type | Default Value | Description | Subsystem |
|---|---|---|---|---|
| `HYBRID_ENABLED` | `bool` | `true` | Enables multi-modal Dense + BM25 Reciprocal Rank Fusion. | Hybrid Retriever |
| `HYBRID_DENSE_CANDIDATES` | `int` | `20` | Number of dense vector candidates retrieved from ChromaDB. | Vector Store |
| `HYBRID_BM25_CANDIDATES` | `int` | `20` | Number of lexical candidates retrieved from BM25 index. | Lexical Index |
| `HYBRID_RRF_K` | `int` | `60` | Reciprocal Rank Fusion constant denominator (1 / (k + rank)). | Fusion Algorithm |
| `HYBRID_FINAL_TOP_K` | `int` | `6` | Number of top fused candidates passed to reranking/grader. | Retrieval Pipeline |

---

### 2.10 Cross-Encoder Reranking Settings (`RerankerSettings`)

| Variable Name | Type | Default Value | Description | Subsystem |
|---|---|---|---|---|
| `RERANKER_ENABLED` | `bool` | `true` | Enables sentence-transformers Cross-Encoder reranking. | Reranker |
| `RERANKER_MODEL` | `str` | `cross-encoder/ms-marco-MiniLM-L-6-v2` | Hugging Face model identifier for cross-encoder reranking. | Reranker |
| `RERANKER_TOP_K` | `int` | `4` | Number of candidate passages retained after reranking. | Reranker |
| `RERANKER_MAX_CANDIDATES` | `int` | `16` | Maximum candidate pool size sent to cross-encoder model. | Reranker |
| `RERANKER_BATCH_SIZE` | `int` | `16` | Batch size for cross-encoder inference passes. | Reranker |
| `RERANKER_DEVICE` | `str` | `cpu` | Device for inference: `cpu`, `cuda`, or `mps`. | Reranker |

---

### 2.11 Decision Model Settings (`DecisionModelSettings`)

| Variable Name | Type | Default Value | Description | Subsystem |
|---|---|---|---|---|
| `DECISION_PROVIDER` | `str` | `jev` | Primary decision model provider: `jev`, `gemini`, `composite`, `disabled`. | Decision Engine |
| `DECISION_MODEL` | `str` | `jev-v1` | Model name / endpoint ID for decision evaluations. | Decision Engine |
| `DECISION_SHADOW_MODE` | `bool` | `false` | Run shadow provider in parallel without blocking primary decisions. | Reliability |
| `DECISION_SHADOW_PROVIDER` | `str` | `gemini` | Shadow provider invoked asynchronously during shadow runs. | Reliability |
| `DECISION_FALLBACK_PROVIDER` | `str` | `disabled` | Automatic failover provider if primary decision engine fails. | Reliability |
| `DECISION_TIMEOUT_SECONDS` | `float` | `5.0` | Max duration before decision call aborts or fails over. | Reliability |
| `GEMINI_API_KEY` | `str` | `""` | Google Gemini API key for `gemini-decision-1` provider. | Decision Engine |

---

### 2.12 Citation Generation & Verification Settings (`CitationSettings`)

| Variable Name | Type | Default Value | Description | Subsystem |
|---|---|---|---|---|
| `CITATION_ENABLED` | `bool` | `true` | Enables citation extraction and multi-stage verification pipeline. | Citation Pipeline |
| `CITATION_VERIFICATION_THRESHOLD` | `float` | `0.40` | Minimum token grounding support ratio required for claim validity. | Citation Verifier |
| `CITATION_MAX_CLAIMS_PER_VERIFICATION` | `int` | `8` | Upper bound on claims verified per tutor response turn. | Citation Verifier |
| `CITATION_STRICT_MODE` | `bool` | `false` | When true, rejects response if any single citation fails verification. | Citation Verifier |

---

### 2.13 Query Rewriting & Decomposition Settings (`QueryRewritingSettings`)

| Variable Name | Type | Default Value | Description | Subsystem |
|---|---|---|---|---|
| `QUERY_REWRITING_ENABLED` | `bool` | `true` | Strips conversational wrappers and decomposes comparative queries. | Query Processor |
| `QUERY_REWRITING_MAX_SUBQUERIES` | `int` | `3` | Maximum number of decomposed subqueries generated per prompt. | Query Processor |

---

## 3. Environment-Specific Configurations

### 3.1 Recommended `.env.development`
```env
APP_ENV=development
DEBUG=true
LOG_LEVEL=DEBUG
LLM_PROVIDER=demo
ROUTING_PROVIDER=deterministic
CACHING_ENABLED=true
DATABASE_URL=sqlite:///./socraticai_dev.db
```

### 3.2 Recommended `.env.production`
```env
APP_ENV=production
DEBUG=false
LOG_LEVEL=INFO
SECRET_KEY=generate-a-strong-random-64-character-secret-key-here!
LLM_PROVIDER=openai
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4o-mini
ROUTING_PROVIDER=jev
TYPESAFE_API_KEY=ts_live_...
ROUTING_FALLBACK_ON_ERROR=true
ROUTING_CONFIDENCE_THRESHOLD=0.70
CACHING_ENABLED=true
CACHE_EMBEDDING_MAX_SIZE=100000
CACHE_RETRIEVAL_MAX_SIZE=20000
DATABASE_URL=sqlite:///./socraticai_prod.db
```

