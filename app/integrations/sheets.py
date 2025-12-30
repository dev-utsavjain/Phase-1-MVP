import pandas as pd
from typing import List, Dict, Optional, BinaryIO
from datetime import datetime
import io

from app.services.task_service import TaskService
from app.schemas.task import TaskCreate
from app.models.task import TaskSource, TaskPriority, TaskStatus

class SheetsIntegration:
    """
    Import tasks from Excel/CSV/Google Sheets
    Supports various column formats and auto-mapping
    """
    
    def __init__(self, db_session):
        self.task_service = TaskService(db_session)
        self.db = db_session
    
    def import_from_excel(
        self,
        file: BinaryIO,
        user_id: int,
        column_mapping: Optional[Dict[str, str]] = None
    ) -> Dict:
        """
        Import tasks from Excel file (.xlsx, .xls)
        
        Args:
            file: File object
            user_id: User ID
            column_mapping: Custom column mapping (optional)
        
        Returns:
            Dict with import results
        """
        try:
            # Read Excel file
            df = pd.read_excel(file)
            return self._process_dataframe(df, user_id, column_mapping)
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'tasks_created': 0
            }
    
    def import_from_csv(
        self,
        file: BinaryIO,
        user_id: int,
        column_mapping: Optional[Dict[str, str]] = None,
        delimiter: str = ','
    ) -> Dict:
        """Import tasks from CSV file"""
        try:
            # Read CSV file
            df = pd.read_csv(file, delimiter=delimiter)
            return self._process_dataframe(df, user_id, column_mapping)
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'tasks_created': 0
            }
    
    def import_from_google_sheets(
        self,
        spreadsheet_id: str,
        sheet_name: str,
        user_id: int,
        credentials,
        column_mapping: Optional[Dict[str, str]] = None
    ) -> Dict:
        """Import tasks from Google Sheets"""
        try:
            from google.oauth2.credentials import Credentials
            from googleapiclient.discovery import build
            
            service = build('sheets', 'v4', credentials=credentials)
            
            # Read sheet data
            range_name = f'{sheet_name}!A1:Z1000'
            result = service.spreadsheets().values().get(
                spreadsheetId=spreadsheet_id,
                range=range_name
            ).execute()
            
            values = result.get('values', [])
            
            if not values:
                return {
                    'success': False,
                    'error': 'No data found in sheet',
                    'tasks_created': 0
                }
            
            # Convert to DataFrame
            df = pd.DataFrame(values[1:], columns=values[0])
            return self._process_dataframe(df, user_id, column_mapping)
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'tasks_created': 0
            }
    
    def _process_dataframe(
        self,
        df: pd.DataFrame,
        user_id: int,
        column_mapping: Optional[Dict[str, str]] = None
    ) -> Dict:
        """Process DataFrame and create tasks"""
        
        # Auto-detect or use provided column mapping
        if not column_mapping:
            column_mapping = self._auto_detect_columns(df.columns.tolist())
        
        tasks_created = []
        errors = []
        
        for idx, row in df.iterrows():
            try:
                task_data = self._row_to_task(row, column_mapping)
                task = self.task_service.create_task(user_id, task_data)
                tasks_created.append(task)
            except Exception as e:
                errors.append({
                    'row': idx + 2,  # +2 for header and 0-indexing
                    'error': str(e)
                })
        
        return {
            'success': True,
            'tasks_created': len(tasks_created),
            'tasks': tasks_created,
            'errors': errors,
            'total_rows': len(df)
        }
    
    def _auto_detect_columns(self, columns: List[str]) -> Dict[str, str]:
        """
        Auto-detect column names based on common patterns
        Maps actual column names to expected fields
        """
        mapping = {}
        
        # Normalize column names
        normalized = [col.lower().strip() for col in columns]
        
        # Title/Task/Description patterns
        title_patterns = ['title', 'task', 'name', 'description', 'todo', 'item']
        for pattern in title_patterns:
            for i, col in enumerate(normalized):
                if pattern in col:
                    mapping['title'] = columns[i]
                    break
            if 'title' in mapping:
                break
        
        # Due date patterns
        date_patterns = ['due', 'deadline', 'date', 'when', 'time']
        for pattern in date_patterns:
            for i, col in enumerate(normalized):
                if pattern in col:
                    mapping['due_date'] = columns[i]
                    break
            if 'due_date' in mapping:
                break
        
        # Priority patterns
        priority_patterns = ['priority', 'importance', 'urgency']
        for pattern in priority_patterns:
            for i, col in enumerate(normalized):
                if pattern in col:
                    mapping['priority'] = columns[i]
                    break
            if 'priority' in mapping:
                break
        
        # Status patterns
        status_patterns = ['status', 'state', 'progress']
        for pattern in status_patterns:
            for i, col in enumerate(normalized):
                if pattern in col:
                    mapping['status'] = columns[i]
                    break
            if 'status' in mapping:
                break
        
        # Duration patterns
        duration_patterns = ['duration', 'time', 'minutes', 'hours']
        for pattern in duration_patterns:
            for i, col in enumerate(normalized):
                if pattern in col:
                    mapping['duration'] = columns[i]
                    break
            if 'duration' in mapping:
                break
        
        # Tags patterns
        tags_patterns = ['tags', 'labels', 'categories', 'category']
        for pattern in tags_patterns:
            for i, col in enumerate(normalized):
                if pattern in col:
                    mapping['tags'] = columns[i]
                    break
            if 'tags' in mapping:
                break
        
        # Notes/Description patterns
        notes_patterns = ['notes', 'details', 'description', 'comments']
        for pattern in notes_patterns:
            for i, col in enumerate(normalized):
                if pattern in col and 'title' not in mapping:
                    mapping['description'] = columns[i]
                    break
            if 'description' in mapping:
                break
        
        return mapping
    
    def _row_to_task(self, row: pd.Series, column_mapping: Dict[str, str]) -> TaskCreate:
        """Convert spreadsheet row to Task object"""
        
        # Get title (required)
        title = str(row.get(column_mapping.get('title', ''), 'Untitled Task')).strip()
        if not title or title == 'nan':
            raise ValueError("Task title is required")
        
        # Get description
        description = None
        if 'description' in column_mapping:
            desc_value = row.get(column_mapping['description'])
            if pd.notna(desc_value):
                description = str(desc_value).strip()
        
        # Parse due date
        due_date = None
        if 'due_date' in column_mapping:
            date_value = row.get(column_mapping['due_date'])
            if pd.notna(date_value):
                due_date = self._parse_date(date_value)
        
        # Parse priority
        priority = TaskPriority.MEDIUM
        if 'priority' in column_mapping:
            priority_value = str(row.get(column_mapping['priority'], '')).lower().strip()
            priority = self._parse_priority(priority_value)
        
        # Parse duration
        duration = 30
        if 'duration' in column_mapping:
            duration_value = row.get(column_mapping['duration'])
            if pd.notna(duration_value):
                duration = self._parse_duration(duration_value)
        
        # Parse tags
        tags = []
        if 'tags' in column_mapping:
            tags_value = row.get(column_mapping['tags'])
            if pd.notna(tags_value):
                tags = [t.strip() for t in str(tags_value).split(',')]
        
        return TaskCreate(
            title=title,
            description=description,
            due_date=due_date,
            duration_minutes=duration,
            priority=priority,
            tags=tags,
            source=TaskSource.MANUAL
        )
    
    def _parse_date(self, value) -> Optional[datetime]:
        """Parse various date formats"""
        if pd.isna(value):
            return None
        
        # If already datetime
        if isinstance(value, datetime):
            return value
        
        # Try to parse string
        try:
            return pd.to_datetime(value)
        except:
            return None
    
    def _parse_priority(self, value: str) -> TaskPriority:
        """Parse priority from string"""
        value = value.lower().strip()
        
        if value in ['urgent', 'critical', 'high', '1', 'p1']:
            return TaskPriority.URGENT
        elif value in ['high', '2', 'p2']:
            return TaskPriority.HIGH
        elif value in ['low', '4', 'p4']:
            return TaskPriority.LOW
        else:
            return TaskPriority.MEDIUM
    
    def _parse_duration(self, value) -> int:
        """Parse duration in minutes"""
        if pd.isna(value):
            return 30
        
        try:
            # If numeric, assume minutes
            if isinstance(value, (int, float)):
                return int(value)
            
            # Parse string like "1h", "30m", "1.5h"
            value_str = str(value).lower().strip()
            
            if 'h' in value_str:
                hours = float(value_str.replace('h', '').strip())
                return int(hours * 60)
            elif 'm' in value_str:
                minutes = float(value_str.replace('m', '').strip())
                return int(minutes)
            else:
                return int(float(value_str))
        except:
            return 30
    
    def export_to_excel(self, tasks: List[Dict], filename: str = 'tasks_export.xlsx') -> BinaryIO:
        """Export tasks to Excel file"""
        df = pd.DataFrame(tasks)
        
        # Reorder columns
        column_order = [
            'title', 'description', 'due_date', 'status', 
            'priority', 'duration_minutes', 'tags', 'created_at'
        ]
        
        # Only include columns that exist
        columns = [col for col in column_order if col in df.columns]
        df = df[columns]
        
        # Create Excel file in memory
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, index=False, sheet_name='Tasks')
        
        output.seek(0)
        return output
    
    def get_column_preview(self, file: BinaryIO, file_type: str = 'excel') -> Dict:
        """
        Preview file columns for user to confirm mapping
        Returns first 5 rows and detected column mapping
        """
        try:
            if file_type == 'excel':
                df = pd.read_excel(file, nrows=5)
            else:
                df = pd.read_csv(file, nrows=5)
            
            column_mapping = self._auto_detect_columns(df.columns.tolist())
            
            return {
                'success': True,
                'columns': df.columns.tolist(),
                'preview': df.to_dict('records'),
                'suggested_mapping': column_mapping,
                'total_columns': len(df.columns)
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }