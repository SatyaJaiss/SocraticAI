FROM python:3.11-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app

# Install uv for fast, reliable dependency resolution
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./
RUN uv pip install --system --no-cache streamlit httpx pandas plotly

COPY apps/frontend ./apps/frontend
COPY .streamlit ./.streamlit

EXPOSE 8501

CMD ["streamlit", "run", "apps/frontend/app.py", "--server.port", "8501", "--server.address", "0.0.0.0"]
