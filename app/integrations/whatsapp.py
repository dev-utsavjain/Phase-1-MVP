from twilio.rest import Client
from twilio.twiml.messaging_response import MessagingResponse
from typing import Dict, Optional
from datetime import datetime, timedelta
import re

from app.core.config import settings
from app.services.task_service import TaskService
from app.services.nlp_service import NLPService
from app.schemas.task import TaskCreate
from app.models.task import TaskSource, TaskPriority

class WhatsAppIntegration:
    """
    WhatsApp integration using Twilio API
    Users send messages to a dedicated WhatsApp number
    Format: "Task: [description] by [deadline] #[priority]"
    """
    
    def __init__(self, db_session):
        self.client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
        self.whatsapp_number = settings.TWILIO_WHATSAPP_NUMBER
        self.task_service = TaskService(db_session)
        self.nlp_service = NLPService()
        self.db = db_session
    
    def process_incoming_message(self, from_number: str, message_body: str, user_id: int) -> Dict:
        """
        Process incoming WhatsApp message and create task
        
        Args:
            from_number: Sender's WhatsApp number
            message_body: Message text
            user_id: User ID (must map phone number to user)
        
        Returns:
            Dict with task details and response message
        """
        try:
            # Parse message using NLP
            parsed_data = self.nlp_service.parse_task_message(message_body)
            
            # Create task
            task_data = TaskCreate(
                title=parsed_data['title'],
                description=parsed_data.get('description'),
                due_date=parsed_data.get('due_date'),
                duration_minutes=parsed_data.get('duration', 30),
                priority=parsed_data.get('priority', TaskPriority.MEDIUM),
                tags=parsed_data.get('tags', []),
                source=TaskSource.WHATSAPP
            )
            
            task = self.task_service.create_task(user_id, task_data)
            
            # Send confirmation
            response_msg = self._format_confirmation_message(task)
            self.send_message(from_number, response_msg)
            
            return {
                'success': True,
                'task_id': task.id,
                'message': response_msg
            }
            
        except Exception as e:
            error_msg = f"Sorry, I couldn't create that task. Error: {str(e)}"
            self.send_message(from_number, error_msg)
            return {
                'success': False,
                'error': str(e),
                'message': error_msg
            }
    
    def send_message(self, to_number: str, message: str) -> bool:
        """Send WhatsApp message via Twilio"""
        try:
            self.client.messages.create(
                from_=f'whatsapp:{self.whatsapp_number}',
                to=f'whatsapp:{to_number}',
                body=message
            )
            return True
        except Exception as e:
            print(f"Failed to send WhatsApp message: {e}")
            return False
    
    def send_task_reminder(self, to_number: str, task_title: str, due_time: datetime):
        """Send task reminder via WhatsApp"""
        message = (
            f"⏰ Reminder: {task_title}\n"
            f"Due: {due_time.strftime('%I:%M %p')}\n"
            f"Reply 'DONE' to mark as complete."
        )
        self.send_message(to_number, message)
    
    def _format_confirmation_message(self, task) -> str:
        """Format task confirmation message"""
        msg = f"✅ Task created!\n\n"
        msg += f"📝 {task.title}\n"
        
        if task.due_date:
            msg += f"📅 Due: {task.due_date.strftime('%b %d, %I:%M %p')}\n"
        
        msg += f"⏱️ Duration: {task.duration_minutes} mins\n"
        msg += f"🎯 Priority: {task.priority.value.upper()}\n"
        msg += f"\nTask ID: #{task.id}"
        
        return msg
    
    def handle_webhook(self, request_data: Dict) -> str:
        """
        Handle incoming webhook from Twilio
        Returns TwiML response
        """
        from_number = request_data.get('From', '').replace('whatsapp:', '')
        message_body = request_data.get('Body', '')
        
        # Get user from phone number
        from app.models.user import User
        user = self.db.query(User).filter(User.phone_number == from_number).first()
        
        if not user:
            response = MessagingResponse()
            response.message("Please register your phone number first at our website.")
            return str(response)
        
        # Process message
        result = self.process_incoming_message(from_number, message_body, user.id)
        
        # Return TwiML response (message already sent in process_incoming_message)
        response = MessagingResponse()
        return str(response)


class WhatsAppMessageParser:
    """Helper class to parse WhatsApp message formats"""
    
    @staticmethod
    def parse_simple_format(message: str) -> Dict:
        """
        Parse simple format: "Task: Call client by 3pm tomorrow #urgent"
        """
        result = {
            'title': '',
            'due_date': None,
            'priority': TaskPriority.MEDIUM,
            'tags': []
        }
        
        # Extract task title
        task_match = re.search(r'(?:task:|todo:)?\s*(.+?)(?:\s+by\s+|\s+#|$)', message, re.IGNORECASE)
        if task_match:
            result['title'] = task_match.group(1).strip()
        else:
            result['title'] = message.strip()
        
        # Extract deadline
        deadline_patterns = [
            r'by\s+(\d{1,2}:\d{2}\s*(?:am|pm)?)',  # by 3:00pm
            r'by\s+(today|tomorrow|tonight)',       # by tomorrow
            r'by\s+(\w+day)',                       # by monday
        ]
        
        for pattern in deadline_patterns:
            match = re.search(pattern, message, re.IGNORECASE)
            if match:
                time_str = match.group(1)
                result['due_date'] = WhatsAppMessageParser._parse_time(time_str)
                break
        
        # Extract priority from hashtags
        if '#urgent' in message.lower() or '#high' in message.lower():
            result['priority'] = TaskPriority.URGENT
        elif '#low' in message.lower():
            result['priority'] = TaskPriority.LOW
        
        # Extract tags
        tags = re.findall(r'#(\w+)', message)
        result['tags'] = [t for t in tags if t.lower() not in ['urgent', 'high', 'low', 'medium']]
        
        return result
    
    @staticmethod
    def _parse_time(time_str: str) -> Optional[datetime]:
        """Parse time string to datetime"""
        now = datetime.now()
        time_str = time_str.lower().strip()
        
        # Handle relative times
        if time_str == 'today':
            return now.replace(hour=17, minute=0, second=0)
        elif time_str == 'tomorrow':
            return (now + timedelta(days=1)).replace(hour=9, minute=0, second=0)
        elif time_str == 'tonight':
            return now.replace(hour=20, minute=0, second=0)
        
        # Handle specific times (e.g., "3pm", "3:30pm")
        time_pattern = r'(\d{1,2})(?::(\d{2}))?\s*(am|pm)?'
        match = re.match(time_pattern, time_str)
        
        if match:
            hour = int(match.group(1))
            minute = int(match.group(2)) if match.group(2) else 0
            meridiem = match.group(3)
            
            if meridiem == 'pm' and hour != 12:
                hour += 12
            elif meridiem == 'am' and hour == 12:
                hour = 0
            
            target = now.replace(hour=hour, minute=minute, second=0)
            
            # If time has passed today, set for tomorrow
            if target < now:
                target += timedelta(days=1)
            
            return target
        
        return None