FROM node:22-alpine AS build

WORKDIR /app

COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci

COPY frontend/ ./
COPY exemplos/ /exemplos/
RUN npm run build

FROM nginx:1.27-alpine

ENV NGINX_CLIENT_MAX_BODY_SIZE=11m

COPY frontend/nginx.conf.template /etc/nginx/templates/default.conf.template
COPY --from=build /app/dist /usr/share/nginx/html

EXPOSE 80

HEALTHCHECK --interval=10s --timeout=3s --start-period=5s --retries=5 \
    CMD wget --quiet --spider http://127.0.0.1/healthz || exit 1
