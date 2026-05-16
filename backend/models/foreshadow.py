import uuid
from datetime import datetime, UTC
from sqlalchemy import Column, String, Integer, Float, Text, DateTime, ForeignKey, Boolean
from sqlalchemy.orm import relationship

from database import Base
from models.types import GUID, JSONType


class Foreshadow(Base):
    __tablename__ = "foreshadows"

    id = Column(GUID, primary_key=True, default=uuid.uuid4)
    project_id = Column(GUID, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    fs_code = Column(String(20), nullable=False)
    name = Column(String(200), nullable=False)
    fs_type = Column(String(20), nullable=False)
    foreshadow_tier = Column(String(20), default="chapter")
    foreshadow_category = Column(String(20), default="chapter", nullable=False, comment="global|chapter|node|scene")
    surface_layer = Column(Text, nullable=True)
    deep_layer = Column(Text, nullable=True)
    truth_layer = Column(Text, nullable=True)
    plant_scene_id = Column(GUID, nullable=True)
    reinforce_scenes = Column(JSONType, default=list)
    reveal_scene_id = Column(GUID, nullable=True)
    wow_factor = Column(Text, nullable=True)
    player_reaction = Column(Text, nullable=True)
    depends_on = Column(JSONType, default=list)
    enables = Column(JSONType, default=list)
    current_status = Column(String(20), default="design")
    reinforce_count = Column(Integer, default=0)
    health = Column(String(20), default="normal")
    wow_plans = Column(JSONType, default=list)
    wow_selected = Column(String(50), nullable=True)
    worldview_refs = Column(JSONType, default=list)
    character_refs = Column(JSONType, default=list)
    foreshadow_links = Column(JSONType, default=list)
    plant_location = Column(String(100), nullable=True)
    reinforce_locations = Column(JSONType, default=list)
    reveal_location = Column(String(100), nullable=True)
    reclaim_status = Column(String(20), default="unplanted")
    created_at = Column(DateTime, default=lambda: datetime.now(UTC))

    project = relationship("Project", backref="foreshadows")


class ForeshadowRelation(Base):
    __tablename__ = "foreshadow_relations"

    id = Column(GUID, primary_key=True, default=uuid.uuid4)
    project_id = Column(GUID, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    from_fs_id = Column(GUID, ForeignKey("foreshadows.id", ondelete="CASCADE"), nullable=False)
    to_fs_id = Column(GUID, ForeignKey("foreshadows.id", ondelete="CASCADE"), nullable=False)
    relation_type = Column(String(20), nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(UTC))

    project = relationship("Project", backref="foreshadow_relations")
    from_fs = relationship("Foreshadow", foreign_keys=[from_fs_id])
    to_fs = relationship("Foreshadow", foreign_keys=[to_fs_id])


class ForeshadowLink(Base):
    __tablename__ = "foreshadow_links"

    id = Column(GUID, primary_key=True, default=uuid.uuid4)
    project_id = Column(GUID, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    source_id = Column(GUID, ForeignKey("foreshadows.id", ondelete="CASCADE"), nullable=False, index=True)
    target_id = Column(GUID, ForeignKey("foreshadows.id", ondelete="CASCADE"), nullable=False, index=True)
    link_type = Column(String(20), nullable=False)
    strength = Column(Float, default=0.5)
    description = Column(Text, default="")
    created_at = Column(DateTime, default=lambda: datetime.now(UTC))
    updated_at = Column(DateTime, default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC))

    project = relationship("Project", backref="foreshadow_links")
    source = relationship("Foreshadow", foreign_keys=[source_id])
    target = relationship("Foreshadow", foreign_keys=[target_id])
