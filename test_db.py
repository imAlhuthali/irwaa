#!/usr/bin/env python3
"""
Simple database connection test for Railway PostgreSQL
"""
import asyncio
import os
import logging
from models import get_database_manager

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_database():
    """Test database connection and table creation"""
    try:
        logger.info("Testing database connection...")
        
        # Test environment variable
        db_url = os.getenv('DATABASE_URL')
        logger.info(f"DATABASE_URL exists: {bool(db_url)}")
        if db_url:
            logger.info(f"Database URL starts with: {db_url[:20]}...")
        
        # Create database manager
        db_manager = get_database_manager()
        logger.info(f"Using database manager: {type(db_manager).__name__}")
        
        # Initialize database
        await db_manager.initialize()
        logger.info("✅ Database initialized successfully!")
        
        # Test health check
        healthy = await db_manager.health_check()
        logger.info(f"✅ Database health check: {healthy}")
        
        # Test basic query
        if hasattr(db_manager, 'get_connection'):
            async with db_manager.get_connection() as conn:
                result = await conn.fetchval('SELECT COUNT(*) FROM students')
                logger.info(f"✅ Students table query result: {result}")
        
        # Close connection
        await db_manager.close()
        logger.info("✅ Database connection closed")
        
    except Exception as e:
        logger.error(f"❌ Database test failed: {e}")
        raise

if __name__ == "__main__":
    asyncio.run(test_database())