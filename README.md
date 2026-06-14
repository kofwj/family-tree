# Family Tree System

家谱管理系统，面向家族内部资料整理、成员关系维护、族谱浏览和档案治理。项目包含前后端、权限体系、备份恢复、Excel 导入、GEDCOM 导出、来源引用和数据质量检查等功能。

> ⚠️ 家谱数据通常包含姓名、亲属关系、生日、住址、照片等隐私信息。请不要把真实数据库、导入表、照片和 `.env` 提交到公开仓库。

## 功能特性

- 家族成员档案管理：姓名、字辈、排行、生卒日期、住址、墓址、教育职业、传记等
- 族谱关系图：父母、配偶、子女关系可视化，支持缩放和定位
- 权限治理：超级管理员、管理员、编辑者、只读成员等角色
- 隐私控制：成员字段可见性、分支视角、基础关系可见范围
- 受保护媒体：成员照片需登录并通过成员可见性校验后访问
- 数据质量：缺失字段、关系异常、待审核请求等治理入口
- 来源引用：为成员字段维护来源记录和引用说明
- Excel 导入：下载样表后批量导入成员数据，支持事务化替换和失败回滚
- GEDCOM 导出：导出通用族谱交换格式
- 备份恢复：手动备份、自动安全备份、备份下载、完整性校验与安全恢复
- Docker 部署：前端 Nginx + 后端 FastAPI + SQLite 数据卷

## 技术栈

- Backend：FastAPI + SQLModel + SQLite
- Frontend：Vue 3 + Vite + Element Plus + Vue Flow
- Deploy：Docker Compose

## 目录结构

```text
.
├── backend/              # FastAPI 后端
├── frontend/             # Vue 前端
├── scripts/              # 备份、部署、关系回填脚本
├── docs/                 # 设计文档和阶段记录
├── data/                 # 本地运行数据，禁止提交
├── import/               # 本地导入文件，禁止提交
├── docker-compose.yml
├── .env.example
└── README.md
```

## 本地启动

1. 准备环境变量：

```bash
cp .env.example .env
```

修改 `.env`：

```env
JWT_SECRET=replace-with-a-long-random-secret
ADMIN_PASSWORD=replace-with-a-strong-admin-password
CORS_ORIGIN=http://localhost:8088
```

建议生成 `JWT_SECRET`：

```bash
python3 -c "import secrets; print(secrets.token_urlsafe(48))"
```

2. 启动服务：

```bash
docker compose up -d --build
```

3. 访问：

- 前端：http://localhost:8088
- 后端健康检查：http://localhost:3000/health
- 默认登录账号：`admin`
- 默认登录密码：使用 `.env` 中的 `ADMIN_PASSWORD`

## 开发命令

### 后端测试与语法检查

首次本地 Python 开发建议使用独立虚拟环境，避免污染系统或其他工具运行时：

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r backend/requirements.txt pytest
```

运行回归测试：

```bash
python -m pytest tests -q
```

语法检查：

```bash
PYTHONPYCACHEPREFIX=/tmp/family-tree-pycache python -m py_compile backend/main.py check_layout.py test_crud.py scripts/*.py tests/*.py
```

### 前端构建

```bash
npm --prefix frontend ci
npm --prefix frontend run build
```

### Docker Compose 配置检查

```bash
docker compose config
```

### 服务状态

```bash
docker compose ps
curl -fsS http://localhost:3000/health
```

## GitHub Actions

仓库包含自动检查工作流：

- 后端依赖安装与 `pytest tests -q` 回归测试
- Python 语法检查
- 前端依赖安装和生产构建
- Docker Compose 配置校验

每次 push 或 pull request 到 `main` 分支时会自动执行。

## 隐私和数据安全

- `/settings` 需要登录并具备 `settings.view` 权限；公开首页仅读取 `/public-settings` 的白名单字段。
- 成员照片不再通过静态目录公开裸访问，`/member-photos/{filename}` 会校验登录状态、`member.view` 权限和成员可见范围。
- Excel 替换导入使用单事务处理：导入失败会回滚旧数据；成功替换会清理成员相关引用、审核请求和用户绑定，避免孤儿数据。
- Excel 上传仅支持 `.xlsx`，默认大小上限为 10MB，可通过 `EXCEL_MAX_BYTES` 调整。
- 照片上传仅支持 JPG/PNG/WebP，默认大小上限为 5MB，可通过 `PHOTO_MAX_BYTES` 调整。
- 删除成员前会检查父母/配偶关系、来源引用、审核请求、用户绑定等依赖；存在依赖时返回 `409 Conflict`。
- 备份创建使用 SQLite online backup；恢复前会执行 SQLite 完整性和必要表结构校验，恢复过程采用 staging + 原子替换，并在失败时尝试回滚到恢复前安全备份。
- 前端 Nginx 配置包含 `client_max_body_size`、CSP、`X-Content-Type-Options`、`X-Frame-Options`、`Referrer-Policy` 和 `Permissions-Policy` 等基础安全头。

以下文件/目录可能包含真实隐私数据，已通过 `.gitignore` 排除：

```text
.env
data/*.db
data/backups/
data/member-photos/
import/*.xlsx
backups/
*.ged
```

上传 GitHub 前建议检查：

```bash
git status --short
git diff --cached --name-only
```

确认不要出现 `.env`、`data/`、`import/`、`backups/`、`*.db`、成员照片等文件。

## 生产部署建议

生产环境建议：

- 使用强随机 `JWT_SECRET`
- 使用强管理员密码
- 使用 HTTPS 域名访问
- 设置 `CORS_ORIGIN=https://你的域名`
- 定期下载或异地保存 `data/backups/` 中的备份
- 不要将真实 `data/` 目录同步到公开仓库

示例：

```bash
cp .env.example .env
# 修改 .env 后启动
docker compose up -d --build
```

## 备份与恢复

系统会在关键操作前创建安全备份，也支持手动备份。备份文件默认位于：

```text
data/backups/
```

备份和恢复保护策略：

- 自动备份默认仅保留最近 30 个普通自动备份。
- 手动备份和恢复前安全备份不会被自动清理。
- 创建备份时使用 SQLite online backup，降低运行中复制导致的不一致风险。
- 恢复前会校验备份文件是否为有效 SQLite 数据库、`PRAGMA integrity_check` 是否为 `ok`、是否包含必要表结构。
- 恢复过程先写入 staging 文件，再原子替换当前数据库；失败时会尝试回滚到恢复前保护备份。

该目录包含真实家谱数据，禁止提交到 GitHub。

## 文档

更多设计说明、权限矩阵、信息架构和阶段记录见：

```text
docs/
```
