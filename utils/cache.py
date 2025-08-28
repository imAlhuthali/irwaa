"""
Redis Caching Layer for Production Scalability
Critical for handling 7000+ concurrent users efficiently
"""

import json
import pickle
import redis.asyncio as redis
from typing import Any, Optional, Union, Callable
import logging
import os
from functools import wraps
import hashlib

logger = logging.getLogger(__name__)

class CacheManager:
    """
    Production Redis cache manager
    Reduces database load for frequently accessed data
    """
    
    def __init__(self):
        self.redis_client: Optional[redis.Redis] = None
        self.enabled = os.getenv('REDIS_ENABLED', 'true').lower() == 'true'
        
        if self.enabled:
            self.redis_url = os.getenv('REDIS_URL', 'redis://localhost:6379/0')
            self.default_ttl = int(os.getenv('CACHE_DEFAULT_TTL', '300'))  # 5 minutes
        
    async def initialize(self):
        """Initialize Redis connection"""
        if not self.enabled:
            logger.info("Cache disabled, skipping Redis initialization")
            return
            
        try:
            # Check if Redis URL is available
            if not self.redis_url or self.redis_url == 'redis://localhost:6379/0':
                logger.warning("No Redis URL configured, disabling cache")
                self.enabled = False
                return
                
            self.redis_client = redis.from_url(
                self.redis_url,
                max_connections=20,
                retry_on_timeout=True,
                socket_keepalive=True,
                socket_keepalive_options={},
                socket_connect_timeout=5  # 5 second timeout
            )
            
            # Test connection
            await self.redis_client.ping()
            logger.info("✅ Redis cache connected successfully")
            
        except Exception as e:
            logger.warning(f"⚠️ Redis connection failed, cache disabled: {e}")
            self.enabled = False
            self.redis_client = None
    
    async def get(self, key: str) -> Optional[Any]:
        """Get value from cache"""
        if not self.enabled or not self.redis_client:
            return None
            
        try:
            cached_data = await self.redis_client.get(key)
            if cached_data:
                return pickle.loads(cached_data)
        except Exception as e:
            logger.warning(f"Cache GET error for key {key}: {e}")
        
        return None
    
    async def set(
        self, 
        key: str, 
        value: Any, 
        ttl: Optional[int] = None
    ) -> bool:
        """Set value in cache"""
        if not self.enabled or not self.redis_client:
            return False
            
        try:
            ttl = ttl or self.default_ttl
            serialized_value = pickle.dumps(value)
            await self.redis_client.setex(key, ttl, serialized_value)
            return True
        except Exception as e:
            logger.warning(f"Cache SET error for key {key}: {e}")
            return False
    
    async def delete(self, key: str) -> bool:
        """Delete key from cache"""
        if not self.enabled or not self.redis_client:
            return False
            
        try:
            await self.redis_client.delete(key)
            return True
        except Exception as e:
            logger.warning(f"Cache DELETE error for key {key}: {e}")
            return False
    
    async def clear_pattern(self, pattern: str) -> int:
        """Clear all keys matching pattern"""
        if not self.enabled or not self.redis_client:
            return 0
            
        try:
            keys = await self.redis_client.keys(pattern)
            if keys:
                return await self.redis_client.delete(*keys)
            return 0
        except Exception as e:
            logger.warning(f"Cache CLEAR PATTERN error for {pattern}: {e}")
            return 0
    
    async def close(self):
        """Close Redis connection"""
        if self.redis_client:
            await self.redis_client.aclose()

# Global cache instance
cache_manager = CacheManager()

def cache_key(*args, **kwargs) -> str:
    """Generate cache key from arguments"""
    key_data = f"{args}_{sorted(kwargs.items())}"
    return hashlib.md5(key_data.encode()).hexdigest()

def cached(ttl: int = 300, key_prefix: str = ""):
    """
    Decorator for caching function results
    Critical for reducing database load with 7000+ users
    """
    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Generate cache key
            func_key = f"{key_prefix}{func.__name__}_{cache_key(*args, **kwargs)}"
            
            # Try to get from cache
            cached_result = await cache_manager.get(func_key)
            if cached_result is not None:
                logger.debug(f"Cache HIT: {func_key}")
                return cached_result
            
            # Execute function and cache result
            logger.debug(f"Cache MISS: {func_key}")
            result = await func(*args, **kwargs)
            
            # Cache the result
            await cache_manager.set(func_key, result, ttl)
            
            return result
        
        return wrapper
    return decorator

# Specific cache decorators for common operations
def cache_student_data(ttl: int = 600):  # 10 minutes
    """Cache student data - frequently accessed"""
    return cached(ttl=ttl, key_prefix="student_")

def cache_materials(ttl: int = 1800):  # 30 minutes
    """Cache course materials - changes less frequently"""
    return cached(ttl=ttl, key_prefix="materials_")

def cache_quiz_data(ttl: int = 300):  # 5 minutes
    """Cache quiz data - moderate frequency"""
    return cached(ttl=ttl, key_prefix="quiz_")

def cache_analytics(ttl: int = 120):  # 2 minutes
    """Cache analytics data - changes frequently but expensive to compute"""
    return cached(ttl=ttl, key_prefix="analytics_")

# Cache invalidation helpers
async def invalidate_student_cache(student_id: int):
    """Invalidate all cache entries for a student"""
    pattern = f"student_*{student_id}*"
    cleared = await cache_manager.clear_pattern(pattern)
    logger.info(f"Invalidated {cleared} cache entries for student {student_id}")

async def invalidate_materials_cache(section: str = None, week: int = None):
    """Invalidate materials cache"""
    if section and week:
        pattern = f"materials_*{section}*{week}*"
    elif section:
        pattern = f"materials_*{section}*"
    else:
        pattern = "materials_*"
    
    cleared = await cache_manager.clear_pattern(pattern)
    logger.info(f"Invalidated {cleared} materials cache entries")

async def invalidate_quiz_cache(quiz_id: int = None):
    """Invalidate quiz cache"""
    pattern = f"quiz_*{quiz_id}*" if quiz_id else "quiz_*"
    cleared = await cache_manager.clear_pattern(pattern)
    logger.info(f"Invalidated {cleared} quiz cache entries")