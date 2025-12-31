 # All Google API logic
 
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from typing import List, Dict, Optional
from datetime import datetime, timedelta
from sqlalchemy.orm import Session

from app.models.user import User
from app.models.task import Task, TaskSource, TaskStatus

class GoogleService:
    """Handles all Google API interactions"""
    
    def __init__(self, user: User, db: Session):
        self.user = user
        self.db = db
        self.credentials = self._get_credentials()
    
    def _get_credentials(self) -> Credentials:
        """Build Google credentials from user's tokens"""
        return Credentials(
            token=self.user.google_access_token,
            refresh_token=self.user.google_refresh_token,
            token_uri="https://oauth2.googleapis.com/token",
            client_id=None,  # Not needed for API calls
            client_secret=None,
            scopes=[
                'https://www.googleapis.com/auth/gmail.readonly',
                'https://www.googleapis.com/auth/calendar'
            ]
        )
    
    # ==================== CALENDAR ====================
    
    def sync_calendar_events(self) -> List[Task]:
        """Sync Google Calendar events to tasks"""
        service = build('calendar', 'v3', credentials=self.credentials)
        
        # Get events from now onwards
        now = datetime.utcnow().isoformat() + 'Z'
        events_result = service.events().list(
            calendarId='primary',
            timeMin=now,
            maxResults=50,
            singleEvents=True,
            orderBy='startTime'
        ).execute()
        
        events = events_result.get('items', [])
        synced_tasks = []
        
        for event in events:
            # Check if task already exists
            existing = self.db.query(Task).filter(
                Task.google_event_id == event['id'],
                Task.user_id == self.user.id
            ).first()
            
            if existing:
                # Update existing
                self._update_task_from_event(existing, event)
                synced_tasks.append(existing)
            else:
                # Create new
                task = self._create_task_from_event(event)
                synced_tasks.append(task)
        
        self.db.commit()
        return synced_tasks
    
    def _create_task_from_event(self, event: Dict) -> Task:
        """Convert calendar event to task"""
        start = event['start'].get('dateTime', event['start'].get('date'))
        end = event['end'].get('dateTime', event['end'].get('date'))
        
        start_dt = datetime.fromisoformat(start.replace('Z', '+00:00'))
        end_dt = datetime.fromisoformat(end.replace('Z', '+00:00'))
        duration = int((end_dt - start_dt).total_seconds() / 60)
        
        task = Task(
            user_id=self.user.id,
            title=event.get('summary', 'Untitled Event'),
            description=event.get('description', ''),
            scheduled_start=start_dt,
            scheduled_end=end_dt,
            duration_minutes=duration,
            status=TaskStatus.SCHEDULED,
            source=TaskSource.CALENDAR,
            google_event_id=event['id']
        )
        
        self.db.add(task)
        return task
    
    def _update_task_from_event(self, task: Task, event: Dict):
        """Update task from calendar event"""
        start = event['start'].get('dateTime', event['start'].get('date'))
        end = event['end'].get('dateTime', event['end'].get('date'))
        
        start_dt = datetime.fromisoformat(start.replace('Z', '+00:00'))
        end_dt = datetime.fromisoformat(end.replace('Z', '+00:00'))
        
        task.title = event.get('summary', task.title)
        task.description = event.get('description', task.description)
        task.scheduled_start = start_dt
        task.scheduled_end = end_dt
        task.updated_at = datetime.utcnow()
    
    def push_task_to_calendar(self, task: Task) -> str:
        """Create/update calendar event from task"""
        service = build('calendar', 'v3', credentials=self.credentials)
        
        event_body = {
            'summary': task.title,
            'description': task.description or '',
            'start': {
                'dateTime': task.scheduled_start.isoformat(),
                'timeZone': 'UTC',
            },
            'end': {
                'dateTime': task.scheduled_end.isoformat(),
                'timeZone': 'UTC',
            },
        }
        
        if task.google_event_id:
            # Update existing
            event = service.events().update(
                calendarId='primary',
                eventId=task.google_event_id,
                body=event_body
            ).execute()
        else:
            # Create new
            event = service.events().insert(
                calendarId='primary',
                body=event_body
            ).execute()
            task.google_event_id = event['id']
            self.db.commit()
        
        return event['id']
    
    # ==================== GMAIL ====================
    
    def get_recent_emails(self, max_results: int = 20) -> List[Dict]:
        """Fetch recent unread emails"""
        service = build('gmail', 'v1', credentials=self.credentials)
        
        results = service.users().messages().list(
            userId='me',
            q='is:unread',
            maxResults=max_results
        ).execute()
        
        messages = results.get('messages', [])
        emails = []
        
        for msg in messages:
            email_data = self._get_email_details(service, msg['id'])
            if email_data:
                emails.append(email_data)
        
        return emails
    
    def _get_email_details(self, service, message_id: str) -> Optional[Dict]:
        """Get email details"""
        import base64
        
        try:
            message = service.users().messages().get(
                userId='me',
                id=message_id,
                format='full'
            ).execute()
            
            headers = message['payload']['headers']
            subject = next((h['value'] for h in headers if h['name'] == 'Subject'), 'No Subject')
            sender = next((h['value'] for h in headers if h['name'] == 'From'), 'Unknown')
            
            # Get snippet
            snippet = message.get('snippet', '')
            
            return {
                'id': message_id,
                'subject': subject,
                'sender': sender,
                'snippet': snippet
            }
        except Exception as e:
            print(f"Error fetching email: {e}")
            return None
    
    def email_to_task(self, email_id: str, custom_title: Optional[str] = None) -> Task:
        """Convert email to task"""
        service = build('gmail', 'v1', credentials=self.credentials)
        email = self._get_email_details(service, email_id)
        
        if not email:
            raise ValueError("Email not found")
        
        task = Task(
            user_id=self.user.id,
            title=custom_title or email['subject'],
            description=f"From: {email['sender']}\n\n{email['snippet']}",
            status=TaskStatus.INBOX,
            source=TaskSource.GMAIL,
            gmail_message_id=email_id
        )
        
        self.db.add(task)
        self.db.commit()
        self.db.refresh(task)
        
        return task