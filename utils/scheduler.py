import logging
import asyncio
from datetime import datetime, timedelta, time
from typing import Dict, List, Optional, Callable, Any
from dataclasses import dataclass
from enum import Enum
import json

from models import get_database_manager
from services.content_service import ContentService
from services.quiz_service import QuizService
from services.analytics_service import AnalyticsService

logger = logging.getLogger(__name__)

class TaskFrequency(Enum):
    ONCE = "once"
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    CUSTOM = "custom"

@dataclass
class ScheduledTask:
    name: str
    func: Callable
    frequency: TaskFrequency
    next_run: datetime
    last_run: Optional[datetime] = None
    is_active: bool = True
    max_retries: int = 3
    retry_count: int = 0
    metadata: Dict[str, Any] = None

    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}

class TaskScheduler:
    """Scheduler for automated tasks and system maintenance"""
    
    def __init__(self, db_manager, content_service: ContentService,
                 quiz_service: QuizService, analytics_service: AnalyticsService):
        self.db = db_manager
        self.content_service = content_service
        self.quiz_service = quiz_service
        self.analytics_service = analytics_service
        
        self.tasks: Dict[str, ScheduledTask] = {}
        self.running = False
        self.scheduler_task: Optional[asyncio.Task] = None
        
        # Task execution tracking
        self.execution_history: List[Dict[str, Any]] = []
        self.max_history = 1000
        
    async def start(self):
        """Start the scheduler"""
        if self.running:
            logger.warning("Scheduler is already running")
            return
            
        logger.info("Starting task scheduler...")
        
        # Register default tasks
        await self._register_default_tasks()
        
        # Start scheduler loop
        self.running = True
        self.scheduler_task = asyncio.create_task(self._scheduler_loop())
        
        logger.info("Task scheduler started successfully")

    async def stop(self):
        """Stop the scheduler"""
        logger.info("Stopping task scheduler...")
        
        self.running = False
        
        if self.scheduler_task and not self.scheduler_task.done():
            self.scheduler_task.cancel()
            try:
                await self.scheduler_task
            except asyncio.CancelledError:
                pass
        
        logger.info("Task scheduler stopped")

    async def add_task(self, task: ScheduledTask):
        """Add a new scheduled task"""
        self.tasks[task.name] = task
        logger.info(f"Added scheduled task: {task.name}")

    async def remove_task(self, task_name: str):
        """Remove a scheduled task"""
        if task_name in self.tasks:
            del self.tasks[task_name]
            logger.info(f"Removed scheduled task: {task_name}")

    async def get_task_status(self) -> Dict[str, Any]:
        """Get scheduler status and task information"""
        return {
            'running': self.running,
            'total_tasks': len(self.tasks),
            'active_tasks': len([t for t in self.tasks.values() if t.is_active]),
            'tasks': {
                name: {
                    'frequency': task.frequency.value,
                    'next_run': task.next_run.isoformat(),
                    'last_run': task.last_run.isoformat() if task.last_run else None,
                    'is_active': task.is_active,
                    'retry_count': task.retry_count
                }
                for name, task in self.tasks.items()
            },
            'recent_executions': self.execution_history[-10:]
        }

    async def _scheduler_loop(self):
        """Main scheduler loop"""
        while self.running:
            try:
                current_time = datetime.now()
                
                # Check which tasks need to run
                tasks_to_run = []
                for task in self.tasks.values():
                    if (task.is_active and 
                        current_time >= task.next_run and
                        task.retry_count <= task.max_retries):
                        tasks_to_run.append(task)
                
                # Execute due tasks
                if tasks_to_run:
                    await self._execute_tasks(tasks_to_run)
                
                # Sleep for 60 seconds before next check
                await asyncio.sleep(60)
                
            except Exception as e:
                logger.error(f"Error in scheduler loop: {e}")
                await asyncio.sleep(60)

    async def _execute_tasks(self, tasks: List[ScheduledTask]):
        """Execute a list of tasks"""
        for task in tasks:
            try:
                start_time = datetime.now()
                logger.info(f"Executing scheduled task: {task.name}")
                
                # Execute the task
                result = await task.func()
                
                # Task completed successfully
                end_time = datetime.now()
                execution_time = (end_time - start_time).total_seconds()
                
                # Update task
                task.last_run = start_time
                task.next_run = self._calculate_next_run(task)
                task.retry_count = 0
                
                # Log execution
                execution_record = {
                    'task_name': task.name,
                    'start_time': start_time.isoformat(),
                    'end_time': end_time.isoformat(),
                    'execution_time_seconds': execution_time,
                    'status': 'success',
                    'result': result if isinstance(result, (dict, str, int)) else str(result)
                }
                
                self._add_execution_record(execution_record)
                logger.info(f"Task {task.name} completed successfully in {execution_time:.2f}s")
                
            except Exception as e:
                # Task failed
                task.retry_count += 1
                
                if task.retry_count <= task.max_retries:
                    # Schedule retry in 5 minutes
                    task.next_run = datetime.now() + timedelta(minutes=5)
                    logger.warning(f"Task {task.name} failed (attempt {task.retry_count}/{task.max_retries}): {e}")
                else:
                    # Max retries reached, schedule for next regular run
                    task.next_run = self._calculate_next_run(task)
                    task.retry_count = 0
                    logger.error(f"Task {task.name} failed after {task.max_retries} retries: {e}")
                
                # Log failed execution
                execution_record = {
                    'task_name': task.name,
                    'start_time': datetime.now().isoformat(),
                    'status': 'failed',
                    'error': str(e),
                    'retry_count': task.retry_count
                }
                
                self._add_execution_record(execution_record)

    def _calculate_next_run(self, task: ScheduledTask) -> datetime:
        """Calculate next run time for a task"""
        now = datetime.now()
        
        if task.frequency == TaskFrequency.ONCE:
            # One-time tasks don't get rescheduled
            return now + timedelta(days=365)  # Far in the future
            
        elif task.frequency == TaskFrequency.DAILY:
            return now + timedelta(days=1)
            
        elif task.frequency == TaskFrequency.WEEKLY:
            return now + timedelta(weeks=1)
            
        elif task.frequency == TaskFrequency.MONTHLY:
            # Add approximately one month
            if now.month == 12:
                next_month = now.replace(year=now.year + 1, month=1)
            else:
                next_month = now.replace(month=now.month + 1)
            return next_month
            
        else:  # CUSTOM
            # Custom frequency should be handled by the task itself
            custom_interval = task.metadata.get('interval_minutes', 60)
            return now + timedelta(minutes=custom_interval)

    def _add_execution_record(self, record: Dict[str, Any]):
        """Add execution record to history"""
        self.execution_history.append(record)
        
        # Keep history within limits
        if len(self.execution_history) > self.max_history:
            self.execution_history = self.execution_history[-self.max_history:]

    async def _register_default_tasks(self):
        """Register default system tasks"""
        # Daily cleanup tasks
        await self.add_task(ScheduledTask(
            name="daily_analytics_flush",
            func=self._flush_analytics_buffer,
            frequency=TaskFrequency.DAILY,
            next_run=self._get_next_daily_time(hour=1, minute=0)  # 1:00 AM
        ))
        
        await self.add_task(ScheduledTask(
            name="daily_inactive_user_cleanup",
            func=self._cleanup_inactive_users,
            frequency=TaskFrequency.DAILY,
            next_run=self._get_next_daily_time(hour=2, minute=0)  # 2:00 AM
        ))
        
        await self.add_task(ScheduledTask(
            name="daily_file_cleanup",
            func=self._cleanup_old_files,
            frequency=TaskFrequency.DAILY,
            next_run=self._get_next_daily_time(hour=3, minute=0)  # 3:00 AM
        ))
        
        # Weekly tasks
        await self.add_task(ScheduledTask(
            name="weekly_performance_report",
            func=self._generate_weekly_report,
            frequency=TaskFrequency.WEEKLY,
            next_run=self._get_next_weekly_time(weekday=6, hour=9)  # Sunday 9:00 AM
        ))
        
        await self.add_task(ScheduledTask(
            name="weekly_user_engagement_check",
            func=self._check_user_engagement,
            frequency=TaskFrequency.WEEKLY,
            next_run=self._get_next_weekly_time(weekday=0, hour=10)  # Monday 10:00 AM
        ))
        
        # Monthly tasks
        await self.add_task(ScheduledTask(
            name="monthly_analytics_archive",
            func=self._archive_old_analytics,
            frequency=TaskFrequency.MONTHLY,
            next_run=self._get_next_monthly_time(day=1, hour=4)  # 1st of month, 4:00 AM
        ))
        
        # Hourly tasks
        await self.add_task(ScheduledTask(
            name="hourly_system_health_check",
            func=self._system_health_check,
            frequency=TaskFrequency.CUSTOM,
            next_run=datetime.now() + timedelta(minutes=5),
            metadata={'interval_minutes': 60}  # Every hour
        ))
        
        # Real-time notification tasks
        await self.add_task(ScheduledTask(
            name="quiz_deadline_reminders",
            func=self._send_quiz_reminders,
            frequency=TaskFrequency.CUSTOM,
            next_run=datetime.now() + timedelta(minutes=10),
            metadata={'interval_minutes': 120}  # Every 2 hours
        ))

    def _get_next_daily_time(self, hour: int, minute: int = 0) -> datetime:
        """Get next occurrence of daily time"""
        now = datetime.now()
        target_time = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        
        if target_time <= now:
            target_time += timedelta(days=1)
        
        return target_time

    def _get_next_weekly_time(self, weekday: int, hour: int, minute: int = 0) -> datetime:
        """Get next occurrence of weekly time (weekday: 0=Monday, 6=Sunday)"""
        now = datetime.now()
        days_ahead = weekday - now.weekday()
        
        if days_ahead <= 0:  # Target day already happened this week
            days_ahead += 7
        
        target_date = now + timedelta(days=days_ahead)
        target_time = target_date.replace(hour=hour, minute=minute, second=0, microsecond=0)
        
        return target_time

    def _get_next_monthly_time(self, day: int, hour: int, minute: int = 0) -> datetime:
        """Get next occurrence of monthly time"""
        now = datetime.now()
        
        # Try current month first
        try:
            target_time = now.replace(day=day, hour=hour, minute=minute, second=0, microsecond=0)
            if target_time > now:
                return target_time
        except ValueError:
            pass  # Day doesn't exist in current month
        
        # Move to next month
        if now.month == 12:
            next_month = now.replace(year=now.year + 1, month=1, day=day, hour=hour, minute=minute, second=0, microsecond=0)
        else:
            try:
                next_month = now.replace(month=now.month + 1, day=day, hour=hour, minute=minute, second=0, microsecond=0)
            except ValueError:
                # Day doesn't exist in next month, use last day of month
                if now.month == 11:  # November -> December
                    next_month = now.replace(month=12, day=31, hour=hour, minute=minute, second=0, microsecond=0)
                else:
                    # Use a safe day and adjust
                    next_month = now.replace(month=now.month + 1, day=1, hour=hour, minute=minute, second=0, microsecond=0)
                    next_month = next_month.replace(day=min(day, 28))  # Safe day
        
        return next_month

    # Task implementations
    async def _flush_analytics_buffer(self) -> Dict[str, Any]:
        """Flush analytics buffer to database"""
        try:
            # Flush any pending activities
            await self.analytics_service._flush_activity_buffer()
            
            return {"status": "success", "message": "Analytics buffer flushed"}
        except Exception as e:
            logger.error(f"Error flushing analytics buffer: {e}")
            raise

    async def _cleanup_inactive_users(self) -> Dict[str, Any]:
        """Clean up inactive user sessions and data"""
        try:
            # Clean up old user sessions
            cutoff_date = datetime.now() - timedelta(days=30)
            deleted_sessions = await self.db.delete_expired_sessions(cutoff_date)
            
            # Clean up temporary user data
            deleted_temp_data = await self.db.cleanup_temp_user_data(days=7)
            
            return {
                "status": "success",
                "deleted_sessions": deleted_sessions,
                "deleted_temp_data": deleted_temp_data
            }
        except Exception as e:
            logger.error(f"Error cleaning up inactive users: {e}")
            raise

    async def _cleanup_old_files(self) -> Dict[str, Any]:
        """Clean up old uploaded files"""
        try:
            deleted_count = await self.content_service.cleanup_old_files(days_old=90)
            
            return {
                "status": "success",
                "deleted_files": deleted_count
            }
        except Exception as e:
            logger.error(f"Error cleaning up old files: {e}")
            raise

    async def _generate_weekly_report(self) -> Dict[str, Any]:
        """Generate and store weekly performance report"""
        try:
            # Generate reports for all sections
            sections = await self.db.get_all_sections()
            reports_generated = 0
            
            for section in sections:
                report = await self.analytics_service.generate_performance_report(
                    section=section, date_range=7
                )
                
                if report:
                    # Store report in database
                    await self.db.store_performance_report({
                        'section': section,
                        'report_type': 'weekly',
                        'data': json.dumps(report),
                        'generated_at': datetime.now()
                    })
                    reports_generated += 1
            
            return {
                "status": "success",
                "reports_generated": reports_generated
            }
        except Exception as e:
            logger.error(f"Error generating weekly report: {e}")
            raise

    async def _check_user_engagement(self) -> Dict[str, Any]:
        """Check user engagement and send notifications"""
        try:
            # Get inactive users (no activity in 3 days)
            inactive_users = await self.db.get_inactive_students(days=3)
            notifications_sent = 0
            
            for user in inactive_users:
                if user.get('notification_enabled', True):
                    # Send engagement notification (implement notification service)
                    # For now, just log it
                    logger.info(f"Would send engagement notification to user {user['id']}")
                    notifications_sent += 1
            
            return {
                "status": "success",
                "inactive_users_found": len(inactive_users),
                "notifications_sent": notifications_sent
            }
        except Exception as e:
            logger.error(f"Error checking user engagement: {e}")
            raise

    async def _archive_old_analytics(self) -> Dict[str, Any]:
        """Archive old analytics data"""
        try:
            archived_data = await self.analytics_service.cleanup_old_analytics_data(days_to_keep=90)
            
            return {
                "status": "success",
                **archived_data
            }
        except Exception as e:
            logger.error(f"Error archiving analytics: {e}")
            raise

    async def _system_health_check(self) -> Dict[str, Any]:
        """Perform system health check"""
        try:
            health_data = {
                "timestamp": datetime.now().isoformat(),
                "database_status": "unknown",
                "memory_usage": 0,
                "active_connections": 0
            }
            
            # Check database connection
            try:
                await self.db.health_check()
                health_data["database_status"] = "healthy"
            except Exception as e:
                health_data["database_status"] = f"error: {str(e)}"
            
            # Check active connections
            try:
                active_connections = await self.db.get_active_connections_count()
                health_data["active_connections"] = active_connections
            except Exception:
                health_data["active_connections"] = -1
            
            # Log critical issues
            if health_data["database_status"] != "healthy":
                logger.critical(f"Database health check failed: {health_data['database_status']}")
            
            return health_data
            
        except Exception as e:
            logger.error(f"Error in system health check: {e}")
            raise

    async def _send_quiz_reminders(self) -> Dict[str, Any]:
        """Send quiz deadline reminders"""
        try:
            # Get quizzes with upcoming deadlines (within 24 hours)
            upcoming_deadlines = await self.db.get_quizzes_with_deadlines(hours=24)
            reminders_sent = 0
            
            for quiz_deadline in upcoming_deadlines:
                # Get students who haven't completed the quiz
                incomplete_students = await self.db.get_students_without_quiz_completion(
                    quiz_deadline['quiz_id']
                )
                
                for student in incomplete_students:
                    if student.get('notification_enabled', True):
                        # Send reminder (implement notification service)
                        logger.info(f"Would send quiz reminder to student {student['id']} for quiz {quiz_deadline['quiz_id']}")
                        reminders_sent += 1
            
            return {
                "status": "success",
                "upcoming_deadlines": len(upcoming_deadlines),
                "reminders_sent": reminders_sent
            }
        except Exception as e:
            logger.error(f"Error sending quiz reminders: {e}")
            raise

    async def run_task_now(self, task_name: str) -> Dict[str, Any]:
        """Run a specific task immediately"""
        if task_name not in self.tasks:
            return {"status": "error", "message": f"Task '{task_name}' not found"}
        
        task = self.tasks[task_name]
        
        try:
            start_time = datetime.now()
            result = await task.func()
            end_time = datetime.now()
            
            execution_time = (end_time - start_time).total_seconds()
            
            # Update task
            task.last_run = start_time
            task.retry_count = 0
            
            return {
                "status": "success",
                "task_name": task_name,
                "execution_time_seconds": execution_time,
                "result": result
            }
            
        except Exception as e:
            logger.error(f"Error running task {task_name}: {e}")
            return {
                "status": "error",
                "task_name": task_name,
                "error": str(e)
            }

    async def get_execution_history(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Get task execution history"""
        return self.execution_history[-limit:] if self.execution_history else []