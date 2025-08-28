"""
Circuit Breaker Pattern Implementation for Production Scalability
Prevents cascading failures when database or external services fail
"""

import asyncio
import time
from enum import Enum
from typing import Callable, Any, Optional
import logging

logger = logging.getLogger(__name__)

class CircuitState(Enum):
    CLOSED = "CLOSED"
    OPEN = "OPEN"
    HALF_OPEN = "HALF_OPEN"

class CircuitBreakerError(Exception):
    """Raised when circuit breaker is open"""
    pass

class CircuitBreaker:
    """
    Circuit breaker to prevent cascading failures in production
    Critical for handling 7000+ concurrent users
    """
    
    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: int = 60,
        expected_exception: type = Exception,
        name: str = "CircuitBreaker"
    ):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.expected_exception = expected_exception
        self.name = name
        
        self.failure_count = 0
        self.last_failure_time = None
        self.state = CircuitState.CLOSED
        
    async def call(self, func: Callable, *args, **kwargs) -> Any:
        """Execute function with circuit breaker protection"""
        
        if self.state == CircuitState.OPEN:
            if self._should_attempt_reset():
                self.state = CircuitState.HALF_OPEN
                logger.info(f"Circuit breaker {self.name} attempting reset (HALF_OPEN)")
            else:
                raise CircuitBreakerError(f"Circuit breaker {self.name} is OPEN")
        
        try:
            result = await func(*args, **kwargs)
            self._on_success()
            return result
            
        except self.expected_exception as e:
            self._on_failure()
            raise e
    
    def _should_attempt_reset(self) -> bool:
        """Check if enough time has passed to attempt reset"""
        return (
            self.last_failure_time is not None and
            time.time() - self.last_failure_time >= self.recovery_timeout
        )
    
    def _on_success(self):
        """Reset circuit breaker on successful operation"""
        if self.state == CircuitState.HALF_OPEN:
            logger.info(f"Circuit breaker {self.name} reset to CLOSED")
        
        self.failure_count = 0
        self.state = CircuitState.CLOSED
        self.last_failure_time = None
    
    def _on_failure(self):
        """Handle failure and potentially open circuit"""
        self.failure_count += 1
        self.last_failure_time = time.time()
        
        if self.failure_count >= self.failure_threshold:
            self.state = CircuitState.OPEN
            logger.error(
                f"Circuit breaker {self.name} opened after {self.failure_count} failures"
            )

# Production-ready decorators for common operations
def with_database_circuit_breaker(func):
    """Decorator for database operations"""
    breaker = CircuitBreaker(
        failure_threshold=3,
        recovery_timeout=30,
        name=f"DB_{func.__name__}"
    )
    
    async def wrapper(*args, **kwargs):
        return await breaker.call(func, *args, **kwargs)
    
    return wrapper

def with_retry_and_circuit_breaker(
    max_retries: int = 3,
    backoff_factor: float = 2.0,
    circuit_breaker_threshold: int = 5
):
    """Combined retry and circuit breaker decorator"""
    
    def decorator(func):
        breaker = CircuitBreaker(
            failure_threshold=circuit_breaker_threshold,
            recovery_timeout=60,
            name=f"Retry_{func.__name__}"
        )
        
        async def wrapper(*args, **kwargs):
            last_exception = None
            
            for attempt in range(max_retries + 1):
                try:
                    return await breaker.call(func, *args, **kwargs)
                    
                except CircuitBreakerError:
                    # Circuit breaker is open, don't retry
                    raise
                    
                except Exception as e:
                    last_exception = e
                    if attempt < max_retries:
                        delay = backoff_factor ** attempt
                        logger.warning(
                            f"Attempt {attempt + 1} failed for {func.__name__}, "
                            f"retrying in {delay}s: {e}"
                        )
                        await asyncio.sleep(delay)
                    else:
                        logger.error(f"All {max_retries + 1} attempts failed for {func.__name__}")
            
            raise last_exception
        
        return wrapper
    return decorator