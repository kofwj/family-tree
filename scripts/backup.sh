#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
TS="$(date +%Y%m%d-%H%M%S)"
mkdir -p "$ROOT/data/backups" "$ROOT/backups/code"
[ -f "$ROOT/data/family.db" ] && cp "$ROOT/data/family.db" "$ROOT/data/backups/family-$TS-manual.db"
tar --exclude='./backups' --exclude='./data' --exclude='./frontend/node_modules' -czf "$ROOT/backups/code/code-$TS-manual.tgz" -C "$ROOT" .
echo "备份完成："
echo "- 数据库: $ROOT/data/backups/family-$TS-manual.db"
echo "- 代码: $ROOT/backups/code/code-$TS-manual.tgz"
