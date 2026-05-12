"""
Embedding 数据库模型: pgvector 向量存储表。
"""

import uuid
from datetime import datetime, UTC
from sqlalchemy import Column, String, Text, DateTime, ForeignKey
from sqlalchemy.orm import relationship

from database import Base
from models.types import GUID, JSONType


class Embedding(Base):
    __tablename__ = "embeddings"

    id = Column(GUID, primary_key=True, default=uuid.uuid4)
    project_id = Column(String, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    content_type = Column(String(20), nullable=False)
    content_id = Column(GUID, nullable=False)
    chunk_text = Column(Text, nullable=False)
    embedding = Column(Text, nullable=True)
    extra_data = Column("metadata", JSONType, default=dict)
    created_at = Column(DateTime, default=lambda: datetime.now(UTC))

    project = relationship("Project", backref="embeddings")
