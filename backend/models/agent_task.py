import uuid
from datetime import datetime, UTC
from sqlalchemy import Column, String, Integer, Text, DateTime, ForeignKey
from sqlalchemy.orm import relationship

from database import Base
from models.types import GUID, JSONType


class AgentTask(Base):
    __tablename__ = "agent_tasks"

    id = Column(GUID, primary_key=True, default=uuid.uuid4)
    project_id = Column(GUID, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    task_type = Column(String(30), nullable=False)
    assigned_to = Column(String(20), nullable=False)
    status = Column(String(20), default="pending")
    priority = Column(Integer, default=5)
    payload = Column(JSONType, nullable=False)
    result = Column(JSONType, nullable=True)
    error_message = Column(Text, nullable=True)
    retry_count = Column(Integer, default=0)
    max_retries = Column(Integer, default=3)
    created_at = Column(DateTime, default=lambda: datetime.now(UTC))
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)

    project = relationship("Project", backref="agent_tasks")
