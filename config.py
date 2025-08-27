import os
from datetime import datetime
import pytz

class Config:
    # Bot Configuration
    BOT_TOKEN = os.getenv('BOT_TOKEN', '')
    ADMIN_IDS = [int(id.strip()) for id in os.getenv('ADMIN_ID', '6651738535').split(',') if id.strip()]
    
    # Database Configuration
    DATABASE_URL = os.getenv('DATABASE_URL', 'sqlite:///arabic_learning_bot.db')
    
    # Webhook Configuration (for deployment)
    WEBHOOK_URL = os.getenv('WEBHOOK_URL', '')
    PORT = int(os.getenv('PORT', 8080))
    
    # Business Rules
    INACTIVE_PERIOD_DAYS = 30
    QUIZ_INTERVAL_WEEKS = 3
    MAX_STUDENTS = 7000
    WEEKLY_CONTENT_DAY = 0  # Monday (0=Monday, 6=Sunday)
    
    # Analytics Settings
    ENABLE_DETAILED_ANALYTICS = True
    REPORT_GENERATION_INTERVAL = 'daily'
    ANALYTICS_RETENTION_DAYS = 90
    
    # Arabic Language Settings
    LANGUAGE = 'ar'
    TIMEZONE = 'Asia/Riyadh'
    
    # Content Settings
    CONTENT_FOLDER = 'content'
    AUDIO_FOLDER = 'audio'
    QUIZ_EXCEL_FILE = 'quiz_questions.xlsx'
    
    # Rate Limiting
    RATE_LIMIT_MESSAGES_PER_MINUTE = 20
    RATE_LIMIT_COMMANDS_PER_HOUR = 100
    
    # Security
    AUTHORIZED_ADMINS = [ADMIN_ID]  # Can add more admin IDs here
    
    @classmethod
    def get_timezone(cls):
        """Get configured timezone object"""
        return pytz.timezone(cls.TIMEZONE)
    
    @classmethod
    def get_current_time(cls):
        """Get current time in configured timezone"""
        return datetime.now(cls.get_timezone())