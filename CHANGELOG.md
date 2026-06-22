# Changelog

All notable changes to the Family Tree System will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [1.1.0] - 2026-06-23

### Added
- **凭证安全强校验 (Fail-Fast)**: 引入非测试环境启动强制合规校验，若 JWT_SECRET 缺失/弱、或 ADMIN_PASSWORD 缺失/为默认弱密码（如 `admin123`），系统将拒绝启动并抛出 `RuntimeError`，杜绝配置弱密码的安全风险。
- **SECURE_COOKIE 配置**: 新增环境变量 `SECURE_COOKIE`（默认 `false`），支持开发环境 HTTP 运行与生产环境 HTTPS 强制 Secure Cookie 传输的按需切换。
- **AUTO_ORGANIZE_ON_STARTUP 保护**: 引入启动期自动重组和关系修复开关，默认设为 `false`。仅当显式设置此变量为 `true` 时才在启动期修改数据，避免默认启动自动篡改业务数据。
- **异步安全路由守卫**: 前端路由守卫在进入 `/workspace` 时增加基于 API `/api/me` 的单次异步会话验证，防止用户通过在浏览器控制台手动写入 `localStorage.isAuthenticated = 'true'` 绕过登录拦截。
- **全景图动态亲属路径**: 同心圆 BFS 布局计算增加 `relationToCenter` 动态称谓路径计算，能够根据极坐标中心焦点人物，实时生成长辈、晚辈与旁系亲属的确切称谓路径（例如：“配偶的父亲”、“儿子的女儿”、“父亲的兄弟姐妹”）。
- **全景图悬浮信息卡 (Tooltip)**: 全景图节点悬浮框增加显示该成员与焦点人物的亲属关系、职业（Occupation）以及所在地/出生地（Location）的信息展示。
- **联动跳转桥梁**: 成员详情抽屉（MemberDrawer）新增联动跳转支持。用户在阅读模式点击“设为关系圈中心”时，系统将自动关闭抽屉、将主页卡切换至“世系图谱”并切换为“全景关系图”，并将坐标焦点对齐定位到该成员。

### Changed
- **HttpOnly Cookie 认证**: 重构鉴权体系，将 JWT Token 传输从前端 `localStorage` 标头迁移至 HttpOnly、SameSite=Lax 的 Session Cookie (`access_token`)，彻底防御 XSS 劫持 Token 漏洞。
- **祖源接口可见性裁剪 (Scheme A 截断)**：在 `/members/{id}/ancestry` 祖源查询中，严格应用 visibility 可见性范围。如果某一代祖先节点对当前用户不可见，将采用 **Scheme A 硬截断**，阻断向上追溯且不返回该不可见节点，保障隐私数据不被推演泄露。
- **收紧成员管理与行政配置权限**:
  * 用户角色分配/删除端点（`POST/DELETE /families/{id}/users`）的访问权限校验收紧为 `can_admin_family`，非家族管理员/全局管理员（如普通的 `editor`）不再允许管理他人权限。
  * 家族基本信息更新端点（`PUT /families/{id}`）中，限制家族级别 `editor` 无法修改 `root_member_id`（根成员指向）、`primary_line`（主世系）等结构性配置，仅被允许修改名称、简介等展示性元数据。若强行尝试修改，将显式拒绝并返回 `403 Forbidden`。
- **ECharts 全景图交互去抽屉化**: 全景关系图节点点击（Click）逻辑直接绑定为设置该节点为中心人物，摒弃双击改单键，同时在全景视图模式下不再弹出抽屉侧边栏，带来无干扰的沉浸式家族网络漫游体验。
- **Pytest 扫描导入保护**: 重构 `test_crud.py` 脚本，将所有顶级 HTTP 请求 and 环境变量校验移至 `if __name__ == '__main__':` 守卫中，彻底解决了 Pytest 运行全局扫描时发生测试收集错误的问题。

### Removed
- **清理残留临时文件**: 清理了根目录下的遗留补丁脚本（`.tmp_*.py`）、沙盒运行缓存（`scratch_members.json`）、布局检测工具（`check_layout.py`）以及损坏的 `.venv` 虚拟环境文件夹，并在 `.gitignore` 中追加了对应的防污染规则。

---

## [1.0.0] - 2026-06-19

### Added
- **初版发布**: 家谱管理系统核心架构搭建完毕。
- **世系展示与数据治理**: 支持自适应两级树结构可视化、多家族分类切换管理、备份与原子回滚机制。
- **媒体照片与安全沙盒**: 受登录态保护的媒体照片访问、Excel 数据事务性安全批量导入、GEDCOM 族谱国际标准数据交换规范导出等功能。
- **Alembic 数据库自动迁移**: 集成 Alembic API 以在容器启动时自动应用和应用全部版本数据库表迁移。
