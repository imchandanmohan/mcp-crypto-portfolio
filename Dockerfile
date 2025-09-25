# Faster/lean Python base
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# system deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    tini curl ca-certificates && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

# copy project
COPY pyproject.toml /app/
COPY src /app/src
COPY .env.example /app/.env.example

# install uv (fast Python package manager)
RUN curl -LsSf https://astral.sh/uv/install.sh | sh && \
    /root/.cargo/bin/uv pip install --system --no-cache-dir \
      "fastmcp>=2.0.0" "httpx>=0.27" "pydantic>=2.8" "python-dotenv>=1.0"

# expose FastMCP port
EXPOSE 3333
ENTRYPOINT ["/usr/bin/tini", "--"]
CMD ["python", "-m", "src.server"]
