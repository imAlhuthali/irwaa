from .database import DatabaseManager
from .database_postgres import PostgreSQLManager
import os

def get_database_manager():
    """Factory function to get the appropriate database manager"""
    database_url = os.getenv('DATABASE_URL', 'sqlite+aiosqlite:///./telebot.db')
    
    if database_url.startswith('postgresql://') or database_url.startswith('postgres://'):
        # Railway uses postgres:// but asyncpg needs postgresql://
        if database_url.startswith('postgres://'):
            database_url = database_url.replace('postgres://', 'postgresql://', 1)
        # Use PostgreSQL manager for production
        return PostgreSQLManager(database_url)
    else:
        # Use SQLite manager for development/local testing
        return DatabaseManager(database_url)

__all__ = [
    'DatabaseManager',
    'PostgreSQLManager',
    'get_database_manager'
]