import uuid
from datetime import datetime, UTC
from sqlalchemy import Column, String, Integer, Text, DateTime, Boolean, ForeignKey
from sqlalchemy.orm import relationship

from database import Base
from models.types import GUID, JSONType


class Character(Base):
    __tablename__ = "characters"

    id = Column(GUID, primary_key=True, default=uuid.uuid4)
    project_id = Column(GUID, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    char_code = Column(String(20), nullable=False)
    name = Column(String(100), nullable=False)
    role_type = Column(String(20), nullable=True)
    background = Column(Text, nullable=True)
    core_goal = Column(Text, nullable=True)
    core_fear = Column(Text, nullable=True)
    surface_image = Column(Text, nullable=True)
    true_self = Column(Text, nullable=True)
    language_style = Column(Text, nullable=True)
    catchphrase = Column(String(200), nullable=True)
    dark_secret = Column(Text, nullable=True)
    arc_description = Column(Text, nullable=True)
    behavior_inevitable = Column(JSONType, default=list)
    behavior_never = Column(JSONType, default=list)
    behavior_conditional = Column(JSONType, default=list)
    status = Column(String(20), default="active")
    location = Column(String(100), nullable=True)
    emotional_state = Column(String(50), nullable=True)
    physical_state = Column(String(50), nullable=True)
    current_goal = Column(Text, nullable=True)
    known_info = Column(JSONType, default=list)
    created_at = Column(DateTime, default=lambda: datetime.now(UTC))

    project = relationship("Project", backref="characters")


class CharacterRelation(Base):
    __tablename__ = "character_relations"

    id = Column(GUID, primary_key=True, default=uuid.uuid4)
    project_id = Column(GUID, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    char_a_id = Column(GUID, ForeignKey("characters.id", ondelete="CASCADE"), nullable=False)
    char_b_id = Column(GUID, ForeignKey("characters.id", ondelete="CASCADE"), nullable=False)
    relation_type = Column(String(50), nullable=True)
    trust = Column(Integer, default=50)
    favor = Column(Integer, default=50)
    info_known_a_about_b = Column(JSONType, default=list)
    info_known_b_about_a = Column(JSONType, default=list)
    info_asymmetry = Column(JSONType, default=dict)
    is_hidden = Column(Boolean, default=False)
    arc_direction = Column(String(20), default="stable")
    trigger_condition = Column(Text, nullable=True)
    arc_milestones = Column(JSONType, default=list)
    value = Column(Integer, default=50)
    last_interaction = Column(String(50), nullable=True)
    updated_at = Column(DateTime, default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC))

    project = relationship("Project", backref="character_relations")
    char_a = relationship("Character", foreign_keys=[char_a_id])
    char_b = relationship("Character", foreign_keys=[char_b_id])
