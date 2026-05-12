import uuid
from datetime import datetime, UTC
from sqlalchemy import Column, String, Integer, Text, DateTime, ForeignKey
from sqlalchemy.orm import relationship

from database import Base
from models.types import GUID, JSONType


class Element(Base):
    __tablename__ = "elements"

    id = Column(GUID, primary_key=True, default=uuid.uuid4)
    project_id = Column(GUID, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    element_type = Column(String(20), nullable=False)
    element_code = Column(String(20), nullable=False)
    name = Column(String(200), nullable=False)
    status = Column(String(20), default="active")
    first_appear_scene_code = Column(String(30), nullable=True)
    last_update_scene_code = Column(String(30), nullable=True)
    description = Column(Text, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(UTC))

    project = relationship("Project", backref="elements")


class InfoPoint(Base):
    __tablename__ = "info_points"

    id = Column(GUID, primary_key=True, default=uuid.uuid4)
    project_id = Column(GUID, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    info_code = Column(String(20), nullable=False)
    content = Column(Text, nullable=False)
    importance = Column(String(10), nullable=True)
    known_by = Column(JSONType, default=list)
    planted_in_scene_code = Column(String(30), nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(UTC))

    project = relationship("Project", backref="info_points")
