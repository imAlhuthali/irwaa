"""
Production Configuration for Educational Telegram Bot
Optimized for 7000+ concurrent users over 2 years
"""

import os
from typing import Dict, Any

class ProductionConfig:
    """Production-optimized configuration settings"""
    
    # Environment
    ENVIRONMENT = "production"
    
    # Database Configuration - Critical for scalability
    DATABASE_CONFIG = {
        'min_connections': int(os.getenv('DB_MIN_CONNECTIONS', '10')),
        'max_connections': int(os.getenv('DB_MAX_CONNECTIONS', '50')),
        'connection_timeout': int(os.getenv('DB_CONNECTION_TIMEOUT', '30')),
        'command_timeout': int(os.getenv('DB_COMMAND_TIMEOUT', '60')),
        'pool_recycle': int(os.getenv('DB_POOL_RECYCLE', '3600')),  # 1 hour
    }
    
    # Redis Cache Configuration
    REDIS_CONFIG = {
        'enabled': os.getenv('REDIS_ENABLED', 'true').lower() == 'true',
        'url': os.getenv('REDIS_URL', 'redis://localhost:6379/0'),
        'max_connections': int(os.getenv('REDIS_MAX_CONNECTIONS', '20')),
        'default_ttl': int(os.getenv('CACHE_DEFAULT_TTL', '300')),  # 5 minutes
        'max_memory_policy': 'allkeys-lru',
    }
    
    # Analytics Buffer Configuration
    ANALYTICS_CONFIG = {
        'buffer_size': int(os.getenv('ANALYTICS_BUFFER_SIZE', '500')),
        'max_buffer_size': int(os.getenv('ANALYTICS_MAX_BUFFER_SIZE', '2000')),
        'flush_interval': int(os.getenv('ANALYTICS_FLUSH_INTERVAL', '60')),  # seconds
        'retention_days': int(os.getenv('ANALYTICS_RETENTION_DAYS', '365')),  # 1 year
    }
    
    # Rate Limiting - Protection against abuse
    RATE_LIMITING = {
        'enabled': True,
        'default_limits': ["100/minute", "2000/hour", "10000/day"],
        'webhook_limits': ["200/minute", "5000/hour"],
        'health_check_limits': ["50/minute"],
        'metrics_limits': ["30/minute"],
    }
    
    # File Handling Configuration
    FILE_CONFIG = {
        'max_file_size': int(os.getenv('MAX_FILE_SIZE', str(50 * 1024 * 1024))),  # 50MB
        'allowed_mime_types': {
            'application/pdf',
            'application/msword',
            'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
            'image/jpeg',
            'image/png',
            'audio/mpeg',
            'audio/mp4',
        },
        'max_concurrent_uploads': int(os.getenv('MAX_CONCURRENT_UPLOADS', '10')),
        'upload_timeout': int(os.getenv('UPLOAD_TIMEOUT', '300')),  # 5 minutes
    }
    
    # Performance Configuration
    PERFORMANCE_CONFIG = {
        'max_concurrent_operations': int(os.getenv('MAX_CONCURRENT_OPERATIONS', '100')),
        'request_timeout': int(os.getenv('REQUEST_TIMEOUT', '30')),
        'long_request_timeout': int(os.getenv('LONG_REQUEST_TIMEOUT', '120')),
        'max_retries': int(os.getenv('MAX_RETRIES', '3')),
        'backoff_factor': float(os.getenv('BACKOFF_FACTOR', '2.0')),
    }
    
    # Circuit Breaker Configuration
    CIRCUIT_BREAKER_CONFIG = {
        'database_failure_threshold': int(os.getenv('DB_CIRCUIT_BREAKER_THRESHOLD', '5')),
        'database_recovery_timeout': int(os.getenv('DB_CIRCUIT_BREAKER_TIMEOUT', '60')),
        'cache_failure_threshold': int(os.getenv('CACHE_CIRCUIT_BREAKER_THRESHOLD', '10')),
        'cache_recovery_timeout': int(os.getenv('CACHE_CIRCUIT_BREAKER_TIMEOUT', '30')),
    }
    
    # Monitoring Configuration
    MONITORING_CONFIG = {
        'enabled': os.getenv('MONITORING_ENABLED', 'true').lower() == 'true',
        'metrics_update_interval': int(os.getenv('METRICS_UPDATE_INTERVAL', '30')),
        'health_check_interval': int(os.getenv('HEALTH_CHECK_INTERVAL', '60')),
        'log_level': os.getenv('LOG_LEVEL', 'INFO'),
        'structured_logging': True,
    }
    
    # Security Configuration
    SECURITY_CONFIG = {
        'max_request_size': int(os.getenv('MAX_REQUEST_SIZE', str(100 * 1024 * 1024))),  # 100MB
        'request_id_header': 'X-Request-ID',
        'cors_enabled': False,  # Telegram bot doesn't need CORS
        'secure_headers': True,
    }
    
    # Telegram API Configuration
    TELEGRAM_CONFIG = {
        'api_timeout': int(os.getenv('TELEGRAM_API_TIMEOUT', '30')),
        'max_retries': int(os.getenv('TELEGRAM_MAX_RETRIES', '3')),
        'rate_limit_buffer': float(os.getenv('TELEGRAM_RATE_LIMIT_BUFFER', '0.1')),  # 10% buffer
    }
    
    # Cleanup and Maintenance
    MAINTENANCE_CONFIG = {
        'cleanup_interval_hours': int(os.getenv('CLEANUP_INTERVAL_HOURS', '24')),
        'old_sessions_cleanup_days': int(os.getenv('OLD_SESSIONS_CLEANUP_DAYS', '7')),
        'analytics_aggregation_interval': int(os.getenv('ANALYTICS_AGGREGATION_INTERVAL', '3600')),  # 1 hour
        'database_vacuum_interval': int(os.getenv('DATABASE_VACUUM_INTERVAL', '86400')),  # 24 hours
    }
    
    @classmethod
    def get_all_config(cls) -> Dict[str, Any]:
        """Get all configuration as a dictionary"""
        return {
            'database': cls.DATABASE_CONFIG,
            'redis': cls.REDIS_CONFIG,
            'analytics': cls.ANALYTICS_CONFIG,
            'rate_limiting': cls.RATE_LIMITING,
            'files': cls.FILE_CONFIG,
            'performance': cls.PERFORMANCE_CONFIG,
            'circuit_breaker': cls.CIRCUIT_BREAKER_CONFIG,
            'monitoring': cls.MONITORING_CONFIG,
            'security': cls.SECURITY_CONFIG,
            'telegram': cls.TELEGRAM_CONFIG,
            'maintenance': cls.MAINTENANCE_CONFIG,
        }
    
    @classmethod
    def validate_config(cls) -> Dict[str, Any]:
        """Validate configuration and return status"""
        issues = []
        warnings = []
        
        # Check database connections
        if cls.DATABASE_CONFIG['max_connections'] < 20:
            issues.append("Database max_connections too low for production (minimum 20 recommended)")
        
        if cls.DATABASE_CONFIG['max_connections'] < cls.DATABASE_CONFIG['min_connections']:
            issues.append("Database max_connections must be >= min_connections")
        
        # Check buffer sizes
        if cls.ANALYTICS_CONFIG['buffer_size'] < 100:
            warnings.append("Analytics buffer_size is quite low, may cause frequent DB writes")
        
        if cls.ANALYTICS_CONFIG['max_buffer_size'] < cls.ANALYTICS_CONFIG['buffer_size'] * 2:
            warnings.append("Analytics max_buffer_size should be at least 2x buffer_size")
        
        # Check file limits
        if cls.FILE_CONFIG['max_file_size'] > 100 * 1024 * 1024:  # 100MB
            warnings.append("Large max_file_size may impact performance")
        
        # Check performance settings
        if cls.PERFORMANCE_CONFIG['max_concurrent_operations'] < 50:
            warnings.append("Low max_concurrent_operations may bottleneck under high load")
        
        return {
            'valid': len(issues) == 0,
            'issues': issues,
            'warnings': warnings
        }

# Environment-specific configurations
ENVIRONMENT_CONFIGS = {
    'production': ProductionConfig,
    'staging': ProductionConfig,  # Use same config for staging
    'development': None,  # Use default config for development
}

def get_config():
    """Get configuration based on environment"""
    env = os.getenv('ENVIRONMENT', 'development')
    config_class = ENVIRONMENT_CONFIGS.get(env)
    
    if config_class:
        return config_class()
    else:
        # Return basic config for development
        return type('Config', (), {})()

# Configuration validation on import
if os.getenv('ENVIRONMENT') == 'production':
    validation_result = ProductionConfig.validate_config()
    if not validation_result['valid']:
        import logging
        logger = logging.getLogger(__name__)
        logger.error("❌ Production configuration validation failed:")
        for issue in validation_result['issues']:
            logger.error(f"  - {issue}")
        
        if validation_result['warnings']:
            logger.warning("⚠️ Production configuration warnings:")
            for warning in validation_result['warnings']:
                logger.warning(f"  - {warning}")
        
        raise ValueError("Invalid production configuration")