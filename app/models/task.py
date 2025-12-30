from sqlalchemy import Column, Integer, String, DateTime, Boolean, ForeignKey, Enum
from sqlalchemy.orm import relationship
from datetime import datetime
import enum
from app.core.database import Base

class TaskStatus(str, enum.Enum):
    INBOX = "inbox"
    SCHEDULED = "scheduled"
    COMPLETED = "completed"
    ARCHIVED = "archived"

class TaskPriority(str, enum.Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    URGENT = "urgent"

class TaskSource(str, enum.Enum):
    MANUAL = "manual"
    EMAIL = "email"
    WHATSAPP = "whatsapp"
    CALENDAR = "calendar"
    VOICE = "voice"

class Task(Base):
    __tablename__ = "tasks"
    
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, nullable=False)
    description = Column(String, nullable=True)
    
    # Scheduling
    due_date = Column(DateTime, nullable=True)
    scheduled_start = Column(DateTime, nullable=True)
    scheduled_end = Column(DateTime, nullable=True)
    duration_minutes = Column(Integer, default=30)
    
    # Metadata
    status = Column(Enum(TaskStatus), default=TaskStatus.INBOX)
    priority = Column(Enum(TaskPriority), default=TaskPriority.MEDIUM)
    source = Column(Enum(TaskSource), default=TaskSource.MANUAL)
    tags = Column(String, nullable=True)  # JSON string
    
    # Relations
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    user = relationship("User", back_populates="tasks")
    
    # External IDs (for syncing)
    external_id = Column(String, nullable=True)  # Google Calendar event ID, etc.
    external_source = Column(String, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)
    
    # Reminders
    reminders = relationship("Reminder", back_populates="task", cascade="all, delete-orphan")