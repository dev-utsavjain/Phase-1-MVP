from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional
from app.models.task import TaskStatus, TaskPriority, TaskSource

class TaskBase(BaseModel):
    title: str = Field(..., min_length=1)
    description: Optional[str] = None
    due_date: Optional[datetime] = None
    duration_minutes: int = Field(default=30, ge=5, le=480)
    priority: TaskPriority = TaskPriority.MEDIUM

class TaskCreate(TaskBase):
    pass

class TaskUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    due_date: Optional[datetime] = None
    scheduled_start: Optional[datetime] = None
    status: Optional[TaskStatus] = None
    priority: Optional[TaskPriority] = None

class TaskResponse(TaskBase):
    id: int
    user_id: int
    status: TaskStatus
    source: TaskSource
    scheduled_start: Optional[datetime]
    scheduled_end: Optional[datetime]
    created_at: datetime
    
    class Config:
        from_attributes = True