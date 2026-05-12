import logging
from contextlib import asynccontextmanager

try:
    import redis.asyncio as aioredis
    _REDIS_AVAILABLE = True
except ImportError:
    aioredis = None
    _REDIS_AVAILABLE = False

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from pydantic import BaseModel

from config import CORS_ORIGINS, APP_ENV, REDIS_URL, DATABASE_URL
from database import init_db, close_db, async_session_factory, check_db_health
from middleware.rate_limit import RateLimitMiddleware
from middleware.audit_log import AuditLogger, AuditLoggingMiddleware
from api import projects, characters, foreshadows, scenes, chapters, ai, export, pipeline, templates, script_viz
from websocket.router import router as ws_router
import models
import core.pipeline.pipeline_state_model
import core.rag.embedding_model
import core.gateway.token_usage_model

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        if APP_ENV == "production":
            response.headers["Strict-Transport-Security"] = "max-age=31536000"
        return response


@asynccontextmanager
async def lifespan(app: FastAPI):
    AuditLogger.configure(async_session_factory)
    try:
        from core.pipeline.template_loader import load_templates
        load_templates()
        logger.info("编排模板加载完成")
    except Exception as e:
        logger.warning(f"模板加载跳过: {e}")
    try:
        import core.agent
        from core.agent.registry import list_agents
        agents = [a["name"] for a in list_agents()]
        logger.info(f"Agent注册完成: {agents}")
    except Exception as e:
        logger.warning(f"Agent注册跳过: {e}")
    try:
        await init_db()
        logger.info("数据库ORM表初始化完成")
    except Exception as e:
        logger.warning(f"数据库ORM初始化跳过: {e}")

    try:
        from sqlalchemy import text
        async with async_session_factory() as sess:
            await sess.execute(text("""
                CREATE TABLE IF NOT EXISTS pipeline_state (
                    project_id VARCHAR(36) PRIMARY KEY,
                    template_name VARCHAR(100) NOT NULL DEFAULT '',
                    current_phase_index INTEGER NOT NULL DEFAULT 0,
                    current_step_index INTEGER NOT NULL DEFAULT 0,
                    status VARCHAR(20) NOT NULL DEFAULT 'not_started',
                    result_data TEXT DEFAULT '{}',
                    error_message TEXT DEFAULT '',
                    task_results TEXT DEFAULT '[]',
                    config TEXT DEFAULT '{}',
                    run_id VARCHAR(36),
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """))
            await sess.commit()
        logger.info("pipeline_state 表确认完成")
    except Exception as e:
        logger.warning(f"pipeline_state 建表跳过: {e}")

    try:
        if "sqlite" in DATABASE_URL:
            import sqlite3
            db_path = DATABASE_URL.replace("sqlite+aiosqlite:///", "").replace("sqlite:///", "")
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()

            cursor.execute("PRAGMA table_info(chapters)")
            cols = [row[1] for row in cursor.fetchall()]
            if "core_conflict" not in cols:
                conn.execute("ALTER TABLE chapters ADD COLUMN core_conflict TEXT")
                conn.commit()
                logger.info("数据库迁移：已为 chapters 表添加 core_conflict 列")
            if "focus_characters" not in cols:
                conn.execute("ALTER TABLE chapters ADD COLUMN focus_characters TEXT DEFAULT '[]'")
                conn.commit()
                logger.info("数据库迁移：已为 chapters 表添加 focus_characters 列")
            if "worldview_refs" not in cols:
                conn.execute("ALTER TABLE chapters ADD COLUMN worldview_refs TEXT DEFAULT '[]'")
                conn.commit()
                logger.info("数据库迁移：已为 chapters 表添加 worldview_refs 列")

            cursor.execute("PRAGMA table_info(characters)")
            char_cols = [row[1] for row in cursor.fetchall()]
            if "dark_secret" not in char_cols:
                conn.execute("ALTER TABLE characters ADD COLUMN dark_secret TEXT")
                conn.commit()
                logger.info("数据库迁移：已为 characters 表添加 dark_secret 列")
            if "location" not in char_cols:
                conn.execute("ALTER TABLE characters ADD COLUMN location VARCHAR(100)")
                conn.commit()
            if "emotional_state" not in char_cols:
                conn.execute("ALTER TABLE characters ADD COLUMN emotional_state VARCHAR(50)")
                conn.commit()
            if "physical_state" not in char_cols:
                conn.execute("ALTER TABLE characters ADD COLUMN physical_state VARCHAR(50)")
                conn.commit()
            if "current_goal" not in char_cols:
                conn.execute("ALTER TABLE characters ADD COLUMN current_goal TEXT")
                conn.commit()
            if "known_info" not in char_cols:
                conn.execute("ALTER TABLE characters ADD COLUMN known_info TEXT DEFAULT '[]'")
                conn.commit()

            cursor.execute("PRAGMA table_info(character_relations)")
            rel_cols = [row[1] for row in cursor.fetchall()]
            if "value" not in rel_cols:
                conn.execute("ALTER TABLE character_relations ADD COLUMN value INTEGER DEFAULT 50")
                conn.commit()
            if "last_interaction" not in rel_cols:
                conn.execute("ALTER TABLE character_relations ADD COLUMN last_interaction VARCHAR(50)")
                conn.commit()

            cursor.execute("PRAGMA table_info(scenes)")
            scene_cols = [row[1] for row in cursor.fetchall()]
            if "suggestions" not in scene_cols:
                conn.execute("ALTER TABLE scenes ADD COLUMN suggestions TEXT DEFAULT '[]'")
                conn.commit()
                logger.info("数据库迁移：已为 scenes 表添加 suggestions 列")

            conn.close()
    except Exception as e:
        logger.warning("数据库迁移跳过: %s", e)

    try:
        from core.pipeline.state_machine import PipelineStateMachine, PipelineStatus
        async with async_session_factory() as sess:
            sm = PipelineStateMachine(sess)
            from sqlalchemy import text
            result = await sess.execute(
                text("SELECT project_id, status FROM pipeline_state WHERE status = 'running'")
            )
            running_pipelines = result.fetchall()
            for row in running_pipelines:
                pid, status = row
                logger.info("恢复中断的流水线: project_id=%s, 将状态从running改为failed", pid)
                await sm.mark_failed(pid, "服务重启，流水线中断。请手动重试。")
            await sess.commit()
    except Exception as e:
        logger.warning("流水线状态恢复跳过: %s", e)

    yield
    try:
        from core.gateway.client import get_gateway
        gateway = get_gateway()
        await gateway.close()
    except Exception:
        pass
    try:
        await close_db()
    except Exception:
        pass


app = FastAPI(
    title="互动影游剧本智能体集群",
    description="Web应用支持几万字到150万字的互动影游剧本协作生产",
    version="0.2.0",
    lifespan=lifespan,
)

app.add_middleware(SecurityHeadersMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["*"],
)


class DynamicLocalhostCORSMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        origin = request.headers.get("origin", "")
        if origin.startswith("http://localhost:") or origin.startswith("http://127.0.0.1:"):
            request.scope["origin"] = origin
        response = await call_next(request)
        if origin.startswith("http://localhost:") or origin.startswith("http://127.0.0.1:"):
            response.headers["Access-Control-Allow-Origin"] = origin
            response.headers["Access-Control-Allow-Credentials"] = "true"
            response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, DELETE"
            response.headers["Access-Control-Allow-Headers"] = "*"
        return response


app.add_middleware(DynamicLocalhostCORSMiddleware)

app.add_middleware(RateLimitMiddleware, max_requests=60, window_seconds=60.0)

app.add_middleware(AuditLoggingMiddleware)

app.include_router(projects.router, prefix="/api", tags=["projects"])
app.include_router(characters.router, prefix="/api", tags=["characters"])
app.include_router(foreshadows.router, prefix="/api", tags=["foreshadows"])
app.include_router(scenes.router, prefix="/api", tags=["scenes"])
app.include_router(chapters.router, prefix="/api", tags=["chapters"])
app.include_router(ai.router, prefix="/api", tags=["ai"])
app.include_router(export.router, prefix="/api", tags=["export"])
app.include_router(pipeline.router, prefix="/api", tags=["pipeline"])
app.include_router(pipeline.public_router, prefix="/api", tags=["pipeline"])
app.include_router(templates.router, prefix="/api", tags=["templates"])
app.include_router(script_viz.router, prefix="/api", tags=["script-viz"])
app.include_router(ws_router)


@app.get("/api/health")
async def health_check():
    db_healthy = await check_db_health()

    redis_healthy = False
    if _REDIS_AVAILABLE and aioredis is not None:
        try:
            redis_client = aioredis.from_url(REDIS_URL, socket_connect_timeout=3, socket_timeout=3)
            await redis_client.ping()
            redis_healthy = True
            await redis_client.close()
        except Exception:
            pass

    checks = {
        "database": "ok" if db_healthy else "error",
        "redis": "ok" if redis_healthy else "unavailable",
    }

    overall = "ok" if db_healthy else "degraded"

    return {
        "status": overall,
        "service": "script-engine-backend",
        "version": "0.2.0",
        "checks": checks,
    }


class LLMConfigUpdate(BaseModel):
    deepseek_base_url: str | None = None
    deepseek_api_key: str | None = None
    mimo_base_url: str | None = None
    mimo_api_key: str | None = None


@app.get("/api/config/models")
async def get_available_models():
    return {
        "models": [
            {"value": "ds-v4-pro", "label": "DeepSeek V4 Pro (推荐)", "provider": "deepseek"},
            {"value": "ds-v4-flash", "label": "DeepSeek V4 Flash (快速)", "provider": "deepseek"},
            {"value": "ds-reasoner", "label": "DeepSeek Reasoner (深度推理)", "provider": "deepseek"},
            {"value": "mimo-v2-pro", "label": "MiMo V2 Pro", "provider": "mimo"},
            {"value": "mimo-v2-omni", "label": "MiMo V2 Omni (多模态)", "provider": "mimo"},
            {"value": "mimo-v2.5-pro", "label": "MiMo V2.5 Pro", "provider": "mimo"},
        ],
        "default": "ds-v4-pro",
    }


@app.get("/api/config/llm")
async def get_llm_config():
    import os
    from config import DEEPSEEK_BASE_URL, MIMO_BASE_URL
    return {
        "deepseek_base_url": DEEPSEEK_BASE_URL,
        "deepseek_api_key_set": bool(os.getenv("DEEPSEEK_API_KEY", "")),
        "mimo_base_url": MIMO_BASE_URL,
        "mimo_api_key_set": bool(os.getenv("MIMO_API_KEY", "")),
    }


@app.post("/api/config/llm")
async def update_llm_config(body: LLMConfigUpdate):
    import os
    from pathlib import Path
    import config as config_module
    from core.gateway.client import MODEL_CONFIG

    updated = []
    env_updates: dict[str, str] = {}

    if body.deepseek_base_url is not None:
        os.environ["DEEPSEEK_BASE_URL"] = body.deepseek_base_url
        config_module.DEEPSEEK_BASE_URL = body.deepseek_base_url
        for model_cfg in MODEL_CONFIG.values():
            if model_cfg.get("api_key_env") == "DEEPSEEK_API_KEY":
                model_cfg["base_url"] = body.deepseek_base_url
        env_updates["DEEPSEEK_BASE_URL"] = body.deepseek_base_url
        updated.append("deepseek_base_url")

    if body.deepseek_api_key is not None:
        os.environ["DEEPSEEK_API_KEY"] = body.deepseek_api_key
        env_updates["DEEPSEEK_API_KEY"] = body.deepseek_api_key
        updated.append("deepseek_api_key")

    if body.mimo_base_url is not None:
        os.environ["MIMO_BASE_URL"] = body.mimo_base_url
        config_module.MIMO_BASE_URL = body.mimo_base_url
        for model_cfg in MODEL_CONFIG.values():
            if model_cfg.get("api_key_env") == "MIMO_API_KEY":
                model_cfg["base_url"] = body.mimo_base_url
        env_updates["MIMO_BASE_URL"] = body.mimo_base_url
        updated.append("mimo_base_url")

    if body.mimo_api_key is not None:
        os.environ["MIMO_API_KEY"] = body.mimo_api_key
        env_updates["MIMO_API_KEY"] = body.mimo_api_key
        updated.append("mimo_api_key")

    if env_updates:
        env_path = Path(__file__).parent / ".env"
        existing: dict[str, str] = {}
        if env_path.exists():
            for line in env_path.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, _, v = line.partition("=")
                    existing[k.strip()] = v.strip()
        existing.update(env_updates)
        env_path.write_text(
            "\n".join(f"{k}={v}" for k, v in existing.items()) + "\n",
            encoding="utf-8",
        )
        logger.info("LLM config persisted to .env: %s", ", ".join(env_updates.keys()))

    logger.info("LLM config updated: %s", ", ".join(updated))
    return {"status": "ok", "updated": updated}
