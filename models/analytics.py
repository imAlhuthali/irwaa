from sqlalchemy import Column, Integer, String, DateTime, Float, Boolean, Text, Date
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime, date
import json

Base = declarative_base()

class DailyAnalytics(Base):
    __tablename__ = 'daily_analytics'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    date = Column(Date, nullable=False, unique=True, index=True)
    
    # Student Metrics
    total_active_students = Column(Integer, default=0)
    new_registrations = Column(Integer, default=0)
    students_removed = Column(Integer, default=0)
    students_at_risk = Column(Integer, default=0)
    
    # Engagement Metrics
    content_confirmations = Column(Integer, default=0)
    quiz_attempts = Column(Integer, default=0)
    quiz_completions = Column(Integer, default=0)
    messages_sent = Column(Integer, default=0)
    commands_used = Column(Integer, default=0)
    
    # Performance Metrics
    average_engagement_score = Column(Float, default=0.0)
    average_quiz_score = Column(Float, default=0.0)
    quiz_completion_rate = Column(Float, default=0.0)
    content_engagement_rate = Column(Float, default=0.0)
    
    # Week Distribution (JSON)
    week_distribution = Column(Text, default='{}')  # {week: count}
    engagement_distribution = Column(Text, default='{}')  # {level: count}
    
    created_at = Column(DateTime, default=datetime.utcnow)
    
    def set_week_distribution(self, distribution):
        """تعيين توزيع الطلاب حسب الأسبوع"""
        self.week_distribution = json.dumps(distribution)
    
    def get_week_distribution(self):
        """الحصول على توزيع الطلاب حسب الأسبوع"""
        return json.loads(self.week_distribution or '{}')
    
    def set_engagement_distribution(self, distribution):
        """تعيين توزيع مستويات المشاركة"""
        self.engagement_distribution = json.dumps(distribution)
    
    def get_engagement_distribution(self):
        """الحصول على توزيع مستويات المشاركة"""
        return json.loads(self.engagement_distribution or '{}')
    
    def calculate_growth_rate(self, previous_day_data):
        """حساب معدل النمو مقارنة باليوم السابق"""
        if not previous_day_data:
            return 0.0
        
        if previous_day_data.total_active_students == 0:
            return 100.0 if self.total_active_students > 0 else 0.0
            
        growth = ((self.total_active_students - previous_day_data.total_active_students) / 
                 previous_day_data.total_active_students) * 100
        return round(growth, 2)
    
    def to_dict(self):
        """تحويل البيانات إلى قاموس"""
        return {
            'date': self.date.isoformat(),
            'total_active_students': self.total_active_students,
            'new_registrations': self.new_registrations,
            'students_removed': self.students_removed,
            'students_at_risk': self.students_at_risk,
            'content_confirmations': self.content_confirmations,
            'quiz_attempts': self.quiz_attempts,
            'quiz_completions': self.quiz_completions,
            'messages_sent': self.messages_sent,
            'commands_used': self.commands_used,
            'average_engagement_score': self.average_engagement_score,
            'average_quiz_score': self.average_quiz_score,
            'quiz_completion_rate': self.quiz_completion_rate,
            'content_engagement_rate': self.content_engagement_rate,
            'week_distribution': self.get_week_distribution(),
            'engagement_distribution': self.get_engagement_distribution()
        }

class WeeklyReport(Base):
    __tablename__ = 'weekly_reports'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    week_start = Column(Date, nullable=False, index=True)
    week_end = Column(Date, nullable=False)
    
    # Summary Metrics
    total_students = Column(Integer, default=0)
    active_students = Column(Integer, default=0)
    new_students = Column(Integer, default=0)
    churned_students = Column(Integer, default=0)
    
    # Engagement Summary
    total_content_interactions = Column(Integer, default=0)
    total_quiz_attempts = Column(Integer, default=0)
    total_quiz_completions = Column(Integer, default=0)
    average_session_duration = Column(Float, default=0.0)
    
    # Performance Summary
    weekly_avg_engagement = Column(Float, default=0.0)
    weekly_avg_quiz_score = Column(Float, default=0.0)
    retention_rate = Column(Float, default=0.0)
    completion_rate = Column(Float, default=0.0)
    
    # Detailed Analysis (JSON)
    performance_trends = Column(Text, default='{}')
    student_segments = Column(Text, default='{}')
    recommendations = Column(Text, default='{}')
    
    created_at = Column(DateTime, default=datetime.utcnow)
    
    def set_performance_trends(self, trends):
        """تعيين اتجاهات الأداء"""
        self.performance_trends = json.dumps(trends)
    
    def get_performance_trends(self):
        """الحصول على اتجاهات الأداء"""
        return json.loads(self.performance_trends or '{}')
    
    def set_student_segments(self, segments):
        """تعيين تقسيمات الطلاب"""
        self.student_segments = json.dumps(segments)
    
    def get_student_segments(self):
        """الحصول على تقسيمات الطلاب"""
        return json.loads(self.student_segments or '{}')
    
    def set_recommendations(self, recommendations):
        """تعيين التوصيات"""
        self.recommendations = json.dumps(recommendations)
    
    def get_recommendations(self):
        """الحصول على التوصيات"""
        return json.loads(self.recommendations or '{}')
    
    def calculate_weekly_growth(self, previous_week_data):
        """حساب النمو الأسبوعي"""
        if not previous_week_data or previous_week_data.total_students == 0:
            return 0.0
        
        growth = ((self.total_students - previous_week_data.total_students) / 
                 previous_week_data.total_students) * 100
        return round(growth, 2)
    
    def to_dict(self):
        """تحويل التقرير إلى قاموس"""
        return {
            'week_start': self.week_start.isoformat(),
            'week_end': self.week_end.isoformat(),
            'total_students': self.total_students,
            'active_students': self.active_students,
            'new_students': self.new_students,
            'churned_students': self.churned_students,
            'total_content_interactions': self.total_content_interactions,
            'total_quiz_attempts': self.total_quiz_attempts,
            'total_quiz_completions': self.total_quiz_completions,
            'weekly_avg_engagement': self.weekly_avg_engagement,
            'weekly_avg_quiz_score': self.weekly_avg_quiz_score,
            'retention_rate': self.retention_rate,
            'completion_rate': self.completion_rate,
            'performance_trends': self.get_performance_trends(),
            'student_segments': self.get_student_segments(),
            'recommendations': self.get_recommendations()
        }

class SystemMetrics(Base):
    __tablename__ = 'system_metrics'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    
    # System Performance
    response_time_avg = Column(Float, default=0.0)  # milliseconds
    memory_usage_mb = Column(Float, default=0.0)
    cpu_usage_percent = Column(Float, default=0.0)
    
    # Bot Performance
    messages_per_minute = Column(Integer, default=0)
    commands_per_minute = Column(Integer, default=0)
    errors_count = Column(Integer, default=0)
    
    # Database Performance
    db_query_time_avg = Column(Float, default=0.0)  # milliseconds
    active_connections = Column(Integer, default=0)
    
    def to_dict(self):
        """تحويل المقاييس إلى قاموس"""
        return {
            'timestamp': self.timestamp.isoformat(),
            'response_time_avg': self.response_time_avg,
            'memory_usage_mb': self.memory_usage_mb,
            'cpu_usage_percent': self.cpu_usage_percent,
            'messages_per_minute': self.messages_per_minute,
            'commands_per_minute': self.commands_per_minute,
            'errors_count': self.errors_count,
            'db_query_time_avg': self.db_query_time_avg,
            'active_connections': self.active_connections
        }