# syntax=docker/dockerfile:1
FROM node:24.21.0-bookworm@sha256:64af3819f9275802414d7cdc38c27e9d82bd564dec4d4da87d008255d36c63b4 AS development

WORKDIR /workspace
ENV NEXT_TELEMETRY_DISABLED=1

COPY package.json package-lock.json ./
COPY apps/web/package.json ./apps/web/package.json
RUN npm ci --no-audit --no-fund

COPY apps/web ./apps/web

EXPOSE 3000
CMD ["npm", "run", "dev", "--workspace", "apps/web", "--", "--hostname", "0.0.0.0"]
