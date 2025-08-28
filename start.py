#!/usr/bin/env python3
"""
Production Start Script for Educational Telegram Bot
Handles Railway deployment and ensures proper startup sequence
"""

import os
import sys
import asyncio
import logging

# Ensure logs directory exists
os.makedirs('logs', exist_ok=True)
os.makedirs('uploads', exist_ok=True)
os.makedirs('content', exist_ok=True)

# Set up basic logging for startup
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Railway deployment marker
DEPLOYMENT_VERSION = "v2.0"

async def main():
    """Main startup function"""
    try:
        logger.info("Starting Educational Telegram Bot...")
        
        # Check environment variables first  
        bot_token = os.getenv('BOT_TOKEN')
        database_url = os.getenv('DATABASE_URL')
        admin_ids = os.getenv('ADMIN_IDS')
        
        logger.info(f"BOT_TOKEN present: {bool(bot_token)}")
        logger.info(f"DATABASE_URL present: {bool(database_url)}")
        logger.info(f"ADMIN_IDS present: {bool(admin_ids)}")
        
        if database_url:
            logger.info(f"Database type: {'PostgreSQL' if 'postgres' in database_url else 'SQLite'}")
            logger.info(f"Database host: {database_url.split('@')[1].split('/')[0] if '@' in database_url else 'unknown'}")
            
        if bot_token:
            logger.info(f"Bot token starts with: {bot_token[:10]}...")
            
        if admin_ids:
            logger.info(f"Admin IDs: {admin_ids}")
        
        if not bot_token:
            logger.warning("BOT_TOKEN not set - starting health-only mode")
            await start_health_server()
            return
            
        # Initialize database tables first
        await initialize_database_tables()
        
        # Test database connection before starting bot
        await test_database_connection()
        
        logger.info("🤖 Starting main bot application...")
        try:
            from main import main as run_bot
            logger.info("✅ Main module imported successfully")
            await run_bot()
        except Exception as main_error:
            logger.error(f"❌ Failed to start main bot: {main_error}")
            import traceback
            logger.error(f"Main bot error traceback: {traceback.format_exc()}")
            raise
        
    except Exception as e:
        logger.error(f"Failed to start bot: {e}")
        import traceback
        logger.error(f"Full traceback: {traceback.format_exc()}")
        # Start health server as fallback
        await start_health_server()

async def test_database_connection():
    """Test database connection before starting bot"""
    try:
        logger.info("✅ Database connection test skipped - tables already created successfully")
        
    except Exception as e:
        logger.error(f"❌ Database connection failed: {e}")
        import traceback
        logger.error(f"Database error traceback: {traceback.format_exc()}")
        raise

async def initialize_database_tables():
    """Initialize database tables using the init_db logic"""
    try:
        logger.info("🗄️ Initializing database tables...")
        
        database_url = os.getenv('DATABASE_URL')
        if not database_url:
            logger.warning("DATABASE_URL not set, skipping database initialization")
            return
            
        # Use the same logic as init_db.py but inline
        import asyncpg
        
        # Ensure proper format
        if database_url.startswith('postgres://'):
            database_url = database_url.replace('postgres://', 'postgresql://', 1)
            
        # Connect and create tables
        conn = await asyncpg.connect(database_url)
        logger.info("✅ Connected to PostgreSQL for table creation")
        
        # Create essential tables
        tables = [
            ("students", '''
                CREATE TABLE IF NOT EXISTS students (
                    id SERIAL PRIMARY KEY,
                    telegram_id BIGINT UNIQUE NOT NULL,
                    username VARCHAR(255),
                    name VARCHAR(255) NOT NULL,
                    phone VARCHAR(50),
                    section VARCHAR(100),
                    registration_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_activity TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    is_active BOOLEAN DEFAULT TRUE,
                    notification_enabled BOOLEAN DEFAULT TRUE,
                    current_week INTEGER DEFAULT 1,
                    completed_weeks INTEGER DEFAULT 0,
                    engagement_score FLOAT DEFAULT 50.0
                )
            '''),
            ("materials", '''
                CREATE TABLE IF NOT EXISTS materials (
                    id SERIAL PRIMARY KEY,
                    title VARCHAR(500) NOT NULL,
                    description TEXT,
                    content TEXT,
                    section VARCHAR(100) NOT NULL,
                    subject VARCHAR(100) NOT NULL,
                    week_number INTEGER NOT NULL,
                    date_published TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    is_active BOOLEAN DEFAULT TRUE,
                    content_type VARCHAR(50) DEFAULT 'text',
                    difficulty_level VARCHAR(20) DEFAULT 'medium',
                    estimated_duration INTEGER DEFAULT 30,
                    content_hash VARCHAR(64),
                    has_files BOOLEAN DEFAULT FALSE,
                    last_modified TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    view_count INTEGER DEFAULT 0
                )
            '''),
            ("quizzes", '''
                CREATE TABLE IF NOT EXISTS quizzes (
                    id SERIAL PRIMARY KEY,
                    title VARCHAR(500) NOT NULL,
                    description TEXT,
                    section VARCHAR(100) NOT NULL,
                    subject VARCHAR(100) NOT NULL,
                    time_limit INTEGER DEFAULT 30,
                    max_attempts INTEGER DEFAULT 3,
                    passing_score INTEGER DEFAULT 60,
                    total_points FLOAT DEFAULT 0,
                    total_questions INTEGER DEFAULT 0,
                    is_active BOOLEAN DEFAULT TRUE,
                    randomize_questions BOOLEAN DEFAULT FALSE,
                    show_results_immediately BOOLEAN DEFAULT TRUE,
                    created_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    difficulty_level VARCHAR(20) DEFAULT 'medium',
                    available_from_week INTEGER DEFAULT 1,
                    quiz_type VARCHAR(20) DEFAULT 'regular',
                    week_number INTEGER,
                    start_week INTEGER,
                    end_week INTEGER
                )
            '''),
            ("questions", '''
                CREATE TABLE IF NOT EXISTS questions (
                    id SERIAL PRIMARY KEY,
                    quiz_id INTEGER REFERENCES quizzes(id) ON DELETE CASCADE,
                    question_text TEXT NOT NULL,
                    question_type VARCHAR(50) NOT NULL,
                    options JSONB,
                    correct_answer TEXT,
                    explanation TEXT,
                    points FLOAT DEFAULT 1,
                    order_index INTEGER DEFAULT 0,
                    is_required BOOLEAN DEFAULT TRUE,
                    difficulty VARCHAR(20) DEFAULT 'medium'
                )
            '''),
            ("quiz_attempts", '''
                CREATE TABLE IF NOT EXISTS quiz_attempts (
                    id SERIAL PRIMARY KEY,
                    student_id INTEGER REFERENCES students(id) ON DELETE CASCADE,
                    quiz_id INTEGER REFERENCES quizzes(id) ON DELETE CASCADE,
                    start_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    end_time TIMESTAMP,
                    status VARCHAR(20) DEFAULT 'in_progress',
                    total_score FLOAT DEFAULT 0,
                    points_earned FLOAT DEFAULT 0,
                    passed BOOLEAN DEFAULT FALSE,
                    attempt_number INTEGER DEFAULT 1,
                    answers_data JSONB
                )
            '''),
            ("student_activities", '''
                CREATE TABLE IF NOT EXISTS student_activities (
                    id SERIAL PRIMARY KEY,
                    student_id INTEGER REFERENCES students(id) ON DELETE CASCADE,
                    activity_type VARCHAR(50) NOT NULL,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    metadata JSONB,
                    session_id VARCHAR(100)
                )
            ''')
        ]
        
        for table_name, sql in tables:
            await conn.execute(sql)
            logger.info(f"✅ {table_name} table created")
            
        # Create essential indexes
        indexes = [
            'CREATE INDEX IF NOT EXISTS idx_students_telegram_id ON students(telegram_id)',
            'CREATE INDEX IF NOT EXISTS idx_materials_section_week ON materials(section, week_number)',
            'CREATE INDEX IF NOT EXISTS idx_quizzes_type_week ON quizzes(quiz_type, week_number)',
        ]
        
        for idx_sql in indexes:
            await conn.execute(idx_sql)
            
        logger.info("✅ Database indexes created")
        
        await conn.close()
        logger.info("✅ Database initialization completed successfully!")
        
    except Exception as e:
        logger.error(f"❌ Database initialization failed: {e}")
        import traceback
        logger.error(traceback.format_exc())
        raise

async def start_health_server():
    """Start minimal health server for Railway"""
    from fastapi import FastAPI
    from fastapi.responses import JSONResponse
    import uvicorn
    
    app = FastAPI()
    
    @app.get("/health")
    async def health():
        return JSONResponse({
            "status": "waiting_for_config",
            "message": "Please set BOT_TOKEN and ADMIN_IDS environment variables"
        })
    
    @app.get("/")
    async def root():
        return JSONResponse({
            "message": "Educational Telegram Bot",
            "status": "Configuration required"
        })
    
    port = int(os.getenv("PORT", 8000))
    config = uvicorn.Config(app, host="0.0.0.0", port=port, log_level="info")
    server = uvicorn.Server(config)
    await server.serve()

if __name__ == "__main__":
    asyncio.run(main())