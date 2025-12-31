# Gmail, Calendar, Sheets sync

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.user import User
from app.schemas.task import TaskResponse
from app.services.google_service import GoogleService

router = APIRouter()

@router.post("/calendar/sync", response_model=List[TaskResponse])
def sync_calendar(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Sync Google Calendar events to tasks"""
    if not user.google_access_token:
        raise HTTPException(status_code=400, detail="Google account not connected")
    
    google = GoogleService(user, db)
    tasks = google.sync_calendar_events()
    
    return tasks

@router.post("/calendar/push/{task_id}")
def push_to_calendar(
    task_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Push a task to Google Calendar"""
    from app.models.task import Task
    
    task = db.query(Task).filter(
        Task.id == task_id,
        Task.user_id == user.id
    ).first()
    
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    if not task.scheduled_start or not task.scheduled_end:
        raise HTTPException(status_code=400, detail="Task must have scheduled time")
    
    google = GoogleService(user, db)
    event_id = google.push_task_to_calendar(task)
    
    return {"event_id": event_id, "message": "Task pushed to calendar"}

@router.get("/gmail/emails")
def get_emails(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get recent Gmail emails"""
    if not user.google_access_token:
        raise HTTPException(status_code=400, detail="Google account not connected")
    
    google = GoogleService(user, db)
    emails = google.get_recent_emails()
    
    return {"emails": emails}

@router.post("/gmail/to-task/{email_id}", response_model=TaskResponse)
def convert_email_to_task(
    email_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Convert Gmail email to task"""
    if not user.google_access_token:
        raise HTTPException(status_code=400, detail="Google account not connected")
    
    google = GoogleService(user, db)
    task = google.email_to_task(email_id)
    
    return task