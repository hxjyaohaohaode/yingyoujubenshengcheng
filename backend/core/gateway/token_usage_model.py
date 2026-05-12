"""
TokenUsage 数据库模型: 记录每次模型调用的 token 用量和费用。
"""

import uuid
from datetime import datetime, UTC
from sqlalchemy import Column, String, Integer, DateTime, ForeignKey, Numeric
from sqlalchemy.orm import relationship

from database import Base
from models.types import GUID


class TokenUsage(Base):
    __tablename__ = "token_usage"

    id = Column(GUID, primary_key=True, default=uuid.uuid4)
    project_id = Column(GUID, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    agent_name = Column(String(50), nullable=False)
    intent = Column(String(50), nullable=False)
    model = Column(String(50), nullable=False)
    input_tokens = Column(Integer, nullable=False)
    output_tokens = Column(Integer, nullable=False)
    cost = Column(Numeric(10, 6), nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(UTC))

    project = relationship("Project", backref="token_usages")
