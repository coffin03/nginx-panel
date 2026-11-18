# nginx-panel 容器镜像：面板 + 自带 nginx，开箱即可在容器内管理一份 nginx 配置
# 构建：docker build -t nginx-panel .
# 运行：docker run -d -p 8090:8090 -p 8080:80 -v nginx-panel-data:/data nginx-panel

FROM node:20-alpine AS web
WORKDIR /build
COPY web/package.json web/package-lock.json ./
RUN npm ci
COPY web/ ./
RUN npm run build

FROM python:3.12-slim
ENV PYTHONUNBUFFERED=1 \
    NGINX_PANEL_HOST=0.0.0.0 \
    NGINX_PANEL_PORT=8090 \
    NGINX_PANEL_NO_BROWSER=1 \
    NGINX_PANEL_DATA_DIR=/data

RUN apt-get update \
    && apt-get install -y --no-install-recommends nginx \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY server/requirements.txt ./server/requirements.txt
RUN pip install --no-cache-dir -r server/requirements.txt
COPY server/ ./server/
COPY --from=web /build/dist ./web/dist

VOLUME ["/data"]
EXPOSE 80 8090
CMD ["python", "server/run.py"]