from typing import Dict, Optional
from datetime import datetime, timedelta
import re
from dateutil import parser
from app.models.task import TaskPriority

class NLPService:
    """
    Basic NLP service for parsing task-related text
    Can be enhanced with spaCy or other NLP libraries
    """
    
    def parse_task_message(self, message: str) -> Dict:
        """
        Parse a natural language message into task components
        Example: "Call client by 3pm tomorrow #urgent"
        """
        result = {
            'title': '',
            'description': None,
            'due_date': None,
            'duration': 30,
            'priority': TaskPriority.MEDIUM,
            'tags': []
        }
        
        # Extract hashtags
        hashtags = re.findall(r'#(\w+)', message)
        
        # Check for priority tags
        priority_map = {
            'urgent': TaskPriority.URGENT,
            'high': TaskPriority.HIGH,
            'low': TaskPriority.LOW,
            'medium': TaskPriority.MEDIUM
        }
        
        for tag in hashtags:
            if tag.lower() in priority_map:
                result['priority'] = priority_map[tag.lower()]
            else:
                result['tags'].append(tag)
        
        # Remove hashtags from message
        clean_message = re.sub(r'#\w+', '', message).strip()
        
        # Extract deadline phrases
        deadline_patterns = [
            (r'by\s+(\d{1,2}:\d{2}\s*(?:am|pm)?)', 'time'),
            (r'by\s+(today|tomorrow|tonight)', 'relative'),
            (r'by\s+(\w+day)', 'day'),
            (r'by\s+(next\s+\w+)', 'next'),
        ]
        
        deadline_text = None
        for pattern, pattern_type in deadline_patterns:
            match = re.search(pattern, clean_message, re.IGNORECASE)
            if match:
                deadline_text = match.group(1)
                clean_message = clean_message[:match.start()] + clean_message[match.end():]
                break
        
        if deadline_text:
            result['due_date'] = self._parse_deadline(deadline_text)
        
        # Extract duration if mentioned
        duration_match = re.search(r'(\d+)\s*(?:mins?|minutes?|hrs?|hours?)', clean_message, re.IGNORECASE)
        if duration_match:
            duration_value = int(duration_match.group(1))
            if 'h' in duration_match.group(0).lower():
                duration_value *= 60
            result['duration'] = duration_value
            clean_message = clean_message[:duration_match.start()] + clean_message[duration_match.end():]
        
        # Remove common prefixes
        clean_message = re.sub(r'^(task:|todo:|reminder:)\s*', '', clean_message, flags=re.IGNORECASE)
        
        result['title'] = clean_message.strip()
        
        return result
    
    def extract_task_from_email(self, subject: str, body: str, snippet: str) -> Dict:
        """Extract task information from email"""
        
        # Use subject as title
        title = subject
        
        # Look for action items in body
        action_patterns = [
            r'(?:please|could you|can you)\s+(.+?)(?:\.|$)',
            r'(?:action item|todo|task):\s*(.+?)(?:\.|$)',
            r'(?:need to|must|should)\s+(.+?)(?:\.|$)',
        ]
        
        description = snippet[:200] if len(snippet) > 200 else snippet
        
        for pattern in action_patterns:
            matches = re.findall(pattern, body, re.IGNORECASE)
            if matches:
                title = matches[0].strip()
                break
        
        # Try to extract deadline
        due_date = self._extract_date_from_text(body)
        
        # Determine priority based on keywords
        priority = TaskPriority.MEDIUM
        urgent_keywords = ['urgent', 'asap', 'immediately', 'critical', 'important']
        
        text_to_check = (subject + ' ' + body).lower()
        if any(keyword in text_to_check for keyword in urgent_keywords):
            priority = TaskPriority.URGENT
        
        return {
            'title': title,
            'description': description,
            'due_date': due_date,
            'priority': priority,
            'tags': ['email']
        }
    
    def _parse_deadline(self, text: str) -> Optional[datetime]:
        """Parse deadline text to datetime"""
        now = datetime.now()
        text = text.lower().strip()
        
        # Relative times
        if text == 'today':
            return now.replace(hour=17, minute=0, second=0, microsecond=0)
        elif text == 'tomorrow':
            return (now + timedelta(days=1)).replace(hour=9, minute=0, second=0, microsecond=0)
        elif text == 'tonight':
            return now.replace(hour=20, minute=0, second=0, microsecond=0)
        
        # Days of week
        weekdays = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']
        if text in weekdays:
            target_day = weekdays.index(text)
            current_day = now.weekday()
            days_ahead = target_day - current_day
            if days_ahead <= 0:
                days_ahead += 7
            return (now + timedelta(days=days_ahead)).replace(hour=9, minute=0, second=0, microsecond=0)
        
        # Time parsing (e.g., "3pm", "3:30pm")
        time_match = re.match(r'(\d{1,2})(?::(\d{2}))?\s*(am|pm)?', text)
        if time_match:
            hour = int(time_match.group(1))
            minute = int(time_match.group(2)) if time_match.group(2) else 0
            meridiem = time_match.group(3)
            
            if meridiem == 'pm' and hour != 12:
                hour += 12
            elif meridiem == 'am' and hour == 12:
                hour = 0
            
            target = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
            
            if target < now:
                target += timedelta(days=1)
            
            return target
        
        # Try general date parsing
        try:
            return parser.parse(text)
        except:
            return None
    
    def _extract_date_from_text(self, text: str) -> Optional[datetime]:
        """Extract any date mentioned in text"""
        
        # Common date patterns
        patterns = [
            r'(?:by|due|deadline|on)\s+(\w+\s+\d{1,2}(?:st|nd|rd|th)?)',
            r'(\d{1,2}/\d{1,2}(?:/\d{2,4})?)',
            r'(\d{4}-\d{2}-\d{2})',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                try:
                    return parser.parse(match.group(1))
                except:
                    continue
        
        return None

