FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y git curl sqlite3 procps && rm -rf /var/lib/apt/lists/*

# Install python dependencies for Agent OS, LangGraph, and HTTP Gateway
RUN pip install --no-cache-dir langchain langchain-openai langgraph fastapi uvicorn pydantic httpx pyyaml

COPY . /app

# Expose HTTP Gateway (8000) and AgentMemory / services ports
EXPOSE 8000 3111 8005

# Healthcheck on HTTP Gateway
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD curl -f http://localhost:8000/healthz || exit 1

# Start autonomous watchdog and services
CMD ["python3", "scripts/watchdog.py", "daemon"]
