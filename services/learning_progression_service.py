"""
Learning Progression Service
Manages the 2-year sustainable learning flow with weekly content and progressive quizzes
"""

import logging
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timedelta
from enum import Enum

logger = logging.getLogger(__name__)


class QuizType(Enum):
    """Types of quizzes in the learning system"""
    WEEKLY = "weekly"           # Single question after each week
    CUMULATIVE = "cumulative"   # 5-10 questions every 3 weeks


class LearningPhase(Enum):
    """Learning phases for content delivery"""
    CONTENT = "content"         # Delivering weekly content
    WEEKLY_QUIZ = "weekly_quiz" # Weekly single-question quiz
    CUMULATIVE_QUIZ = "cumulative_quiz"  # Multi-question assessment


class LearningProgressionService:
    """
    Manages sustainable learning progression over 2+ years
    
    Flow:
    - Week 1: Content → Weekly Quiz (1 question)
    - Week 2: Content → Weekly Quiz (1 question) 
    - Week 3: Content → Weekly Quiz (1 question) → Cumulative Quiz (5-10 questions)
    - Repeat cycle with increasing complexity
    """
    
    def __init__(self, db_manager, content_service, quiz_service):
        self.db = db_manager
        self.content_service = content_service
        self.quiz_service = quiz_service
        
        # Configuration for sustainable growth
        self.WEEKS_PER_CYCLE = 3
        self.MAX_WEEKS = 104  # 2 years
        self.CUMULATIVE_QUIZ_MIN_QUESTIONS = 5
        self.CUMULATIVE_QUIZ_MAX_QUESTIONS = 10
        
    async def get_student_current_phase(self, student_id: int) -> Tuple[int, LearningPhase, Dict[str, Any]]:
        """
        Get student's current learning phase and week
        Returns: (current_week, phase, phase_data)
        """
        student = await self.db.get_student_by_id(student_id)
        if not student:
            raise ValueError("Student not found")
            
        current_week = student.get('current_week', 1)
        completed_weeks = student.get('completed_weeks', 0)
        
        # Determine current phase
        if current_week > completed_weeks + 1:
            # Student is behind - need to complete previous content
            actual_week = completed_weeks + 1
        else:
            actual_week = current_week
            
        phase_data = await self._determine_phase_for_week(student_id, actual_week)
        
        return actual_week, phase_data['phase'], phase_data
    
    async def _determine_phase_for_week(self, student_id: int, week: int) -> Dict[str, Any]:
        """Determine what phase the student should be in for a given week"""
        
        # Check if content for this week has been consumed
        content_completed = await self._is_week_content_completed(student_id, week)
        
        # Check if weekly quiz has been taken
        weekly_quiz_completed = await self._is_weekly_quiz_completed(student_id, week)
        
        # Check if it's a cumulative quiz week (every 3rd week)
        is_cumulative_week = week % self.WEEKS_PER_CYCLE == 0
        
        if not content_completed:
            return {
                'phase': LearningPhase.CONTENT,
                'week': week,
                'description': f'مراجعة محتوى الأسبوع {week}'
            }
            
        elif not weekly_quiz_completed:
            return {
                'phase': LearningPhase.WEEKLY_QUIZ,
                'week': week,
                'description': f'اختبار الأسبوع {week} (سؤال واحد)'
            }
            
        elif is_cumulative_week:
            cumulative_completed = await self._is_cumulative_quiz_completed(student_id, week)
            if not cumulative_completed:
                start_week = week - self.WEEKS_PER_CYCLE + 1
                return {
                    'phase': LearningPhase.CUMULATIVE_QUIZ,
                    'week': week,
                    'start_week': start_week,
                    'end_week': week,
                    'description': f'اختبار شامل للأسابيع {start_week}-{week} ({self.CUMULATIVE_QUIZ_MIN_QUESTIONS}-{self.CUMULATIVE_QUIZ_MAX_QUESTIONS} أسئلة)'
                }
        
        # All requirements met - advance to next week
        await self._advance_student_week(student_id)
        return await self._determine_phase_for_week(student_id, week + 1)
    
    async def get_week_content(self, student_id: int, week: int) -> List[Dict[str, Any]]:
        """Get content materials for a specific week"""
        student = await self.db.get_student_by_id(student_id)
        section = student.get('section', 'الصف الأول')
        
        materials = await self.db.get_materials_by_section_and_week(section, week)
        
        if not materials:
            # Auto-generate placeholder content structure for sustainability
            logger.info(f"No content found for week {week}, section {section}")
            return [{
                'id': f'placeholder_{week}',
                'title': f'محتوى الأسبوع {week}',
                'description': f'المحتوى التعليمي للأسبوع {week} - سيتم إضافته قريباً',
                'content': f'هذا الأسبوع سنتعلم مواضيع مهمة في الأسبوع {week}',
                'week_number': week,
                'section': section,
                'is_placeholder': True
            }]
            
        return materials
    
    async def generate_weekly_quiz(self, student_id: int, week: int) -> Dict[str, Any]:
        """Generate or get weekly quiz (single question)"""
        student = await self.db.get_student_by_id(student_id)
        section = student.get('section', 'الصف الأول')
        
        # Try to find existing weekly quiz
        existing_quiz = await self._find_weekly_quiz(section, week)
        if existing_quiz:
            return existing_quiz
            
        # Generate new weekly quiz
        quiz_data = {
            'title': f'اختبار الأسبوع {week}',
            'description': f'اختبار سريع حول محتوى الأسبوع {week}',
            'section': section,
            'subject': f'Week_{week}',
            'time_limit': 5,  # 5 minutes for single question
            'max_attempts': 2,
            'passing_score': 70,
            'quiz_type': QuizType.WEEKLY.value,
            'week_number': week,
            'difficulty_level': self._calculate_difficulty_for_week(week)
        }
        
        quiz_id = await self.db.create_quiz(quiz_data)
        
        # Generate single question
        question_data = {
            'quiz_id': quiz_id,
            'question_text': f'سؤال حول محتوى الأسبوع {week}',
            'question_type': 'multiple_choice',
            'options': {
                'A': 'الخيار الأول',
                'B': 'الخيار الثاني', 
                'C': 'الخيار الثالث',
                'D': 'الخيار الرابع'
            },
            'correct_answer': 'A',
            'explanation': f'شرح الإجابة للأسبوع {week}',
            'points': 1,
            'order_index': 1
        }
        
        await self.db.create_question(question_data)
        
        # Update quiz totals
        await self.db.execute('''
            UPDATE quizzes SET total_questions = 1, total_points = 1 
            WHERE id = $1
        ''', quiz_id)
        
        return await self.db.get_quiz_by_id(quiz_id)
    
    async def generate_cumulative_quiz(self, student_id: int, end_week: int) -> Dict[str, Any]:
        """Generate cumulative quiz for a 3-week cycle"""
        student = await self.db.get_student_by_id(student_id)
        section = student.get('section', 'الصف الأول')
        
        start_week = end_week - self.WEEKS_PER_CYCLE + 1
        
        # Check for existing cumulative quiz
        existing_quiz = await self._find_cumulative_quiz(section, start_week, end_week)
        if existing_quiz:
            return existing_quiz
            
        # Generate new cumulative quiz
        num_questions = min(
            self.CUMULATIVE_QUIZ_MAX_QUESTIONS,
            max(self.CUMULATIVE_QUIZ_MIN_QUESTIONS, end_week // 2)
        )
        
        quiz_data = {
            'title': f'اختبار شامل - الأسابيع {start_week} إلى {end_week}',
            'description': f'اختبار شامل يغطي محتوى الأسابيع من {start_week} إلى {end_week}',
            'section': section,
            'subject': f'Cumulative_{start_week}_{end_week}',
            'time_limit': num_questions * 3,  # 3 minutes per question
            'max_attempts': 2,
            'passing_score': 70,
            'quiz_type': QuizType.CUMULATIVE.value,
            'start_week': start_week,
            'end_week': end_week,
            'difficulty_level': self._calculate_difficulty_for_week(end_week)
        }
        
        quiz_id = await self.db.create_quiz(quiz_data)
        
        # Generate questions covering the week range
        total_points = 0
        for i in range(num_questions):
            week_focus = start_week + (i % self.WEEKS_PER_CYCLE)
            points = 1 + (i // 5)  # Increase points for later questions
            
            question_data = {
                'quiz_id': quiz_id,
                'question_text': f'سؤال رقم {i+1} - محتوى الأسبوع {week_focus}',
                'question_type': 'multiple_choice',
                'options': {
                    'A': f'الخيار الأول للأسبوع {week_focus}',
                    'B': f'الخيار الثاني للأسبوع {week_focus}',
                    'C': f'الخيار الثالث للأسبوع {week_focus}',
                    'D': f'الخيار الرابع للأسبوع {week_focus}'
                },
                'correct_answer': ['A', 'B', 'C', 'D'][i % 4],
                'explanation': f'شرح السؤال {i+1} للأسبوع {week_focus}',
                'points': points,
                'order_index': i + 1,
                'difficulty': self._calculate_difficulty_for_week(week_focus)
            }
            
            await self.db.create_question(question_data)
            total_points += points
        
        # Update quiz totals
        await self.db.execute('''
            UPDATE quizzes SET total_questions = $1, total_points = $2 
            WHERE id = $3
        ''', num_questions, total_points, quiz_id)
        
        return await self.db.get_quiz_by_id(quiz_id)
    
    async def mark_content_completed(self, student_id: int, week: int):
        """Mark weekly content as completed for student"""
        await self.db.log_activity(
            student_id, 
            'content_completed', 
            {'week': week, 'timestamp': datetime.now().isoformat()}
        )
    
    async def mark_quiz_completed(self, student_id: int, quiz_id: int, quiz_type: str):
        """Mark quiz as completed and potentially advance student"""
        quiz = await self.db.get_quiz_by_id(quiz_id)
        week = quiz.get('week_number', quiz.get('end_week', 1))
        
        await self.db.log_activity(
            student_id,
            f'{quiz_type}_quiz_completed',
            {
                'quiz_id': quiz_id,
                'week': week,
                'quiz_type': quiz_type,
                'timestamp': datetime.now().isoformat()
            }
        )
        
        # Check if student should advance
        if quiz_type == QuizType.CUMULATIVE.value or (
            quiz_type == QuizType.WEEKLY.value and week % self.WEEKS_PER_CYCLE != 0
        ):
            await self._advance_student_week(student_id)
    
    async def get_student_progress_summary(self, student_id: int) -> Dict[str, Any]:
        """Get comprehensive progress summary for student"""
        student = await self.db.get_student_by_id(student_id)
        current_week = student.get('current_week', 1)
        completed_weeks = student.get('completed_weeks', 0)
        
        # Calculate progress metrics
        total_progress = (completed_weeks / self.MAX_WEEKS) * 100
        current_cycle = (current_week - 1) // self.WEEKS_PER_CYCLE + 1
        week_in_cycle = ((current_week - 1) % self.WEEKS_PER_CYCLE) + 1
        
        # Get recent activities
        recent_activities = await self.db.get_student_recent_activities(student_id, days=7)
        
        return {
            'student_id': student_id,
            'current_week': current_week,
            'completed_weeks': completed_weeks,
            'total_progress_percent': round(total_progress, 1),
            'current_cycle': current_cycle,
            'week_in_cycle': week_in_cycle,
            'weeks_remaining': self.MAX_WEEKS - current_week,
            'recent_activities': recent_activities[:5],  # Last 5 activities
            'next_milestone': self._get_next_milestone(current_week)
        }
    
    # Private helper methods
    
    async def _is_week_content_completed(self, student_id: int, week: int) -> bool:
        """Check if student has completed content for a specific week"""
        activities = await self.db.get_student_activities_by_type(
            student_id, 'content_completed'
        )
        return any(
            activity.get('metadata', {}).get('week') == week 
            for activity in activities
        )
    
    async def _is_weekly_quiz_completed(self, student_id: int, week: int) -> bool:
        """Check if student has completed weekly quiz"""
        activities = await self.db.get_student_activities_by_type(
            student_id, 'weekly_quiz_completed'
        )
        return any(
            activity.get('metadata', {}).get('week') == week 
            for activity in activities
        )
    
    async def _is_cumulative_quiz_completed(self, student_id: int, end_week: int) -> bool:
        """Check if student has completed cumulative quiz for cycle"""
        activities = await self.db.get_student_activities_by_type(
            student_id, 'cumulative_quiz_completed'
        )
        return any(
            activity.get('metadata', {}).get('week') == end_week 
            for activity in activities
        )
    
    async def _find_weekly_quiz(self, section: str, week: int) -> Optional[Dict[str, Any]]:
        """Find existing weekly quiz"""
        # Implementation depends on your quiz storage structure
        return None  # Placeholder
    
    async def _find_cumulative_quiz(self, section: str, start_week: int, end_week: int) -> Optional[Dict[str, Any]]:
        """Find existing cumulative quiz"""
        # Implementation depends on your quiz storage structure  
        return None  # Placeholder
    
    async def _advance_student_week(self, student_id: int):
        """Advance student to next week"""
        await self.db.execute('''
            UPDATE students 
            SET completed_weeks = current_week,
                current_week = current_week + 1,
                last_activity = CURRENT_TIMESTAMP
            WHERE id = $1
        ''', student_id)
    
    def _calculate_difficulty_for_week(self, week: int) -> str:
        """Calculate appropriate difficulty level for week"""
        if week <= 10:
            return 'easy'
        elif week <= 30:
            return 'medium'
        elif week <= 60:
            return 'hard'
        else:
            return 'expert'
    
    def _get_next_milestone(self, current_week: int) -> Dict[str, Any]:
        """Get information about the next learning milestone"""
        if current_week % self.WEEKS_PER_CYCLE == 0:
            return {
                'type': 'cumulative_quiz',
                'description': f'اختبار شامل للأسابيع {current_week - 2}-{current_week}',
                'weeks_away': 0
            }
        else:
            weeks_to_cumulative = self.WEEKS_PER_CYCLE - (current_week % self.WEEKS_PER_CYCLE)
            target_week = current_week + weeks_to_cumulative
            return {
                'type': 'cumulative_quiz',
                'description': f'اختبار شامل قادم في الأسبوع {target_week}',
                'weeks_away': weeks_to_cumulative
            }