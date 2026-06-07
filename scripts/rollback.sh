#!/usr/bin/env bash
set -euo pipefail
if [ $# -lt 1 ]; then
  echo "用法: scripts/rollback.sh backups/code/code-YYYYmmdd-HHMMSS.tgz [数据库备份文件]" >&2
  exit 1
fi
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
CODE_TGZ="$1"
DB_BACKUP="${2:-}"
if [[ "$CODE_TGZ" != /* ]]; then CODE_TGZ="$ROOT/$CODE_TGZ"; fi
[ -f "$CODE_TGZ" ] || { echo "代码备份不存在: $CODE_TGZ" >&2; exit 1; }

TS="$(date +%Y%m%d-%H%M%S)"
mkdir -p "$ROOT/backups/code" "$ROOT/data/backups"
tar --exclude='./backups' --exclude='./data' --exclude='./frontend/node_modules' -czf "$ROOT/backups/code/code-$TS-before-rollback.tgz" -C "$ROOT" .
if [ -f "$ROOT/data/family.db" ]; then cp "$ROOT/data/family.db" "$ROOT/data/backups/family-$TS-before-rollback.db"; fi

echo "回退代码到 $CODE_TGZ"
tar -xzf "$CODE_TGZ" -C "$ROOT"
if [ -n "$DB_BACKUP" ]; then
  if [[ "$DB_BACKUP" != /* ]]; then DB_BACKUP="$ROOT/$DB_BACKUP"; fi
  [ -f "$DB_BACKUP" ] || { echo "数据库备份不存在: $DB_BACKUP" >&2; exit 1; }
  cp "$DB_BACKUP" "$ROOT/data/family.db"
fi
cd "$ROOT"
docker compose build --no-cache
docker compose up -d --force-recreate
echo "回退完成：http://localhost:8088"
