import logging
from typing import Dict, List, Optional, Any, Union
from datetime import datetime, timedelta
import asyncio
import json
import os
from collections import defaultdict, Counter
from dataclasses import dataclass
from enum import Enum

from models import get_database_manager

logger = logging.getLogger(__name__)

class ActivityType(Enum):
    LOGIN = "login"
    QUIZ_START = "quiz_start"
    QUIZ_COMPLETE = "quiz_complete"
    MATERIAL_VIEW = "material_view"
    REGISTRATION = "registration"
    SETTINGS_CHANGE = "settings_change"

@dataclass
class StudentActivity:
    student_id: int
    activity_type: str
    timestamp: datetime
    metadata: Dict[str, Any]
    session_id: Optional[str] = None

class AnalyticsService:
    """Service for analytics, progress tracking, and real-time dashboard"""
    
    def __init__(self, db_manager):
        self.db = db_manager
        self.activity_buffer = []
        # Production-optimized buffer size for 7000+ users
        self.buffer_size = int(os.getenv('ANALYTICS_BUFFER_SIZE', '500'))
        self.max_buffer_size = int(os.getenv('ANALYTICS_MAX_BUFFER_SIZE', '2000'))  # Emergency limit
        self.realtime_subscribers = set()
        self._flush_lock = asyncio.Lock()  # Prevent concurrent flushes
        
    async def log_student_activity(self, student_id: int, activity_type: str, 
                                 metadata: Optional[Dict[str, Any]] = None, 
                                 session_id: Optional[str] = None):
        """Log student activity for analytics"""
        try:
            activity = StudentActivity(
                student_id=student_id,
                activity_type=activity_type,
                timestamp=datetime.now(),
                metadata=metadata or {},
                session_id=session_id
            )
            
            # Add to buffer with overflow protection
            self.activity_buffer.append(activity)
            
            # Emergency flush if buffer exceeds maximum size
            if len(self.activity_buffer) >= self.max_buffer_size:
                logger.warning(f"Analytics buffer overflow: {len(self.activity_buffer)} items, forcing flush")
                await self._flush_activity_buffer()
            
            # Normal flush when buffer reaches target size
            elif len(self.activity_buffer) >= self.buffer_size:
                await self._flush_activity_buffer()
            
            # Send real-time updates
            await self._notify_realtime_subscribers(activity)
            
        except Exception as e:
            logger.error(f"Error logging activity: {e}")

    async def get_student_progress(self, student_id: int) -> Dict[str, Any]:
        """Get comprehensive progress data for a student"""
        try:
            # Get student basic info
            student = await self.db.get_student_by_id(student_id)
            if not student:
                return {}
            
            # Get quiz statistics
            quiz_stats = await self._get_student_quiz_stats(student_id)
            
            # Get material engagement
            material_stats = await self._get_student_material_stats(student_id)
            
            # Get activity patterns
            activity_stats = await self._get_student_activity_stats(student_id)
            
            # Calculate overall performance metrics
            performance_metrics = await self._calculate_performance_metrics(student_id)
            
            # Get learning streaks
            learning_streak = await self._calculate_learning_streak(student_id)
            
            # Get achievement progress
            achievements = await self._get_student_achievements(student_id)
            
            return {
                'student_info': {
                    'id': student['id'],
                    'name': student['name'],
                    'section': student['section'],
                    'registration_date': student['registration_date'],
                    'days_since_registration': (datetime.now() - student['registration_date']).days
                },
                'quiz_performance': quiz_stats,
                'material_engagement': material_stats,
                'activity_patterns': activity_stats,
                'performance_metrics': performance_metrics,
                'learning_streak': learning_streak,
                'achievements': achievements,
                'progress_summary': {
                    'overall_score': performance_metrics.get('overall_score', 0),
                    'improvement_trend': performance_metrics.get('improvement_trend', 'stable'),
                    'activity_level': activity_stats.get('activity_level', 'low'),
                    'recommendations': await self._generate_recommendations(student_id)
                }
            }
            
        except Exception as e:
            logger.error(f"Error getting student progress: {e}")
            return {}

    async def get_section_analytics(self, section: str, date_range: Optional[int] = 30) -> Dict[str, Any]:
        """Get analytics for a specific section"""
        try:
            end_date = datetime.now()
            start_date = end_date - timedelta(days=date_range)
            
            # Get section students
            students = await self.db.get_students_by_section(section)
            student_ids = [s['id'] for s in students]
            
            if not student_ids:
                return {'error': 'No students found in section'}
            
            # Section performance metrics
            section_metrics = await self._calculate_section_metrics(student_ids, start_date, end_date)
            
            # Quiz performance analysis
            quiz_analytics = await self._get_section_quiz_analytics(section, start_date, end_date)
            
            # Material engagement analysis
            material_analytics = await self._get_section_material_analytics(section, start_date, end_date)
            
            # Activity trends
            activity_trends = await self._get_section_activity_trends(student_ids, start_date, end_date)
            
            # Student rankings
            student_rankings = await self._get_section_student_rankings(student_ids)
            
            return {
                'section': section,
                'date_range': {
                    'start': start_date.isoformat(),
                    'end': end_date.isoformat(),
                    'days': date_range
                },
                'overview': {
                    'total_students': len(students),
                    'active_students': section_metrics.get('active_students', 0),
                    'average_score': section_metrics.get('average_score', 0),
                    'completion_rate': section_metrics.get('completion_rate', 0)
                },
                'quiz_analytics': quiz_analytics,
                'material_analytics': material_analytics,
                'activity_trends': activity_trends,
                'student_rankings': student_rankings,
                'insights': await self._generate_section_insights(section, section_metrics)
            }
            
        except Exception as e:
            logger.error(f"Error getting section analytics: {e}")
            return {}

    async def get_bot_statistics(self) -> Dict[str, Any]:
        """Get overall bot statistics"""
        try:
            # User statistics
            user_stats = await self.db.get_user_statistics()
            
            # Content statistics
            content_stats = await self.db.get_content_statistics()
            
            # Quiz statistics
            quiz_stats = await self.db.get_quiz_statistics()
            
            # Activity statistics
            activity_stats = await self._get_overall_activity_stats()
            
            # Performance trends
            performance_trends = await self._get_performance_trends()
            
            # System health metrics
            system_health = await self._get_system_health_metrics()
            
            return {
                'timestamp': datetime.now().isoformat(),
                'users': {
                    'total_registered': user_stats.get('total_users', 0),
                    'active_today': user_stats.get('active_today', 0),
                    'active_this_week': user_stats.get('active_this_week', 0),
                    'new_registrations_today': user_stats.get('new_today', 0),
                    'sections_distribution': user_stats.get('sections_distribution', {})
                },
                'content': {
                    'total_materials': content_stats.get('total_materials', 0),
                    'materials_published_today': content_stats.get('published_today', 0),
                    'total_file_size_mb': content_stats.get('total_file_size', 0) / (1024*1024),
                    'materials_by_subject': content_stats.get('by_subject', {})
                },
                'quizzes': {
                    'total_quizzes': quiz_stats.get('total_quizzes', 0),
                    'total_attempts': quiz_stats.get('total_attempts', 0),
                    'attempts_today': quiz_stats.get('attempts_today', 0),
                    'average_score': quiz_stats.get('average_score', 0),
                    'completion_rate': quiz_stats.get('completion_rate', 0)
                },
                'activity': activity_stats,
                'trends': performance_trends,
                'system_health': system_health
            }
            
        except Exception as e:
            logger.error(f"Error getting bot statistics: {e}")
            return {}

    async def get_realtime_dashboard_data(self) -> Dict[str, Any]:
        """Get real-time dashboard data"""
        try:
            now = datetime.now()
            
            # Current active users (last 5 minutes)
            active_users = await self.db.get_active_users_count(minutes=5)
            
            # Recent activities (last hour)
            recent_activities = await self.db.get_recent_activities(hours=1, limit=50)
            
            # Live quiz attempts
            live_quiz_attempts = await self.db.get_active_quiz_attempts()
            
            # Current system load
            system_metrics = await self._get_current_system_metrics()
            
            # Today's highlights
            daily_highlights = await self._get_daily_highlights()
            
            return {
                'timestamp': now.isoformat(),
                'live_metrics': {
                    'active_users_5min': active_users,
                    'quiz_attempts_active': len(live_quiz_attempts),
                    'system_load': system_metrics.get('load_percentage', 0),
                    'response_time_ms': system_metrics.get('avg_response_time', 0)
                },
                'recent_activities': [
                    {
                        'type': activity['activity_type'],
                        'student_name': activity.get('student_name', 'Unknown'),
                        'timestamp': activity['timestamp'].isoformat(),
                        'details': activity.get('metadata', {})
                    }
                    for activity in recent_activities
                ],
                'live_quizzes': [
                    {
                        'quiz_title': attempt['quiz_title'],
                        'student_name': attempt['student_name'],
                        'start_time': attempt['start_time'].isoformat(),
                        'progress': attempt.get('progress_percentage', 0)
                    }
                    for attempt in live_quiz_attempts
                ],
                'daily_highlights': daily_highlights,
                'alerts': await self._get_system_alerts()
            }
            
        except Exception as e:
            logger.error(f"Error getting realtime dashboard data: {e}")
            return {}

    async def generate_performance_report(self, section: Optional[str] = None, 
                                        date_range: int = 30) -> Dict[str, Any]:
        """Generate comprehensive performance report"""
        try:
            end_date = datetime.now()
            start_date = end_date - timedelta(days=date_range)
            
            # Base query filters
            filters = {'start_date': start_date, 'end_date': end_date}
            if section:
                filters['section'] = section
            
            # Executive summary
            executive_summary = await self._generate_executive_summary(filters)
            
            # Detailed analytics
            detailed_analytics = await self._generate_detailed_analytics(filters)
            
            # Student performance analysis
            student_analysis = await self._generate_student_performance_analysis(filters)
            
            # Content effectiveness analysis
            content_analysis = await self._generate_content_effectiveness_analysis(filters)
            
            # Recommendations
            recommendations = await self._generate_actionable_recommendations(filters)
            
            # Visual data for charts
            chart_data = await self._generate_chart_data(filters)
            
            return {
                'report_metadata': {
                    'generated_at': datetime.now().isoformat(),
                    'date_range': f"{start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}",
                    'section': section or 'All Sections',
                    'report_type': 'Performance Analysis'
                },
                'executive_summary': executive_summary,
                'detailed_analytics': detailed_analytics,
                'student_analysis': student_analysis,
                'content_analysis': content_analysis,
                'recommendations': recommendations,
                'chart_data': chart_data
            }
            
        except Exception as e:
            logger.error(f"Error generating performance report: {e}")
            return {}

    async def _get_student_quiz_stats(self, student_id: int) -> Dict[str, Any]:
        """Get quiz statistics for a student"""
        quiz_results = await self.db.get_student_quiz_results(student_id)
        
        if not quiz_results:
            return {
                'total_quizzes_taken': 0,
                'total_quizzes_passed': 0,
                'average_score': 0,
                'best_score': 0,
                'recent_scores': [],
                'subjects_performance': {}
            }
        
        # Calculate statistics
        total_taken = len(quiz_results)
        total_passed = sum(1 for result in quiz_results if result.get('passed', False))
        scores = [result.get('total_score', 0) for result in quiz_results]
        average_score = sum(scores) / len(scores) if scores else 0
        best_score = max(scores) if scores else 0
        recent_scores = scores[-10:]  # Last 10 scores
        
        # Performance by subject
        subjects_performance = {}
        for result in quiz_results:
            subject = result.get('subject', 'Unknown')
            if subject not in subjects_performance:
                subjects_performance[subject] = {'scores': [], 'count': 0}
            subjects_performance[subject]['scores'].append(result.get('total_score', 0))
            subjects_performance[subject]['count'] += 1
        
        # Calculate subject averages
        for subject, data in subjects_performance.items():
            data['average'] = sum(data['scores']) / len(data['scores']) if data['scores'] else 0
            data['best'] = max(data['scores']) if data['scores'] else 0
        
        return {
            'total_quizzes_taken': total_taken,
            'total_quizzes_passed': total_passed,
            'pass_rate': (total_passed / total_taken * 100) if total_taken > 0 else 0,
            'average_score': round(average_score, 2),
            'best_score': best_score,
            'recent_scores': recent_scores,
            'subjects_performance': subjects_performance,
            'improvement_trend': self._calculate_score_trend(scores)
        }

    async def _get_student_material_stats(self, student_id: int) -> Dict[str, Any]:
        """Get material engagement statistics for a student"""
        material_views = await self.db.get_student_material_views(student_id)
        
        if not material_views:
            return {
                'total_materials_viewed': 0,
                'unique_materials': 0,
                'total_view_time': 0,
                'subjects_engagement': {},
                'recent_activity': []
            }
        
        total_views = len(material_views)
        unique_materials = len(set(view['material_id'] for view in material_views))
        total_view_time = sum(view.get('view_duration', 0) for view in material_views)
        
        # Engagement by subject
        subjects_engagement = {}
        for view in material_views:
            subject = view.get('subject', 'Unknown')
            if subject not in subjects_engagement:
                subjects_engagement[subject] = {'views': 0, 'time': 0, 'materials': set()}
            subjects_engagement[subject]['views'] += 1
            subjects_engagement[subject]['time'] += view.get('view_duration', 0)
            subjects_engagement[subject]['materials'].add(view['material_id'])
        
        # Convert sets to counts
        for subject, data in subjects_engagement.items():
            data['unique_materials'] = len(data['materials'])
            del data['materials']
        
        recent_activity = material_views[-10:] if material_views else []
        
        return {
            'total_materials_viewed': total_views,
            'unique_materials': unique_materials,
            'total_view_time_minutes': round(total_view_time / 60, 2),
            'average_view_time_minutes': round((total_view_time / total_views) / 60, 2) if total_views > 0 else 0,
            'subjects_engagement': subjects_engagement,
            'recent_activity': recent_activity
        }

    async def _get_student_activity_stats(self, student_id: int, days: int = 30) -> Dict[str, Any]:
        """Get student activity statistics"""
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)
        
        activities = await self.db.get_student_activities(student_id, start_date, end_date)
        
        if not activities:
            return {
                'total_activities': 0,
                'active_days': 0,
                'activity_level': 'inactive',
                'peak_hours': [],
                'activity_types': {}
            }
        
        # Calculate active days
        active_dates = set(activity['timestamp'].date() for activity in activities)
        active_days = len(active_dates)
        
        # Activity level classification
        activity_level = 'low'
        if active_days >= 20:
            activity_level = 'high'
        elif active_days >= 10:
            activity_level = 'medium'
        
        # Peak hours analysis
        hours = [activity['timestamp'].hour for activity in activities]
        hour_counts = Counter(hours)
        peak_hours = [hour for hour, count in hour_counts.most_common(3)]
        
        # Activity types distribution
        activity_types = Counter(activity['activity_type'] for activity in activities)
        
        return {
            'total_activities': len(activities),
            'active_days': active_days,
            'activity_level': activity_level,
            'average_daily_activities': round(len(activities) / max(days, 1), 2),
            'peak_hours': peak_hours,
            'activity_types': dict(activity_types)
        }

    async def _calculate_performance_metrics(self, student_id: int) -> Dict[str, Any]:
        """Calculate overall performance metrics"""
        try:
            # Get recent quiz scores for trend analysis
            recent_scores = await self.db.get_student_recent_quiz_scores(student_id, limit=10)
            
            if len(recent_scores) < 2:
                return {
                    'overall_score': recent_scores[0] if recent_scores else 0,
                    'improvement_trend': 'insufficient_data',
                    'consistency_score': 0,
                    'performance_category': 'beginner'
                }
            
            # Calculate overall score (weighted average, recent scores have more weight)
            weights = [i + 1 for i in range(len(recent_scores))]
            weighted_sum = sum(score * weight for score, weight in zip(recent_scores, weights))
            weight_sum = sum(weights)
            overall_score = weighted_sum / weight_sum
            
            # Calculate improvement trend
            improvement_trend = self._calculate_score_trend(recent_scores)
            
            # Calculate consistency (standard deviation)
            if len(recent_scores) > 1:
                mean_score = sum(recent_scores) / len(recent_scores)
                variance = sum((score - mean_score) ** 2 for score in recent_scores) / len(recent_scores)
                std_dev = variance ** 0.5
                consistency_score = max(0, 100 - std_dev)  # Higher is more consistent
            else:
                consistency_score = 100
            
            # Performance category
            if overall_score >= 90:
                performance_category = 'excellent'
            elif overall_score >= 80:
                performance_category = 'good'
            elif overall_score >= 70:
                performance_category = 'average'
            elif overall_score >= 60:
                performance_category = 'below_average'
            else:
                performance_category = 'needs_improvement'
            
            return {
                'overall_score': round(overall_score, 2),
                'improvement_trend': improvement_trend,
                'consistency_score': round(consistency_score, 2),
                'performance_category': performance_category,
                'recent_scores_count': len(recent_scores)
            }
            
        except Exception as e:
            logger.error(f"Error calculating performance metrics: {e}")
            return {}

    def _calculate_score_trend(self, scores: List[float]) -> str:
        """Calculate trend from score list"""
        if len(scores) < 3:
            return 'insufficient_data'
        
        # Simple linear trend calculation
        recent_avg = sum(scores[-3:]) / 3
        older_avg = sum(scores[:-3]) / len(scores[:-3]) if len(scores) > 3 else sum(scores[:3]) / 3
        
        diff = recent_avg - older_avg
        
        if diff > 5:
            return 'improving'
        elif diff < -5:
            return 'declining'
        else:
            return 'stable'

    async def _calculate_learning_streak(self, student_id: int) -> Dict[str, Any]:
        """Calculate learning streak for student"""
        try:
            # Get recent activity dates
            activities = await self.db.get_student_recent_activities(student_id, days=60)
            
            if not activities:
                return {'current_streak': 0, 'longest_streak': 0, 'last_activity': None}
            
            # Extract unique activity dates
            activity_dates = sorted(set(
                activity['timestamp'].date() for activity in activities
            ), reverse=True)
            
            # Calculate current streak
            current_streak = 0
            today = datetime.now().date()
            
            for i, date in enumerate(activity_dates):
                expected_date = today - timedelta(days=i)
                if date == expected_date or (i == 0 and date == today - timedelta(days=1)):
                    current_streak += 1
                else:
                    break
            
            # Calculate longest streak
            longest_streak = 0
            temp_streak = 1
            
            for i in range(1, len(activity_dates)):
                if activity_dates[i-1] - activity_dates[i] == timedelta(days=1):
                    temp_streak += 1
                    longest_streak = max(longest_streak, temp_streak)
                else:
                    temp_streak = 1
            
            return {
                'current_streak': current_streak,
                'longest_streak': max(longest_streak, current_streak),
                'last_activity': activity_dates[0].isoformat() if activity_dates else None
            }
            
        except Exception as e:
            logger.error(f"Error calculating learning streak: {e}")
            return {'current_streak': 0, 'longest_streak': 0, 'last_activity': None}

    async def _get_student_achievements(self, student_id: int) -> List[Dict[str, Any]]:
        """Get student achievements and badges"""
        try:
            achievements = []
            
            # Quiz-based achievements
            quiz_stats = await self._get_student_quiz_stats(student_id)
            
            if quiz_stats['total_quizzes_taken'] >= 10:
                achievements.append({
                    'title': 'Quiz Master',
                    'description': 'Completed 10+ quizzes',
                    'type': 'quiz',
                    'earned_date': datetime.now().isoformat()
                })
            
            if quiz_stats['average_score'] >= 90:
                achievements.append({
                    'title': 'Excellence',
                    'description': 'Maintained 90%+ average score',
                    'type': 'performance',
                    'earned_date': datetime.now().isoformat()
                })
            
            # Streak-based achievements
            streak_data = await self._calculate_learning_streak(student_id)
            
            if streak_data['current_streak'] >= 7:
                achievements.append({
                    'title': 'Week Warrior',
                    'description': '7-day learning streak',
                    'type': 'consistency',
                    'earned_date': datetime.now().isoformat()
                })
            
            return achievements
            
        except Exception as e:
            logger.error(f"Error getting student achievements: {e}")
            return []

    async def _generate_recommendations(self, student_id: int) -> List[str]:
        """Generate personalized recommendations for student"""
        try:
            recommendations = []
            
            # Get student data
            quiz_stats = await self._get_student_quiz_stats(student_id)
            material_stats = await self._get_student_material_stats(student_id)
            activity_stats = await self._get_student_activity_stats(student_id)
            
            # Performance-based recommendations
            if quiz_stats['average_score'] < 70:
                recommendations.append("راجع المواد الدراسية قبل حل الاختبارات لتحسين درجاتك")
            
            if quiz_stats.get('improvement_trend') == 'declining':
                recommendations.append("درجاتك في تراجع - حاول التركيز أكثر على المواضيع الصعبة")
            
            # Activity-based recommendations
            if activity_stats['activity_level'] == 'low':
                recommendations.append("حاول زيادة نشاطك اليومي على المنصة لتحقيق أفضل النتائج")
            
            if material_stats['total_materials_viewed'] < 5:
                recommendations.append("استكشف المزيد من المواد التعليمية المتاحة")
            
            # Subject-specific recommendations
            subjects_performance = quiz_stats.get('subjects_performance', {})
            weak_subjects = [
                subject for subject, data in subjects_performance.items() 
                if data['average'] < 70
            ]
            
            if weak_subjects:
                recommendations.append(f"ركز على تحسين أدائك في: {', '.join(weak_subjects)}")
            
            # Default encouragement
            if not recommendations:
                recommendations.append("أداؤك جيد! استمر في التعلم وحل الاختبارات")
            
            return recommendations[:5]  # Limit to 5 recommendations
            
        except Exception as e:
            logger.error(f"Error generating recommendations: {e}")
            return ["استمر في التعلم والممارسة!"]

    async def _flush_activity_buffer(self):
        """Production-optimized activity buffer flush with error handling"""
        # Use lock to prevent concurrent flushes that could cause data loss
        async with self._flush_lock:
            if not self.activity_buffer:
                return
            
            buffer_copy = self.activity_buffer.copy()
            buffer_size = len(buffer_copy)
            
            try:
                activities_data = []
                for activity in buffer_copy:
                    activities_data.append({
                        'student_id': activity.student_id,
                        'activity_type': activity.activity_type,
                        'timestamp': activity.timestamp,
                        'metadata': json.dumps(activity.metadata),
                        'session_id': activity.session_id
                    })
                
                # Use circuit breaker for database operations if available
                try:
                    from utils.circuit_breaker import with_database_circuit_breaker
                    
                    @with_database_circuit_breaker
                    async def flush_to_db():
                        return await self.db.bulk_insert_activities(activities_data)
                    
                    await flush_to_db()
                except ImportError:
                    # Direct database call if circuit breaker not available
                    await self.db.bulk_insert_activities(activities_data)
                
                # Only clear buffer after successful database write
                self.activity_buffer = self.activity_buffer[buffer_size:]
                
                logger.info(f"Successfully flushed {buffer_size} activities to database")
            
            except Exception as e:
                logger.error(f"Error flushing activity buffer: {e}")
                # Keep failed items in buffer for retry, but limit buffer size
                if len(self.activity_buffer) > self.max_buffer_size:
                    # Drop oldest items if buffer is too large to prevent memory issues
                    overflow = len(self.activity_buffer) - self.buffer_size
                    self.activity_buffer = self.activity_buffer[overflow:]
                    logger.warning(f"Dropped {overflow} old activities due to persistent flush failures")

    async def _notify_realtime_subscribers(self, activity: StudentActivity):
        """Notify real-time dashboard subscribers"""
        if not self.realtime_subscribers:
            return
        
        try:
            # Prepare real-time event data
            event_data = {
                'type': 'student_activity',
                'data': {
                    'student_id': activity.student_id,
                    'activity_type': activity.activity_type,
                    'timestamp': activity.timestamp.isoformat(),
                    'metadata': activity.metadata
                }
            }
            
            # Send to all subscribers (WebSocket implementation would go here)
            # For now, we'll just log it
            logger.info(f"Real-time event: {event_data}")
            
        except Exception as e:
            logger.error(f"Error notifying real-time subscribers: {e}")

    async def _get_daily_highlights(self) -> Dict[str, Any]:
        """Get today's highlights for dashboard"""
        today = datetime.now().date()
        
        try:
            return {
                'new_registrations': await self.db.get_registrations_count(today),
                'quizzes_completed': await self.db.get_quizzes_completed_count(today),
                'materials_viewed': await self.db.get_materials_viewed_count(today),
                'active_students': await self.db.get_active_students_count(today),
                'top_performers': await self.db.get_top_performers(today, limit=5)
            }
        except Exception as e:
            logger.error(f"Error getting daily highlights: {e}")
            return {}

    async def _get_system_alerts(self) -> List[Dict[str, Any]]:
        """Get system alerts for dashboard"""
        alerts = []
        
        try:
            # Check for students with declining performance
            declining_students = await self.db.get_students_with_declining_performance()
            if declining_students:
                alerts.append({
                    'type': 'warning',
                    'title': 'Students with Declining Performance',
                    'message': f"{len(declining_students)} students showing performance decline",
                    'action': 'review_students'
                })
            
            # Check for inactive students
            inactive_students = await self.db.get_inactive_students(days=7)
            if len(inactive_students) > 10:
                alerts.append({
                    'type': 'info',
                    'title': 'Inactive Students',
                    'message': f"{len(inactive_students)} students inactive for 7+ days",
                    'action': 'send_reminders'
                })
            
            return alerts
            
        except Exception as e:
            logger.error(f"Error getting system alerts: {e}")
            return []

    async def cleanup_old_analytics_data(self, days_to_keep: int = 90):
        """Clean up old analytics data"""
        try:
            cutoff_date = datetime.now() - timedelta(days=days_to_keep)
            
            deleted_activities = await self.db.delete_activities_before_date(cutoff_date)
            deleted_sessions = await self.db.delete_sessions_before_date(cutoff_date)
            
            logger.info(f"Cleaned up {deleted_activities} activities and {deleted_sessions} sessions")
            
            return {
                'deleted_activities': deleted_activities,
                'deleted_sessions': deleted_sessions,
                'cutoff_date': cutoff_date.isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error cleaning up analytics data: {e}")
            return {'error': str(e)}