"""
SQLite/PostgreSQL 兼容类型。

在 SQLite 下使用 String/Text + TypeDecorator 模拟 UUID/JSONB，
在 PostgreSQL 下使用原生类型。
"""

import json
import uuid as _uuid
from sqlalchemy import String, Text, TypeDecorator
from sqlalchemy.dialects.postgresql import UUID as _PG_UUID, JSONB as _PG_JSONB


def _is_postgresql():
    from config import DATABASE_URL
    return "postgresql" in DATABASE_URL.lower()


class GUID(TypeDecorator):
    """Platform-independent UUID type.
    Uses PostgreSQL's UUID type, otherwise uses String(36).
    """
    impl = String(36)
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            return dialect.type_descriptor(_PG_UUID(as_uuid=True))
        return dialect.type_descriptor(String(36))

    def process_bind_param(self, value, dialect):
        if value is None:
            return value
        if dialect.name == "postgresql":
            return value
        if isinstance(value, _uuid.UUID):
            return str(value)
        return str(value)

    def process_result_value(self, value, dialect):
        if value is None:
            return value
        if not isinstance(value, _uuid.UUID):
            value = _uuid.UUID(str(value))
        return value


class JSONType(TypeDecorator):
    """Platform-independent JSON type.
    Uses PostgreSQL's JSONB type, otherwise uses Text with JSON serialization.
    """
    impl = Text
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            return dialect.type_descriptor(_PG_JSONB)
        return dialect.type_descriptor(Text)

    def process_bind_param(self, value, dialect):
        if value is None:
            return value
        if dialect.name == "postgresql":
            return value
        return json.dumps(value, ensure_ascii=False)

    def process_result_value(self, value, dialect):
        if value is None:
            return value
        if dialect.name == "postgresql":
            return value
        if isinstance(value, str):
            try:
                return json.loads(value)
            except (json.JSONDecodeError, TypeError):
                return value
        return value
