import re
import uuid
from datetime import datetime
from typing import Optional, Any
from pydantic import BaseModel, Field, field_validator

SCENE_CODE_PATTERN = re.compile(r"^(CH\d{2}-S\d{2}(-[A-Z])?|SC-\d{3,})$")
VALID_SCENE_STATUS = ["draft", "auditing", "passed", "rejected", "approved", "final"]


class SceneCreate(BaseModel):
    scene_code: str = Field(..., min_length=1, max_length=30)
    chapter_id: Optional[uuid.UUID] = None
    scene_type: Optional[str] = None
    location: Optional[str] = None
    weather: Optional[str] = None
    time_start: Optional[str] = None
    time_end: Optional[str] = None
    emotion_level: int = 5
    narration: Optional[str] = None
    dialogue: list[Any] = []
    actions: list[Any] = []
    foreshadow_ops: list[Any] = []
    choices: list[Any] = []
    causal_chain: Optional[Any] = None
    is_wow_moment: bool = False
    wow_type: Optional[str] = None
    wow_spec: Optional[str] = None
    characters_involved: list[Any] = []
    status: str = "draft"

    @field_validator("scene_code")
    @classmethod
    def validate_scene_code(cls, v: str) -> str:
        if not SCENE_CODE_PATTERN.match(v):
            raise ValueError("场景编号格式错误，必须匹配 CH00-S00 或 CH00-S00-A 格式")
        return v

    @field_validator("emotion_level")
    @classmethod
    def validate_emotion_level(cls, v: int) -> int:
        if v < 0 or v > 10:
            raise ValueError("情感等级必须在0-10之间")
        return v

    @field_validator("status")
    @classmethod
    def validate_status(cls, v: str) -> str:
        if v not in VALID_SCENE_STATUS:
            raise ValueError(f"无效的场景状态，允许: {', '.join(VALID_SCENE_STATUS)}")
        return v


class SceneUpdate(BaseModel):
    scene_code: Optional[str] = None
    chapter_id: Optional[uuid.UUID] = None
    scene_type: Optional[str] = None
    location: Optional[str] = None
    weather: Optional[str] = None
    time_start: Optional[str] = None
    time_end: Optional[str] = None
    emotion_level: Optional[int] = None
    narration: Optional[str] = None
    dialogue: Optional[list[Any]] = None
    actions: Optional[list[Any]] = None
    foreshadow_ops: Optional[list[Any]] = None
    choices: Optional[list[Any]] = None
    causal_chain: Optional[Any] = None
    is_wow_moment: Optional[bool] = None
    wow_type: Optional[str] = None
    wow_spec: Optional[str] = None
    characters_involved: Optional[list[Any]] = None
    status: Optional[str] = None
    human_reviewed: Optional[bool] = None
    human_feedback: Optional[str] = None

    @field_validator("scene_code")
    @classmethod
    def validate_scene_code(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        if not SCENE_CODE_PATTERN.match(v):
            raise ValueError("场景编号格式错误，必须匹配 CH00-S00 或 CH00-S00-A 格式")
        return v

    @field_validator("emotion_level")
    @classmethod
    def validate_emotion_level(cls, v: Optional[int]) -> Optional[int]:
        if v is None:
            return v
        if v < 0 or v > 10:
            raise ValueError("情感等级必须在0-10之间")
        return v

    @field_validator("status")
    @classmethod
    def validate_status(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        if v not in VALID_SCENE_STATUS:
            raise ValueError(f"无效的场景状态，允许: {', '.join(VALID_SCENE_STATUS)}")
        return v


class SceneResponse(BaseModel):
    id: uuid.UUID
    project_id: uuid.UUID
    chapter_id: Optional[uuid.UUID] = None
    scene_code: str
    scene_type: Optional[str] = None
    location: Optional[str] = None
    weather: Optional[str] = None
    time_start: Optional[str] = None
    time_end: Optional[str] = None
    emotion_level: int = 5
    narration: Optional[str] = None
    dialogue: Any = []
    actions: Any = []
    foreshadow_ops: Any = []
    choices: Any = []
    causal_chain: Optional[Any] = None
    is_wow_moment: bool = False
    wow_type: Optional[str] = None
    wow_spec: Optional[str] = None
    characters_involved: Any = []
    status: str = "draft"
    version: int = 1
    audit_reports: Any = []
    human_reviewed: bool = False
    human_feedback: Optional[str] = None
    suggestions: Any = []
    git_commit_hash: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class SceneVersionResponse(BaseModel):
    id: uuid.UUID
    scene_id: uuid.UUID
    version: int
    content: Any
    audit_report: Optional[Any] = None
    change_reason: Optional[str] = None
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True
