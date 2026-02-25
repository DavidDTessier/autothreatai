# Build and run any single ADK agent. Use with build-arg AGENT_NAME or override at runtime.
# Expects build context = project root (docker build -f agents/Dockerfile .)
ARG PYTHON_VERSION=3.14
FROM python:${PYTHON_VERSION}-slim-bookworm

RUN apt-get update && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/* \
    && curl -LsSf https://astral.sh/uv/install.sh | sh \
    && mv /root/.local/bin/uv /usr/local/bin/uv

WORKDIR /app

# Install deps from lock so build is reproducible
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

# Full project (agents, shared, app for wrapper output)
COPY agents ./agents
COPY shared ./shared
COPY app ./app

COPY agents/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]
