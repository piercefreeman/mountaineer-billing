FROM python:3.12-slim AS python-base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_LINK_MODE=copy

WORKDIR /workspace

RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates \
    && rm -rf /var/lib/apt/lists/* \
    && pip install --no-cache-dir uv

COPY pyproject.toml README.md /workspace/
COPY mountaineer_billing /workspace/mountaineer_billing
COPY integration-runner /workspace/integration-runner

RUN uv sync --project integration-runner --locked


FROM python-base AS app-server


FROM python-base AS daemon


FROM mcr.microsoft.com/playwright/python:v1.58.0-noble AS runner

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_LINK_MODE=copy

WORKDIR /workspace

RUN apt-get update \
    && apt-get install -y --no-install-recommends xauth xvfb \
    && rm -rf /var/lib/apt/lists/* \
    && pip install --no-cache-dir uv

COPY pyproject.toml README.md /workspace/
COPY mountaineer_billing /workspace/mountaineer_billing
COPY integration-runner /workspace/integration-runner

RUN uv sync --project integration-runner --locked
