import asyncio
import json
import logging
import time
from datetime import datetime, timezone
from typing import Any

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

logger = logging.getLogger("audit")


class AuditLogger:
    _db_session_factory = None

    @classmethod
    def configure(cls, session_factory):
        cls._db_session_factory = session_factory

    @staticmethod
    def _now_iso() -> str:
        return datetime.now(timezone.utc).isoformat()

    @classmethod
    def log_ai_call(
        cls,
        project_id: str,
        agent_name: str,
        success: bool,
        extra: dict[str, Any] | None = None,
    ):
        record = {
            "event": "ai_api_call",
            "project_id": str(project_id),
            "agent_name": agent_name,
            "timestamp": cls._now_iso(),
            "success": success,
            "extra": extra or {},
        }
        logger.info(json.dumps(record, ensure_ascii=False))
        cls._write_to_db(record)

    @classmethod
    def log_delete(
        cls,
        project_id: str,
        entity_type: str,
        entity_id: str,
    ):
        record = {
            "event": "delete_operation",
            "project_id": str(project_id),
            "entity_type": entity_type,
            "entity_id": str(entity_id),
            "timestamp": cls._now_iso(),
        }
        logger.info(json.dumps(record, ensure_ascii=False))
        cls._write_to_db(record)

    @classmethod
    def log_finalize(
        cls,
        project_id: str,
        scene_id: str,
    ):
        record = {
            "event": "finalize_operation",
            "project_id": str(project_id),
            "scene_id": str(scene_id),
            "timestamp": cls._now_iso(),
        }
        logger.info(json.dumps(record, ensure_ascii=False))
        cls._write_to_db(record)

    @classmethod
    def _write_to_db(cls, record: dict[str, Any]):
        if cls._db_session_factory is None:
            return
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                loop.create_task(cls._async_write_to_db(record))
            else:
                asyncio.ensure_future(cls._async_write_to_db(record))
        except RuntimeError:
            pass

    @classmethod
    async def _async_write_to_db(cls, record: dict[str, Any]):
        if cls._db_session_factory is None:
            return
        try:
            from models.audit import AuditRecord
        except ImportError:
            return
        try:
            async with cls._db_session_factory() as session:
                audit = AuditRecord(
                    project_id=record.get("project_id"),
                    scene_id=record.get("scene_id"),
                    audit_type=record.get("event", "unknown"),
                    checker_results=record,
                    overall_result="pass" if record.get("success", True) else "fail",
                )
                session.add(audit)
                await session.commit()
        except Exception:
            pass


class AuditLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        start = time.time()
        response = await call_next(request)
        duration_ms = (time.time() - start) * 1000

        path = request.url.path
        method = request.method

        if method == "DELETE":
            project_id = self._extract_project_id(path)
            entity_type = self._resolve_entity_type(path)
            entity_id = self._extract_last_uuid(path)
            if project_id:
                AuditLogger.log_delete(
                    project_id=project_id,
                    entity_type=entity_type,
                    entity_id=entity_id or "unknown",
                )

        if "/ai/" in path:
            project_id = self._extract_project_id(path)
            agent_name = self._resolve_agent_name(path)
            success = 200 <= response.status_code < 300
            if project_id:
                AuditLogger.log_ai_call(
                    project_id=project_id,
                    agent_name=agent_name,
                    success=success,
                )

        return response

    @staticmethod
    def _extract_project_id(path: str) -> str | None:
        import re
        uuid_pat = re.compile(
            r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}"
        )
        segments = path.split("/")
        for i, seg in enumerate(segments):
            if seg == "projects" and i + 1 < len(segments):
                candidate = segments[i + 1]
                if uuid_pat.fullmatch(candidate):
                    return candidate
        return None

    @staticmethod
    def _extract_last_uuid(path: str) -> str | None:
        import re
        uuid_pat = re.compile(
            r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}"
        )
        segments = path.split("/")
        for seg in reversed(segments):
            if uuid_pat.fullmatch(seg):
                return seg
        return None

    @staticmethod
    def _resolve_entity_type(path: str) -> str:
        entity_map = {
            "projects": "project",
            "scenes": "scene",
            "chapters": "chapter",
            "characters": "character",
            "relations": "relation",
            "foreshadows": "foreshadow",
        }
        segments = path.split("/")
        for seg in reversed(segments):
            if seg in entity_map:
                return entity_map[seg]
        return "unknown"

    @staticmethod
    def _resolve_agent_name(path: str) -> str:
        if "world-gen" in path:
            return "world_gen"
        if "character-gen" in path:
            return "character_gen"
        if "foreshadow-wow-gen" in path or "wow-plans" in path:
            return "foreshadow_wow_gen"
        if "foreshadow-health" in path:
            return "foreshadow_health"
        if "foreshadow-reaction" in path:
            return "foreshadow_reaction"
        if "scene-gen" in path or "/generate" in path:
            return "scene_gen"
        if "scene-audit" in path or "/audit" in path:
            return "scene_audit"
        if "emotion-curve" in path:
            return "emotion_curve"
        if "foreshadows/generate" in path:
            return "foreshadow_gen"
        return "ai_call"
