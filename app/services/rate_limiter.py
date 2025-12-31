import time
import redis
from flask import current_app

class RateLimiter:
    """
    Fixed window counter for rate limiting.
    Limit: 60 requests per minute.
    """
    LIMIT = 60
    
    @staticmethod
    def _get_redis():
        return redis.from_url(current_app.config.get('CELERY_BROKER_URL', 'redis://localhost:6379/0'))

    @staticmethod
    def check_limit():
        """
        Check if the request can proceed within the current minute window.
        Returns: (can_send, remaining_requests)
        """
        try:
            r = RateLimiter._get_redis()
            # Key based on current minute timestamp
            current_minute = int(time.time() / 60)
            key = f"whatsapp:ratelimit:minute:{current_minute}"
            
            count = r.get(key)
            if count is None:
                return True, RateLimiter.LIMIT
                
            count = int(count)
            if count >= RateLimiter.LIMIT:
                return False, 0
                
            return True, RateLimiter.LIMIT - count
        except (redis.exceptions.ConnectionError, redis.exceptions.RedisError):
            current_app.logger.warning("Redis Unavailable: RateLimiter allowing traffic by default.")
            return True, RateLimiter.LIMIT

    @staticmethod
    def increment():
        """Increments the current minute counter"""
        try:
            r = RateLimiter._get_redis()
            current_minute = int(time.time() / 60)
            key = f"whatsapp:ratelimit:minute:{current_minute}"
            
            r.incr(key)
            r.expire(key, 60) # Only needed for 1 minute
        except (redis.exceptions.ConnectionError, redis.exceptions.RedisError):
             current_app.logger.warning("Redis Unavailable: RateLimiter could not increment counter.")
