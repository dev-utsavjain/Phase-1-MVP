 # Task model

from sqlalchemy import Column, Integer, String, DateTime, Text, ForeignKey, Enum as SQLEnum
from sqlalchemy.orm import relationship
from datetime import datetime
import enum
from app.core.database import Base

class TaskStatus(str, enum.Enum):
    INBOX = "inbox"
    SCHEDULED = "scheduled"
    COMPLETED = "completed"

class TaskPriority(str, enum.Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"

class TaskSource(str, enum.Enum):
    MANUAL = "manual"
    GMAIL = "gmail"
    CALENDAR = "calendar"

class Task(Base):
    __tablename__ = "tasks"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    
    # Basic info
    title = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    
    # Scheduling
    due_date = Column(DateTime, nullable=True)
    scheduled_start = Column(DateTime, nullable=True)
    scheduled_end = Column(DateTime, nullable=True)
    duration_minutes = Column(Integer, default=30)
    
    # Metadata
    status = Column(SQLEnum(TaskStatus), default=TaskStatus.INBOX)
    priority = Column(SQLEnum(TaskPriority), default=TaskPriority.MEDIUM)
    source = Column(SQLEnum(TaskSource), default=TaskSource.MANUAL)
    
    # External references
    google_event_id = Column(String, nullable=True)  # Calendar event ID
    gmail_message_id = Column(String, nullable=True)  # Email message ID
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    user = relationship("User", backref="tasks")