import logging
from contextlib import asynccontextmanager

try:
    import redis.asyncio as aioredis
    _REDIS_AVAILABLE = True
except ImportError:
    aioredis = None
    _REDIS_AVAILABLE = False

from fastapi import FastAPI, Depends, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from pydantic import BaseModel

from config import CORS_ORIGINS, APP_ENV, REDIS_URL, DATABASE_URL
from database import init_db, close_db, async_session_factory, check_db_health, get_db
from middleware.rate_limit import RateLimitMiddleware
from middleware.audit_log import AuditLogger, AuditLoggingMiddleware
from api import projects, characters, foreshadows, scenes, chapters, ai, export, pipeline, upload, search
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
        from sqlalchemy import text as _txt
        async with async_session_factory() as sess:
            await sess.execute(_txt("""
                CREATE TABLE IF NOT EXISTS project_files (
                    id VARCHAR(36) PRIMARY KEY,
                    project_id VARCHAR(36) NOT NULL,
                    filename VARCHAR(255) NOT NULL,
                    file_type VARCHAR(20) NOT NULL DEFAULT '',
                    file_size INTEGER NOT NULL DEFAULT 0,
                    page_count INTEGER NOT NULL DEFAULT 1,
                    text_preview TEXT DEFAULT '',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """))
            await sess.execute(_txt("""
                CREATE TABLE IF NOT EXISTS search_cache (
                    cache_key TEXT PRIMARY KEY,
                    entity_name TEXT NOT NULL DEFAULT '',
                    result_json TEXT NOT NULL DEFAULT '[]',
                    searched_at TEXT NOT NULL DEFAULT '',
                    ttl INTEGER NOT NULL DEFAULT 86400
                )
            """))
            await sess.commit()
        logger.info("project_files / search_cache 表确认完成")
    except Exception as e:
        logger.warning(f"project_files / search_cache 建表跳过: {e}")

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

            conn.execute("UPDATE scenes SET is_wow_moment = 0 WHERE is_wow_moment IS NULL")
            conn.execute("UPDATE scenes SET version = 1 WHERE version IS NULL")
            conn.execute("UPDATE scenes SET human_reviewed = 0 WHERE human_reviewed IS NULL")
            conn.execute("UPDATE scenes SET emotion_level = 5 WHERE emotion_level IS NULL")
            conn.execute("UPDATE scenes SET status = 'draft' WHERE status IS NULL")
            conn.execute("UPDATE scenes SET dialogue = '[]' WHERE dialogue IS NULL")
            conn.execute("UPDATE scenes SET actions = '[]' WHERE actions IS NULL")
            conn.execute("UPDATE scenes SET foreshadow_ops = '[]' WHERE foreshadow_ops IS NULL")
            conn.execute("UPDATE scenes SET choices = '[]' WHERE choices IS NULL")
            conn.execute("UPDATE scenes SET characters_involved = '[]' WHERE characters_involved IS NULL")
            conn.execute("UPDATE scenes SET audit_reports = '[]' WHERE audit_reports IS NULL")
            conn.commit()
            logger.info("数据库迁移：已修复 scenes 表 NULL 值")

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
app.include_router(upload.router, prefix="/api", tags=["upload"])
app.include_router(search.router, prefix="/api", tags=["search"])
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
    brave_api_key: str | None = None
    serpapi_key: str | None = None
    bing_api_key: str | None = None


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
        "brave_api_key_set": bool(os.getenv("BRAVE_API_KEY", "")),
        "serpapi_key_set": bool(os.getenv("SERPAPI_KEY", "")),
        "bing_api_key_set": bool(os.getenv("BING_API_KEY", "")),
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

    if body.brave_api_key is not None:
        os.environ["BRAVE_API_KEY"] = body.brave_api_key
        import core.search.brave_search as _bs
        _bs.BRAVE_API_KEY = body.brave_api_key
        env_updates["BRAVE_API_KEY"] = body.brave_api_key
        updated.append("brave_api_key")

    if body.serpapi_key is not None:
        os.environ["SERPAPI_KEY"] = body.serpapi_key
        import core.search.brave_search as _bs2
        _bs2.SERPAPI_KEY = body.serpapi_key
        env_updates["SERPAPI_KEY"] = body.serpapi_key
        updated.append("serpapi_key")

    if body.bing_api_key is not None:
        os.environ["BING_API_KEY"] = body.bing_api_key
        import core.search.brave_search as _bs3
        _bs3.BING_API_KEY = body.bing_api_key
        env_updates["BING_API_KEY"] = body.bing_api_key
        updated.append("bing_api_key")

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

# ===== 叙事记忆API =====
@app.get("/api/projects/{project_id}/narrative-memory")
async def get_narrative_memory(project_id: str, db=Depends(get_db)):
    from core.narrative.memory_loader import build_narrative_context
    ctx = await build_narrative_context(db, project_id)
    return {"project_id": project_id, "narrative_context": ctx}


@app.get("/api/projects/{project_id}/narrative-memory/category/{category}")
async def get_narrative_memory_by_category(project_id: str, category: str, db=Depends(get_db)):
    from core.narrative.memory_store import get_long_term_memories
    memories = await get_long_term_memories(db, project_id, category)
    return {
        "project_id": project_id,
        "category": category,
        "memories": [{"id": str(m.id), "content": m.content, "entity_id": m.entity_id} for m in memories],
    }

# ===== 全局审查API =====
@app.post("/api/projects/{project_id}/review/global")
async def trigger_global_review(project_id: str, db=Depends(get_db)):
    from core.narrative.revision_orchestrator import run_global_review
    report = await run_global_review(db, project_id)
    return {
        "project_id": project_id,
        "structure_issues": report.structure_issues,
        "rhythm_issues": report.rhythm_issues,
        "unresolved_foreshadows": report.unresolved_foreshadows,
        "character_arc_issues": report.character_arc_issues,
        "overall_score": report.overall_score,
        "summary": report.summary,
    }

# ===== 单场景精炼API =====
@app.post("/api/scenes/{scene_id}/refine")
async def refine_scene(scene_id: str, project_id: str, db=Depends(get_db)):
    from core.narrative.revision_orchestrator import refine_scene
    from models.scene import Scene
    from sqlalchemy import select
    scene = (await db.execute(select(Scene).where(Scene.id == scene_id))).scalar_one_or_none()
    if not scene:
        raise HTTPException(status_code=404, detail="场景不存在")
    result = await refine_scene(db, project_id, scene_id, scene.narration or "")
    return {
        "scene_id": scene_id,
        "all_passed": result.all_passed,
        "iterations": result.iterations,
        "refined_content": result.refined_content,
        "checks_before": [{"layer": c.layer, "passed": c.passed, "score": c.score, "issues": c.issues} for c in result.checks_before],
        "checks_after": [{"layer": c.layer, "passed": c.passed, "score": c.score, "issues": c.issues} for c in result.checks_after],
        "changes_summary": result.changes_summary,
    }

# ===== 字数规划API =====
@app.get("/api/projects/{project_id}/word-budget")
async def get_word_budget(project_id: str, db=Depends(get_db)):
    from core.narrative.word_budget import get_project_budgets
    budgets = await get_project_budgets(db, project_id)
    return {
        "project_id": project_id,
        "budgets": [
            {
                "id": str(b.id),
                "target_words": b.target_words,
                "actual_words": b.actual_words,
                "chapter_id": str(b.chapter_id) if b.chapter_id else None,
                "scene_id": str(b.scene_id) if b.scene_id else None,
            }
            for b in budgets
        ],
    }


@app.put("/api/projects/{project_id}/word-budget")
async def update_word_budget(project_id: str, body: dict, db=Depends(get_db)):
    from core.narrative.word_budget import save_budget, allocate_chapter_budget, allocate_scene_budget
    total_words = body.get("total_words", 500000)
    chapter_count = body.get("chapter_count", 10)
    chapters = allocate_chapter_budget(total_words, chapter_count, body.get("chapter_weights"))
    results = []
    for i, ch_words in enumerate(chapters):
        scene_count = body.get("scenes_per_chapter", 5)
        scene_words = allocate_scene_budget(ch_words, scene_count)
        for j, sw in enumerate(scene_words):
            budget = await save_budget(db, project_id, f"ch_{i+1}", f"sc_{i+1}_{j+1}", sw)
            results.append({"chapter_index": i + 1, "scene_index": j + 1, "target_words": sw})
    return {"project_id": project_id, "total_words": total_words, "allocations": results}


# ===== 大纲架构工作台API =====
@app.get("/api/projects/{project_id}/outline-graph")
async def get_outline_graph(project_id: str, db=Depends(get_db)):
    from core.outline.outline_service import load_outline_graph
    graph = await load_outline_graph(db, project_id)
    return {
        "project_id": project_id,
        "nodes": [
            {
                "id": n.id, "node_type": n.node_type, "title": n.title,
                "summary": n.summary, "position_x": n.position_x, "position_y": n.position_y,
                "parent_id": n.parent_id, "arc_type": n.arc_type,
                "emotion_target": n.emotion_target, "word_target": n.word_target,
                "metadata": n.metadata,
            }
            for n in graph.nodes
        ],
        "edges": [
            {
                "id": e.id, "source_id": e.source_id, "target_id": e.target_id,
                "edge_type": e.edge_type, "label": e.label, "metadata": e.metadata,
            }
            for e in graph.edges
        ],
    }


@app.post("/api/projects/{project_id}/outline-graph/generate")
async def generate_outline_graph(project_id: str, body: dict, db=Depends(get_db)):
    from core.outline.outline_service import ai_generate_outline, save_outline_graph
    graph = await ai_generate_outline(
        db=db, project_id=project_id,
        genre=body.get("genre", ""),
        theme=body.get("theme", ""),
        core_contradiction=body.get("core_contradiction", ""),
        target_chapters=body.get("target_chapters", 10),
        narrative_structure=body.get("narrative_structure", "three_act"),
        user_description=body.get("user_description", ""),
    )
    save_result = await save_outline_graph(db, project_id, graph)
    return {
        "project_id": project_id,
        "nodes": [
            {
                "id": n.id, "node_type": n.node_type, "title": n.title,
                "summary": n.summary, "position_x": n.position_x, "position_y": n.position_y,
                "parent_id": n.parent_id, "arc_type": n.arc_type,
                "emotion_target": n.emotion_target, "word_target": n.word_target,
                "metadata": n.metadata,
            }
            for n in graph.nodes
        ],
        "edges": [
            {
                "id": e.id, "source_id": e.source_id, "target_id": e.target_id,
                "edge_type": e.edge_type, "label": e.label, "metadata": e.metadata,
            }
            for e in graph.edges
        ],
        "save_result": save_result,
    }


@app.put("/api/projects/{project_id}/outline-graph")
async def update_outline_graph(project_id: str, body: dict, db=Depends(get_db)):
    from core.outline.outline_service import OutlineNode, OutlineEdge, OutlineGraph, save_outline_graph
    nodes = [
        OutlineNode(
            id=n.get("id", ""), node_type=n.get("node_type", "chapter"),
            title=n.get("title", ""), summary=n.get("summary", ""),
            position_x=n.get("position_x", 0), position_y=n.get("position_y", 0),
            parent_id=n.get("parent_id"), arc_type=n.get("arc_type", "main"),
            emotion_target=n.get("emotion_target", 5),
            word_target=n.get("word_target", 0),
            metadata=n.get("metadata", {}),
        )
        for n in body.get("nodes", [])
    ]
    edges = [
        OutlineEdge(
            id=e.get("id", ""), source_id=e.get("source_id", ""),
            target_id=e.get("target_id", ""), edge_type=e.get("edge_type", "sequence"),
            label=e.get("label", ""), metadata=e.get("metadata", {}),
        )
        for e in body.get("edges", [])
    ]
    graph = OutlineGraph(nodes=nodes, edges=edges)
    result = await save_outline_graph(db, project_id, graph)
    return result


@app.post("/api/projects/{project_id}/outline-graph/modify")
async def modify_outline_graph(project_id: str, body: dict, db=Depends(get_db)):
    from core.outline.outline_service import (
        load_outline_graph, ai_modify_outline, save_outline_graph,
    )
    current_graph = await load_outline_graph(db, project_id)
    modified_graph = await ai_modify_outline(
        db=db, project_id=project_id,
        current_graph=current_graph,
        instruction=body.get("instruction", ""),
    )
    save_result = await save_outline_graph(db, project_id, modified_graph)
    return {
        "project_id": project_id,
        "nodes": [
            {
                "id": n.id, "node_type": n.node_type, "title": n.title,
                "summary": n.summary, "position_x": n.position_x, "position_y": n.position_y,
                "parent_id": n.parent_id, "arc_type": n.arc_type,
                "emotion_target": n.emotion_target, "word_target": n.word_target,
                "metadata": n.metadata,
            }
            for n in modified_graph.nodes
        ],
        "edges": [
            {
                "id": e.id, "source_id": e.source_id, "target_id": e.target_id,
                "edge_type": e.edge_type, "label": e.label, "metadata": e.metadata,
            }
            for e in modified_graph.edges
        ],
        "save_result": save_result,
    }


@app.post("/api/projects/{project_id}/outline-graph/sync")
async def sync_outline_to_chapters(project_id: str, db=Depends(get_db)):
    from core.outline.outline_service import load_outline_graph, sync_outline_to_chapters
    graph = await load_outline_graph(db, project_id)
    result = await sync_outline_to_chapters(db, project_id, graph)
    return result


@app.post("/api/projects/{project_id}/outline-graph/parse-document")
async def parse_document_to_outline(project_id: str, file: UploadFile, db=Depends(get_db)):
    from core.outline.outline_service import parse_document_to_outline, save_outline_graph
    content = await file.read()
    graph = await parse_document_to_outline(db, project_id, content, file.filename or "unknown.txt")
    if graph.nodes:
        await save_outline_graph(db, project_id, graph)
    return {
        "nodes": [
            {"id": n.id, "node_type": n.node_type, "title": n.title, "summary": n.summary,
             "position_x": n.position_x, "position_y": n.position_y,
             "parent_id": n.parent_id, "arc_type": n.arc_type,
             "emotion_target": n.emotion_target, "word_target": n.word_target,
             "metadata": n.metadata}
            for n in graph.nodes
        ],
        "edges": [
            {"id": e.id, "source_id": e.source_id, "target_id": e.target_id,
             "edge_type": e.edge_type, "label": e.label, "metadata": e.metadata}
            for e in graph.edges
        ],
    }
