from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from typing import List, Dict
from datetime import datetime

from app.models.task import Task, TaskSource
from app.services.task_service import TaskService

class GoogleCalendarIntegration:
    def __init__(self, credentials: Credentials, db_session):
        self.service = build('calendar', 'v3', credentials=credentials)
        self.task_service = TaskService(db_session)
    
    def sync_events_to_tasks(self, user_id: int, calendar_id: str = 'primary') -> List[Task]:
        """Sync Google Calendar events to tasks"""
        # Get events from Google Calendar
        now = datetime.utcnow().isoformat() + 'Z'
        events_result = self.service.events().list(
            calendarId=calendar_id,
            timeMin=now,
            maxResults=100,
            singleEvents=True,
            orderBy='startTime'
        ).execute()
        
        events = events_result.get('items', [])
        synced_tasks = []
        
        for event in events:
            # Convert event to task
            task_data = self._event_to_task(event)
            
            # Check if task already exists
            existing_task = self.task_service.db.query(Task).filter(
                Task.external_id == event['id'],
                Task.user_id == user_id
            ).first()
            
            if existing_task:
                # Update existing task
                self.task_service.update_task(existing_task.id, user_id, task_data)
                synced_tasks.append(existing_task)
            else:
                # Create new task
                task = self.task_service.create_task(user_id, task_data)
                task.external_id = event['id']
                task.external_source = 'google_calendar'
                synced_tasks.append(task)
        
        return synced_tasks
    
    def push_task_to_calendar(self, task: Task, calendar_id: str = 'primary') -> str:
        """Push a task to Google Calendar as an event"""
        event_body = {
            'summary': task.title,
            'description': task.description,
            'start': {
                'dateTime': task.scheduled_start.isoformat(),
                'timeZone': 'UTC',
            },
            'end': {
                'dateTime': task.scheduled_end.isoformat(),
                'timeZone': 'UTC',
            },
        }
        
        if task.external_id:
            # Update existing event
            event = self.service.events().update(
                calendarId=calendar_id,
                eventId=task.external_id,
                body=event_body
            ).execute()
        else:
            # Create new event
            event = self.service.events().insert(
                calendarId=calendar_id,
                body=event_body
            ).execute()
            task.external_id = event['id']
        
        return event['id']
    
    def _event_to_task(self, event: Dict) -> Dict:
        """Convert Google Calendar event to task format"""
        start = event['start'].get('dateTime', event['start'].get('date'))
        end = event['end'].get('dateTime', event['end'].get('date'))
        
        start_dt = datetime.fromisoformat(start.replace('Z', '+00:00'))
        end_dt = datetime.fromisoformat(end.replace('Z', '+00:00'))
        
        duration = int((end_dt - start_dt).total_seconds() / 60)
        
        return {
            'title': event['summary'],
            'description': event.get('description', ''),
            'scheduled_start': start_dt,
            'scheduled_end': end_dt,
            'duration_minutes': duration,
            'source': TaskSource.CALENDAR,
            'status': 'scheduled'
        }