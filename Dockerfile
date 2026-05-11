FROM python:3.12-slim

WORKDIR /app

# System deps for grpc + crypto
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential libssl-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY agents/ ./agents/
COPY prompts/ ./prompts/
COPY data/ ./data/

ENV PYTHONUNBUFFERED=1
ENV PORT=8080
ENV GOOGLE_GENAI_USE_VERTEXAI=true
ENV GOOGLE_CLOUD_PROJECT=predictive-fx-495200-j4

EXPOSE 8080

CMD exec uvicorn agents.runtime:app --host 0.0.0.0 --port $PORT --workers 1
