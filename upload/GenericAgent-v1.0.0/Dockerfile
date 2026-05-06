# ══════════════════════════════════════════════════════════════════════════════
#  GenericAgent — Dockerfile for headless deployment
#  Build:   docker build -t genericagent .
#  Run:     docker run -e LLM_API_KEY=sk-... genericagent
# ══════════════════════════════════════════════════════════════════════════════

FROM python:3.12-slim AS base

# ── Metadata ────────────────────────────────────────────────────────────────
LABEL maintainer="GenericAgent Team"
LABEL description="GenericAgent — Self-evolving autonomous agent framework"
LABEL org.opencontainers.image.source="https://github.com/genericagent/genericagent"

# ── System dependencies ─────────────────────────────────────────────────────
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
       curl \
    && rm -rf /var/lib/apt/lists/*

# ── Working directory ───────────────────────────────────────────────────────
WORKDIR /app

# ── Install Python dependencies first (layer caching) ───────────────────────
COPY pyproject.toml ./
RUN pip install --no-cache-dir --upgrade pip setuptools wheel \
    && pip install --no-cache-dir .

# ── Copy project source ─────────────────────────────────────────────────────
COPY . .

# ── Re-install in editable mode to pick up all source files ─────────────────
RUN pip install --no-cache-dir -e .

# ── Create workspace directory ──────────────────────────────────────────────
RUN mkdir -p /app/workspace

# ── Expose API server port ───────────────────────────────────────────────
EXPOSE 8765

# ── Health check ────────────────────────────────────────────────────────────
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8765/status || exit 1

# ── Default environment ─────────────────────────────────────────────────────
ENV LOG_LEVEL=INFO
ENV AGENT_WORKSPACE_DIR=/app/workspace

# ── Entrypoint ──────────────────────────────────────────────────────────────
# GA_MODE=server → start the FastAPI server (default for Docker)
# GA_MODE=cli    → start the interactive CLI REPL
ENV GA_MODE=server
ENTRYPOINT ["sh", "-c", "if [ \"$GA_MODE\" = \"cli\" ]; then\n  exec python -m agentmain\nelse\n  exec python -c \"from server import run_server; run_server()\"\nfi"]
