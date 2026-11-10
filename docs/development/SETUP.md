# SocraticAI — Local Development Setup Guide

This guide walks you through setting up, configuring, and running SocraticAI locally.

---

## 1. Prerequisites

- **Python**: 3.11 or higher (Python 3.11 or 3.12 recommended).
- **Package Manager**: [uv](https://docs.astral.sh/uv/) (strongly recommended) or standard `pip` + `venv`.
- **Git**: For version control.
- **Docker & Docker Compose**: (Optional) For running containerized services.

---

## 2. Environment Setup

### 2.1 Using `uv` (Recommended)

1. Clone or navigate to the repository root:
   ```bash
   cd SocraticAI
   ```

2. Create a virtual environment with Python 3.11+:
   ```bash
   uv venv
   ```

3. Activate the virtual environment:
   - **Linux / macOS**:
     ```bash
     source .venv/bin/activate
     ```
   - **Windows (PowerShell)**:
     ```powershell
     .venv\Scripts\Activate.ps1
     ```

4. Install dependencies (including development and testing tools):
   ```bash
   uv pip install -r requirements-dev.txt
   ```

### 2.2 Using Standard `pip`

```bash
python -m venv .venv
source .venv/bin/activate  # Or .venv\Scripts\activate on Windows
pip install --upgrade pip
pip install -r requirements-dev.txt
```

---

## 3. Configuration

SocraticAI reads its configuration from environment variables or a local `.env` file located at the project root.

1. Copy the example environment file:
   ```bash
   cp .env.example .env
   ```
   *(On Windows PowerShell: `Copy-Item .env.example .env`)*

2. Configure your environment:
   - **Offline Demo Mode (Default / No API Keys Required):**
     ```env
     LLM_PROVIDER=demo
     DATABASE_URL=sqlite:///./data/edueagent.db
     VECTOR_PERSIST_DIRECTORY=./data/chroma
     ```
     *This allows full application testing, chat, quizzes, and RAG without incurring API costs or requiring external network calls.*

   - **OpenAI Integration:**
     ```env
     LLM_PROVIDER=openai
     LLM_OPENAI_API_KEY=sk-...
     LLM_OPENAI_MODEL=gpt-4o-mini
     ```

   - **Google Gemini Integration:**
     ```env
     LLM_PROVIDER=gemini
     LLM_GEMINI_API_KEY=AIza...
     LLM_GEMINI_MODEL=gemini-1.5-flash
     ```

3. Initialize the database schema:
   ```bash
   python scripts/migration/init_db.py
   ```

---

## 4. Running the Application

### 4.1 Running the Backend API

Start the FastAPI application with hot reload:

```bash
# Using Make:
make run-backend

# Or directly with Uvicorn:
uv run uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload --app-dir apps/backend
```

- **API Base URL**: `http://localhost:8000/api/v1`
- **Swagger Documentation**: `http://localhost:8000/docs`
- **ReDoc Documentation**: `http://localhost:8000/redoc`
- **Health Check**: `http://localhost:8000/api/v1/health`

### 4.2 Running the Frontend UI

In a separate terminal window:

```bash
# Using Make:
make run-frontend

# Or directly with Streamlit:
uv run streamlit run apps/frontend/app.py --server.port 8501
```

- **Frontend URL**: `http://localhost:8501`

---

## 5. End-to-End Subsystem Verification

You can run the automated verification script to confirm that all subsystems (database, RAG chunking, LLM provider, LangGraph workflows, and prompt loader) initialize properly:

```bash
make verify
# Or:
uv run python scripts/development/e2e_verify.py
```

---

## 6. Running with Docker Compose

To run both backend and frontend as containerized services:

```bash
docker compose up --build
```

- Backend will be available at `http://localhost:8000`
- Frontend will be available at `http://localhost:8501`
- SQLite database and ChromaDB vectors persist in `./data/`
- Logs persist in `./logs/`

To shut down:
```bash
docker compose down
```

