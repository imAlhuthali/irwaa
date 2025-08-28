#!/usr/bin/env python3
"""
Direct database initialization script for Railway
This will create all tables directly without the bot complexity
"""
import asyncio
import os
import logging
import asyncpg

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def init_database_direct():
    """Initialize database tables directly using asyncpg"""
    try:
        database_url = os.getenv('DATABASE_URL')
        if not database_url:
            logger.error("DATABASE_URL environment variable not set")
            return False
            
        logger.info(f"Connecting to database...")
        
        # Ensure proper format
        if database_url.startswith('postgres://'):
            database_url = database_url.replace('postgres://', 'postgresql://', 1)
            
        # Connect directly
        conn = await asyncpg.connect(database_url)
        logger.info("✅ Connected to PostgreSQL!")
        
        # Get version
        version = await conn.fetchval('SELECT version()')
        logger.info(f"Database version: {version}")
        
        # Create tables
        logger.info("Creating students table...")
        await conn.execute('''
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
        ''')
        logger.info("✅ Students table created")
        
        logger.info("Creating materials table...")
        await conn.execute('''
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
        ''')
        logger.info("✅ Materials table created")
        
        logger.info("Creating quizzes table...")
        await conn.execute('''
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
        ''')
        logger.info("✅ Quizzes table created")
        
        logger.info("Creating questions table...")
        await conn.execute('''
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
        ''')
        logger.info("✅ Questions table created")
        
        logger.info("Creating quiz_attempts table...")
        await conn.execute('''
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
        ''')
        logger.info("✅ Quiz attempts table created")
        
        logger.info("Creating student_activities table...")
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS student_activities (
                id SERIAL PRIMARY KEY,
                student_id INTEGER REFERENCES students(id) ON DELETE CASCADE,
                activity_type VARCHAR(50) NOT NULL,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                metadata JSONB,
                session_id VARCHAR(100)
            )
        ''')
        logger.info("✅ Student activities table created")
        
        # Create indexes
        logger.info("Creating indexes...")
        await conn.execute('CREATE INDEX IF NOT EXISTS idx_students_telegram_id ON students(telegram_id)')
        await conn.execute('CREATE INDEX IF NOT EXISTS idx_materials_section_week ON materials(section, week_number)')
        await conn.execute('CREATE INDEX IF NOT EXISTS idx_quizzes_type_week ON quizzes(quiz_type, week_number)')
        logger.info("✅ Indexes created")
        
        # Test data insertion
        logger.info("Testing data insertion...")
        result = await conn.fetchval('SELECT COUNT(*) FROM students')
        logger.info(f"✅ Students table contains {result} records")
        
        await conn.close()
        logger.info("✅ All database tables initialized successfully!")
        return True
        
    except Exception as e:
        logger.error(f"❌ Database initialization failed: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False

if __name__ == "__main__":
    success = asyncio.run(init_database_direct())
    if success:
        print("🎉 Database initialization completed!")
    else:
        print("💥 Database initialization failed!")
        exit(1)