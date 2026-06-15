#!/bin/bash
set -e

echo "========================================="
echo ">>> Starting Family Tree System Update <<<"
echo "========================================="

# 1. Pull latest changes
echo ">>> Pulling latest code from Git..."
git pull

# 2. Rebuild and restart docker containers
echo ">>> Rebuilding and restarting Docker containers..."
docker compose up -d --build

echo "========================================="
echo ">>> Update completed successfully!    <<<"
echo "========================================="
