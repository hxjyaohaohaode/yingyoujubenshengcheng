# 互动影游剧本智能体集群

> Interactive Film/Game Script Agent Cluster — 多Agent协同的智能剧本创作系统

## 项目简介

一个基于多Agent集群架构的互动影游剧本创作平台。系统采用7个专业化AI Agent协同工作，覆盖从世界观构建、角色设计、伏笔网络、场景创作到质量审计的完整创作流程。支持单线叙事、双主角、多角色群像三种互动影游模式。

### 核心特性

- **7-Agent集群**：编排/创作/审计/状态/素材/伏笔/创意 Agent 各司其职
- **全流程覆盖**：Phase 0-6 从需求对齐到全剧终审的7阶段管线
- **三层伏笔体系**：表层线索 → 深层暗示 → 核心真相，支持哇塞方案设计
- **结构化场景编辑**：对白/动作/选择节点/因果链/伏笔操作一体化编辑器
- **自动审计**：6项程序化检测 + 6维LLM质量评估，封驳机制确保内容质量
- **情感曲线可视化**：全局情感曲线 + 节奏规则引擎（4条规则自动检测）
- **多格式导出**：JSON / Markdown / 纯文本 / Excel，支持按章节/场景范围导出

## 技术栈

| 层级 | 技术 |
|------|------|
| **前端** | React 18 + TypeScript + Vite + Tailwind CSS + Ant Design 5 + Recharts + D3.js |
| **后端** | FastAPI + SQLAlchemy 2.0 (async) + Pydantic v2 |
| **数据库** | PostgreSQL 15 + asyncpg |
| **缓存/队列** | Redis 7 + Celery 5 |
| **AI大模型** | DeepSeek (deepseek-v3 / deepseek-r1) + MiMo (mimo-v2-pro / mimo-v2-omni / mimo-v2.5-pro) |
| **容器化** | Docker + Docker Compose |
| **部署** | Render (Web Service + Static Site + Worker + Beat + PostgreSQL + Redis) |

### Agent-模型映射

| Agent | 模型 | 用途 |
|-------|------|------|
| 📋 编排Agent | DeepSeek V3 | 项目流程编排、任务调度 |
| ✍️ 创作Agent | DeepSeek V3 | 场景创作、对白生成 |
| 🔍 审计Agent | DeepSeek R1 / V3 | 内容质量审计、封驳决策 |
| 📊 状态Agent | MiMo V2.5 Pro | 项目健康监控、进度跟踪 |
| 🎨 素材Agent | MiMo V2 Omni / V2 Pro | 参考素材检索、风格匹配 |
| 🎯 伏笔Agent | DeepSeek R1 | 伏笔逻辑推理、三层结构设计 |
| 💡 创意Agent | DeepSeek V4 Pro | 哇塞时刻设计、创意发散 |

## 快速开始

### 前置要求

- Docker & Docker Compose
- Node.js 20+ (仅前端本地开发需要)
- Python 3.11+ (仅后端本地开发需要)

### 一键启动（推荐）

```bash
# 1. 克隆项目
git clone <repo-url>
cd script-engine

# 2. 配置环境变量
cp .env.example .env
# 编辑 .env 填入 DEEPSEEK_API_KEY 和 MIMO_API_KEY

# 3. 启动所有服务
docker-compose up -d

# 4. 访问
# 前端: http://localhost:5173
# 后端API文档: http://localhost:8000/docs
```

### 本地开发

```bash
# 后端
cd backend
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
uvicorn main:app --reload --port 8000

# 前端
cd frontend
npm install
npm run dev

# Celery Worker（需要时）
cd backend
celery -A tasks worker --loglevel=info

# Celery Beat（自动巡检/补偿）
cd backend
celery -A tasks beat --loglevel=info
```

## 环境变量

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `DATABASE_URL` | PostgreSQL连接串（async） | `postgresql+asyncpg://postgres:password@localhost:5432/script_engine` |
| `DATABASE_URL_SYNC` | PostgreSQL连接串（同步） | `postgresql://postgres:password@localhost:5432/script_engine` |
| `REDIS_URL` | Redis连接串 | `redis://localhost:6379/0` |
| `DEEPSEEK_API_KEY` | DeepSeek API密钥 | （必填） |
| `DEEPSEEK_BASE_URL` | DeepSeek API地址 | `https://api.deepseek.com/v1` |
| `MIMO_API_KEY` | MiMo API密钥 | （必填） |
| `MIMO_BASE_URL` | MiMo API地址 | `https://token-plan-cn.xiaomimimo.com/v1` |
| `SECRET_KEY` | 应用密钥 | `dev-secret-key-change-in-production` |
| `CORS_ORIGINS` | CORS允许的前端地址 | `http://localhost:5173` |
| `APP_ENV` | 运行环境 | `development` |

## Docker Compose 服务

```yaml
services:
  postgres      # PostgreSQL 15 (port 5432)
  redis         # Redis 7 (port 6379)
  backend       # FastAPI (port 8000)
  frontend      # Vite Dev Server (port 5173)
  celery-worker # Celery异步任务
  celery-beat   # Celery定时调度/补偿任务
```

## 项目结构

```
script-engine/
├── backend/
│   ├── api/            # API路由（projects/characters/foreshadows/scenes/chapters/ai）
│   ├── models/         # SQLAlchemy ORM模型（14张表）
│   ├── schemas/        # Pydantic数据模型
│   ├── services/       # 业务服务（任务调度/运行时/Prompt）
│   ├── tasks/          # Celery异步任务与定时维护任务
│   ├── config.py       # 配置管理
│   ├── database.py     # 数据库连接
│   ├── main.py         # FastAPI入口
│   └── ...
├── frontend/
│   ├── src/
│   │   ├── api/        # API调用层（client.ts）
│   │   ├── components/ # 通用组件（Layout/AgentPanel/EmotionChart/...）
│   │   ├── pages/      # 页面组件（10个页面）
│   │   ├── stores/     # Zustand状态管理
│   │   └── styles/     # 全局样式
│   └── ...
├── docker-compose.yml
├── render.yaml         # Render部署配置
└── .env.example
```

## API 概览

### 项目管理
- `CRUD /api/projects` — 项目CRUD
- `GET /api/projects/{id}/dashboard` — 项目仪表盘与统计汇总
- `GET /api/projects/{id}/config` — 项目配置读取

### 世界观 & 角色
- `POST /api/ai/world-gen/{project_id}/{config_key}` — 世界观配置生成
- `CRUD /api/projects/{project_id}/characters` — 角色管理
- `CRUD /api/projects/{project_id}/relations` — 角色关系管理

### 伏笔
- `CRUD /api/projects/{project_id}/foreshadows` — 伏笔CRUD
- `GET /api/projects/{project_id}/foreshadow-health` — 伏笔健康检查
- `POST /api/ai/foreshadow-reaction/{project_id}` — 化学反应分析
- `POST /api/ai/projects/{project_id}/foreshadows/generate` — 伏笔体系生成任务

### 场景 & 章节
- `CRUD /api/projects/{project_id}/scenes` — 场景CRUD
- `CRUD /api/projects/{project_id}/chapters` — 章节CRUD
- `POST /api/projects/{project_id}/scenes/{scene_id}/finalize` — 场景定稿

### AI Agent（关键端点）
| 端点 | Agent |
|------|-------|
| `POST /api/ai/world-gen/{project_id}/{config_key}` | 创作Agent |
| `POST /api/ai/character-gen/{project_id}` | 创作Agent |
| `POST /api/ai/foreshadow-wow-gen/{foreshadow_id}` | 创意Agent |
| `POST /api/ai/emotion-curve-design/{project_id}` | 创意Agent |
| `POST /api/ai/projects/{id}/scenes/{sid}/generate` | 创作Agent（调度） |
| `POST /api/ai/projects/{id}/scenes/{sid}/audit` | 审计Agent（调度） |
| `POST /api/ai/projects/{id}/foreshadows/generate` | 伏笔Agent（调度） |
| `POST /api/ai/projects/{id}/foreshadows/{fid}/wow-plans` | 创意Agent（调度） |
| `POST /api/ai/projects/{id}/full-audit` | 审计Agent（调度） |
| `GET /api/ai/tasks/{task_id}` | 任务进度轮询 |
| `POST /api/ai/cancel/{task_id}` | 任务取消 |

## 部署到 Render

1. Fork 本仓库
2. 在 Render Dashboard 中选择 "Blueprint" 部署
3. 连接仓库，Render 自动读取 `render.yaml`
4. 设置环境变量 `DEEPSEEK_API_KEY` 和 `MIMO_API_KEY`
5. 点击部署

系统将自动创建：
- Web Service（FastAPI后端 + 健康检查）
- Static Site（React前端 + SPA路由）
- Worker（Celery异步任务）
- Worker（Celery Beat 自动巡检/补偿）
- PostgreSQL 数据库
- Redis 缓存

## License

MIT
