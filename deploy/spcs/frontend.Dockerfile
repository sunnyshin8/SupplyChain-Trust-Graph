ARG BUILDPLATFORM=linux/amd64

FROM --platform=${BUILDPLATFORM} node:22-bookworm-slim AS dependencies
WORKDIR /app
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci

FROM --platform=${BUILDPLATFORM} node:22-bookworm-slim AS builder
WORKDIR /app
ENV NEXT_TELEMETRY_DISABLED=1 \
    NEXT_OUTPUT=export
COPY --from=dependencies /app/node_modules ./node_modules
COPY frontend/ ./
RUN npm run build

FROM --platform=linux/amd64 nginxinc/nginx-unprivileged:1.27-alpine AS runtime
COPY deploy/spcs/nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=builder /app/out /usr/share/nginx/html
EXPOSE 3000
