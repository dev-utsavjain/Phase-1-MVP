from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from typing import List, Dict, Optional
from datetime import datetime
import base64
import re
from email.mime.text import MIMEText

from app.services.task_service import TaskService
from app.services.nlp_service import NLPService
from app.schemas.task import TaskCreate
from app.models.task import Task, TaskSource, TaskPriority

class GmailIntegration:
    """
    Gmail integration for:
    - Converting emails to tasks
    - Sending email notifications
    - Parsing action items from emails
    """
    
    def __init__(self, credentials: Credentials, db_session):
        self.service = build('gmail', 'v1', credentials=credentials)
        self.task_service = TaskService(db_session)
        self.nlp_service = NLPService()
        self.db = db_session
    
    def get_unread_emails(self, max_results: int = 20, query: str = 'is:unread') -> List[Dict]:
        """Fetch unread emails"""
        try:
            results = self.service.users().messages().list(
                userId='me',
                q=query,
                maxResults=max_results
            ).execute()
            
            messages = results.get('messages', [])
            
            emails = []
            for message in messages:
                email_data = self.get_email_details(message['id'])
                if email_data:
                    emails.append(email_data)
            
            return emails
            
        except HttpError as error:
            print(f'An error occurred: {error}')
            return []
    
    def get_email_details(self, message_id: str) -> Optional[Dict]:
        """Get detailed email information"""
        try:
            message = self.service.users().messages().get(
                userId='me',
                id=message_id,
                format='full'
            ).execute()
            
            headers = message['payload']['headers']
            
            # Extract headers
            subject = next((h['value'] for h in headers if h['name'] == 'Subject'), 'No Subject')
            sender = next((h['value'] for h in headers if h['name'] == 'From'), 'Unknown')
            date = next((h['value'] for h in headers if h['name'] == 'Date'), '')
            
            # Extract body
            body = self._get_email_body(message['payload'])
            
            # Extract snippet
            snippet = message.get('snippet', '')
            
            return {
                'id': message_id,
                'subject': subject,
                'sender': sender,
                'date': date,
                'body': body,
                'snippet': snippet,
                'labels': message.get('labelIds', [])
            }
            
        except HttpError as error:
            print(f'Error fetching email {message_id}: {error}')
            return None
    
    def email_to_task(self, email_id: str, user_id: int, custom_title: Optional[str] = None) -> Task:
        """Convert an email to a task"""
        email_data = self.get_email_details(email_id)
        
        if not email_data:
            raise ValueError(f"Email {email_id} not found")
        
        # Parse email for task details
        parsed = self.nlp_service.extract_task_from_email(
            subject=email_data['subject'],
            body=email_data['body'],
            snippet=email_data['snippet']
        )
        
        # Create task
        task_data = TaskCreate(
            title=custom_title or parsed['title'],
            description=f"From: {email_data['sender']}\n\n{parsed['description']}",
            due_date=parsed.get('due_date'),
            duration_minutes=parsed.get('duration', 30),
            priority=parsed.get('priority', TaskPriority.MEDIUM),
            tags=['email'] + parsed.get('tags', []),
            source=TaskSource.EMAIL
        )
        
        task = self.task_service.create_task(user_id, task_data)
        
        # Store email ID as external reference
        task.external_id = email_id
        task.external_source = 'gmail'
        self.db.commit()
        
        # Label email as processed
        self.add_label_to_email(email_id, 'TASK_CREATED')
        
        return task
    
    def batch_convert_emails(self, email_ids: List[str], user_id: int) -> List[Task]:
        """Convert multiple emails to tasks"""
        tasks = []
        for email_id in email_ids:
            try:
                task = self.email_to_task(email_id, user_id)
                tasks.append(task)
            except Exception as e:
                print(f"Failed to convert email {email_id}: {e}")
        
        return tasks
    
    def search_emails(self, query: str, max_results: int = 50) -> List[Dict]:
        """Search emails with custom query"""
        return self.get_unread_emails(max_results=max_results, query=query)
    
    def send_email(self, to: str, subject: str, body: str) -> bool:
        """Send an email"""
        try:
            message = MIMEText(body)
            message['to'] = to
            message['subject'] = subject
            
            raw = base64.urlsafe_b64encode(message.as_bytes()).decode()
            
            self.service.users().messages().send(
                userId='me',
                body={'raw': raw}
            ).execute()
            
            return True
            
        except HttpError as error:
            print(f'Error sending email: {error}')
            return False
    
    def send_task_summary(self, to: str, tasks: List[Task]):
        """Send daily task summary via email"""
        subject = f"Your Task Summary - {datetime.now().strftime('%B %d, %Y')}"
        
        body = "Here's your task summary:\n\n"
        body += "📋 Pending Tasks:\n"
        
        for i, task in enumerate(tasks, 1):
            body += f"\n{i}. {task.title}\n"
            if task.due_date:
                body += f"   Due: {task.due_date.strftime('%b %d, %I:%M %p')}\n"
            body += f"   Priority: {task.priority.value.upper()}\n"
        
        body += f"\n\nTotal tasks: {len(tasks)}"
        
        self.send_email(to, subject, body)
    
    def add_label_to_email(self, message_id: str, label: str):
        """Add a label to an email"""
        try:
            # Get or create label
            label_id = self._get_or_create_label(label)
            
            self.service.users().messages().modify(
                userId='me',
                id=message_id,
                body={'addLabelIds': [label_id]}
            ).execute()
            
        except HttpError as error:
            print(f'Error adding label: {error}')
    
    def _get_or_create_label(self, label_name: str) -> str:
        """Get label ID or create if doesn't exist"""
        try:
            # List existing labels
            results = self.service.users().labels().list(userId='me').execute()
            labels = results.get('labels', [])
            
            # Check if label exists
            for label in labels:
                if label['name'] == label_name:
                    return label['id']
            
            # Create new label
            label = self.service.users().labels().create(
                userId='me',
                body={
                    'name': label_name,
                    'labelListVisibility': 'labelShow',
                    'messageListVisibility': 'show'
                }
            ).execute()
            
            return label['id']
            
        except HttpError as error:
            print(f'Error managing label: {error}')
            return None
    
    def _get_email_body(self, payload: Dict) -> str:
        """Extract email body from payload"""
        body = ""
        
        if 'parts' in payload:
            for part in payload['parts']:
                if part['mimeType'] == 'text/plain':
                    data = part['body'].get('data', '')
                    if data:
                        body = base64.urlsafe_b64decode(data).decode('utf-8')
                        break
                elif part['mimeType'] == 'text/html' and not body:
                    data = part['body'].get('data', '')
                    if data:
                        html_body = base64.urlsafe_b64decode(data).decode('utf-8')
                        # Strip HTML tags (basic)
                        body = re.sub('<[^<]+?>', '', html_body)
        else:
            data = payload['body'].get('data', '')
            if data:
                body = base64.urlsafe_b64decode(data).decode('utf-8')
        
        return body.strip()
    
    def watch_mailbox(self, topic_name: str) -> Dict:
        """
        Set up Gmail push notifications (requires Cloud Pub/Sub)
        This enables real-time email notifications
        """
        try:
            request = {
                'labelIds': ['INBOX'],
                'topicName': topic_name
            }
            
            response = self.service.users().watch(
                userId='me',
                body=request
            ).execute()
            
            return response
            
        except HttpError as error:
            print(f'Error setting up watch: {error}')
            return {}