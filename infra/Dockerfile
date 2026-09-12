# Tebaki engine container — deployable to Bedrock AgentCore Runtime or any container host.
#
# AgentCore Runtime invokes the entrypoint with a runtime session endpoint +
# bearer token as arguments. The Strands AgentCore adapter handles that
# protocol; in plain-container mode (ECS/Fargate/local) the same image runs
# uvicorn directly.

FROM python:3.12-slim

WORKDIR /app

# system deps for uv (fast installs)
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# engine files; README next to pyproject so hatchling resolves it
COPY engine/pyproject.toml ./engine/
COPY engine/app ./engine/app
COPY README.md ./engine/README.md
COPY cities ./cities
COPY cli ./cli
COPY sandbox-portal ./sandbox-portal

WORKDIR /app/engine
# slim install: no uv cache, no bytecode, tests stripped
ENV UV_NO_CACHE=1 PYTHONDONTWRITEBYTECODE=1
RUN uv venv /app/.venv \
    && uv pip install --python /app/.venv/bin/python -e . --no-progress \
    && find /app/.venv -depth -type d -name "tests" -exec rm -rf {} + 2>/dev/null; \
    find /app/.venv -depth -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null; \
    find /app/.venv -name "*.pyc" -delete 2>/dev/null; true

WORKDIR /app
ENV PYTHONPATH=/app/engine:/app/sandbox-portal \
    PATH="/app/.venv/bin:$PATH" \
    TEBAKI_CITIES_DIR=/app/cities \
    PYTHONDONTWRITEBYTECODE=1

# default: plain HTTP server (ECS/Fargate/local). AgentCore overrides the
# entrypoint args at deploy time for the runtime protocol.
EXPOSE 8080
CMD ["python", "-m", "uvicorn", "app.api.main:app", "--host", "0.0.0.0", "--port", "8080"]
