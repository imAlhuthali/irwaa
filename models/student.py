from sqlalchemy import Column, Integer, String, Boolean, DateTime, Float, Text
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime, timedelta
import json

Base = declarative_base()

class Student(Base):
    __tablename__ = 'students'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    telegram_id = Column(Integer, unique=True, nullable=False, index=True)
    username = Column(String(255), nullable=True)
    first_name = Column(String(255), nullable=True)
    last_name = Column(String(255), nullable=True)
    
    # Academic Progress
    current_week = Column(Integer, default=1)
    completed_weeks = Column(Integer, default=0)
    consecutive_active_weeks = Column(Integer, default=0)
    
    # Status and Activity
    is_active = Column(Boolean, default=True)
    last_activity = Column(DateTime, default=datetime.utcnow, index=True)
    join_date = Column(DateTime, default=datetime.utcnow, index=True)
    
    # Performance Metrics
    total_quiz_score = Column(Float, default=0.0)
    quiz_attempts = Column(Integer, default=0)
    engagement_score = Column(Float, default=50.0)
    average_response_time = Column(Float, default=0.0)  # in hours
    
    # Reading Confirmations
    weekly_confirmations = Column(Text, default='{}')  # JSON: {week: bool}
    content_interactions = Column(Integer, default=0)
    
    # Analytics
    total_messages_sent = Column(Integer, default=0)
    total_commands_used = Column(Integer, default=0)
    preferred_interaction_time = Column(String(10), default='morning')  # morning, afternoon, evening
    
    def update_activity(self):
        """تحديث وقت آخر نشاط للطالب"""
        self.last_activity = datetime.utcnow()
        self.total_messages_sent += 1
        
    def advance_week(self):
        """نقل الطالب للأسبوع التالي"""
        self.current_week += 1
        self.completed_weeks += 1
        self.consecutive_active_weeks += 1
        
    def confirm_weekly_reading(self, week_number, confirmed=True):
        """تأكيد قراءة محتوى أسبوع معين"""
        confirmations = json.loads(self.weekly_confirmations or '{}')
        confirmations[str(week_number)] = confirmed
        self.weekly_confirmations = json.dumps(confirmations)
        
        if confirmed:
            self.content_interactions += 1
            
    def get_weekly_confirmations(self):
        """الحصول على تأكيدات القراءة الأسبوعية"""
        return json.loads(self.weekly_confirmations or '{}')
        
    def has_confirmed_week(self, week_number):
        """فحص إذا تم تأكيد قراءة أسبوع معين"""
        confirmations = self.get_weekly_confirmations()
        return confirmations.get(str(week_number), False)
        
    def calculate_engagement_score(self):
        """حساب نقاط المشاركة بناءً على أنماط النشاط"""
        base_score = 50
        
        # مكافأة للأسابيع المتتالية (حد أقصى 30 نقطة)
        consecutive_bonus = min(self.consecutive_active_weeks * 2, 30)
        
        # مكافأة لتأكيدات المحتوى (حد أقصى 15 نقطة)
        content_bonus = min(self.content_interactions * 0.5, 15)
        
        # مكافأة لدرجات الاختبارات (حد أقصى 20 نقطة)
        if self.quiz_attempts > 0:
            quiz_bonus = min((self.total_quiz_score / self.quiz_attempts) * 0.2, 20)
        else:
            quiz_bonus = 0
        
        # عقوبة لعدم النشاط
        days_since_activity = (datetime.utcnow() - self.last_activity).days
        inactivity_penalty = min(days_since_activity * 1.5, 40)
        
        # حساب النقاط النهائية
        final_score = base_score + consecutive_bonus + content_bonus + quiz_bonus - inactivity_penalty
        self.engagement_score = max(0, min(100, final_score))
        
        return self.engagement_score
    
    def get_average_quiz_score(self):
        """حساب متوسط درجات الاختبارات"""
        if self.quiz_attempts == 0:
            return 0.0
        return self.total_quiz_score / self.quiz_attempts
    
    def is_at_risk(self):
        """فحص إذا كان الطالب معرض لخطر الحذف"""
        days_inactive = (datetime.utcnow() - self.last_activity).days
        return days_inactive >= 21  # تحذير قبل 9 أيام من الحذف
    
    def should_be_removed(self):
        """فحص إذا يجب حذف الطالب"""
        days_inactive = (datetime.utcnow() - self.last_activity).days
        return days_inactive >= 30
    
    def get_engagement_level(self):
        """الحصول على مستوى المشاركة كنص"""
        score = self.calculate_engagement_score()
        if score >= 80:
            return "ممتاز 🏆"
        elif score >= 60:
            return "جيد 👍"
        elif score >= 40:
            return "متوسط 📈"
        else:
            return "يحتاج تحسين ⚠️"
    
    def to_dict(self):
        """تحويل بيانات الطالب إلى قاموس للتحليلات"""
        return {
            'id': self.id,
            'telegram_id': self.telegram_id,
            'username': self.username,
            'first_name': self.first_name,
            'current_week': self.current_week,
            'completed_weeks': self.completed_weeks,
            'is_active': self.is_active,
            'join_date': self.join_date.isoformat() if self.join_date else None,
            'last_activity': self.last_activity.isoformat() if self.last_activity else None,
            'engagement_score': self.engagement_score,
            'average_quiz_score': self.get_average_quiz_score(),
            'total_interactions': self.content_interactions + self.quiz_attempts
        }
    
    def __repr__(self):
        return f"<Student(telegram_id={self.telegram_id}, week={self.current_week}, active={self.is_active})>"