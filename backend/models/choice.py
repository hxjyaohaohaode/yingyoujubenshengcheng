import uuid
from datetime import datetime, UTC
from sqlalchemy import Column, String, Integer, Text, Boolean, DateTime, ForeignKey
from sqlalchemy.orm import relationship

from database import Base
from models.types import GUID, JSONType


class ChoiceDesign(Base):
    __tablename__ = "choice_designs"

    id = Column(GUID, primary_key=True, default=uuid.uuid4)
    project_id = Column(GUID, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    section_id = Column(GUID, ForeignKey("chapter_sections.id", ondelete="CASCADE"), nullable=False)
    choice_number = Column(Integer, nullable=False)
    text = Column(Text, nullable=False)
    consequence_direct = Column(Text, nullable=True)
    consequence_indirect = Column(Text, nullable=True)
    consequence_long_term = Column(Text, nullable=True)
    character_impact = Column(JSONType, default=list, server_default="[]", nullable=False)
    is_hidden = Column(Boolean, default=False, server_default="0", nullable=False)
    hidden_condition = Column(Text, nullable=True)
    moral_alignment = Column(String(20), default="gray", server_default="gray", nullable=False)
    branch_target = Column(String(200), nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(UTC), nullable=False)
    updated_at = Column(DateTime, default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC), nullable=False)

    project = relationship("Project", backref="choice_designs")
    section = relationship("ChapterSection", backref="choice_designs")
