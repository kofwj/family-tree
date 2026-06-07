#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
TS="$(date +%Y%m%d-%H%M%S)"
mkdir -p "$ROOT/backups/code" "$ROOT/data/backups"

echo "[1/5] 备份当前代码..."
tar --exclude='./backups' --exclude='./data' --exclude='./frontend/node_modules' -czf "$ROOT/backups/code/code-$TS.tgz" -C "$ROOT" .

echo "[2/5] 备份数据库..."
if [ -f "$ROOT/data/family.db" ]; then
  cp "$ROOT/data/family.db" "$ROOT/data/backups/family-$TS-before-deploy.db"
fi

echo "[3/5] 构建镜像..."
cd "$ROOT"
docker compose build --no-cache

echo "[4/5] 重建容器..."
docker compose up -d --force-recreate

echo "[5/5] 健康检查..."
for i in {1..30}; do
  if curl -fsS http://localhost:8088 >/dev/null && curl -fsS http://localhost:3000/health >/dev/null; then
    echo "部署成功：http://localhost:8088"
    echo "代码备份：$ROOT/backups/code/code-$TS.tgz"
    exit 0
  fi
  sleep 2
done

echo "健康检查失败，可执行：scripts/rollback.sh $ROOT/backups/code/code-$TS.tgz" >&2
exit 1
