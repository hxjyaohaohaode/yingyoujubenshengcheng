import re
import uuid
from datetime import datetime
from typing import Optional, Any
from pydantic import BaseModel, Field, field_validator

FS_CODE_PATTERN = re.compile(r"^(F-[A-Z]+-\d{3}|FS-\d{3,}|F[A-Z]-\d{3,})$")
VALID_FS_TYPES = ["global", "chapter", "scene", "interactive"]
VALID_FS_STATUSES = ["design", "active", "planted", "reinforced", "revealed", "abandoned"]


class ForeshadowCreate(BaseModel):
    fs_code: str = Field(..., min_length=1, max_length=20)
    name: str = Field(..., min_length=1, max_length=200)
    fs_type: str = Field(..., min_length=1, max_length=20)
    foreshadow_tier: Optional[str] = "chapter"
    surface_layer: Optional[str] = None
    deep_layer: Optional[str] = None
    truth_layer: Optional[str] = None
    plant_scene_id: Optional[uuid.UUID] = None
    reinforce_scenes: list[Any] = []
    reveal_scene_id: Optional[uuid.UUID] = None
    wow_factor: Optional[str] = None
    player_reaction: Optional[str] = None
    depends_on: list[Any] = []
    enables: list[Any] = []
    current_status: str = "design"
    reinforce_count: int = 0
    health: str = "normal"
    wow_plans: list[Any] = []
    wow_selected: Optional[str] = None
    worldview_refs: list[Any] = []
    character_refs: list[Any] = []
    foreshadow_links: list[Any] = []
    plant_location: Optional[str] = None
    reinforce_locations: list[Any] = []
    reveal_location: Optional[str] = None
    reclaim_status: Optional[str] = "unplanted"

    @field_validator("fs_code")
    @classmethod
    def validate_fs_code(cls, v: str) -> str:
        if not FS_CODE_PATTERN.match(v):
            raise ValueError("伏笔编号格式错误，支持 F-XXX-000 / FS-001 / FA-001 等格式")
        return v

    @field_validator("fs_type")
    @classmethod
    def validate_fs_type(cls, v: str) -> str:
        if v not in VALID_FS_TYPES:
            raise ValueError(f"无效的伏笔类型，允许: {', '.join(VALID_FS_TYPES)}")
        return v

    @field_validator("current_status")
    @classmethod
    def validate_current_status(cls, v: str) -> str:
        if v not in VALID_FS_STATUSES:
            raise ValueError(f"无效的伏笔状态，允许: {', '.join(VALID_FS_STATUSES)}")
        return v


class ForeshadowUpdate(BaseModel):
    fs_code: Optional[str] = None
    name: Optional[str] = None
    fs_type: Optional[str] = None
    foreshadow_tier: Optional[str] = None
    surface_layer: Optional[str] = None
    deep_layer: Optional[str] = None
    truth_layer: Optional[str] = None
    plant_scene_id: Optional[uuid.UUID] = None
    reinforce_scenes: Optional[list[Any]] = None
    reveal_scene_id: Optional[uuid.UUID] = None
    wow_factor: Optional[str] = None
    player_reaction: Optional[str] = None
    depends_on: Optional[list[Any]] = None
    enables: Optional[list[Any]] = None
    current_status: Optional[str] = None
    reinforce_count: Optional[int] = None
    health: Optional[str] = None
    wow_plans: Optional[list[Any]] = None
    wow_selected: Optional[str] = None
    worldview_refs: Optional[list[Any]] = None
    character_refs: Optional[list[Any]] = None
    foreshadow_links: Optional[list[Any]] = None
    plant_location: Optional[str] = None
    reinforce_locations: Optional[list[Any]] = None
    reveal_location: Optional[str] = None
    reclaim_status: Optional[str] = None

    @field_validator("fs_code")
    @classmethod
    def validate_fs_code(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        if not FS_CODE_PATTERN.match(v):
            raise ValueError("伏笔编号格式错误，支持 F-XXX-000 / FS-001 / FA-001 等格式")
        return v

    @field_validator("fs_type")
    @classmethod
    def validate_fs_type(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        if v not in VALID_FS_TYPES:
            raise ValueError(f"无效的伏笔类型，允许: {', '.join(VALID_FS_TYPES)}")
        return v


class ForeshadowResponse(BaseModel):
    id: uuid.UUID
    project_id: uuid.UUID
    fs_code: str
    name: str
    fs_type: str
    foreshadow_tier: Optional[str] = "chapter"
    surface_layer: Optional[str] = None
    deep_layer: Optional[str] = None
    truth_layer: Optional[str] = None
    plant_scene_id: Optional[uuid.UUID] = None
    reinforce_scenes: Any = []
    reveal_scene_id: Optional[uuid.UUID] = None
    wow_factor: Optional[str] = None
    player_reaction: Optional[str] = None
    depends_on: Any = []
    enables: Any = []
    current_status: str = "design"
    reinforce_count: int = 0
    health: str = "normal"
    wow_plans: Any = []
    wow_selected: Optional[str] = None
    worldview_refs: Any = []
    character_refs: Any = []
    foreshadow_links: Any = []
    plant_location: Optional[str] = None
    reinforce_locations: Any = []
    reveal_location: Optional[str] = None
    reclaim_status: Optional[str] = "unplanted"
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class ForeshadowRelationCreate(BaseModel):
    from_fs_id: uuid.UUID
    to_fs_id: uuid.UUID
    relation_type: str = Field(..., min_length=1, max_length=20)


class ForeshadowRelationResponse(BaseModel):
    id: uuid.UUID
    project_id: uuid.UUID
    from_fs_id: uuid.UUID
    to_fs_id: uuid.UUID
    relation_type: str
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True
