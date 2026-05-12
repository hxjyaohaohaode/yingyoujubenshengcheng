import uuid
from datetime import datetime, UTC
from sqlalchemy import Column, String, Text, DateTime, ForeignKey
from sqlalchemy.orm import relationship

from database import Base
from models.types import GUID, JSONType


class AuditRecord(Base):
    __tablename__ = "audit_records"

    id = Column(GUID, primary_key=True, default=uuid.uuid4)
    project_id = Column(GUID, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    scene_id = Column(GUID, ForeignKey("scenes.id", ondelete="CASCADE"), nullable=True)
    audit_type = Column(String(20), nullable=False)
    checker_results = Column(JSONType, nullable=False)
    llm_results = Column(JSONType, nullable=True)
    creative_scores = Column(JSONType, nullable=True)
    overall_result = Column(String(10), nullable=True)
    issues = Column(JSONType, default=list)
    suggestions = Column(JSONType, default=list)
    created_at = Column(DateTime, default=lambda: datetime.now(UTC))

    project = relationship("Project", backref="audit_records")
    scene = relationship("Scene", backref="audit_records")
