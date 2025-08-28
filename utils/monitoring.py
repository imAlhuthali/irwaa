"""
Production Monitoring and Metrics for Educational Telegram Bot
Critical for managing 7000+ concurrent users
"""

import time
import psutil
import asyncio
from typing import Dict, Any, Optional
from datetime import datetime, timedelta
import logging
import os
from prometheus_client import Counter, Histogram, Gauge, generate_latest, CONTENT_TYPE_LATEST
from fastapi import Response
from contextlib import asynccontextmanager

logger = logging.getLogger(__name__)

# Prometheus metrics for production monitoring
METRICS = {
    # Request metrics
    'requests_total': Counter(
        'telegram_requests_total', 
        'Total requests processed', 
        ['endpoint', 'status']
    ),
    'request_duration': Histogram(
        'telegram_request_duration_seconds',
        'Request processing time',
        ['endpoint']
    ),
    
    # Database metrics
    'db_operations_total': Counter(
        'database_operations_total',
        'Database operations count',
        ['operation', 'table', 'status']
    ),
    'db_query_duration': Histogram(
        'database_query_duration_seconds',
        'Database query execution time',
        ['operation', 'table']
    ),
    'db_connections_active': Gauge(
        'database_connections_active',
        'Active database connections'
    ),
    'db_connections_max': Gauge(
        'database_connections_max',
        'Maximum database connections'
    ),
    
    # User metrics
    'active_users': Gauge(
        'active_users_current',
        'Currently active users'
    ),
    'users_total': Gauge(
        'users_total',
        'Total registered users'
    ),
    'messages_processed': Counter(
        'telegram_messages_processed_total',
        'Total messages processed',
        ['message_type', 'status']
    ),
    
    # System metrics
    'memory_usage': Gauge(
        'system_memory_usage_bytes',
        'Memory usage in bytes'
    ),
    'cpu_usage': Gauge(
        'system_cpu_usage_percent',
        'CPU usage percentage'
    ),
    
    # Cache metrics
    'cache_hits_total': Counter(
        'cache_hits_total',
        'Cache hits',
        ['cache_type']
    ),
    'cache_misses_total': Counter(
        'cache_misses_total', 
        'Cache misses',
        ['cache_type']
    ),
    
    # Error metrics
    'errors_total': Counter(
        'errors_total',
        'Total errors',
        ['error_type', 'component']
    ),
    'circuit_breaker_state': Gauge(
        'circuit_breaker_state',
        'Circuit breaker state (0=closed, 1=open, 2=half-open)',
        ['breaker_name']
    )
}

class PerformanceMonitor:
    """
    Production performance monitoring
    Tracks system health and performance metrics
    """
    
    def __init__(self):
        self.start_time = time.time()
        self.enabled = os.getenv('MONITORING_ENABLED', 'true').lower() == 'true'
        
    async def update_system_metrics(self):
        """Update system resource metrics"""
        if not self.enabled:
            return
            
        try:
            # Memory metrics
            memory = psutil.virtual_memory()
            METRICS['memory_usage'].set(memory.used)
            
            # CPU metrics
            cpu_percent = psutil.cpu_percent(interval=1)
            METRICS['cpu_usage'].set(cpu_percent)
            
        except Exception as e:
            logger.warning(f"Error updating system metrics: {e}")
    
    async def update_database_metrics(self, db_manager):
        """Update database connection metrics"""
        if not self.enabled or not db_manager:
            return
            
        try:
            if hasattr(db_manager, 'pool') and db_manager.pool:
                METRICS['db_connections_active'].set(db_manager.pool.get_size())
                METRICS['db_connections_max'].set(db_manager.max_connections)
                
        except Exception as e:
            logger.warning(f"Error updating database metrics: {e}")
    
    async def update_user_metrics(self, db_manager):
        """Update user-related metrics"""
        if not self.enabled or not db_manager:
            return
            
        try:
            # Get active users count (last 5 minutes)
            five_minutes_ago = datetime.now() - timedelta(minutes=5)
            
            # This would be implemented with proper queries
            # active_count = await db_manager.count_active_users_since(five_minutes_ago)
            # total_count = await db_manager.count_total_users()
            
            # METRICS['active_users'].set(active_count)
            # METRICS['users_total'].set(total_count)
            
        except Exception as e:
            logger.warning(f"Error updating user metrics: {e}")

# Global monitor instance
performance_monitor = PerformanceMonitor()

# Context managers for tracking operations
@asynccontextmanager
async def track_request(endpoint: str):
    """Track request performance"""
    start_time = time.time()
    status = "success"
    
    try:
        yield
    except Exception as e:
        status = "error"
        METRICS['errors_total'].labels(
            error_type=type(e).__name__,
            component="request_handler"
        ).inc()
        raise
    finally:
        duration = time.time() - start_time
        METRICS['request_duration'].labels(endpoint=endpoint).observe(duration)
        METRICS['requests_total'].labels(endpoint=endpoint, status=status).inc()

@asynccontextmanager
async def track_database_operation(operation: str, table: str):
    """Track database operation performance"""
    start_time = time.time()
    status = "success"
    
    try:
        yield
    except Exception as e:
        status = "error"
        METRICS['errors_total'].labels(
            error_type=type(e).__name__,
            component="database"
        ).inc()
        raise
    finally:
        duration = time.time() - start_time
        METRICS['db_query_duration'].labels(operation=operation, table=table).observe(duration)
        METRICS['db_operations_total'].labels(operation=operation, table=table, status=status).inc()

# Decorators for easy metrics integration
def track_message_processing(message_type: str):
    """Decorator to track message processing"""
    def decorator(func):
        async def wrapper(*args, **kwargs):
            status = "success"
            try:
                result = await func(*args, **kwargs)
                return result
            except Exception as e:
                status = "error"
                METRICS['errors_total'].labels(
                    error_type=type(e).__name__,
                    component="message_handler"
                ).inc()
                raise
            finally:
                METRICS['messages_processed'].labels(
                    message_type=message_type,
                    status=status
                ).inc()
        
        return wrapper
    return decorator

def track_cache_operation(cache_type: str):
    """Track cache hit/miss rates"""
    def record_hit():
        METRICS['cache_hits_total'].labels(cache_type=cache_type).inc()
    
    def record_miss():
        METRICS['cache_misses_total'].labels(cache_type=cache_type).inc()
    
    return record_hit, record_miss

# Health check with detailed component status
async def comprehensive_health_check(bot_instance) -> Dict[str, Any]:
    """
    Comprehensive health check for production monitoring
    """
    health_status = {
        'healthy': True,
        'timestamp': datetime.now().isoformat(),
        'uptime_seconds': time.time() - performance_monitor.start_time,
        'components': {}
    }
    
    # Database health
    try:
        if bot_instance.db_manager:
            await bot_instance.db_manager.health_check()
            health_status['components']['database'] = {
                'status': 'healthy',
                'connections_active': getattr(bot_instance.db_manager, 'pool', {}).get_size() if hasattr(bot_instance.db_manager, 'pool') else 'unknown'
            }
        else:
            health_status['components']['database'] = {'status': 'not_initialized'}
            health_status['healthy'] = False
    except Exception as e:
        health_status['components']['database'] = {'status': 'unhealthy', 'error': str(e)}
        health_status['healthy'] = False
    
    # Cache health
    try:
        from utils.cache import cache_manager
        if cache_manager.enabled and cache_manager.redis_client:
            await cache_manager.redis_client.ping()
            health_status['components']['cache'] = {'status': 'healthy'}
        else:
            health_status['components']['cache'] = {'status': 'disabled'}
    except Exception as e:
        health_status['components']['cache'] = {'status': 'unhealthy', 'error': str(e)}
        # Cache failure is not critical
    
    # Telegram bot health
    try:
        if bot_instance.app and bot_instance.app.bot:
            # Test bot API connectivity
            me = await bot_instance.app.bot.get_me()
            health_status['components']['telegram'] = {
                'status': 'healthy',
                'bot_username': me.username
            }
        else:
            health_status['components']['telegram'] = {'status': 'not_initialized'}
            health_status['healthy'] = False
    except Exception as e:
        health_status['components']['telegram'] = {'status': 'unhealthy', 'error': str(e)}
        health_status['healthy'] = False
    
    # System resources
    try:
        memory = psutil.virtual_memory()
        cpu_percent = psutil.cpu_percent()
        
        # Alert if resources are critically low
        memory_critical = memory.percent > 90
        cpu_critical = cpu_percent > 90
        
        health_status['components']['system'] = {
            'status': 'critical' if (memory_critical or cpu_critical) else 'healthy',
            'memory_percent': memory.percent,
            'cpu_percent': cpu_percent,
            'warnings': []
        }
        
        if memory_critical:
            health_status['components']['system']['warnings'].append('High memory usage')
        if cpu_critical:
            health_status['components']['system']['warnings'].append('High CPU usage')
            
        if memory_critical or cpu_critical:
            health_status['healthy'] = False
            
    except Exception as e:
        health_status['components']['system'] = {'status': 'unknown', 'error': str(e)}
    
    return health_status

def get_metrics_response():
    """Generate Prometheus metrics response"""
    return Response(
        content=generate_latest(),
        media_type=CONTENT_TYPE_LATEST
    )

# Background task for periodic metrics updates
async def metrics_updater_task(bot_instance):
    """Background task to update metrics periodically"""
    if not performance_monitor.enabled:
        return
        
    logger.info("Starting metrics updater task")
    
    while True:
        try:
            await performance_monitor.update_system_metrics()
            await performance_monitor.update_database_metrics(bot_instance.db_manager)
            await performance_monitor.update_user_metrics(bot_instance.db_manager)
            
        except Exception as e:
            logger.error(f"Error updating metrics: {e}")
        
        await asyncio.sleep(30)  # Update every 30 seconds