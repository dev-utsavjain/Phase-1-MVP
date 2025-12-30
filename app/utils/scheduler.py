from sqlalchemy.orm import Session
from typing import List
from datetime import datetime, timedelta
from app.models.task import Task

class AutoScheduler:
    def __init__(self, db: Session):
        self.db = db
        self.working_hours_start = 9  # 9 AM
        self.working_hours_end = 18   # 6 PM
        self.buffer_minutes = 15
    
    def auto_schedule(self, tasks: List[Task], user_id: int) -> List[Task]:
        """
        Auto-schedule tasks into available time slots
        Simple algorithm: Find next available slot for each task
        """
        # Get existing scheduled tasks
        existing_tasks = self.db.query(Task).filter(
            Task.user_id == user_id,
            Task.scheduled_start.isnot(None),
            Task.status != "completed"
        ).order_by(Task.scheduled_start).all()
        
        # Sort tasks by priority and due date
        sorted_tasks = sorted(
            tasks,
            key=lambda t: (
                self._priority_weight(t.priority),
                t.due_date or datetime.max
            )
        )
        
        current_time = self._next_working_hour(datetime.now())
        
        for task in sorted_tasks:
            # Find next available slot
            slot_start = self._find_next_slot(
                current_time,
                task.duration_minutes,
                existing_tasks
            )
            
            task.scheduled_start = slot_start
            task.scheduled_end = slot_start + timedelta(minutes=task.duration_minutes)
            
            # Add to existing tasks list
            existing_tasks.append(task)
            existing_tasks.sort(key=lambda t: t.scheduled_start)
            
            # Move current time forward
            current_time = task.scheduled_end + timedelta(minutes=self.buffer_minutes)
        
        return sorted_tasks
    
    def _find_next_slot(
        self,
        start_time: datetime,
        duration_minutes: int,
        existing_tasks: List[Task]
    ) -> datetime:
        """Find the next available time slot"""
        candidate = start_time
        
        while True:
            # Check if within working hours
            if not self._is_working_hours(candidate, duration_minutes):
                candidate = self._next_working_hour(candidate)
                continue
            
            # Check for conflicts
            end_time = candidate + timedelta(minutes=duration_minutes)
            conflict = self._has_conflict(candidate, end_time, existing_tasks)
            
            if not conflict:
                return candidate
            
            # Move to after the conflicting task
            candidate = conflict.scheduled_end + timedelta(minutes=self.buffer_minutes)
    
    def _has_conflict(
        self,
        start: datetime,
        end: datetime,
        tasks: List[Task]
    ) -> Optional[Task]:
        """Check if time slot conflicts with existing tasks"""
        for task in tasks:
            if task.scheduled_start and task.scheduled_end:
                if not (end <= task.scheduled_start or start >= task.scheduled_end):
                    return task
        return None
    
    def _is_working_hours(self, start: datetime, duration_minutes: int) -> bool:
        """Check if slot falls within working hours"""
        end = start + timedelta(minutes=duration_minutes)
        return (
            self.working_hours_start <= start.hour < self.working_hours_end and
            self.working_hours_start <= end.hour <= self.working_hours_end
        )
    
    def _next_working_hour(self, dt: datetime) -> datetime:
        """Get the next working hour"""
        if dt.hour < self.working_hours_start:
            return dt.replace(hour=self.working_hours_start, minute=0, second=0)
        elif dt.hour >= self.working_hours_end:
            # Next day
            next_day = dt + timedelta(days=1)
            return next_day.replace(hour=self.working_hours_start, minute=0, second=0)
        return dt
    
    def _priority_weight(self, priority: str) -> int:
        """Convert priority to numeric weight"""
        weights = {"urgent": 0, "high": 1, "medium": 2, "low": 3}
        return weights.get(priority, 2)