# SocraticAI — Proposed Target Architecture Specification

**Author:** Senior AI Engineer & LLM Systems Architect  
**Date:** November 2026  
**Status:** Target Architectural Specification (Phase 2)  
**Target Codebase:** [SocraticAI Repository](file:///d:/ML/EduAgent-master)

---

## 1. System Topology & Architectural Principles

The proposed architecture evolves SocraticAI from a synchronous, single-turn lecture platform into an enterprise-grade, stateful, multi-agent AI tutoring system.

### Core Architectural Principles
1. **True Socratic Interaction:** Pedagogical turns transition from passive lecture dumps to multi-turn guided inquiries that prompt critical thinking.
2. **Stateful Checkpointed Workflows:** Workflows maintain full conversational state across turns using persistent LangGraph checkpointers.
3. **Strict Multi-Tenant Isolation:** Vector indices and relational databases enforce multi-tenancy at the query level, preventing data cross-contamination.
4. **Resilient Hybrid Retrieval:** RAG combines dense semantic vectors with sparse BM25 keyword matching and cross-encoder reranking.
5. **Decoupled Asynchronous Processing:** Heavy operations (PDF extraction, embedding generation, memory consolidation) execute in background workers.

```mermaid
flowchart TD
    subgraph Clients["Presentation Tier"]
        UI_Web["Web App (Next.js / Streamlit)"]
        Mobile["Mobile / Responsive UI"]
    end

    subgraph Gateway["API & Security Boundary"]
        ReverseProxy["Reverse Proxy (Nginx / Caddy)"]
        AuthMiddleware["JWT Authentication & Rate Limiting"]
    end

    subgraph BackendApp["FastAPI Application Server"]
        Router["Versioned API Routers (/api/v1)"]
        DI["Dependency Injection Container"]
        
        subgraph GraphOrchestration["LangGraph Multi-Agent Engine (Compiled Singleton)"]
            Checkpointer[("State Checkpointer\n(SQLite / Redis / Postgres)")]
            StateEngine["SocraticAIState Engine"]
            
            subgraph AgentNodes["Specialized Agent Nodes"]
                Planner["Planner & Query Reformulator"]
                RAGNode["Hybrid RAG Coordinator"]
                SocraticTutor["Socratic Dialogue Agent"]
                QuizEngine["Adaptive Quiz Agent"]
                Evaluator["Deterministic & LLM Evaluator"]
                MemoryConsolidator["Memory Consolidation Agent"]
                Recommender["Curriculum Recommender"]
            end
        end
    end

    subgraph RAGSubsystem["Hybrid RAG Subsystem"]
        BM25Retriever["BM25 Sparse Search"]
        DenseRetriever["Dense Vector Retriever"]
        RRF["Reciprocal Rank Fusion (RRF)"]
        Reranker["Cross-Encoder Reranker"]
    end

    subgraph StorageTier["Data & Persistence Tier"]
        RelationalDB[("PostgreSQL / SQLite\nStudents, Quizzes, Transcripts")]
        VectorStore[("ChromaDB / Qdrant\n(Isolated by student_id)")]
        CacheQueue[("Redis\nCache, Session Lock, Task Queue")]
        FileStore[("Object Storage / S3\nDocument Uploads")]
    end

    UI_Web --> ReverseProxy
    Mobile --> ReverseProxy
    ReverseProxy --> AuthMiddleware
    AuthMiddleware --> Router
    Router --> DI
    DI --> GraphOrchestration
    
    GraphOrchestration <--> Checkpointer
    StateEngine --> AgentNodes
    
    RAGNode --> RAGSubsystem
    RAGSubsystem --> VectorStore
    RAGSubsystem --> BM25Retriever
    RAGSubsystem --> DenseRetriever
    DenseRetriever --> RRF
    BM25Retriever --> RRF
    RRF --> Reranker
    
    AgentNodes --> RelationalDB
    AgentNodes --> CacheQueue
    Router --> FileStore
```

---

## 2. Advanced Multi-Agent Orchestration & Socratic Dialogue State Machine

### 2.1 Compiled Singleton Workflow with Persistent Checkpointing
Rather than recompiling the LangGraph workflow on every HTTP request, the compiled graph is built once during application startup and cached as a process singleton. Per-turn execution is managed by passing `{"configurable": {"thread_id": session_id}}` to the LangGraph checkpointer.

```mermaid
stateDiagram-v2
    [*] --> Start
    Start --> PlannerNode: User message & session_id
    
    state PlannerNode {
        [*] --> ClassifyIntent
        ClassifyIntent --> RewriteQuery: Multi-turn contextual query expansion
        RewriteQuery --> [*]
    }
    
    PlannerNode --> RouteChoice: route_decision
    
    RouteChoice --> RAGCoordinator: Intent in (learn, answer_question) AND has_docs
    RouteChoice --> SocraticDialogue: Intent in (learn, answer_question) AND no_docs
    RouteChoice --> QuizGenerator: Intent == practice
    RouteChoice --> DirectChat: Intent == general
    
    RAGCoordinator --> SocraticDialogue: Augmented with grounded chunks & citations
    
    state SocraticDialogue {
        [*] --> AnalyzeStudentInput
        AnalyzeStudentInput --> ProbingQuestion: Concept partially understood
        AnalyzeStudentInput --> ScaffoldingHint: Student stuck or misconception
        AnalyzeStudentInput --> DiscoveryCelebration: Student discovers correct concept
        ProbingQuestion --> [*]
        ScaffoldingHint --> [*]
        DiscoveryCelebration --> [*]
    }
    
    SocraticDialogue --> StreamResponse: Yield token stream to student
    QuizGenerator --> StreamResponse
    DirectChat --> StreamResponse
    
    StreamResponse --> AsyncMemoryQueue: Enqueue turn transcript
    AsyncMemoryQueue --> MemoryConsolidator: Background extraction & deduplication
    MemoryConsolidator --> CheckpointState: Save persistent memory facts
    CheckpointState --> [*]
```

### 2.2 Socratic Dialogue Scaffolding Engine
Instead of emitting complete answers, the `SocraticDialogueAgent` uses a dynamic pedagogical state machine:

| Scaffolding Stage | Pedagogical Goal | Prompt Strategy | Example Tutor Output |
| :--- | :--- | :--- | :--- |
| **Stage 1: Elicitation** | Probe the student's existing intuition. | Ask what they already know about the topic. | *"Before we look at the formula, how do you think plants get energy when there is no food around them?"* |
| **Stage 2: Guided Inquiry** | Point out contradictions or misconceptions. | Present a relatable counter-example. | *"If plants absorbed all green light, what color would their leaves look to our eyes?"* |
| **Stage 3: Scaffolding** | Provide intermediate clues when stuck. | Break problem into smaller steps with hints. | *"Think about what happens to water ($H_2O$) when sunlight splits it. What gas gets released?"* |
| **Stage 4: Synthesis** | Prompt the student to summarize the core rule. | Ask the student to state the principle in their own words. | *"Spot on! Can you summarize the two main stages of photosynthesis in your own words?"* |

---

## 3. Production Hybrid RAG Pipeline Architecture

To achieve accurate grounding without cross-tenant data leaks or keyword blindness, the retrieval pipeline adopts **Tenant-Isolated Hybrid RAG with Cross-Encoder Reranking**.

```mermaid
flowchart LR
    subgraph QueryIngress["Query Processing"]
        RawQuery["Raw User Query\n'Wait, what does that formula mean?'"]
        History["Chat History Context"]
        Reformulator["Contextual Query Rewriter (LLM)"]
        CleanQuery["Standalone Query:\n'chemical equation for photosynthesis reactants products'"]
        RawQuery & History --> Reformulator
        Reformulator --> CleanQuery
    end

    subgraph ParallelRetrieval["Tenant-Isolated Parallel Retrieval"]
        DenseSearch["Dense Vector Search\n(ChromaDB / Qdrant)\nwhere={'student_id': id}"]
        SparseSearch["Sparse BM25 Search\n(Inverted Index)\nFiltered by student_id"]
    end

    subgraph FusionAndReranking["Fusion & Reranking"]
        RRFMerge["Reciprocal Rank Fusion (RRF)\nRRF(d) = Σ 1/(k + r_dense) + 1/(k + r_sparse)"]
        CrossEncoder["Cross-Encoder Reranker\n(bge-reranker-base / FlashRank)"]
        TopKContext["Top 3-4 High-Relevance Chunks\nwith Page & Document Citations"]
    end

    CleanQuery --> DenseSearch
    CleanQuery --> SparseSearch
    DenseSearch --> RRFMerge
    SparseSearch --> RRFMerge
    RRFMerge --> CrossEncoder
    CrossEncoder --> TopKContext
```

### 3.3 Multi-Tenant Document Ingestion Lifecycle
```mermaid
sequenceDiagram
    autonumber
    actor Student
    participant API as FastAPI /api/v1/documents
    participant Queue as Background Task Queue
    participant Chunker as Semantic Chunker
    participant Embedder as Local Embedding Provider
    participant Store as Vector Store & SQLite

    Student->>API: POST /documents/{student_id} (PDF/TXT)
    API->>API: Validate file size (<25MB) & MIME type
    API->>Store: Create Document row (status="PENDING")
    API->>Queue: Enqueue ingestion task (doc_id, path, student_id)
    API-->>Student: HTTP 202 Accepted {doc_id, status: "PROCESSING"}

    Queue->>Chunker: Extract pages & split with sentence boundary awareness
    Chunker->>Queue: Document chunks with {text, page, student_id, doc_id}
    Queue->>Embedder: Batch compute embeddings (32 chunks/batch)
    Embedder->>Store: Store chunks in ChromaDB with metadata filter tag
    Queue->>Store: Update Document row (status="COMPLETED", chunk_count=N)
    
    Student->>API: GET /documents/{student_id}
    API-->>Student: Document list with status="COMPLETED"
```

---

## 4. Two-Tier Student Memory & Concept Knowledge Graph

### 4.1 Memory Hierarchy
The student profile is upgraded from a flat list of text facts into a formal two-tier memory architecture:

1. **Short-Term Conversational Memory:** Managed by the LangGraph Checkpointer (`thread_id=session_id`), storing verbatim dialogue, agent outputs, and immediate conversational turn context.
2. **Long-Term Consolidated Semantic Memory:** A structured profile containing verified student traits, learning styles, goals, and detected misconceptions.
3. **Concept Mastery Knowledge Graph (DAG):** A structured directed acyclic graph mapping subject domains into discrete concepts with prerequisite edges.

```mermaid
graph TD
    subgraph ConceptDAG["Concept Knowledge Graph (Mathematics)"]
        Fractions["Fractions & Decimals"]
        LinearEq["Linear Equations"]
        QuadEq["Quadratic Equations"]
        Polynomials["Polynomial Functions"]
        Calculus["Differential Calculus"]

        Fractions --> LinearEq
        LinearEq --> QuadEq
        QuadEq --> Polynomials
        Polynomials --> Calculus
    end

    subgraph StudentMastery["Student Mastery Profile"]
        FractionsScore["Fractions: 92% (Mastered)"]
        LinearScore["Linear Equations: 88% (Mastered)"]
        QuadScore["Quadratic Equations: 42% (Struggling)"]
    end

    QuadScore -.->|Prerequisite Check: OK| LinearEq
    QuadScore -->|Diagnostic Path| DiagnosticQuiz["Generate Targeted Practice on Factoring Quad Equations"]
```

### 4.2 Spaced Repetition Memory Decay Algorithm (FSRS / SM-2)
Concept proficiency incorporates a time-decay factor $R(t) = e^{-\frac{t}{S}}$, where:
- $t$ is the elapsed time in days since the last quiz or practice session.
- $S$ is the concept stability factor, updated upon successful recall:
$$S_{new} = S_{prev} \cdot (1 + c \cdot \text{proficiency})$$
When retrieval probability $R(t)$ falls below $0.70$, the `RecommendationAgent` schedules an active recall prompt or short quiz item before new topics are introduced.

---

## 5. Evaluation & Quality Assurance Architecture

To ensure high pedagogical quality, zero hallucinations, and consistent quiz validity, an automated evaluation pipeline is integrated into continuous integration.

```mermaid
flowchart TD
    subgraph EvalTriggers["Evaluation Triggers"]
        PR["Pull Request / Code Change"]
        Weekly["Scheduled Quality Benchmark"]
    end

    subgraph Benchmarks["Benchmark Suites"]
        SyntheticCorpus["Curated 100-Turn Evaluation Corpus"]
        LiveServer["Hermetic Fast-API Container"]
    end

    subgraph MetricEngines["Evaluation Engines"]
        Ragas["Ragas RAG Evaluator\n- Faithfulness\n- Context Recall\n- Context Precision"]
        LLMJudge["LLM-as-a-Judge Pedagogy Evaluator\n- Socratic Scaffolding Index\n- Tone & Encouragement\n- Question Relevance"]
        QuizQuality["Quiz Engine Evaluator\n- Question Validity\n- Distractor Distinctness\n- Grading Determinism"]
    end

    subgraph Reporting["CI Quality Gate"]
        ThresholdCheck{"Assert Metrics >= Threshold:\nFaithfulness >= 0.92\nContext Precision >= 0.85\nScaffolding >= 0.80"}
        Pass["Pass CI Build"]
        Fail["Block PR with Forensic Report"]
    end

    PR & Weekly --> Benchmarks
    Benchmarks --> MetricEngines
    MetricEngines --> ThresholdCheck
    ThresholdCheck -->|Meets target| Pass
    ThresholdCheck -->|Below target| Fail
```

---

## 6. Backend Infrastructure & Production Scalability

```mermaid
flowchart LR
    subgraph Edge["Edge & Load Balancing"]
        DNS["Route 53 / Cloudflare"]
        ALB["Application Load Balancer"]
    end

    subgraph AppCluster["Application Cluster (Docker / ECS / K8s)"]
        Worker1["FastAPI Worker 1"]
        Worker2["FastAPI Worker 2"]
        WorkerN["FastAPI Worker N"]
    end

    subgraph AsyncCluster["Background Task Cluster"]
        CeleryWorker["Async Worker (Ingestion & Memory Consolidation)"]
    end

    subgraph DataServices["Managed Data Services"]
        Postgres[("Amazon RDS PostgreSQL\n(Application State & Transcripts)")]
        RedisCluster[("Redis Cluster\n(LangGraph Checkpoints & Task Queue)")]
        QdrantStore[("Qdrant / Chroma Cluster\n(Tenant-Partitioned Vectors)")]
        S3Bucket[("Amazon S3\n(Document Notes & PDF Storage)")]
    end

    DNS --> ALB
    ALB --> Worker1 & Worker2 & WorkerN
    Worker1 & Worker2 & WorkerN <--> RedisCluster
    Worker1 & Worker2 & WorkerN --> Postgres
    Worker1 & Worker2 & WorkerN --> QdrantStore
    Worker1 & Worker2 & WorkerN --> S3Bucket
    Worker1 & Worker2 & WorkerN --> CeleryWorker
    CeleryWorker --> QdrantStore
    CeleryWorker --> Postgres
```

---

## 7. End-to-End Chat Data Flow

```mermaid
sequenceDiagram
    autonumber
    actor Student
    participant UI as Frontend (Streamlit / Next.js)
    participant API as FastAPI /api/v1/chat
    participant Graph as Compiled Socratic Graph
    participant RAG as Hybrid RAG Subsystem
    participant LLM as LLM Provider (OpenAI / Gemini)
    participant Checkpoint as State Checkpointer

    Student->>UI: Types "Why does sunlight split water in plants?"
    UI->>API: POST /chat {student_id, session_id, message}
    API->>Checkpoint: Load turn history for session_id
    Checkpoint-->>API: Restored SocraticAIState with previous turns
    
    API->>Graph: ainvoke(state, config={"thread_id": session_id})
    Graph->>Graph: PlannerAgent rewrites query & classifies intent (learn)
    
    alt Student has uploaded notes
        Graph->>RAG: Retrieve chunks (query, student_id)
        RAG-->>Graph: Return top-3 reranked chunks with citations
    end

    Graph->>LLM: SocraticDialogueAgent prompts with scaffolding instructions
    LLM-->>Graph: Socratic response with probing question & citation
    
    Graph->>Checkpoint: Save updated state (messages, turn metrics)
    Graph-->>API: Yield final turn response
    API-->>UI: Stream/render response with citations & follow-up question
    UI-->>Student: Displays answer with interactive Socratic prompt
```
