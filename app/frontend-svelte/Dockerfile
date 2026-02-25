# Build Svelte app and serve with nginx. Build context = app/frontend-svelte (or project root with -f).
# For project-root context: docker build -f app/frontend-svelte/Dockerfile .
# node:20-alpine has fewer CVEs than node:20-bookworm-slim (Alpine = smaller attack surface).
FROM node:20-alpine AS build
RUN corepack enable && corepack prepare yarn@stable --activate
WORKDIR /build
COPY app/frontend-svelte/package.json app/frontend-svelte/yarn.lock ./
RUN yarn install --frozen-lockfile --production=false
COPY app/frontend-svelte/ ./
RUN yarn build

FROM nginx:alpine
RUN apk upgrade --no-cache
COPY --from=build /build/dist /usr/share/nginx/html
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
