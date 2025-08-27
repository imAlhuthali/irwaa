from sqlalchemy import Column, Integer, String, DateTime, Float, Boolean, Text, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from datetime import datetime
import json

Base = declarative_base()

class QuizQuestion(Base):
    __tablename__ = 'quiz_questions'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    week_number = Column(Integer, nullable=False, index=True)
    question_text = Column(Text, nullable=False)
    option_a = Column(String(500), nullable=False)
    option_b = Column(String(500), nullable=False)
    option_c = Column(String(500), nullable=False)
    option_d = Column(String(500), nullable=False)
    correct_answer = Column(String(1), nullable=False)  # A, B, C, or D
    hint = Column(Text, nullable=True)
    difficulty_level = Column(String(20), default='medium')  # easy, medium, hard
    created_at = Column(DateTime, default=datetime.utcnow)
    is_active = Column(Boolean, default=True)
    
    def get_options_dict(self):
        """الحصول على خيارات الإجابة كقاموس"""
        return {
            'A': self.option_a,
            'B': self.option_b,
            'C': self.option_c,
            'D': self.option_d
        }
    
    def get_correct_option_text(self):
        """الحصول على نص الإجابة الصحيحة"""
        options = self.get_options_dict()
        return options.get(self.correct_answer.upper(), '')
    
    def is_correct_answer(self, answer):
        """فحص إذا كانت الإجابة صحيحة"""
        return answer.upper() == self.correct_answer.upper()
    
    def to_dict(self):
        """تحويل السؤال إلى قاموس"""
        return {
            'id': self.id,
            'week_number': self.week_number,
            'question_text': self.question_text,
            'options': self.get_options_dict(),
            'correct_answer': self.correct_answer,
            'hint': self.hint,
            'difficulty_level': self.difficulty_level
        }

class QuizAttempt(Base):
    __tablename__ = 'quiz_attempts'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    student_id = Column(Integer, ForeignKey('students.id'), nullable=False, index=True)
    week_number = Column(Integer, nullable=False, index=True)
    started_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)
    total_questions = Column(Integer, default=0)
    correct_answers = Column(Integer, default=0)
    score_percentage = Column(Float, default=0.0)
    answers_json = Column(Text, default='{}')  # JSON: {question_id: answer}
    hints_used = Column(Integer, default=0)
    time_taken_minutes = Column(Float, default=0.0)
    is_completed = Column(Boolean, default=False)
    
    def add_answer(self, question_id, answer, is_correct=False):
        """إضافة إجابة للمحاولة"""
        answers = json.loads(self.answers_json or '{}')
        answers[str(question_id)] = {
            'answer': answer,
            'is_correct': is_correct,
            'answered_at': datetime.utcnow().isoformat()
        }
        self.answers_json = json.dumps(answers)
        
        if is_correct:
            self.correct_answers += 1
            
    def use_hint(self):
        """استخدام تلميح"""
        self.hints_used += 1
        
    def complete_quiz(self):
        """إكمال الاختبار وحساب النتيجة"""
        self.completed_at = datetime.utcnow()
        self.is_completed = True
        
        if self.started_at and self.completed_at:
            time_diff = self.completed_at - self.started_at
            self.time_taken_minutes = time_diff.total_seconds() / 60
        
        if self.total_questions > 0:
            self.score_percentage = (self.correct_answers / self.total_questions) * 100
        
        return self.score_percentage
    
    def get_answers(self):
        """الحصول على إجابات الطالب"""
        return json.loads(self.answers_json or '{}')
    
    def get_performance_analysis(self):
        """تحليل أداء الطالب في الاختبار"""
        return {
            'score': self.score_percentage,
            'correct_answers': self.correct_answers,
            'total_questions': self.total_questions,
            'hints_used': self.hints_used,
            'time_taken': self.time_taken_minutes,
            'accuracy': self.score_percentage,
            'efficiency': max(0, 100 - (self.hints_used * 10)),  # كفاءة بناءً على استخدام التلميحات
            'speed_score': min(100, max(0, 100 - (self.time_taken_minutes * 2)))  # سرعة الإجابة
        }
    
    def to_dict(self):
        """تحويل المحاولة إلى قاموس"""
        return {
            'id': self.id,
            'student_id': self.student_id,
            'week_number': self.week_number,
            'started_at': self.started_at.isoformat() if self.started_at else None,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
            'score_percentage': self.score_percentage,
            'correct_answers': self.correct_answers,
            'total_questions': self.total_questions,
            'hints_used': self.hints_used,
            'time_taken_minutes': self.time_taken_minutes,
            'is_completed': self.is_completed
        }