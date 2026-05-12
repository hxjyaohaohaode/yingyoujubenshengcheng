import uuid
from datetime import datetime, UTC
from sqlalchemy import Column, Integer, DateTime, ForeignKey, Boolean, String
from sqlalchemy.orm import relationship

from database import Base
from models.types import GUID


class EmotionCurve(Base):
    __tablename__ = "emotion_curve"

    id = Column(GUID, primary_key=True, default=uuid.uuid4)
    project_id = Column(GUID, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    chapter_id = Column(GUID, ForeignKey("chapters.id", ondelete="SET NULL"), nullable=True)
    scene_id = Column(GUID, ForeignKey("scenes.id", ondelete="SET NULL"), nullable=True)
    target_emotion = Column(Integer, nullable=True)
    actual_emotion = Column(Integer, nullable=True)
    is_wow_moment = Column(Boolean, default=False)
    wow_type = Column(String(30), nullable=True)
    position_order = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(UTC))

    project = relationship("Project", backref="emotion_curves")
    chapter = relationship("Chapter", backref="emotion_curves")
    scene = relationship("Scene", backref="emotion_curves")
