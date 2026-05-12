import uuid
from datetime import datetime
from typing import Optional, Any
from pydantic import BaseModel


class AgentTaskResponse(BaseModel):
    id: uuid.UUID
    project_id: uuid.UUID
    task_type: str
    assigned_to: str
    status: str
    priority: int
    payload: Any
    result: Optional[Any]
    error_message: Optional[str]
    retry_count: int
    max_retries: int
    created_at: datetime
    started_at: Optional[datetime]
    completed_at: Optional[datetime]

    class Config:
        from_attributes = True
