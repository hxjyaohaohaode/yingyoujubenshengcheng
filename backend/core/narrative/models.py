import uuid
from datetime import datetime
from sqlalchemy import Column, String, Integer, Float, Text, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from database import Base


class NarrativeMemory(Base):
    __tablename__ = 'narrative_memory'

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id = Column(UUID(as_uuid=True), ForeignKey('projects.id', ondelete='CASCADE'), nullable=False)
    memory_type = Column(String(20), nullable=False)
    category = Column(String(50), nullable=False)
    entity_id = Column(String(36), nullable=True)
    content = Column(Text, nullable=False)
    scene_anchor = Column(String(36), nullable=True)
    chapter_anchor = Column(String(36), nullable=True)
    priority = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class WordBudget(Base):
    __tablename__ = 'word_budget'

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id = Column(UUID(as_uuid=True), ForeignKey('projects.id', ondelete='CASCADE'), nullable=False)
    chapter_id = Column(UUID(as_uuid=True), ForeignKey('chapters.id', ondelete='CASCADE'), nullable=True)
    scene_id = Column(UUID(as_uuid=True), ForeignKey('scenes.id', ondelete='CASCADE'), nullable=True)
    target_words = Column(Integer, nullable=False)
    actual_words = Column(Integer, default=0)
    tolerance_pct = Column(Float, default=20.0)