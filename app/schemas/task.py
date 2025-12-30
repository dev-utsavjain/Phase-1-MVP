from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional, List
from app.models.task import TaskStatus, TaskPriority, TaskSource

class TaskBase(BaseModel):
    title: str = Field(..., min_length=1, max_length=500)
    description: Optional[str] = None
    due_date: Optional[datetime] = None
    duration_minutes: int = Field(default=30, ge=5, le=480)
    priority: TaskPriority = TaskPriority.MEDIUM
    tags: Optional[List[str]] = None

class TaskCreate(TaskBase):
    source: TaskSource = TaskSource.MANUAL

class TaskUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    due_date: Optional[datetime] = None
    scheduled_start: Optional[datetime] = None
    status: Optional[TaskStatus] = None
    priority: Optional[TaskPriority] = None
    tags: Optional[List[str]] = None

class TaskResponse(TaskBase):
    id: int
    status: TaskStatus
    source: TaskSource
    scheduled_start: Optional[datetime]
    scheduled_end: Optional[datetime]
    user_id: int
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True

class TaskScheduleRequest(BaseModel):
    task_ids: List[int]
    auto_slot: bool = True  # Use auto-scheduling algorithm