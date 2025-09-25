# Dockerfile
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# System deps (tini for clean signals; curl for health checks if needed)
RUN apt-get update && apt-get install -y --no-install-recommends \
    tini ca-certificates curl && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy only what we need first (better layer caching)
COPY src /app/src
COPY pyproject.toml /app/      # optional; not required for pip install below
COPY .env.example /app/.env.example

# Install Python deps (no uv; keep it simple)
RUN pip install --no-cache-dir \
      fastmcp>=2.0.0 \
      httpx>=0.27 \
      pydantic>=2.8 \
      python-dotenv>=1.0

EXPOSE 3333
ENTRYPOINT ["/usr/bin/tini", "--"]
CMD ["python", "-m", "src.server"]
