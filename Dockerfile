# Dockerfile
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# minimal OS deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    tini ca-certificates curl build-essential && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

# --- install uv and put it on PATH ---
RUN curl -LsSf https://astral.sh/uv/install.sh | sh
ENV PATH="/root/.local/bin:${PATH}"

# Copy project files (pyproject first for better layer caching)
COPY pyproject.toml /app/pyproject.toml
# If you have a README used by packaging, copy it too:
# COPY README.md /app/README.md

# Copy source
COPY src /app/src
# (optional) env example for reference
COPY .env.example /app/.env.example

# --- install project deps with uv using your pyproject ---
# -e . = editable install (so src code paths work)
RUN uv pip install --system --no-cache-dir -e .

EXPOSE 3333
ENTRYPOINT ["/usr/bin/tini", "--"]
CMD ["python", "-m", "src.server"]
