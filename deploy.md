# Render 部署指南

## 项目架构

```
render.yaml 定义的 Blueprint:
├── script-engine-backend  (Web Service · Python · FastAPI)
├── script-engine-frontend (Static Site · React + Vite)
├── script-engine-worker   (Worker · Python · Celery)
├── script-engine-beat     (Worker · Celery Beat)
├── script-engine-db       (PostgreSQL 15)
└── script-engine-redis    (Redis 7)
```

## 一键部署步骤

### 1. Fork / 推送代码到 GitHub

将项目推送到 GitHub 仓库（公开或私有均可）。

### 2. 在 Render 创建 Blueprint

1. 登录 [Render Dashboard](https://dashboard.render.com)
2. 点击 **New → Blueprint**
3. 连接 GitHub 仓库
4. Render 自动检测根目录的 `render.yaml`
5. 点击 **Apply** — 所有服务将自动创建

### 3. 配置敏感环境变量

Blueprint 部署完成后，以下变量需要在 Render Dashboard 手动填写：

| 变量名 | 说明 | 设为 sync: false |
|--------|------|:---:|
| `DEEPSEEK_API_KEY` | DeepSeek API 密钥 | ✅ |
| `MIMO_API_KEY` | MiMo API 密钥 | ✅ |

其余变量（`DATABASE_URL`、`REDIS_URL`、`SECRET_KEY`、`CORS_ORIGINS`）由 Render 自动注入。

### 4. 部署顺序

渲染会自动按依赖顺序启动服务：
1. PostgreSQL + Redis — 最先启动
2. Backend — 依赖数据库就绪
3. Worker — 依赖数据库与 Redis 就绪
4. Beat — 依赖数据库与 Redis 就绪
5. Frontend — 依赖 Backend 启动

## 手动配置步骤

### 设置 API Key

在 Render Dashboard → 对应服务 → Environment：

```
后端 (script-engine-backend):
  DEEPSEEK_API_KEY = your-deepseek-api-key
  MIMO_API_KEY     = your-mimo-api-key

Worker (script-engine-worker):
  DEEPSEEK_API_KEY = your-deepseek-api-key
  MIMO_API_KEY     = your-mimo-api-key
```

### 验证部署

```bash
# 检查后端健康状态
curl https://script-engine-backend.onrender.com/api/health

# 预期返回:
# {
#   "status": "ok",
#   "service": "script-engine-backend",
#   "version": "1.0.0",
#   "checks": {"database": "ok", "redis": "ok"}
# }
```

### 环境变量完整清单

| 变量名 | 必需 | 默认值 | 说明 |
|--------|:---:|--------|------|
| `PYTHON_VERSION` | ✅ | 3.11.0 | Python 版本 |
| `DATABASE_URL` | ✅ | — | PostgreSQL async 连接串 |
| `DATABASE_URL_SYNC` | ✅ | — | PostgreSQL 同步连接串 |
| `REDIS_URL` | ✅ | — | Redis 连接串 |
| `DEEPSEEK_API_KEY` | ✅ | — | DeepSeek API 密钥 |
| `DEEPSEEK_BASE_URL` | — | `https://api.deepseek.com/v1` | DeepSeek API 端点 |
| `MIMO_API_KEY` | ✅ | — | MiMo API 密钥 |
| `MIMO_BASE_URL` | — | `https://token-plan-cn.xiaomimimo.com/v1` | MiMo API 端点 |
| `SECRET_KEY` | ✅ | 自动生成 | 应用密钥 |
| `APP_ENV` | ✅ | `production` | 运行环境 |
| `CORS_ORIGINS` | ✅ | Render 前端域名 | CORS 白名单 |
| `GIT_REPO_PATH` | — | `./data/repos` | 剧本版本库路径 |

## Docker 镜像优化

后端 Dockerfile 采用多阶段构建：

- **Builder 阶段**: `python:3.11-slim-bookworm` + 编译工具链，仅安装 pip 依赖
- **Runtime 阶段**: `python:3.11-slim-bookworm`，仅含运行时库，以非 root 用户 `appuser` 运行
- **HEALTHCHECK**: 每 30 秒自动探测 `/api/health`
- **预计镜像大小**: ~250MB（vs 单阶段 ~450MB）

## 本地开发

```bash
# 1. 克隆项目
git clone <repo-url>
cd script-engine

# 2. 配置环境变量
cp .env.example .env
# 编辑 .env 填入实际 API Key

# 3. Docker Compose 启动
docker compose up -d

# 4. 访问
# 前端: http://localhost:5173
# 后端: http://localhost:8000
# API 文档: http://localhost:8000/docs
```

## 常见问题

### Q: 后端健康检查显示 `database: error`
A: 检查 PostgreSQL 连接串是否正确，确认 `DATABASE_URL` 和 `DATABASE_URL_SYNC` 格式为 `postgresql+asyncpg://user:pass@host:5432/db`

### Q: Worker 未处理任务
A: 检查 Redis 连接，确认 `REDIS_URL` 正确且 Redis 服务正在运行

### Q: 前端无法连接后端 API
A: 确认 `VITE_API_BASE_URL` 指向正确的后端 URL，确认 `CORS_ORIGINS` 包含前端域名

### Q: 部署套餐与休眠策略
A: 当前 `render.yaml` 使用的是 `starter` 方案而非免费方案。若实际部署时改成其他套餐，请以 Render 控制台中的当前计划与休眠策略为准。
