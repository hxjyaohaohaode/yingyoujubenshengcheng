import uuid
from datetime import datetime, UTC
from sqlalchemy import Column, String, Integer, Text, DateTime, ForeignKey
from sqlalchemy.orm import relationship

from database import Base
from models.types import GUID, JSONType


class Chapter(Base):
    __tablename__ = "chapters"

    id = Column(GUID, primary_key=True, default=uuid.uuid4)
    project_id = Column(GUID, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    chapter_number = Column(Integer, nullable=False)
    title = Column(String(200), nullable=True)
    summary = Column(Text, nullable=True)
    outline = Column(Text, nullable=True)
    core_conflict = Column(Text, nullable=True)
    emotion_target = Column(Integer, default=5, server_default="5", nullable=False)
    key_turning_points = Column(JSONType, default=list, server_default="[]", nullable=False)
    foreshadow_tasks = Column(JSONType, default=list, server_default="[]", nullable=False)
    branch_structure = Column(Text, nullable=True)
    anchor_scenes = Column(JSONType, default=list, server_default="[]", nullable=False)
    focus_characters = Column(JSONType, default=list, server_default="[]", nullable=False)
    worldview_refs = Column(JSONType, default=list, server_default="[]", nullable=False)
    status = Column(String(20), default="draft", server_default="draft", nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(UTC), nullable=False)

    project = relationship("Project", backref="chapters")
    scenes = relationship("Scene", back_populates="chapter", cascade="all, delete-orphan")
    sections = relationship("ChapterSection", back_populates="chapter", cascade="all, delete-orphan", order_by="ChapterSection.section_number")


class ChapterSection(Base):
    __tablename__ = "chapter_sections"

    id = Column(GUID, primary_key=True, default=uuid.uuid4)
    project_id = Column(GUID, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    chapter_id = Column(GUID, ForeignKey("chapters.id", ondelete="CASCADE"), nullable=False)
    section_number = Column(Integer, nullable=False)
    title = Column(String(200), nullable=True)
    word_target = Column(Integer, default=1000, server_default="1000", nullable=False)
    emotion_target = Column(Integer, default=5, server_default="5", nullable=False)
    scene_ids = Column(JSONType, default=list, server_default="[]", nullable=False)
    choices = Column(JSONType, nullable=True)
    foreshadow_tasks = Column(JSONType, default=list, server_default="[]", nullable=False)
    focus_characters = Column(JSONType, default=list, server_default="[]", nullable=False)
    branch_type = Column(String(50), default="exploration", server_default="exploration", nullable=False)
    summary = Column(Text, nullable=True)
    status = Column(String(20), default="draft", server_default="draft", nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(UTC), nullable=False)
    updated_at = Column(DateTime, default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC), nullable=False)

    project = relationship("Project", backref="chapter_sections")
    chapter = relationship("Chapter", back_populates="sections")
