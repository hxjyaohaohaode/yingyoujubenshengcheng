import uuid
from datetime import datetime
from typing import Optional, Any
from pydantic import BaseModel, Field, field_validator


class ChapterCreate(BaseModel):
    chapter_number: int = Field(..., gt=0)
    title: Optional[str] = None
    summary: Optional[str] = None
    outline: Optional[str] = None
    core_conflict: Optional[str] = None
    emotion_target: int = 5
    key_turning_points: list[Any] = []
    foreshadow_tasks: list[Any] = []
    focus_characters: list[Any] = []
    worldview_refs: list[Any] = []
    branch_structure: Optional[str] = None
    anchor_scenes: list[Any] = []
    status: str = "draft"

    @field_validator("chapter_number")
    @classmethod
    def validate_chapter_number(cls, v: int) -> int:
        if v <= 0:
            raise ValueError("章节编号必须大于0")
        return v

    @field_validator("emotion_target")
    @classmethod
    def validate_emotion_target(cls, v: int) -> int:
        if v < 0 or v > 10:
            raise ValueError("情感目标必须在0-10之间")
        return v


class ChapterUpdate(BaseModel):
    chapter_number: Optional[int] = None
    title: Optional[str] = None
    summary: Optional[str] = None
    outline: Optional[str] = None
    core_conflict: Optional[str] = None
    emotion_target: Optional[int] = None
    key_turning_points: Optional[list[Any]] = None
    foreshadow_tasks: Optional[list[Any]] = None
    focus_characters: Optional[list[Any]] = None
    worldview_refs: Optional[list[Any]] = None
    branch_structure: Optional[str] = None
    anchor_scenes: Optional[list[Any]] = None
    status: Optional[str] = None

    @field_validator("chapter_number")
    @classmethod
    def validate_chapter_number(cls, v: Optional[int]) -> Optional[int]:
        if v is None:
            return v
        if v <= 0:
            raise ValueError("章节编号必须大于0")
        return v

    @field_validator("emotion_target")
    @classmethod
    def validate_emotion_target(cls, v: Optional[int]) -> Optional[int]:
        if v is None:
            return v
        if v < 0 or v > 10:
            raise ValueError("情感目标必须在0-10之间")
        return v


class ChapterResponse(BaseModel):
    id: uuid.UUID
    project_id: uuid.UUID
    chapter_number: int
    title: Optional[str] = None
    summary: Optional[str] = None
    outline: Optional[str] = None
    core_conflict: Optional[str] = None
    emotion_target: int = 5
    key_turning_points: Any = []
    foreshadow_tasks: Any = []
    focus_characters: Any = []
    worldview_refs: Any = []
    branch_structure: Optional[str] = None
    anchor_scenes: Any = []
    status: str = "draft"
    created_at: Optional[datetime] = None
    sections: list["SectionResponse"] = []

    class Config:
        from_attributes = True


class SectionCreate(BaseModel):
    section_number: int = Field(..., gt=0)
    title: Optional[str] = None
    word_target: int = 1000
    emotion_target: int = 5
    scene_ids: list[Any] = []
    choices: Optional[Any] = None
    foreshadow_tasks: list[Any] = []
    focus_characters: list[Any] = []
    branch_type: str = "exploration"
    summary: Optional[str] = None
    status: str = "draft"

    @field_validator("section_number")
    @classmethod
    def validate_section_number(cls, v: int) -> int:
        if v <= 0:
            raise ValueError("节序号必须大于0")
        return v

    @field_validator("emotion_target")
    @classmethod
    def validate_emotion_target(cls, v: int) -> int:
        if v < 0 or v > 10:
            raise ValueError("情感目标必须在0-10之间")
        return v

    @field_validator("branch_type")
    @classmethod
    def validate_branch_type(cls, v: str) -> str:
        if v not in ("exploration", "decision", "convergence"):
            raise ValueError("分支类型必须是exploration/decision/convergence")
        return v

    @field_validator("status")
    @classmethod
    def validate_status(cls, v: str) -> str:
        if v not in ("draft", "outlined", "writing", "done"):
            raise ValueError("状态必须是draft/outlined/writing/done")
        return v


class SectionUpdate(BaseModel):
    section_number: Optional[int] = None
    title: Optional[str] = None
    word_target: Optional[int] = None
    emotion_target: Optional[int] = None
    scene_ids: Optional[list[Any]] = None
    choices: Optional[Any] = None
    foreshadow_tasks: Optional[list[Any]] = None
    focus_characters: Optional[list[Any]] = None
    branch_type: Optional[str] = None
    summary: Optional[str] = None
    status: Optional[str] = None

    @field_validator("section_number")
    @classmethod
    def validate_section_number(cls, v: Optional[int]) -> Optional[int]:
        if v is None:
            return v
        if v <= 0:
            raise ValueError("节序号必须大于0")
        return v

    @field_validator("emotion_target")
    @classmethod
    def validate_emotion_target(cls, v: Optional[int]) -> Optional[int]:
        if v is None:
            return v
        if v < 0 or v > 10:
            raise ValueError("情感目标必须在0-10之间")
        return v

    @field_validator("branch_type")
    @classmethod
    def validate_branch_type(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        if v not in ("exploration", "decision", "convergence"):
            raise ValueError("分支类型必须是exploration/decision/convergence")
        return v

    @field_validator("status")
    @classmethod
    def validate_status(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        if v not in ("draft", "outlined", "writing", "done"):
            raise ValueError("状态必须是draft/outlined/writing/done")
        return v


class SectionResponse(BaseModel):
    id: uuid.UUID
    project_id: uuid.UUID
    chapter_id: uuid.UUID
    section_number: int
    title: Optional[str] = None
    word_target: int = 1000
    emotion_target: int = 5
    scene_ids: Any = []
    choices: Optional[Any] = None
    foreshadow_tasks: Any = []
    focus_characters: Any = []
    branch_type: str = "exploration"
    summary: Optional[str] = None
    status: str = "draft"
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True
