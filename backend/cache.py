import time
from typing import Any, Optional
from datetime import datetime, timedelta

class SmartCache:
    """In-memory cache with TTL support"""
    
    def __init__(self):
        self.cache = {}
        self.expiry = {}
    
    def set(self, key: str, value: Any, ttl_seconds: int = 300):
        """Set a cache entry with TTL (default 5 minutes)"""
        self.cache[key] = value
        self.expiry[key] = time.time() + ttl_seconds
    
    def get(self, key: str) -> Optional[Any]:
        """Get a cache entry if it exists and hasn't expired"""
        if key not in self.cache:
            return None
        
        # Check if expired
        if time.time() > self.expiry.get(key, 0):
            self.delete(key)
            return None
        
        return self.cache[key]
    
    def delete(self, key: str):
        """Delete a cache entry"""
        self.cache.pop(key, None)
        self.expiry.pop(key, None)
    
    def clear(self):
        """Clear all cache entries"""
        self.cache.clear()
        self.expiry.clear()
    
    def cleanup_expired(self):
        """Remove expired entries"""
        current_time = time.time()
        expired_keys = [
            key for key, expiry_time in self.expiry.items()
            if current_time > expiry_time
        ]
        for key in expired_keys:
            self.delete(key)
    
    def get_stats(self) -> dict:
        """Get cache statistics"""
        self.cleanup_expired()
        return {
            'total_entries': len(self.cache),
            'active_entries': len(self.cache),
            'memory_size_estimate': sum(
                len(str(k)) + len(str(v)) 
                for k, v in self.cache.items()
            )
        }

# Singleton instance
_cache_instance = None

def get_cache() -> SmartCache:
    """Get or create cache instance"""
    global _cache_instance
    if _cache_instance is None:
        _cache_instance = SmartCache()
    return _cache_instance