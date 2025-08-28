import logging
import asyncpg
import asyncio
from typing import Dict, List, Optional, Any, Union
from datetime import datetime, timedelta
import json
import os
from contextlib import asynccontextmanager

logger = logging.getLogger(__name__)

class PostgreSQLManager:
    """Production-ready PostgreSQL database manager for Telegram bot"""
    
    def __init__(self, database_url: str):
        # Ensure proper postgresql:// format for asyncpg
        if database_url.startswith('postgres://'):
            database_url = database_url.replace('postgres://', 'postgresql://', 1)
            
        self.database_url = database_url
        self.pool: Optional[asyncpg.Pool] = None
        self.max_connections = int(os.getenv('DB_MAX_CONNECTIONS', '5'))
        self.min_connections = int(os.getenv('DB_MIN_CONNECTIONS', '1'))
        
    async def initialize(self):
        """Initialize database connection pool and create tables"""
        try:
            logger.info(f"Connecting to PostgreSQL database...")
            logger.info(f"Database URL: {self.database_url[:30]}...")  # Log first 30 chars only
            
            # Create connection pool
            self.pool = await asyncpg.create_pool(
                self.database_url,
                min_size=self.min_connections,
                max_size=self.max_connections,
                command_timeout=60,
                server_settings={
                    'application_name': 'educational_telegram_bot',
                }
            )
            
            logger.info("Database connection pool created successfully")
            
            # Test connection
            async with self.get_connection() as conn:
                result = await conn.fetchval('SELECT version()')
                logger.info(f"Connected to: {result}")
            
            # Create tables
            logger.info("Creating database tables...")
            await self._create_tables()
            
            logger.info("PostgreSQL database initialized successfully")
            
        except Exception as e:
            logger.error(f"Database initialization failed: {e}")
            logger.error(f"Database URL format: {self.database_url.split('@')[0] if '@' in self.database_url else 'Invalid URL'}")
            raise

    async def close(self):
        """Close database connection pool"""
        if self.pool:
            await self.pool.close()
            logger.info("Database connection pool closed")

    @asynccontextmanager
    async def get_connection(self):
        """Get database connection from pool"""
        if not self.pool:
            raise RuntimeError("Database not initialized")
        
        async with self.pool.acquire() as connection:
            yield connection

    async def _create_tables(self):
        """Create all necessary tables"""
        try:
            async with self.get_connection() as conn:
                # Students table
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
                );
            ''')
            
            # Create index for telegram_id
                await conn.execute('''
                CREATE INDEX IF NOT EXISTS idx_students_telegram_id ON students(telegram_id);
                CREATE INDEX IF NOT EXISTS idx_students_section ON students(section);
                CREATE INDEX IF NOT EXISTS idx_students_activity ON students(last_activity);
            ''')
            
            # Materials table
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
                );
            ''')
            
                await conn.execute('''
                CREATE INDEX IF NOT EXISTS idx_materials_section_week ON materials(section, week_number);
                CREATE INDEX IF NOT EXISTS idx_materials_hash ON materials(content_hash);
            ''')
            
            # Quizzes table
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
                );
            ''')
            
                await conn.execute('''
                CREATE INDEX IF NOT EXISTS idx_quizzes_type_week ON quizzes(quiz_type, week_number);
                CREATE INDEX IF NOT EXISTS idx_quizzes_section_week ON quizzes(section, week_number);
            ''')
            
            # Questions table
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
                );
            ''')
            
                await conn.execute('''
                CREATE INDEX IF NOT EXISTS idx_questions_quiz ON questions(quiz_id);
            ''')
            
            # Quiz attempts table
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
                );
            ''')
            
                await conn.execute('''
                CREATE INDEX IF NOT EXISTS idx_quiz_attempts_student ON quiz_attempts(student_id);
                CREATE INDEX IF NOT EXISTS idx_quiz_attempts_quiz ON quiz_attempts(quiz_id);
            ''')
            
            # Student activities table
                await conn.execute('''
                CREATE TABLE IF NOT EXISTS student_activities (
                    id SERIAL PRIMARY KEY,
                    student_id INTEGER REFERENCES students(id) ON DELETE CASCADE,
                    activity_type VARCHAR(50) NOT NULL,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    metadata JSONB,
                    session_id VARCHAR(100)
                );
            ''')
            
                await conn.execute('''
                CREATE INDEX IF NOT EXISTS idx_activities_student ON student_activities(student_id);
                CREATE INDEX IF NOT EXISTS idx_activities_timestamp ON student_activities(timestamp);
                CREATE INDEX IF NOT EXISTS idx_activities_type ON student_activities(activity_type);
            ''')
            
            # Material files table
                await conn.execute('''
                CREATE TABLE IF NOT EXISTS material_files (
                    id SERIAL PRIMARY KEY,
                    material_id INTEGER REFERENCES materials(id) ON DELETE CASCADE,
                    original_filename VARCHAR(255) NOT NULL,
                    stored_filename VARCHAR(255) NOT NULL,
                    file_path TEXT NOT NULL,
                    file_size INTEGER NOT NULL,
                    file_type VARCHAR(10),
                    mime_type VARCHAR(100),
                    upload_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    file_hash VARCHAR(64)
                );
            ''')
            
                logger.info("All database tables created successfully")
                
        except Exception as e:
            logger.error(f"Failed to create database tables: {e}")
            raise

    async def health_check(self):
        """Check database health"""
        try:
            async with self.get_connection() as conn:
                await conn.fetchval('SELECT 1')
            return True
        except Exception as e:
            logger.error(f"Database health check failed: {e}")
            return False

    # Student operations
    async def create_student(self, student_data: Dict[str, Any]) -> int:
        """Create a new student"""
        async with self.get_connection() as conn:
            query = '''
                INSERT INTO students (telegram_id, username, name, phone, section, is_active, notification_enabled)
                VALUES ($1, $2, $3, $4, $5, $6, $7)
                RETURNING id
            '''
            student_id = await conn.fetchval(
                query,
                student_data['telegram_id'],
                student_data.get('username', ''),
                student_data['name'],
                student_data.get('phone', ''),
                student_data.get('section', ''),
                student_data.get('is_active', True),
                student_data.get('notification_enabled', True)
            )
            return student_id

    async def get_student_by_telegram_id(self, telegram_id: int) -> Optional[Dict[str, Any]]:
        """Get student by telegram ID"""
        async with self.get_connection() as conn:
            query = 'SELECT * FROM students WHERE telegram_id = $1'
            row = await conn.fetchrow(query, telegram_id)
            return dict(row) if row else None

    async def get_student_by_id(self, student_id: int) -> Optional[Dict[str, Any]]:
        """Get student by ID"""
        async with self.get_connection() as conn:
            query = 'SELECT * FROM students WHERE id = $1'
            row = await conn.fetchrow(query, student_id)
            return dict(row) if row else None

    async def update_student_activity(self, telegram_id: int):
        """Update student last activity"""
        async with self.get_connection() as conn:
            query = '''
                UPDATE students 
                SET last_activity = CURRENT_TIMESTAMP 
                WHERE telegram_id = $1
            '''
            await conn.execute(query, telegram_id)

    async def get_available_sections(self) -> List[str]:
        """Get available sections from database or return defaults"""
        try:
            async with self.get_connection() as conn:
                query = 'SELECT DISTINCT section FROM students WHERE section IS NOT NULL'
                rows = await conn.fetch(query)
                sections = [row['section'] for row in rows if row['section']]
                
                if sections:
                    return sections
                else:
                    return ["الصف الأول", "الصف الثاني", "الصف الثالث"]
        except:
            return ["الصف الأول", "الصف الثاني", "الصف الثالث"]
    
    async def get_student_notification_setting(self, telegram_id: int) -> bool:
        """Get student notification setting"""
        async with self.get_connection() as conn:
            query = 'SELECT notification_enabled FROM students WHERE telegram_id = $1'
            row = await conn.fetchrow(query, telegram_id)
            return row['notification_enabled'] if row else True
    
    async def update_student_notification_setting(self, telegram_id: int, enabled: bool) -> bool:
        """Update student notification setting"""
        async with self.get_connection() as conn:
            query = '''
                UPDATE students 
                SET notification_enabled = $2, last_activity = CURRENT_TIMESTAMP 
                WHERE telegram_id = $1
            '''
            await conn.execute(query, telegram_id, enabled)
        return True
    
    async def update_student_section(self, telegram_id: int, section: str) -> bool:
        """Update student section"""
        async with self.get_connection() as conn:
            query = '''
                UPDATE students 
                SET section = $2, last_activity = CURRENT_TIMESTAMP 
                WHERE telegram_id = $1
            '''
            await conn.execute(query, telegram_id, section)
        return True

    # Material operations
    async def create_material(self, material_data: Dict[str, Any]) -> int:
        """Create a new material"""
        async with self.get_connection() as conn:
            query = '''
                INSERT INTO materials (title, description, content, section, subject, week_number, 
                                     content_type, difficulty_level, estimated_duration, content_hash)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
                RETURNING id
            '''
            material_id = await conn.fetchval(
                query,
                material_data['title'],
                material_data.get('description', ''),
                material_data.get('content', ''),
                material_data['section'],
                material_data['subject'],
                material_data['week_number'],
                material_data.get('content_type', 'text'),
                material_data.get('difficulty_level', 'medium'),
                material_data.get('estimated_duration', 30),
                material_data.get('content_hash', '')
            )
            return material_id

    async def get_materials_by_section_and_week(self, section: str, week_number: int) -> List[Dict[str, Any]]:
        """Get materials for section and week"""
        async with self.get_connection() as conn:
            query = '''
                SELECT * FROM materials 
                WHERE section = $1 AND week_number = $2 AND is_active = TRUE
                ORDER BY date_published DESC
            '''
            rows = await conn.fetch(query, section, week_number)
            return [dict(row) for row in rows]

    async def get_material_by_id(self, material_id: int) -> Optional[Dict[str, Any]]:
        """Get material by ID"""
        async with self.get_connection() as conn:
            query = 'SELECT * FROM materials WHERE id = $1'
            row = await conn.fetchrow(query, material_id)
            return dict(row) if row else None

    # Quiz operations
    async def create_quiz(self, quiz_data: Dict[str, Any]) -> int:
        """Create a new quiz"""
        async with self.get_connection() as conn:
            query = '''
                INSERT INTO quizzes (title, description, section, subject, time_limit, 
                                   max_attempts, passing_score, total_points, is_active,
                                   randomize_questions, show_results_immediately, difficulty_level)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12)
                RETURNING id
            '''
            quiz_id = await conn.fetchval(
                query,
                quiz_data['title'],
                quiz_data.get('description', ''),
                quiz_data['section'],
                quiz_data['subject'],
                quiz_data.get('time_limit', 30),
                quiz_data.get('max_attempts', 3),
                quiz_data.get('passing_score', 60),
                quiz_data.get('total_points', 0),
                quiz_data.get('is_active', True),
                quiz_data.get('randomize_questions', False),
                quiz_data.get('show_results_immediately', True),
                quiz_data.get('difficulty_level', 'medium')
            )
            return quiz_id

    async def get_active_quizzes_by_section(self, section: str) -> List[Dict[str, Any]]:
        """Get active quizzes for section"""
        async with self.get_connection() as conn:
            query = '''
                SELECT * FROM quizzes 
                WHERE section = $1 AND is_active = TRUE
                ORDER BY created_date DESC
            '''
            rows = await conn.fetch(query, section)
            return [dict(row) for row in rows]

    async def get_quiz_by_id(self, quiz_id: int) -> Optional[Dict[str, Any]]:
        """Get quiz by ID"""
        async with self.get_connection() as conn:
            query = 'SELECT * FROM quizzes WHERE id = $1'
            row = await conn.fetchrow(query, quiz_id)
            return dict(row) if row else None

    # Activity logging
    async def log_activity(self, student_id: int, activity_type: str, metadata: Dict[str, Any] = None):
        """Log student activity"""
        async with self.get_connection() as conn:
            query = '''
                INSERT INTO student_activities (student_id, activity_type, metadata)
                VALUES ($1, $2, $3)
            '''
            await conn.execute(query, student_id, activity_type, json.dumps(metadata or {}))

    async def bulk_insert_activities(self, activities: List[Dict[str, Any]]):
        """Bulk insert activities"""
        if not activities:
            return
        
        async with self.get_connection() as conn:
            query = '''
                INSERT INTO student_activities (student_id, activity_type, metadata, session_id)
                VALUES ($1, $2, $3, $4)
            '''
            values = [
                (
                    activity['student_id'],
                    activity['activity_type'],
                    activity.get('metadata', '{}'),
                    activity.get('session_id')
                )
                for activity in activities
            ]
            await conn.executemany(query, values)

    # Statistics and analytics
    async def get_user_statistics(self) -> Dict[str, Any]:
        """Get user statistics"""
        async with self.get_connection() as conn:
            # Total users
            total_users = await conn.fetchval('SELECT COUNT(*) FROM students')
            
            # Active users today
            active_today = await conn.fetchval('''
                SELECT COUNT(DISTINCT student_id) FROM student_activities 
                WHERE DATE(timestamp) = CURRENT_DATE
            ''')
            
            # Active users this week
            active_week = await conn.fetchval('''
                SELECT COUNT(DISTINCT student_id) FROM student_activities 
                WHERE timestamp >= CURRENT_DATE - INTERVAL '7 days'
            ''')
            
            # New users today
            new_today = await conn.fetchval('''
                SELECT COUNT(*) FROM students 
                WHERE DATE(registration_date) = CURRENT_DATE
            ''')
            
            return {
                'total_users': total_users,
                'active_today': active_today,
                'active_this_week': active_week,
                'new_today': new_today,
                'sections_distribution': {}
            }

    async def get_content_statistics(self) -> Dict[str, Any]:
        """Get content statistics"""
        async with self.get_connection() as conn:
            total_materials = await conn.fetchval(
                'SELECT COUNT(*) FROM materials WHERE is_active = TRUE'
            )
            
            published_today = await conn.fetchval('''
                SELECT COUNT(*) FROM materials 
                WHERE DATE(date_published) = CURRENT_DATE AND is_active = TRUE
            ''')
            
            return {
                'total_materials': total_materials,
                'published_today': published_today,
                'total_file_size': 0,
                'by_subject': {}
            }

    async def get_quiz_statistics(self) -> Dict[str, Any]:
        """Get quiz statistics"""
        async with self.get_connection() as conn:
            total_quizzes = await conn.fetchval(
                'SELECT COUNT(*) FROM quizzes WHERE is_active = TRUE'
            )
            
            total_attempts = await conn.fetchval('SELECT COUNT(*) FROM quiz_attempts')
            
            attempts_today = await conn.fetchval('''
                SELECT COUNT(*) FROM quiz_attempts 
                WHERE DATE(start_time) = CURRENT_DATE
            ''')
            
            avg_score = await conn.fetchval('''
                SELECT COALESCE(AVG(total_score), 0) FROM quiz_attempts 
                WHERE status = 'completed'
            ''')
            
            return {
                'total_quizzes': total_quizzes,
                'total_attempts': total_attempts,
                'attempts_today': attempts_today,
                'average_score': float(avg_score or 0),
                'completion_rate': 0
            }

    async def get_all_active_students(self) -> List[Dict[str, Any]]:
        """Get all active students"""
        async with self.get_connection() as conn:
            query = 'SELECT * FROM students WHERE is_active = TRUE'
            rows = await conn.fetch(query)
            return [dict(row) for row in rows]

    async def get_inactive_students(self, days: int = 7) -> List[Dict[str, Any]]:
        """Get students inactive for specified days"""
        async with self.get_connection() as conn:
            query = '''
                SELECT * FROM students 
                WHERE is_active = TRUE 
                AND last_activity < CURRENT_TIMESTAMP - INTERVAL '%s days'
            ''' % days
            rows = await conn.fetch(query)
            return [dict(row) for row in rows]

    # Additional methods for production features
    async def create_question(self, question_data: Dict[str, Any]) -> int:
        """Create a quiz question"""
        async with self.get_connection() as conn:
            query = '''
                INSERT INTO questions (quiz_id, question_text, question_type, options, 
                                     correct_answer, explanation, points, order_index, difficulty)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                RETURNING id
            '''
            question_id = await conn.fetchval(
                query,
                question_data['quiz_id'],
                question_data['question_text'],
                question_data['question_type'],
                json.dumps(question_data.get('options', {})),
                question_data.get('correct_answer', ''),
                question_data.get('explanation', ''),
                question_data.get('points', 1),
                question_data.get('order_index', 0),
                question_data.get('difficulty', 'medium')
            )
            return question_id

    async def create_quiz_attempt(self, attempt_data: Dict[str, Any]) -> int:
        """Create a quiz attempt"""
        async with self.get_connection() as conn:
            query = '''
                INSERT INTO quiz_attempts (student_id, quiz_id, start_time, status, attempt_number)
                VALUES ($1, $2, $3, $4, $5)
                RETURNING id
            '''
            attempt_id = await conn.fetchval(
                query,
                attempt_data['student_id'],
                attempt_data['quiz_id'],
                attempt_data.get('start_time', datetime.now()),
                attempt_data.get('status', 'in_progress'),
                attempt_data.get('attempt_number', 1)
            )
            return attempt_id
    
    # Learning progression methods
    async def get_student_activities_by_type(self, student_id: int, activity_type: str) -> List[Dict[str, Any]]:
        """Get student activities filtered by type"""
        async with self.get_connection() as conn:
            query = '''
                SELECT * FROM student_activities 
                WHERE student_id = $1 AND activity_type = $2
                ORDER BY timestamp DESC
            '''
            rows = await conn.fetch(query, student_id, activity_type)
            return [dict(row) for row in rows]
    
    async def get_student_recent_activities(self, student_id: int, days: int = 7) -> List[Dict[str, Any]]:
        """Get recent student activities"""
        async with self.get_connection() as conn:
            query = '''
                SELECT * FROM student_activities 
                WHERE student_id = $1 
                AND timestamp >= CURRENT_TIMESTAMP - INTERVAL '%s days'
                ORDER BY timestamp DESC
            ''' % days
            rows = await conn.fetch(query, student_id)
            return [dict(row) for row in rows]
    
    async def get_quiz_by_type_and_week(self, section: str, quiz_type: str, week_number: int) -> Optional[Dict[str, Any]]:
        """Get quiz by type and week"""
        async with self.get_connection() as conn:
            query = '''
                SELECT * FROM quizzes 
                WHERE section = $1 AND quiz_type = $2 AND week_number = $3 AND is_active = TRUE
            '''
            row = await conn.fetchrow(query, section, quiz_type, week_number)
            return dict(row) if row else None
    
    async def get_cumulative_quiz(self, section: str, start_week: int, end_week: int) -> Optional[Dict[str, Any]]:
        """Get cumulative quiz for week range"""
        async with self.get_connection() as conn:
            query = '''
                SELECT * FROM quizzes 
                WHERE section = $1 AND quiz_type = 'cumulative' 
                AND start_week = $2 AND end_week = $3 AND is_active = TRUE
            '''
            row = await conn.fetchrow(query, section, start_week, end_week)
            return dict(row) if row else None
    
    async def update_student_week(self, student_id: int, current_week: int, completed_weeks: int):
        """Update student's week progression"""
        async with self.get_connection() as conn:
            query = '''
                UPDATE students 
                SET current_week = $2, completed_weeks = $3, last_activity = CURRENT_TIMESTAMP
                WHERE id = $1
            '''
            await conn.execute(query, student_id, current_week, completed_weeks)