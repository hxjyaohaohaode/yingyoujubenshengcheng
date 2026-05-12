import uuid
from datetime import datetime, UTC
from sqlalchemy import Column, String, Integer, Text, DateTime, ForeignKey, Boolean
from sqlalchemy.orm import relationship

from database import Base
from models.types import GUID, JSONType


class Scene(Base):
    __tablename__ = "scenes"

    id = Column(GUID, primary_key=True, default=uuid.uuid4)
    project_id = Column(GUID, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    chapter_id = Column(GUID, ForeignKey("chapters.id", ondelete="CASCADE"), nullable=True)
    scene_code = Column(String(30), nullable=False)
    scene_type = Column(String(30), nullable=True)
    location = Column(String(200), nullable=True)
    weather = Column(String(100), nullable=True)
    time_start = Column(String(50), nullable=True)
    time_end = Column(String(50), nullable=True)
    emotion_level = Column(Integer, default=5, server_default="5", nullable=False)
    narration = Column(Text, nullable=True)
    dialogue = Column(JSONType, default=list, server_default="[]", nullable=False)
    actions = Column(JSONType, default=list, server_default="[]", nullable=False)
    foreshadow_ops = Column(JSONType, default=list, server_default="[]", nullable=False)
    choices = Column(JSONType, default=list, server_default="[]", nullable=False)
    causal_chain = Column(JSONType, nullable=True)
    is_wow_moment = Column(Boolean, default=False, server_default="0", nullable=False)
    wow_type = Column(String(30), nullable=True)
    wow_spec = Column(Text, nullable=True)
    characters_involved = Column(JSONType, default=list, server_default="[]", nullable=False)
    status = Column(String(20), default="draft", server_default="draft", nullable=False)
    version = Column(Integer, default=1, server_default="1", nullable=False)
    audit_reports = Column(JSONType, default=list, server_default="[]", nullable=False)
    human_reviewed = Column(Boolean, default=False, server_default="0", nullable=False)
    human_feedback = Column(Text, nullable=True)
    suggestions = Column(JSONType, default=list, server_default="[]", nullable=False)
    git_commit_hash = Column(String(40), nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(UTC), nullable=False)
    updated_at = Column(DateTime, default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC), nullable=False)

    project = relationship("Project", backref="scenes")
    chapter = relationship("Chapter", back_populates="scenes")
    versions = relationship("SceneVersion", back_populates="scene", cascade="all, delete-orphan")


class SceneVersion(Base):
    __tablename__ = "scene_versions"

    id = Column(GUID, primary_key=True, default=uuid.uuid4)
    scene_id = Column(GUID, ForeignKey("scenes.id", ondelete="CASCADE"), nullable=False)
    version = Column(Integer, nullable=False)
    content = Column(JSONType, nullable=False)
    audit_report = Column(JSONType, nullable=True)
    change_reason = Column(String(200), nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(UTC))

    scene = relationship("Scene", back_populates="versions")
