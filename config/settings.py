import os
from typing import List, Optional
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

class BotConfig:
    """Bot configuration management"""
    
    # Telegram Bot Settings
    BOT_TOKEN: str = os.getenv('BOT_TOKEN', '')
    ADMIN_IDS: List[int] = [int(id.strip()) for id in os.getenv('ADMIN_IDS', '').split(',') if id.strip()]
    
    # Database Settings
    DATABASE_URL: str = os.getenv('DATABASE_URL', 'sqlite+aiosqlite:///./telebot.db')
    
    # Webhook Settings
    USE_WEBHOOK: bool = os.getenv('USE_WEBHOOK', 'false').lower() == 'true'
    WEBHOOK_URL: str = os.getenv('WEBHOOK_URL', '')
    WEBHOOK_HOST: str = os.getenv('WEBHOOK_HOST', '0.0.0.0')
    WEBHOOK_PORT: int = int(os.getenv('WEBHOOK_PORT', '8000'))
    
    # Application Settings
    DEBUG: bool = os.getenv('DEBUG', 'false').lower() == 'true'
    LOG_LEVEL: str = os.getenv('LOG_LEVEL', 'INFO')
    
    # File Settings
    MAX_FILE_SIZE: int = int(os.getenv('MAX_FILE_SIZE', '52428800'))  # 50MB
    UPLOAD_PATH: str = os.getenv('UPLOAD_PATH', './uploads')
    CONTENT_PATH: str = os.getenv('CONTENT_PATH', './content')
    
    # Analytics Settings
    ANALYTICS_RETENTION_DAYS: int = int(os.getenv('ANALYTICS_RETENTION_DAYS', '90'))
    ENABLE_REALTIME_ANALYTICS: bool = os.getenv('ENABLE_REALTIME_ANALYTICS', 'true').lower() == 'true'
    
    # Scheduler Settings
    ENABLE_SCHEDULER: bool = os.getenv('ENABLE_SCHEDULER', 'true').lower() == 'true'
    CLEANUP_INTERVAL_HOURS: int = int(os.getenv('CLEANUP_INTERVAL_HOURS', '24'))
    
    def __init__(self):
        # Validate required settings
        if not self.BOT_TOKEN:
            raise ValueError("BOT_TOKEN environment variable is required")
        
        if not self.ADMIN_IDS:
            raise ValueError("ADMIN_IDS environment variable is required")
    
    @property
    def is_valid(self) -> bool:
        """Check if configuration is valid"""
        return bool(self.BOT_TOKEN and self.ADMIN_IDS)