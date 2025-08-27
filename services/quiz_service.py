import logging
from typing import Dict, List, Optional, Any, Union
from datetime import datetime, timedelta
import asyncio
import pandas as pd
import io
import json
import random
from pathlib import Path
import aiofiles

from models.database import DatabaseManager

logger = logging.getLogger(__name__)

class QuizService:
    """Service for managing quizzes and Excel parsing functionality"""
    
    def __init__(self, db_manager: DatabaseManager):
        self.db = db_manager
        self.quiz_templates_dir = Path("quiz_templates")
        self.quiz_templates_dir.mkdir(exist_ok=True)
        
        # Supported question types
        self.question_types = {
            'multiple_choice': 'اختيار من متعدد',
            'true_false': 'صح أم خطأ',
            'fill_in_blank': 'املأ الفراغ',
            'short_answer': 'إجابة قصيرة',
            'essay': 'مقال'
        }
        
        # Excel column mappings for quiz import
        self.excel_column_mappings = {
            'question': ['question', 'سؤال', 'Question', 'السؤال'],
            'option_a': ['option_a', 'a', 'الخيار أ', 'أ', 'Option A'],
            'option_b': ['option_b', 'b', 'الخيار ب', 'ب', 'Option B'],
            'option_c': ['option_c', 'c', 'الخيار ج', 'ج', 'Option C'],
            'option_d': ['option_d', 'd', 'الخيار د', 'د', 'Option D'],
            'correct_answer': ['correct_answer', 'answer', 'الإجابة الصحيحة', 'إجابة', 'Correct Answer'],
            'explanation': ['explanation', 'تفسير', 'شرح', 'Explanation'],
            'difficulty': ['difficulty', 'صعوبة', 'مستوى', 'Difficulty'],
            'points': ['points', 'نقاط', 'درجة', 'Points', 'Score']
        }

    async def create_quiz(self, quiz_data: Dict[str, Any]) -> int:
        """Create a new quiz"""
        try:
            # Validate required fields
            required_fields = ['title', 'section', 'subject']
            for field in required_fields:
                if field not in quiz_data:
                    raise ValueError(f"Missing required field: {field}")
            
            # Set default values
            quiz_data.setdefault('description', '')
            quiz_data.setdefault('time_limit', 30)  # minutes
            quiz_data.setdefault('max_attempts', 3)
            quiz_data.setdefault('passing_score', 60)  # percentage
            quiz_data.setdefault('is_active', True)
            quiz_data.setdefault('randomize_questions', False)
            quiz_data.setdefault('show_results_immediately', True)
            quiz_data.setdefault('created_date', datetime.now())
            quiz_data.setdefault('difficulty_level', 'medium')
            
            # Calculate total points if not provided
            if 'questions' in quiz_data and 'total_points' not in quiz_data:
                total_points = sum(q.get('points', 1) for q in quiz_data['questions'])
                quiz_data['total_points'] = total_points
            
            quiz_id = await self.db.create_quiz(quiz_data)
            
            # Add questions if provided
            if 'questions' in quiz_data:
                for question_data in quiz_data['questions']:
                    question_data['quiz_id'] = quiz_id
                    await self.create_question(question_data)
            
            logger.info(f"Created quiz: {quiz_data['title']} (ID: {quiz_id})")
            return quiz_id
            
        except Exception as e:
            logger.error(f"Error creating quiz: {e}")
            raise

    async def create_question(self, question_data: Dict[str, Any]) -> int:
        """Create a new quiz question"""
        try:
            # Validate required fields
            required_fields = ['quiz_id', 'question_text', 'question_type']
            for field in required_fields:
                if field not in question_data:
                    raise ValueError(f"Missing required field: {field}")
            
            # Set default values
            question_data.setdefault('points', 1)
            question_data.setdefault('order_index', 0)
            question_data.setdefault('is_required', True)
            
            # Validate question type
            if question_data['question_type'] not in self.question_types:
                raise ValueError(f"Invalid question type: {question_data['question_type']}")
            
            # Process options for multiple choice questions
            if question_data['question_type'] == 'multiple_choice':
                if 'options' not in question_data or len(question_data['options']) < 2:
                    raise ValueError("Multiple choice questions must have at least 2 options")
                
                # Ensure options are properly formatted
                options = question_data['options']
                if isinstance(options, dict):
                    question_data['options'] = json.dumps(options)
                elif isinstance(options, list):
                    options_dict = {chr(65 + i): option for i, option in enumerate(options)}
                    question_data['options'] = json.dumps(options_dict)
            
            question_id = await self.db.create_question(question_data)
            
            logger.info(f"Created question for quiz {question_data['quiz_id']} (ID: {question_id})")
            return question_id
            
        except Exception as e:
            logger.error(f"Error creating question: {e}")
            raise

    async def import_quiz_from_excel(self, excel_data: bytes, quiz_metadata: Dict[str, Any]) -> int:
        """Import quiz questions from Excel file"""
        try:
            # Read Excel data
            df = pd.read_excel(io.BytesIO(excel_data), engine='openpyxl')
            
            # Map column names
            column_mapping = self._map_excel_columns(df.columns.tolist())
            
            if 'question' not in column_mapping:
                raise ValueError("Excel file must contain a question column")
            
            # Create the quiz first
            quiz_id = await self.create_quiz(quiz_metadata)
            
            # Process each row as a question
            questions_created = 0
            for index, row in df.iterrows():
                try:
                    question_data = await self._parse_excel_row(row, column_mapping, quiz_id)
                    if question_data:
                        await self.create_question(question_data)
                        questions_created += 1
                except Exception as e:
                    logger.error(f"Error processing row {index + 1}: {e}")
                    continue
            
            # Update quiz with total questions and points
            total_points = await self.db.get_quiz_total_points(quiz_id)
            await self.db.update_quiz(quiz_id, {
                'total_questions': questions_created,
                'total_points': total_points
            })
            
            logger.info(f"Imported {questions_created} questions from Excel for quiz {quiz_id}")
            return quiz_id
            
        except Exception as e:
            logger.error(f"Error importing Excel quiz: {e}")
            raise

    async def get_available_quizzes(self, section: str) -> List[Dict[str, Any]]:
        """Get available quizzes for a section"""
        try:
            quizzes = await self.db.get_active_quizzes_by_section(section)
            
            # Enrich quiz data
            enriched_quizzes = []
            for quiz in quizzes:
                enriched_quiz = await self._enrich_quiz_data(quiz)
                enriched_quizzes.append(enriched_quiz)
            
            return enriched_quizzes
            
        except Exception as e:
            logger.error(f"Error fetching available quizzes: {e}")
            return []

    async def get_quiz_by_id(self, quiz_id: int, include_questions: bool = True) -> Optional[Dict[str, Any]]:
        """Get quiz by ID with optional questions"""
        try:
            quiz = await self.db.get_quiz_by_id(quiz_id)
            if not quiz:
                return None
            
            if include_questions:
                questions = await self.db.get_quiz_questions(quiz_id)
                quiz['questions'] = questions
            
            return await self._enrich_quiz_data(quiz)
            
        except Exception as e:
            logger.error(f"Error fetching quiz {quiz_id}: {e}")
            return None

    async def start_quiz_attempt(self, student_id: int, quiz_id: int) -> Optional[int]:
        """Start a new quiz attempt"""
        try:
            # Check if student can take the quiz
            can_take = await self._can_student_take_quiz(student_id, quiz_id)
            if not can_take['allowed']:
                logger.warning(f"Student {student_id} cannot take quiz {quiz_id}: {can_take['reason']}")
                return None
            
            # Create quiz attempt record
            attempt_data = {
                'student_id': student_id,
                'quiz_id': quiz_id,
                'start_time': datetime.now(),
                'status': 'in_progress',
                'attempt_number': can_take['attempt_number']
            }
            
            attempt_id = await self.db.create_quiz_attempt(attempt_data)
            
            logger.info(f"Started quiz attempt {attempt_id} for student {student_id}, quiz {quiz_id}")
            return attempt_id
            
        except Exception as e:
            logger.error(f"Error starting quiz attempt: {e}")
            return None

    async def submit_quiz_answer(self, attempt_id: int, question_id: int, 
                               student_answer: str) -> bool:
        """Submit an answer for a quiz question"""
        try:
            # Validate attempt is still active
            attempt = await self.db.get_quiz_attempt(attempt_id)
            if not attempt or attempt['status'] != 'in_progress':
                return False
            
            # Check time limit
            if await self._is_attempt_timed_out(attempt):
                await self._timeout_attempt(attempt_id)
                return False
            
            # Get question details
            question = await self.db.get_question_by_id(question_id)
            if not question or question['quiz_id'] != attempt['quiz_id']:
                return False
            
            # Evaluate answer
            is_correct, points_earned = await self._evaluate_answer(question, student_answer)
            
            # Save answer
            answer_data = {
                'attempt_id': attempt_id,
                'question_id': question_id,
                'student_answer': student_answer,
                'is_correct': is_correct,
                'points_earned': points_earned,
                'answered_at': datetime.now()
            }
            
            await self.db.save_quiz_answer(answer_data)
            
            logger.info(f"Submitted answer for attempt {attempt_id}, question {question_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error submitting quiz answer: {e}")
            return False

    async def complete_quiz_attempt(self, attempt_id: int) -> Optional[Dict[str, Any]]:
        """Complete a quiz attempt and calculate results"""
        try:
            # Get attempt details
            attempt = await self.db.get_quiz_attempt(attempt_id)
            if not attempt or attempt['status'] != 'in_progress':
                return None
            
            # Calculate results
            results = await self._calculate_quiz_results(attempt_id)
            
            # Update attempt record
            attempt_updates = {
                'status': 'completed',
                'end_time': datetime.now(),
                'total_score': results['score_percentage'],
                'points_earned': results['points_earned'],
                'passed': results['passed']
            }
            
            await self.db.update_quiz_attempt(attempt_id, attempt_updates)
            
            # Update student progress
            await self._update_student_progress(attempt['student_id'], attempt['quiz_id'], results)
            
            logger.info(f"Completed quiz attempt {attempt_id} with score {results['score_percentage']}%")
            return results
            
        except Exception as e:
            logger.error(f"Error completing quiz attempt: {e}")
            return None

    async def get_student_quiz_results(self, student_id: int, quiz_id: Optional[int] = None) -> List[Dict[str, Any]]:
        """Get quiz results for a student"""
        try:
            results = await self.db.get_student_quiz_results(student_id, quiz_id)
            
            # Enrich with additional data
            enriched_results = []
            for result in results:
                quiz_info = await self.db.get_quiz_by_id(result['quiz_id'])
                result['quiz_title'] = quiz_info['title'] if quiz_info else 'Unknown Quiz'
                result['quiz_subject'] = quiz_info['subject'] if quiz_info else 'Unknown'
                enriched_results.append(result)
            
            return enriched_results
            
        except Exception as e:
            logger.error(f"Error fetching quiz results: {e}")
            return []

    async def get_quiz_analytics(self, quiz_id: int) -> Dict[str, Any]:
        """Get analytics for a specific quiz"""
        try:
            analytics = await self.db.get_quiz_analytics(quiz_id)
            
            return {
                'total_attempts': analytics.get('total_attempts', 0),
                'completed_attempts': analytics.get('completed_attempts', 0),
                'average_score': analytics.get('average_score', 0),
                'pass_rate': analytics.get('pass_rate', 0),
                'average_completion_time': analytics.get('average_completion_time', 0),
                'question_analytics': analytics.get('question_analytics', {}),
                'difficulty_distribution': analytics.get('difficulty_distribution', {}),
                'score_distribution': analytics.get('score_distribution', {})
            }
            
        except Exception as e:
            logger.error(f"Error fetching quiz analytics: {e}")
            return {}

    def _map_excel_columns(self, excel_columns: List[str]) -> Dict[str, str]:
        """Map Excel columns to expected field names"""
        column_mapping = {}
        
        for field, possible_names in self.excel_column_mappings.items():
            for col in excel_columns:
                if col.strip().lower() in [name.lower() for name in possible_names]:
                    column_mapping[field] = col
                    break
        
        return column_mapping

    async def _parse_excel_row(self, row: pd.Series, column_mapping: Dict[str, str], quiz_id: int) -> Optional[Dict[str, Any]]:
        """Parse a single Excel row into question data"""
        try:
            question_text = str(row[column_mapping['question']]).strip()
            if not question_text or question_text.lower() in ['nan', 'none', '']:
                return None
            
            question_data = {
                'quiz_id': quiz_id,
                'question_text': question_text,
                'question_type': 'multiple_choice',  # Default type
                'points': 1
            }
            
            # Check if it's a true/false question
            if any(word in question_text.lower() for word in ['صح أم خطأ', 'true or false', 'صح/خطأ']):
                question_data['question_type'] = 'true_false'
                question_data['options'] = json.dumps({'A': 'صح', 'B': 'خطأ'})
            else:
                # Handle multiple choice options
                options = {}
                for option_key in ['option_a', 'option_b', 'option_c', 'option_d']:
                    if option_key in column_mapping:
                        option_value = str(row[column_mapping[option_key]]).strip()
                        if option_value and option_value.lower() not in ['nan', 'none', '']:
                            options[option_key[-1].upper()] = option_value
                
                if len(options) >= 2:
                    question_data['options'] = json.dumps(options)
                else:
                    question_data['question_type'] = 'short_answer'
            
            # Set correct answer
            if 'correct_answer' in column_mapping:
                correct_answer = str(row[column_mapping['correct_answer']]).strip()
                if correct_answer and correct_answer.lower() not in ['nan', 'none', '']:
                    question_data['correct_answer'] = correct_answer
            
            # Set explanation
            if 'explanation' in column_mapping:
                explanation = str(row[column_mapping['explanation']]).strip()
                if explanation and explanation.lower() not in ['nan', 'none', '']:
                    question_data['explanation'] = explanation
            
            # Set difficulty
            if 'difficulty' in column_mapping:
                difficulty = str(row[column_mapping['difficulty']]).strip().lower()
                if difficulty in ['easy', 'medium', 'hard', 'سهل', 'متوسط', 'صعب']:
                    difficulty_map = {'سهل': 'easy', 'متوسط': 'medium', 'صعب': 'hard'}
                    question_data['difficulty'] = difficulty_map.get(difficulty, difficulty)
            
            # Set points
            if 'points' in column_mapping:
                try:
                    points = float(row[column_mapping['points']])
                    if points > 0:
                        question_data['points'] = points
                except (ValueError, TypeError):
                    pass
            
            return question_data
            
        except Exception as e:
            logger.error(f"Error parsing Excel row: {e}")
            return None

    async def _can_student_take_quiz(self, student_id: int, quiz_id: int) -> Dict[str, Any]:
        """Check if student can take the quiz"""
        try:
            quiz = await self.db.get_quiz_by_id(quiz_id)
            if not quiz or not quiz['is_active']:
                return {'allowed': False, 'reason': 'Quiz not available'}
            
            # Check previous attempts
            attempts = await self.db.get_student_quiz_attempts(student_id, quiz_id)
            attempt_count = len(attempts)
            
            if attempt_count >= quiz['max_attempts']:
                return {'allowed': False, 'reason': 'Maximum attempts reached'}
            
            # Check if there's an active attempt
            active_attempt = next((a for a in attempts if a['status'] == 'in_progress'), None)
            if active_attempt:
                return {'allowed': False, 'reason': 'Active attempt in progress'}
            
            return {
                'allowed': True, 
                'attempt_number': attempt_count + 1,
                'remaining_attempts': quiz['max_attempts'] - attempt_count
            }
            
        except Exception as e:
            logger.error(f"Error checking quiz eligibility: {e}")
            return {'allowed': False, 'reason': 'System error'}

    async def _evaluate_answer(self, question: Dict[str, Any], student_answer: str) -> tuple[bool, float]:
        """Evaluate a student's answer"""
        try:
            question_type = question['question_type']
            correct_answer = question.get('correct_answer', '').strip().lower()
            student_answer = student_answer.strip().lower()
            
            is_correct = False
            
            if question_type == 'multiple_choice':
                # For multiple choice, compare the selected option
                is_correct = student_answer == correct_answer
            
            elif question_type == 'true_false':
                # Handle Arabic and English true/false
                true_values = ['true', 'صح', 'صحيح', '1', 'yes', 'نعم']
                false_values = ['false', 'خطأ', 'خاطئ', '0', 'no', 'لا']
                
                student_bool = student_answer in true_values
                correct_bool = correct_answer in true_values
                is_correct = student_bool == correct_bool
            
            elif question_type == 'fill_in_blank':
                # More flexible matching for fill-in-the-blank
                is_correct = self._fuzzy_match(student_answer, correct_answer)
            
            elif question_type == 'short_answer':
                # Fuzzy matching for short answers
                is_correct = self._fuzzy_match(student_answer, correct_answer)
            
            # Calculate points earned
            points_earned = question['points'] if is_correct else 0
            
            return is_correct, points_earned
            
        except Exception as e:
            logger.error(f"Error evaluating answer: {e}")
            return False, 0

    def _fuzzy_match(self, student_answer: str, correct_answer: str, threshold: float = 0.8) -> bool:
        """Fuzzy string matching for answers"""
        if not student_answer or not correct_answer:
            return False
        
        # Simple similarity check (you can use more sophisticated libraries like fuzzywuzzy)
        student_words = set(student_answer.split())
        correct_words = set(correct_answer.split())
        
        if len(correct_words) == 0:
            return False
        
        intersection = len(student_words.intersection(correct_words))
        similarity = intersection / len(correct_words)
        
        return similarity >= threshold

    async def _calculate_quiz_results(self, attempt_id: int) -> Dict[str, Any]:
        """Calculate quiz results for an attempt"""
        try:
            attempt = await self.db.get_quiz_attempt(attempt_id)
            quiz = await self.db.get_quiz_by_id(attempt['quiz_id'])
            answers = await self.db.get_quiz_attempt_answers(attempt_id)
            
            total_questions = len(answers)
            correct_answers = sum(1 for answer in answers if answer['is_correct'])
            points_earned = sum(answer['points_earned'] for answer in answers)
            total_points = quiz['total_points']
            
            score_percentage = (points_earned / total_points * 100) if total_points > 0 else 0
            passed = score_percentage >= quiz['passing_score']
            
            # Calculate time taken
            start_time = attempt['start_time']
            end_time = datetime.now()
            time_taken = (end_time - start_time).total_seconds() / 60  # minutes
            
            return {
                'attempt_id': attempt_id,
                'total_questions': total_questions,
                'correct_answers': correct_answers,
                'wrong_answers': total_questions - correct_answers,
                'points_earned': points_earned,
                'total_points': total_points,
                'score_percentage': round(score_percentage, 2),
                'passed': passed,
                'passing_score': quiz['passing_score'],
                'time_taken_minutes': round(time_taken, 2),
                'answers': answers
            }
            
        except Exception as e:
            logger.error(f"Error calculating quiz results: {e}")
            return {}

    async def _enrich_quiz_data(self, quiz: Dict[str, Any]) -> Dict[str, Any]:
        """Enrich quiz data with additional information"""
        try:
            # Add question count
            question_count = await self.db.get_quiz_question_count(quiz['id'])
            quiz['question_count'] = question_count
            
            # Add attempt statistics
            attempt_stats = await self.db.get_quiz_attempt_stats(quiz['id'])
            quiz['total_attempts'] = attempt_stats.get('total_attempts', 0)
            quiz['average_score'] = attempt_stats.get('average_score', 0)
            
            # Add time estimates
            if question_count > 0:
                estimated_time = question_count * 1.5  # 1.5 minutes per question
                quiz['estimated_time_minutes'] = int(estimated_time)
            
            return quiz
            
        except Exception as e:
            logger.error(f"Error enriching quiz data: {e}")
            return quiz

    async def _is_attempt_timed_out(self, attempt: Dict[str, Any]) -> bool:
        """Check if quiz attempt has timed out"""
        if not attempt.get('start_time'):
            return False
        
        quiz = await self.db.get_quiz_by_id(attempt['quiz_id'])
        if not quiz or quiz['time_limit'] <= 0:
            return False
        
        elapsed_minutes = (datetime.now() - attempt['start_time']).total_seconds() / 60
        return elapsed_minutes > quiz['time_limit']

    async def _timeout_attempt(self, attempt_id: int):
        """Mark attempt as timed out"""
        await self.db.update_quiz_attempt(attempt_id, {
            'status': 'timed_out',
            'end_time': datetime.now()
        })

    async def _update_student_progress(self, student_id: int, quiz_id: int, results: Dict[str, Any]):
        """Update student progress based on quiz results"""
        try:
            progress_data = {
                'student_id': student_id,
                'quiz_id': quiz_id,
                'score_percentage': results['score_percentage'],
                'passed': results['passed'],
                'completion_date': datetime.now(),
                'time_taken': results['time_taken_minutes']
            }
            
            await self.db.update_student_quiz_progress(progress_data)
            
        except Exception as e:
            logger.error(f"Error updating student progress: {e}")

    async def export_quiz_results(self, quiz_id: int) -> bytes:
        """Export quiz results to Excel"""
        try:
            results = await self.db.get_all_quiz_results(quiz_id)
            quiz = await self.db.get_quiz_by_id(quiz_id)
            
            # Create DataFrame
            df_data = []
            for result in results:
                df_data.append({
                    'Student Name': result.get('student_name', ''),
                    'Attempt': result.get('attempt_number', 1),
                    'Score (%)': result.get('total_score', 0),
                    'Points': f"{result.get('points_earned', 0)}/{quiz.get('total_points', 0)}",
                    'Status': 'Passed' if result.get('passed') else 'Failed',
                    'Time Taken (min)': result.get('completion_time_minutes', 0),
                    'Completion Date': result.get('end_time', '').strftime('%Y-%m-%d %H:%M') if result.get('end_time') else ''
                })
            
            df = pd.DataFrame(df_data)
            
            # Export to Excel bytes
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                df.to_excel(writer, index=False, sheet_name='Quiz Results')
            
            return output.getvalue()
            
        except Exception as e:
            logger.error(f"Error exporting quiz results: {e}")
            return b''