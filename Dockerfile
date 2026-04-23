# syntax=docker/dockerfile:1

ARG PYTHON_VERSION=3.12

# --- Build: dependencies via uv (reproducible from uv.lock) ---
FROM python:${PYTHON_VERSION}-slim-bookworm AS builder

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never

WORKDIR /app

COPY pyproject.toml uv.lock README.md ./
COPY nanobanana_mcp_server ./nanobanana_mcp_server

# 1) Lockfile dependencies only (exclude the local project), 2) install the project as a regular wheel into site-packages.
# (`--no-editable` alone is not always reliable across uv versions/backends when copying only `.venv` in multi-stage builds.)
RUN uv sync --frozen --no-dev --no-install-project \
    && uv pip install --no-cache-dir .

# --- Runtime: slim image, non-root user ---
FROM python:${PYTHON_VERSION}-slim-bookworm

RUN useradd --create-home --uid 1000 --shell /usr/sbin/nologin app \
    && mkdir -p /app/data/images \
    && chown -R app:app /app

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/app/.venv/bin:$PATH" \
    IMAGE_OUTPUT_DIR=/app/data/images \
    FASTMCP_TRANSPORT=http \
    FASTMCP_HOST=0.0.0.0 \
    FASTMCP_PORT=9000

COPY --from=builder --chown=app:app /app/.venv /app/.venv

USER app

EXPOSE 9000

HEALTHCHECK --interval=30s --timeout=3s --start-period=20s --retries=3 \
    CMD python -c "import os,urllib.request; p=os.environ.get('FASTMCP_PORT','9000'); urllib.request.urlopen(f'http://127.0.0.1:{p}/healthz', timeout=2)"

CMD ["nanobanana-mcp-server"]
