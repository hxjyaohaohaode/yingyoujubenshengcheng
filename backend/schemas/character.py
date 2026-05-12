import uuid
from datetime import datetime
from typing import Optional, Any
from pydantic import BaseModel, Field, field_validator

VALID_ROLE_TYPES = ["protagonist", "antagonist", "love_interest", "rival", "mentor", "sidekick", "supporting", "minor", "cameo", "foil"]


class CharacterCreate(BaseModel):
    char_code: str = Field(..., min_length=1, max_length=20)
    name: str = Field(..., min_length=1, max_length=100)
    role_type: Optional[str] = None
    background: Optional[str] = None
    core_goal: Optional[str] = None
    core_fear: Optional[str] = None
    surface_image: Optional[str] = None
    true_self: Optional[str] = None
    language_style: Optional[str] = None
    catchphrase: Optional[str] = None
    dark_secret: Optional[str] = None
    arc_description: Optional[str] = None
    behavior_inevitable: list[Any] = []
    behavior_never: list[Any] = []
    behavior_conditional: list[Any] = []
    status: str = "active"

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        stripped = v.strip()
        if len(stripped) < 1 or len(stripped) > 100:
            raise ValueError("角色名称长度必须在1-100个字符之间")
        return stripped

    @field_validator("role_type")
    @classmethod
    def validate_role_type(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        if v not in VALID_ROLE_TYPES:
            raise ValueError(f"无效的角色类型，允许: {', '.join(VALID_ROLE_TYPES)}")
        return v


class CharacterUpdate(BaseModel):
    char_code: Optional[str] = None
    name: Optional[str] = None
    role_type: Optional[str] = None
    background: Optional[str] = None
    core_goal: Optional[str] = None
    core_fear: Optional[str] = None
    surface_image: Optional[str] = None
    true_self: Optional[str] = None
    language_style: Optional[str] = None
    catchphrase: Optional[str] = None
    dark_secret: Optional[str] = None
    arc_description: Optional[str] = None
    behavior_inevitable: Optional[list[Any]] = None
    behavior_never: Optional[list[Any]] = None
    behavior_conditional: Optional[list[Any]] = None
    status: Optional[str] = None

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        stripped = v.strip()
        if len(stripped) < 1 or len(stripped) > 100:
            raise ValueError("角色名称长度必须在1-100个字符之间")
        return stripped

    @field_validator("role_type")
    @classmethod
    def validate_role_type(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        if v not in VALID_ROLE_TYPES:
            raise ValueError(f"无效的角色类型，允许: {', '.join(VALID_ROLE_TYPES)}")
        return v


class CharacterResponse(BaseModel):
    id: uuid.UUID
    project_id: uuid.UUID
    char_code: str
    name: str
    role_type: Optional[str] = None
    background: Optional[str] = None
    core_goal: Optional[str] = None
    core_fear: Optional[str] = None
    surface_image: Optional[str] = None
    true_self: Optional[str] = None
    language_style: Optional[str] = None
    catchphrase: Optional[str] = None
    dark_secret: Optional[str] = None
    arc_description: Optional[str] = None
    behavior_inevitable: Any = []
    behavior_never: Any = []
    behavior_conditional: Any = []
    status: str = "active"
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class RelationCreate(BaseModel):
    char_a_id: uuid.UUID
    char_b_id: uuid.UUID
    relation_type: Optional[str] = None
    trust: int = 50
    favor: int = 50
    info_known_a_about_b: list[Any] = []
    info_known_b_about_a: list[Any] = []
    info_asymmetry: dict[str, Any] = {}
    is_hidden: bool = False
    arc_direction: str = "stable"
    trigger_condition: Optional[str] = None
    arc_milestones: list[Any] = []


class RelationUpdate(BaseModel):
    relation_type: Optional[str] = None
    trust: Optional[int] = None
    favor: Optional[int] = None
    info_known_a_about_b: Optional[list[Any]] = None
    info_known_b_about_a: Optional[list[Any]] = None
    info_asymmetry: Optional[dict[str, Any]] = None
    is_hidden: Optional[bool] = None
    arc_direction: Optional[str] = None
    trigger_condition: Optional[str] = None
    arc_milestones: Optional[list[Any]] = None


class RelationResponse(BaseModel):
    id: uuid.UUID
    project_id: uuid.UUID
    char_a_id: uuid.UUID
    char_b_id: uuid.UUID
    relation_type: Optional[str] = None
    trust: int = 50
    favor: int = 50
    info_known_a_about_b: Any = []
    info_known_b_about_a: Any = []
    info_asymmetry: Any = {}
    is_hidden: bool = False
    arc_direction: str = "stable"
    trigger_condition: Optional[str] = None
    arc_milestones: Any = []
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True
