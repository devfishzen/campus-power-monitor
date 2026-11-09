#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

if ! command -v docker >/dev/null 2>&1; then
  echo "错误：未找到 docker。请先安装 Docker Engine 和 compose 插件。"
  echo "Debian/Ubuntu: https://docs.docker.com/engine/install/"
  exit 1
fi

if ! docker compose version >/dev/null 2>&1; then
  echo "错误：未找到 docker compose 插件（docker compose version 失败）。"
  exit 1
fi

if [ ! -f .env ]; then
  echo "错误：缺少 .env（应包含学号、房间、QQ 邮箱授权码）。"
  exit 1
fi

chmod 600 .env
mkdir -p data

if [ "$(id -u)" -eq 0 ]; then
  chown -R 1000:1000 data
else
  echo "提示：当前不是 root。如果容器报 /data 不可写，请执行："
  echo "  sudo chown -R 1000:1000 data"
fi

build_args=()
if [ -n "${PIP_INDEX_URL:-}" ]; then
  build_args+=(--build-arg "PIP_INDEX_URL=${PIP_INDEX_URL}")
  echo "使用 pip 源：${PIP_INDEX_URL}"
fi

echo "==> 构建镜像"
docker compose build "${build_args[@]}"

echo "==> 启动容器"
docker compose up -d

echo "==> 等待服务就绪"
ready=0
for _ in $(seq 1 60); do
  if docker compose exec -T dianfei python -c \
    "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8080/healthz', timeout=3)" \
    >/dev/null 2>&1; then
    ready=1
    break
  fi
  sleep 2
done

if [ "$ready" -ne 1 ]; then
  echo "服务未在 120 秒内就绪，最近日志："
  docker compose logs --tail=80
  exit 1
fi

echo "==> 当前读数"
docker compose exec -T dianfei python -c \
  "import json, urllib.request; print(json.dumps(json.load(urllib.request.urlopen('http://127.0.0.1:8080/api/current')), ensure_ascii=False, indent=2))" \
  || true

echo
echo "部署完成： http://<服务器IP>:8080"
echo "查看日志： docker compose logs -f"
