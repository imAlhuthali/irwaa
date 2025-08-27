from .student import Student
from .quiz import QuizQuestion, QuizAttempt
from .analytics import DailyAnalytics, WeeklyReport, SystemMetrics
from .database import DatabaseManager
from .database_postgres import PostgreSQLManager
import os

def get_database_manager():
    """Factory function to get the appropriate database manager"""
    database_url = os.getenv('DATABASE_URL', 'sqlite+aiosqlite:///./telebot.db')
    
    if database_url.startswith('postgresql://') or database_url.startswith('postgres://'):
        # Use PostgreSQL manager for production
        return PostgreSQLManager(database_url)
    else:
        # Use SQLite manager for development/local testing
        return DatabaseManager(database_url)

__all__ = [
    'Student',
    'QuizQuestion',
    'QuizAttempt',
    'DailyAnalytics',
    'WeeklyReport',
    'SystemMetrics',
    'DatabaseManager',
    'PostgreSQLManager',
    'get_database_manager'
]