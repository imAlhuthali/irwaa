import logging
import sqlite3
import aiosqlite
from typing import Dict, List, Optional, Any
from datetime import datetime
import json
import asyncio

logger = logging.getLogger(__name__)

class DatabaseManager:
    """Simplified database manager for local testing with SQLite"""
    
    def __init__(self, database_url: str):
        # Extract database path from URL
        if database_url.startswith('sqlite+aiosqlite:///'):
            self.db_path = database_url.replace('sqlite+aiosqlite:///', '')
        else:
            self.db_path = 'telebot.db'
        
        logger.info(f"Using SQLite database: {self.db_path}")

    async def initialize(self):
        """Initialize database and create tables"""
        try:
            await self._create_tables()
            logger.info("Database initialized successfully")
        except Exception as e:
            logger.error(f"Database initialization failed: {e}")
            raise

    async def _create_tables(self):
        """Create necessary tables"""
        async with aiosqlite.connect(self.db_path) as db:
            # Students table
            await db.execute('''
                CREATE TABLE IF NOT EXISTS students (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    telegram_id INTEGER UNIQUE NOT NULL,
                    username TEXT,
                    name TEXT NOT NULL,
                    phone TEXT,
                    section TEXT,
                    registration_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    is_active BOOLEAN DEFAULT 1,
                    notification_enabled BOOLEAN DEFAULT 1
                )
            ''')
            
            # Materials table
            await db.execute('''
                CREATE TABLE IF NOT EXISTS materials (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT NOT NULL,
                    description TEXT,
                    content TEXT,
                    section TEXT,
                    subject TEXT,
                    week_number INTEGER,
                    date_published TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    is_active BOOLEAN DEFAULT 1,
                    content_type TEXT DEFAULT 'text',
                    difficulty_level TEXT DEFAULT 'medium',
                    estimated_duration INTEGER DEFAULT 30,
                    content_hash TEXT,
                    has_files BOOLEAN DEFAULT 0,
                    last_modified TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Quizzes table
            await db.execute('''
                CREATE TABLE IF NOT EXISTS quizzes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT NOT NULL,
                    description TEXT,
                    section TEXT NOT NULL,
                    subject TEXT NOT NULL,
                    time_limit INTEGER DEFAULT 30,
                    max_attempts INTEGER DEFAULT 3,
                    passing_score INTEGER DEFAULT 60,
                    total_points INTEGER DEFAULT 0,
                    total_questions INTEGER DEFAULT 0,
                    is_active BOOLEAN DEFAULT 1,
                    randomize_questions BOOLEAN DEFAULT 0,
                    show_results_immediately BOOLEAN DEFAULT 1,
                    created_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    difficulty_level TEXT DEFAULT 'medium'
                )
            ''')
            
            # Questions table
            await db.execute('''
                CREATE TABLE IF NOT EXISTS questions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    quiz_id INTEGER NOT NULL,
                    question_text TEXT NOT NULL,
                    question_type TEXT NOT NULL,
                    options TEXT,
                    correct_answer TEXT,
                    explanation TEXT,
                    points REAL DEFAULT 1,
                    order_index INTEGER DEFAULT 0,
                    is_required BOOLEAN DEFAULT 1,
                    difficulty TEXT DEFAULT 'medium',
                    FOREIGN KEY (quiz_id) REFERENCES quizzes (id)
                )
            ''')
            
            # Quiz attempts table
            await db.execute('''
                CREATE TABLE IF NOT EXISTS quiz_attempts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    student_id INTEGER NOT NULL,
                    quiz_id INTEGER NOT NULL,
                    start_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    end_time TIMESTAMP,
                    status TEXT DEFAULT 'in_progress',
                    total_score REAL DEFAULT 0,
                    points_earned REAL DEFAULT 0,
                    passed BOOLEAN DEFAULT 0,
                    attempt_number INTEGER DEFAULT 1,
                    FOREIGN KEY (student_id) REFERENCES students (id),
                    FOREIGN KEY (quiz_id) REFERENCES quizzes (id)
                )
            ''')
            
            # Student activities table
            await db.execute('''
                CREATE TABLE IF NOT EXISTS student_activities (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    student_id INTEGER NOT NULL,
                    activity_type TEXT NOT NULL,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    metadata TEXT,
                    session_id TEXT,
                    FOREIGN KEY (student_id) REFERENCES students (id)
                )
            ''')
            
            await db.commit()

    async def close(self):
        """Close database connection"""
        # SQLite connections are closed automatically
        pass

    async def health_check(self):
        """Check database health"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute('SELECT 1')

    # Student operations
    async def create_student(self, student_data: Dict[str, Any]) -> int:
        """Create a new student"""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute('''
                INSERT INTO students (telegram_id, username, name, phone, section, is_active, notification_enabled)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (
                student_data['telegram_id'],
                student_data.get('username', ''),
                student_data['name'],
                student_data.get('phone', ''),
                student_data.get('section', ''),
                student_data.get('is_active', True),
                student_data.get('notification_enabled', True)
            ))
            await db.commit()
            return cursor.lastrowid

    async def get_student_by_telegram_id(self, telegram_id: int) -> Optional[Dict[str, Any]]:
        """Get student by telegram ID"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute('SELECT * FROM students WHERE telegram_id = ?', (telegram_id,)) as cursor:
                row = await cursor.fetchone()
                return dict(row) if row else None

    async def get_student_by_id(self, student_id: int) -> Optional[Dict[str, Any]]:
        """Get student by ID"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute('SELECT * FROM students WHERE id = ?', (student_id,)) as cursor:
                row = await cursor.fetchone()
                return dict(row) if row else None

    async def get_available_sections(self) -> List[str]:
        """Get available sections"""
        return ["الصف الأول", "الصف الثاني", "الصف الثالث"]

    # Material operations
    async def create_material(self, material_data: Dict[str, Any]) -> int:
        """Create a new material"""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute('''
                INSERT INTO materials (title, description, content, section, subject, week_number, 
                                     content_type, difficulty_level, estimated_duration, content_hash)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
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
            ))
            await db.commit()
            return cursor.lastrowid

    async def get_materials_by_section_and_week(self, section: str, week_number: int) -> List[Dict[str, Any]]:
        """Get materials for section and week"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute('''
                SELECT * FROM materials 
                WHERE section = ? AND week_number = ? AND is_active = 1
                ORDER BY date_published DESC
            ''', (section, week_number)) as cursor:
                rows = await cursor.fetchall()
                return [dict(row) for row in rows]

    async def get_material_by_id(self, material_id: int) -> Optional[Dict[str, Any]]:
        """Get material by ID"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute('SELECT * FROM materials WHERE id = ?', (material_id,)) as cursor:
                row = await cursor.fetchone()
                return dict(row) if row else None

    # Quiz operations
    async def create_quiz(self, quiz_data: Dict[str, Any]) -> int:
        """Create a new quiz"""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute('''
                INSERT INTO quizzes (title, description, section, subject, time_limit, 
                                   max_attempts, passing_score, total_points, is_active,
                                   randomize_questions, show_results_immediately, difficulty_level)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
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
            ))
            await db.commit()
            return cursor.lastrowid

    async def get_active_quizzes_by_section(self, section: str) -> List[Dict[str, Any]]:
        """Get active quizzes for section"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute('''
                SELECT * FROM quizzes 
                WHERE section = ? AND is_active = 1
                ORDER BY created_date DESC
            ''', (section,)) as cursor:
                rows = await cursor.fetchall()
                return [dict(row) for row in rows]

    async def get_quiz_by_id(self, quiz_id: int) -> Optional[Dict[str, Any]]:
        """Get quiz by ID"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute('SELECT * FROM quizzes WHERE id = ?', (quiz_id,)) as cursor:
                row = await cursor.fetchone()
                return dict(row) if row else None

    # Activity logging
    async def log_activity(self, student_id: int, activity_type: str, metadata: Dict[str, Any] = None):
        """Log student activity"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute('''
                INSERT INTO student_activities (student_id, activity_type, metadata)
                VALUES (?, ?, ?)
            ''', (student_id, activity_type, json.dumps(metadata or {})))
            await db.commit()

    async def bulk_insert_activities(self, activities: List[Dict[str, Any]]):
        """Bulk insert activities"""
        async with aiosqlite.connect(self.db_path) as db:
            for activity in activities:
                await db.execute('''
                    INSERT INTO student_activities (student_id, activity_type, metadata, session_id)
                    VALUES (?, ?, ?, ?)
                ''', (
                    activity['student_id'],
                    activity['activity_type'],
                    activity.get('metadata', '{}'),
                    activity.get('session_id')
                ))
            await db.commit()

    # Statistics and analytics
    async def get_user_statistics(self) -> Dict[str, Any]:
        """Get user statistics"""
        async with aiosqlite.connect(self.db_path) as db:
            # Total users
            async with db.execute('SELECT COUNT(*) FROM students') as cursor:
                total_users = (await cursor.fetchone())[0]
            
            # Active users today
            async with db.execute('''
                SELECT COUNT(DISTINCT student_id) FROM student_activities 
                WHERE date(timestamp) = date('now')
            ''') as cursor:
                active_today = (await cursor.fetchone())[0]
            
            return {
                'total_users': total_users,
                'active_today': active_today,
                'active_this_week': active_today,  # Simplified
                'new_today': 0,  # Simplified
                'sections_distribution': {}
            }

    async def get_content_statistics(self) -> Dict[str, Any]:
        """Get content statistics"""
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute('SELECT COUNT(*) FROM materials WHERE is_active = 1') as cursor:
                total_materials = (await cursor.fetchone())[0]
            
            return {
                'total_materials': total_materials,
                'published_today': 0,
                'total_file_size': 0,
                'by_subject': {}
            }

    async def get_quiz_statistics(self) -> Dict[str, Any]:
        """Get quiz statistics"""
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute('SELECT COUNT(*) FROM quizzes WHERE is_active = 1') as cursor:
                total_quizzes = (await cursor.fetchone())[0]
            
            async with db.execute('SELECT COUNT(*) FROM quiz_attempts') as cursor:
                total_attempts = (await cursor.fetchone())[0]
            
            return {
                'total_quizzes': total_quizzes,
                'total_attempts': total_attempts,
                'attempts_today': 0,
                'average_score': 0,
                'completion_rate': 0
            }

    # Simplified methods for demo
    async def get_material_by_hash(self, content_hash: str):
        return None
    
    async def update_material(self, material_id: int, updates: Dict[str, Any]) -> bool:
        return True
    
    async def get_material_view_stats(self, material_id: int) -> Dict[str, Any]:
        return {'view_count': 0, 'unique_viewers': 0}
    
    async def get_student_notification_setting(self, telegram_id: int) -> bool:
        return True
    
    async def update_student_notification_setting(self, telegram_id: int, enabled: bool) -> bool:
        return True
    
    async def get_all_active_students(self) -> List[Dict[str, Any]]:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute('SELECT * FROM students WHERE is_active = 1') as cursor:
                rows = await cursor.fetchall()
                return [dict(row) for row in rows]