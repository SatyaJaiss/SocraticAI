FROM python:3.11-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./
RUN pip install --no-cache-dir streamlit httpx pandas plotly

COPY apps/frontend ./apps/frontend

EXPOSE 8501

CMD ["streamlit", "run", "apps/frontend/app.py", "--server.port", "8501", "--server.address", "0.0.0.0"]

