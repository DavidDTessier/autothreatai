# App service: FastAPI server + Svelte frontend. Build context = project root.
# docker compose build app  (from project root)

# Stage 1: build Svelte frontend
FROM node:20-bookworm-slim AS frontend-build
WORKDIR /build
COPY app/frontend-svelte/package.json app/frontend-svelte/yarn.lock ./
RUN yarn install --frozen-lockfile --production=false
COPY app/frontend-svelte/ ./
RUN yarn build

# Stage 2: Python app server (use explicit tag; ARG before first FROM is not visible to later FROMs)
FROM python:3.14-slim-bookworm

RUN apt-get update && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/* \
    && curl -LsSf https://astral.sh/uv/install.sh | sh \
    && mv /root/.local/bin/uv /usr/local/bin/uv

WORKDIR /app

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

COPY app ./app
COPY shared ./shared
COPY --from=frontend-build /build/dist ./app/frontend-svelte/dist

EXPOSE 8000
CMD ["uv", "run", "uvicorn", "app.server:app", "--host", "0.0.0.0", "--port", "8000"]
