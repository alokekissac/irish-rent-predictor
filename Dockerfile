FROM python:3.12-slim

COPY --from=ghcr.io/astral-sh/uv:0.12 /uv /uvx /bin/
RUN apt-get update && apt-get install -y --no-install-recommends libgomp1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PATH="/app/.venv/bin:$PATH" \
    MLFLOW_DISABLE_AGENT_HINT=1 \
    RENTCAST_DATA_DIR=/app/data \
    RENTCAST_MODEL_DIR=/app/models \
    RENTCAST_REPORTS_DIR=/app/reports

# Dependencies first so they cache across code changes
COPY pyproject.toml uv.lock README.md ./
RUN uv sync --locked --no-dev --no-install-project
COPY src ./src
RUN uv sync --locked --no-dev

COPY dashboard ./dashboard
COPY .streamlit ./.streamlit
COPY data/processed ./data/processed
COPY models ./models
COPY reports ./reports

RUN useradd --create-home app && chown -R app /app
USER app

EXPOSE 8000 8501
HEALTHCHECK --interval=30s --timeout=5s CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1
CMD ["uvicorn", "rentcast.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
