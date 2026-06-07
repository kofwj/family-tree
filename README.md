# Family Tree System

家谱管理系统，包含家族世系阅读、成员档案、权限治理、数据质量、来源引用、GEDCOM 导出、备份等功能。

## 技术栈

- Backend：FastAPI + SQLModel + SQLite
- Frontend：Vue 3 + Vite + Element Plus + Vue Flow
- Deploy：Docker Compose

## 本地启动

1. 准备环境变量：

```bash
cp .env.example .env
# 修改 .env 中的 JWT_SECRET、ADMIN_PASSWORD
```

2. 启动服务：

```bash
docker compose up -d --build
```

3. 访问：

- 前端：http://localhost:8088
- 后端健康检查：http://localhost:3000/health

## 重要说明

- `.env`、`data/family.db`、`data/backups/`、`import/*.xlsx`、成员照片等包含真实隐私数据，不应提交到 GitHub。
- 仓库只提交源码、文档、依赖清单和 `.env.example`。
- 首次部署后请使用 `.env` 中配置的管理员密码登录内置 `admin` 账号。

## 常用检查

```bash
# 后端语法检查
PYTHONDONTWRITEBYTECODE=1 python3 - <<'PY'
from pathlib import Path
p = Path('backend/main.py')
compile(p.read_text(), str(p), 'exec')
print('backend compile ok')
PY

# 前端构建
cd frontend && npm run build

# 服务状态
docker compose ps
curl -fsS http://localhost:3000/health
```

更多设计与阶段记录见 `docs/`。
