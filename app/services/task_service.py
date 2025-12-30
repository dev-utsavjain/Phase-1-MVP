from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime, timedelta

from app.models.task import Task, TaskStatus
from app.schemas.task import TaskCreate, TaskUpdate
from app.utils.scheduler import AutoScheduler

class TaskService:
    def __init__(self, db: Session):
        self.db = db
        self.scheduler = AutoScheduler(db)
    
    def create_task(self, user_id: int, task_data: TaskCreate) -> Task:
        """Create a new task"""
        task = Task(
            **task_data.model_dump(exclude={'tags'}),
            user_id=user_id,
            tags=",".join(task_data.tags) if task_data.tags else None
        )
        self.db.add(task)
        self.db.commit()
        self.db.refresh(task)
        return task
    
    def get_user_tasks(
        self,
        user_id: int,
        status: Optional[TaskStatus] = None,
        priority: Optional[str] = None,
        source: Optional[str] = None
    ) -> List[Task]:
        """Get tasks with filters"""
        query = self.db.query(Task).filter(Task.user_id == user_id)
        
        if status:
            query = query.filter(Task.status == status)
        if priority:
            query = query.filter(Task.priority == priority)
        if source:
            query = query.filter(Task.source == source)
        
        return query.order_by(Task.created_at.desc()).all()
    
    def get_task(self, task_id: int, user_id: int) -> Optional[Task]:
        """Get a single task"""
        return self.db.query(Task).filter(
            Task.id == task_id,
            Task.user_id == user_id
        ).first()
    
    def update_task(self, task_id: int, user_id: int, task_data: TaskUpdate) -> Optional[Task]:
        """Update a task"""
        task = self.get_task(task_id, user_id)
        if not task:
            return None
        
        update_data = task_data.model_dump(exclude_unset=True, exclude={'tags'})
        for field, value in update_data.items():
            setattr(task, field, value)
        
        if task_data.tags is not None:
            task.tags = ",".join(task_data.tags)
        
        task.updated_at = datetime.utcnow()
        self.db.commit()
        self.db.refresh(task)
        return task
    
    def delete_task(self, task_id: int, user_id: int) -> bool:
        """Delete a task"""
        task = self.get_task(task_id, user_id)
        if not task:
            return False
        
        self.db.delete(task)
        self.db.commit()
        return True
    
    def schedule_tasks(self, user_id: int, task_ids: List[int], auto_slot: bool = True) -> List[Task]:
        """Schedule tasks into calendar"""
        tasks = self.db.query(Task).filter(
            Task.id.in_(task_ids),
            Task.user_id == user_id
        ).all()
        
        if auto_slot:
            scheduled_tasks = self.scheduler.auto_schedule(tasks, user_id)
        else:
            # Manual scheduling logic here
            scheduled_tasks = tasks
        
        for task in scheduled_tasks:
            task.status = TaskStatus.SCHEDULED
            task.updated_at = datetime.utcnow()
        
        self.db.commit()
        return scheduled_tasks
    
    def complete_task(self, task_id: int, user_id: int) -> Optional[Task]:
        """Mark task as completed"""
        task = self.get_task(task_id, user_id)
        if not task:
            return None
        
        task.status = TaskStatus.COMPLETED
        task.completed_at = datetime.utcnow()
        self.db.commit()
        self.db.refresh(task)
        return task