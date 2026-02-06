"""
Error recovery module with circuit breaker pattern, retry strategies, and fallback mechanisms.
"""

import asyncio
import random
import time
import logging
import json
from typing import Dict, List, Any, Optional, Callable, Union, Tuple, Awaitable
from dataclasses import dataclass, field
from enum import Enum
from collections import defaultdict, deque
import threading
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

class CircuitState(Enum):
    """Circuit breaker states."""
    CLOSED = "closed"      # Normal operation
    OPEN = "open"          # Failing, reject requests
    HALF_OPEN = "half_open"  # Testing if service recovered

@dataclass
class RetryConfig:
    """Configuration for retry strategies."""
    max_attempts: int = 3
    base_delay: float = 1.0
    max_delay: float = 60.0
    exponential_base: float = 2.0
    jitter: bool = True
    jitter_factor: float = 0.1

@dataclass
class CircuitBreakerConfig:
    """Configuration for circuit breaker."""
    failure_threshold: int = 5
    recovery_timeout: float = 60.0
    success_threshold: int = 3
    timeout: float = 30.0

@dataclass
class ErrorMetrics:
    """Error metrics for tracking patterns."""
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    error_types: Dict[str, int] = field(default_factory=dict)
    error_history: deque = field(default_factory=lambda: deque(maxlen=100))
    last_error_time: Optional[float] = None
    consecutive_failures: int = 0
    consecutive_successes: int = 0
    average_response_time: float = 0.0

class CircuitBreaker:
    """Circuit breaker implementation for external services."""
    
    def __init__(self, name: str, config: CircuitBreakerConfig):
        self.name = name
        self.config = config
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time = 0
        self.metrics = ErrorMetrics()
        self._lock = threading.Lock()
        self.request_queue: deque = deque()
        self.max_queue_size = 100
        self.queue_enabled = True
    
    async def call(self, func: Callable, *args, **kwargs) -> Any:
        """Execute function with circuit breaker protection."""
        with self._lock:
            if self.state == CircuitState.OPEN:
                # Check if we should queue the request
                if self.queue_enabled and len(self.request_queue) < self.max_queue_size:
                    logger.info(f"Queueing request for {self.name} (circuit is OPEN)")
                    return await self._queue_request(func, args, kwargs)
                
                if time.time() - self.last_failure_time < self.config.recovery_timeout:
                    raise CircuitBreakerOpenError(f"Circuit breaker {self.name} is OPEN")
                else:
                    self.state = CircuitState.HALF_OPEN
                    self.success_count = 0
                    logger.info(f"Circuit breaker {self.name} moved to HALF_OPEN")
        
        start_time = time.time()
        try:
            # Set timeout for the function call
            result = await asyncio.wait_for(
                func(*args, **kwargs),
                timeout=self.config.timeout
            )
            
            # Record success
            with self._lock:
                self.metrics.total_requests += 1
                self.metrics.successful_requests += 1
                self.metrics.consecutive_successes += 1
                self.metrics.consecutive_failures = 0
                # Update average response time
                response_time = time.time() - start_time
                self.metrics.average_response_time = (
                    (self.metrics.average_response_time * (self.metrics.total_requests - 1) + response_time) /
                    self.metrics.total_requests
                )
                self._on_success()
            
            # Process queued requests if circuit is now closed
            if self.state == CircuitState.CLOSED and self.request_queue:
                asyncio.create_task(self._process_queue())
            
            return result
            
        except Exception as e:
            # Record failure
            with self._lock:
                self.metrics.total_requests += 1
                self.metrics.failed_requests += 1
                self.metrics.consecutive_failures += 1
                self.metrics.consecutive_successes = 0
                error_type = type(e).__name__
                self.metrics.error_types[error_type] = self.metrics.error_types.get(error_type, 0) + 1
                self.metrics.error_history.append({
                    'timestamp': time.time(),
                    'error_type': error_type,
                    'error_message': str(e),
                    'duration': time.time() - start_time
                })
                self.metrics.last_error_time = time.time()
                self._on_failure()
            
            raise e
    
    async def _queue_request(self, func: Callable, args: Tuple, kwargs: Dict) -> Any:
        """Queue a request when circuit is open."""
        future = asyncio.Future()
        self.request_queue.append((func, args, kwargs, future))
        
        # Wait for the request to be processed or timeout
        try:
            return await asyncio.wait_for(future, timeout=self.config.recovery_timeout)
        except asyncio.TimeoutError:
            with self._lock:
                if future in [item[3] for item in self.request_queue]:
                    # Remove from queue if still there
                    self.request_queue = deque([item for item in self.request_queue if item[3] != future])
            raise CircuitBreakerOpenError(f"Request timed out waiting for circuit {self.name} to recover")
    
    async def _process_queue(self):
        """Process queued requests when circuit recovers."""
        while self.request_queue and self.state == CircuitState.CLOSED:
            func, args, kwargs, future = self.request_queue.popleft()
            try:
                result = await asyncio.wait_for(
                    func(*args, **kwargs),
                    timeout=self.config.timeout
                )
                if not future.done():
                    future.set_result(result)
            except Exception as e:
                if not future.done():
                    future.set_exception(e)
    
    def enable_queue(self):
        """Enable request queuing."""
        with self._lock:
            self.queue_enabled = True
    
    def disable_queue(self):
        """Disable request queuing and clear existing queue."""
        with self._lock:
            self.queue_enabled = False
            # Fail all queued requests
            while self.request_queue:
                _, _, _, future = self.request_queue.popleft()
                if not future.done():
                    future.set_exception(CircuitBreakerOpenError("Circuit breaker queue disabled"))
    
    def _on_success(self):
        """Handle successful request."""
        if self.state == CircuitState.HALF_OPEN:
            self.success_count += 1
            if self.success_count >= self.config.success_threshold:
                self.state = CircuitState.CLOSED
                self.failure_count = 0
                logger.info(f"Circuit breaker {self.name} moved to CLOSED")
        elif self.state == CircuitState.CLOSED:
            self.failure_count = max(0, self.failure_count - 1)
    
    def _on_failure(self):
        """Handle failed request."""
        self.failure_count += 1
        self.last_failure_time = time.time()
        
        if self.state == CircuitState.HALF_OPEN:
            self.state = CircuitState.OPEN
            logger.warning(f"Circuit breaker {self.name} moved to OPEN from HALF_OPEN")
        elif self.state == CircuitState.CLOSED:
            if self.failure_count >= self.config.failure_threshold:
                self.state = CircuitState.OPEN
                logger.warning(f"Circuit breaker {self.name} moved to OPEN")
    
    def get_state(self) -> Dict[str, Any]:
        """Get current circuit breaker state."""
        with self._lock:
            return {
                'name': self.name,
                'state': self.state.value,
                'failure_count': self.failure_count,
                'success_count': self.success_count,
                'last_failure_time': self.last_failure_time,
                'metrics': {
                    'total_requests': self.metrics.total_requests,
                    'success_rate': (
                        self.metrics.successful_requests / self.metrics.total_requests
                        if self.metrics.total_requests > 0 else 0
                    ),
                    'error_types': dict(self.metrics.error_types),
                    'recent_errors': list(self.metrics.error_history)[-5:]
                }
            }

class RetryManager:
    """Manages retry strategies with exponential backoff and jitter."""
    
    def __init__(self, config: RetryConfig):
        self.config = config
    
    async def execute_with_retry(
        self,
        func: Callable,
        *args,
        retry_on: Optional[List[Exception]] = None,
        **kwargs
    ) -> Any:
        """Execute function with retry logic."""
        if retry_on is None:
            retry_on = [Exception]
        
        last_exception = None
        
        for attempt in range(self.config.max_attempts):
            try:
                return await func(*args, **kwargs)
            except Exception as e:
                last_exception = e
                
                # Check if we should retry on this exception
                if not any(isinstance(e, exc_type) for exc_type in retry_on):
                    raise e
                
                if attempt < self.config.max_attempts - 1:
                    delay = self._calculate_delay(attempt)
                    logger.warning(
                        f"Attempt {attempt + 1} failed: {str(e)}. "
                        f"Retrying in {delay:.2f} seconds..."
                    )
                    await asyncio.sleep(delay)
        
        logger.error(f"All {self.config.max_attempts} attempts failed")
        raise last_exception
    
    def _calculate_delay(self, attempt: int) -> float:
        """Calculate delay with exponential backoff and jitter."""
        delay = self.config.base_delay * (self.config.exponential_base ** attempt)
        delay = min(delay, self.config.max_delay)
        
        if self.config.jitter:
            jitter_amount = delay * self.config.jitter_factor
            delay += random.uniform(-jitter_amount, jitter_amount)
        
        return max(0, delay)

class FallbackManager:
    """Manages fallback mechanisms for critical failures."""
    
    def __init__(self):
        self.fallbacks: Dict[str, List[Callable]] = defaultdict(list)
    
    def register_fallback(self, service_name: str, fallback_func: Callable, priority: int = 0):
        """Register a fallback function for a service."""
        self.fallbacks[service_name].append((priority, fallback_func))
        # Sort by priority (higher priority first)
        self.fallbacks[service_name].sort(key=lambda x: x[0], reverse=True)
    
    async def execute_with_fallback(
        self,
        service_name: str,
        primary_func: Callable,
        *args,
        **kwargs
    ) -> Any:
        """Execute primary function with fallbacks."""
        try:
            return await primary_func(*args, **kwargs)
        except Exception as e:
            logger.warning(f"Primary function for {service_name} failed: {str(e)}")
            
            # Try fallbacks in order of priority
            for priority, fallback_func in self.fallbacks[service_name]:
                try:
                    logger.info(f"Trying fallback for {service_name} (priority: {priority})")
                    return await fallback_func(*args, **kwargs)
                except Exception as fallback_error:
                    logger.warning(f"Fallback for {service_name} failed: {str(fallback_error)}")
                    continue
            
            # All fallbacks failed
            raise FallbackExhaustedError(
                f"All fallbacks exhausted for {service_name}. "
                f"Original error: {str(e)}"
            )

class ErrorRecoveryManager:
    """Main error recovery manager that coordinates all recovery mechanisms."""
    
    def __init__(self):
        self.circuit_breakers: Dict[str, CircuitBreaker] = {}
        self.retry_managers: Dict[str, RetryManager] = {}
        self.fallback_manager = FallbackManager()
        self.error_patterns: Dict[str, Dict] = defaultdict(lambda: defaultdict(int))
        self.adaptive_strategies: Dict[str, Dict] = {}
        self._lock = threading.Lock()
        self.checkpoints: Dict[str, Dict] = {}
        self.recovery_history: List[Dict] = []
        self.health_checks: Dict[str, Callable] = {}
        self.degraded_mode = False
        self.partial_responses: Dict[str, Any] = {}
    
    def get_circuit_breaker(
        self,
        name: str,
        config: Optional[CircuitBreakerConfig] = None
    ) -> CircuitBreaker:
        """Get or create a circuit breaker for a service."""
        with self._lock:
            if name not in self.circuit_breakers:
                self.circuit_breakers[name] = CircuitBreaker(
                    name,
                    config or CircuitBreakerConfig()
                )
            return self.circuit_breakers[name]
    
    def get_retry_manager(
        self,
        name: str,
        config: Optional[RetryConfig] = None
    ) -> RetryManager:
        """Get or create a retry manager for a service."""
        with self._lock:
            if name not in self.retry_managers:
                self.retry_managers[name] = RetryManager(
                    config or RetryConfig()
                )
            return self.retry_managers[name]
    
    async def execute_with_recovery(
        self,
        service_name: str,
        func: Callable,
        *args,
        circuit_breaker_config: Optional[CircuitBreakerConfig] = None,
        retry_config: Optional[RetryConfig] = None,
        use_fallback: bool = True,
        **kwargs
    ) -> Any:
        """Execute function with full error recovery."""
        circuit_breaker = self.get_circuit_breaker(service_name, circuit_breaker_config)
        retry_manager = self.get_retry_manager(service_name, retry_config)
        
        if use_fallback:
            return await circuit_breaker.call(
                self.fallback_manager.execute_with_fallback,
                service_name,
                retry_manager.execute_with_retry,
                func,
                *args,
                **kwargs
            )
        else:
            return await circuit_breaker.call(
                retry_manager.execute_with_retry,
                func,
                *args,
                **kwargs
            )
    
    def register_fallback(self, service_name: str, fallback_func: Callable, priority: int = 0):
        """Register a fallback function."""
        self.fallback_manager.register_fallback(service_name, fallback_func, priority)
    
    def track_error_pattern(self, service_name: str, error_type: str, context: Dict[str, Any]):
        """Track error patterns for adaptive strategies."""
        with self._lock:
            self.error_patterns[service_name][error_type] += 1
            
            # Update adaptive strategies based on patterns
            if service_name not in self.adaptive_strategies:
                self.adaptive_strategies[service_name] = {}
            
            # Example: Increase retry attempts for frequent errors
            if self.error_patterns[service_name][error_type] > 5:
                current_config = self.retry_managers.get(service_name)
                if current_config:
                    new_config = RetryConfig(
                        max_attempts=min(current_config.config.max_attempts + 1, 10),
                        base_delay=current_config.config.base_delay,
                        max_delay=current_config.config.max_delay,
                        exponential_base=current_config.config.exponential_base,
                        jitter=current_config.config.jitter,
                        jitter_factor=current_config.config.jitter_factor
                    )
                    self.retry_managers[service_name] = RetryManager(new_config)
                    logger.info(f"Adapted retry strategy for {service_name} due to {error_type}")
    
    def register_health_check(self, service_name: str, check_func: Callable[[], Awaitable[bool]]):
        """Register a health check function for a service."""
        with self._lock:
            self.health_checks[service_name] = check_func
    
    async def check_service_health(self, service_name: str) -> bool:
        """Check if a service is healthy."""
        check_func = self.health_checks.get(service_name)
        if check_func:
            try:
                return await check_func()
            except Exception as e:
                logger.error(f"Health check failed for {service_name}: {e}")
                return False
        
        # Default to checking circuit breaker state
        breaker = self.circuit_breakers.get(service_name)
        if breaker:
            return breaker.state != CircuitState.OPEN
        return True
    
    async def check_all_services(self) -> Dict[str, bool]:
        """Check health of all registered services."""
        results = {}
        for service_name in self.circuit_breakers:
            results[service_name] = await self.check_service_health(service_name)
        return results
    
    def create_checkpoint(self, operation_id: str, data: Dict[str, Any]):
        """Create a recovery checkpoint for a long-running operation."""
        with self._lock:
            self.checkpoints[operation_id] = {
                'data': data,
                'timestamp': time.time(),
                'status': 'active'
            }
            logger.info(f"Created checkpoint for operation {operation_id}")
    
    def get_checkpoint(self, operation_id: str) -> Optional[Dict[str, Any]]:
        """Get a recovery checkpoint."""
        with self._lock:
            return self.checkpoints.get(operation_id)
    
    def complete_checkpoint(self, operation_id: str):
        """Mark a checkpoint as completed."""
        with self._lock:
            if operation_id in self.checkpoints:
                self.checkpoints[operation_id]['status'] = 'completed'
                self.checkpoints[operation_id]['completed_at'] = time.time()
                logger.info(f"Completed checkpoint for operation {operation_id}")
    
    def fail_checkpoint(self, operation_id: str, error: str):
        """Mark a checkpoint as failed."""
        with self._lock:
            if operation_id in self.checkpoints:
                self.checkpoints[operation_id]['status'] = 'failed'
                self.checkpoints[operation_id]['error'] = error
                self.checkpoints[operation_id]['failed_at'] = time.time()
                logger.info(f"Failed checkpoint for operation {operation_id}: {error}")
    
    def cleanup_old_checkpoints(self, max_age: float = 3600):
        """Clean up old checkpoints."""
        with self._lock:
            current_time = time.time()
            to_remove = []
            for op_id, checkpoint in self.checkpoints.items():
                if current_time - checkpoint['timestamp'] > max_age:
                    to_remove.append(op_id)
            for op_id in to_remove:
                del self.checkpoints[op_id]
            logger.info(f"Cleaned up {len(to_remove)} old checkpoints")
    
    def set_degraded_mode(self, enabled: bool):
        """Enable or disable degraded mode."""
        with self._lock:
            self.degraded_mode = enabled
            logger.info(f"Degraded mode {'enabled' if enabled else 'disabled'}")
    
    def is_degraded_mode(self) -> bool:
        """Check if degraded mode is active."""
        with self._lock:
            return self.degraded_mode
    
    def store_partial_response(self, request_id: str, partial_data: Any):
        """Store partial response data for recovery."""
        with self._lock:
            self.partial_responses[request_id] = {
                'data': partial_data,
                'timestamp': time.time()
            }
    
    def get_partial_response(self, request_id: str) -> Optional[Any]:
        """Get partial response data."""
        with self._lock:
            partial = self.partial_responses.get(request_id)
            return partial['data'] if partial else None
    
    def clear_partial_response(self, request_id: str):
        """Clear partial response data."""
        with self._lock:
            if request_id in self.partial_responses:
                del self.partial_responses[request_id]
    
    def record_recovery(self, service_name: str, recovery_type: str, details: Dict[str, Any]):
        """Record a recovery event."""
        with self._lock:
            self.recovery_history.append({
                'timestamp': time.time(),
                'service': service_name,
                'type': recovery_type,
                'details': details
            })
            # Keep only last 100 recovery events
            if len(self.recovery_history) > 100:
                self.recovery_history = self.recovery_history[-100:]
    
    def get_recovery_history(self, limit: int = 20) -> List[Dict]:
        """Get recent recovery history."""
        with self._lock:
            return self.recovery_history[-limit:]
    
    def get_recovery_status(self) -> Dict[str, Any]:
        """Get comprehensive recovery status."""
        status = {
            'circuit_breakers': {},
            'error_patterns': dict(self.error_patterns),
            'adaptive_strategies': self.adaptive_strategies,
            'degraded_mode': self.degraded_mode,
            'active_checkpoints': len(self.checkpoints),
            'partial_responses': len(self.partial_responses),
            'recovery_history_count': len(self.recovery_history),
            'timestamp': time.time()
        }
        
        for name, breaker in self.circuit_breakers.items():
            status['circuit_breakers'][name] = breaker.get_state()
        
        return status
    
    async def perform_health_checks(self) -> Dict[str, Any]:
        """Perform health checks on all services and return results."""
        health_results = await self.check_all_services()
        
        # Determine overall system health
        all_healthy = all(health_results.values())
        
        # If not all healthy, consider degraded mode
        if not all_healthy and not self.degraded_mode:
            logger.warning("Some services are unhealthy, consider enabling degraded mode")
        
        return {
            'all_healthy': all_healthy,
            'services': health_results,
            'timestamp': time.time()
        }

class CircuitBreakerOpenError(Exception):
    """Raised when circuit breaker is open."""
    pass

class FallbackExhaustedError(Exception):
    """Raised when all fallbacks are exhausted."""
    pass

# Global error recovery manager instance
error_recovery_manager = ErrorRecoveryManager()

# Decorators for easy use
def with_error_recovery(
    service_name: str,
    circuit_breaker_config: Optional[CircuitBreakerConfig] = None,
    retry_config: Optional[RetryConfig] = None,
    use_fallback: bool = True
):
    """Decorator for adding error recovery to functions."""
    def decorator(func):
        async def wrapper(*args, **kwargs):
            return await error_recovery_manager.execute_with_recovery(
                service_name,
                func,
                *args,
                circuit_breaker_config=circuit_breaker_config,
                retry_config=retry_config,
                use_fallback=use_fallback,
                **kwargs
            )
        return wrapper
    return decorator

def register_fallback(service_name: str, priority: int = 0):
    """Decorator for registering fallback functions."""
    def decorator(func):
        error_recovery_manager.register_fallback(service_name, func, priority)
        return func
    return decorator