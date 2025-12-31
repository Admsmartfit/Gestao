import time
import redis
from flask import current_app

class CircuitBreaker:
    """
    Implements Circuit Breaker pattern with 3 states:
    - CLOSED: Normal operation
    - OPEN: Blocked after multiple failures
    - HALF_OPEN: Testing recovery after timeout
    """
    
    STATES = ['CLOSED', 'OPEN', 'HALF_OPEN']
    THRESHOLD = 5
    TIMEOUT = 600 # 10 minutes in seconds

    @staticmethod
    def _get_redis():
        return redis.from_url(current_app.config.get('CELERY_BROKER_URL', 'redis://localhost:6379/0'))

    @staticmethod
    def get_state() -> str:
        """Retrieves current state from Redis, handling automatic transition to HALF_OPEN"""
        try:
            r = CircuitBreaker._get_redis()
            state = r.get('whatsapp:cb:state')
            
            if not state:
                return 'CLOSED'
            
            state = state.decode('utf-8')
            
            if state == 'OPEN':
                opened_at = r.get('whatsapp:cb:opened_at')
                if opened_at and (time.time() - float(opened_at)) >= CircuitBreaker.TIMEOUT:
                    # Transition to HALF_OPEN automatically after timeout
                    r.set('whatsapp:cb:state', 'HALF_OPEN')
                    return 'HALF_OPEN'
            
            return state
        except (redis.exceptions.ConnectionError, redis.exceptions.RedisError):
            current_app.logger.warning("Redis Unavailable: returning default CLOSED state for CircuitBreaker.")
            return 'CLOSED'

    @staticmethod
    def record_success():
        """Resets failures and returns state to CLOSED"""
        try:
            r = CircuitBreaker._get_redis()
            r.set('whatsapp:cb:state', 'CLOSED')
            r.delete('whatsapp:cb:failures')
            r.delete('whatsapp:cb:opened_at')
        except (redis.exceptions.ConnectionError, redis.exceptions.RedisError):
             current_app.logger.warning("Redis Unavailable: could not record success in CircuitBreaker.")

    @staticmethod
    def record_failure():
        """Increments failure count and opens circuit if threshold reached"""
        try:
            r = CircuitBreaker._get_redis()
            failures = r.incr('whatsapp:cb:failures')
            
            # Set expiry for failure counter if first failure
            if failures == 1:
                r.expire('whatsapp:cb:failures', 300) # 5 minutes TTL
                
            if failures >= CircuitBreaker.THRESHOLD:
                r.set('whatsapp:cb:state', 'OPEN')
                r.set('whatsapp:cb:opened_at', time.time())
                r.expire('whatsapp:cb:opened_at', CircuitBreaker.TIMEOUT + 60) # Buffer
                # Log critical event
                current_app.logger.critical("WhatsApp Circuit Breaker is now OPEN (Threshold reached).")
        except (redis.exceptions.ConnectionError, redis.exceptions.RedisError):
             current_app.logger.warning("Redis Unavailable: could not record failure in CircuitBreaker.")

    @staticmethod
    def should_attempt() -> bool:
        """Returns True if request should be attempted based on circuit state"""
        state = CircuitBreaker.get_state()
        if state == 'OPEN':
            return False
        return True
