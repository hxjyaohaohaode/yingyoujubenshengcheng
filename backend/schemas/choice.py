import uuid
from datetime import datetime
from typing import Optional, Any
from pydantic import BaseModel, Field, field_validator


class ChoiceDesignCreate(BaseModel):
    choice_number: int = Field(..., gt=0)
    text: str = Field(..., min_length=1)
    consequence_direct: Optional[str] = None
    consequence_indirect: Optional[str] = None
    consequence_long_term: Optional[str] = None
    character_impact: list[Any] = []
    is_hidden: bool = False
    hidden_condition: Optional[str] = None
    moral_alignment: str = "gray"
    branch_target: Optional[str] = None

    @field_validator("choice_number")
    @classmethod
    def validate_choice_number(cls, v: int) -> int:
        if v <= 0:
            raise ValueError("选项序号必须大于0")
        return v

    @field_validator("moral_alignment")
    @classmethod
    def validate_moral_alignment(cls, v: str) -> str:
        if v not in ("good", "neutral", "evil", "gray"):
            raise ValueError("道德倾向必须是good/neutral/evil/gray")
        return v


class ChoiceDesignUpdate(BaseModel):
    choice_number: Optional[int] = None
    text: Optional[str] = None
    consequence_direct: Optional[str] = None
    consequence_indirect: Optional[str] = None
    consequence_long_term: Optional[str] = None
    character_impact: Optional[list[Any]] = None
    is_hidden: Optional[bool] = None
    hidden_condition: Optional[str] = None
    moral_alignment: Optional[str] = None
    branch_target: Optional[str] = None

    @field_validator("choice_number")
    @classmethod
    def validate_choice_number(cls, v: Optional[int]) -> Optional[int]:
        if v is None:
            return v
        if v <= 0:
            raise ValueError("选项序号必须大于0")
        return v

    @field_validator("moral_alignment")
    @classmethod
    def validate_moral_alignment(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        if v not in ("good", "neutral", "evil", "gray"):
            raise ValueError("道德倾向必须是good/neutral/evil/gray")
        return v


class ChoiceDesignResponse(BaseModel):
    id: uuid.UUID
    project_id: uuid.UUID
    section_id: uuid.UUID
    choice_number: int
    text: str
    consequence_direct: Optional[str] = None
    consequence_indirect: Optional[str] = None
    consequence_long_term: Optional[str] = None
    character_impact: Any = []
    is_hidden: bool = False
    hidden_condition: Optional[str] = None
    moral_alignment: str = "gray"
    branch_target: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True
