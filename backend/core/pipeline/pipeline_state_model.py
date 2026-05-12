"""
PipelineState 数据库模型。
兼容SQLite和PostgreSQL，不使用PG专有类型。
"""

from datetime import datetime, UTC
from sqlalchemy import Column, String, Integer, Text, DateTime, ForeignKey
from sqlalchemy.orm import relationship

from database import Base
from models.types import GUID, JSONType


class PipelineState(Base):
    __tablename__ = "pipeline_state"

    project_id = Column(String(36), ForeignKey("projects.id", ondelete="CASCADE"), primary_key=True)
    template_name = Column(String(100), nullable=False, default="")
    current_phase_index = Column(Integer, default=0)
    current_step_index = Column(Integer, default=0)
    status = Column(String(20), nullable=False, default="not_started")
    result_data = Column(Text, default="{}")
    error_message = Column(Text, default="")
    task_results = Column(Text, default="[]")
    config = Column(Text, default="{}")
    run_id = Column(String(36), nullable=True)
    updated_at = Column(DateTime, default=lambda: datetime.now(UTC))

    project = relationship("Project", backref="pipeline_state")
