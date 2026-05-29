"""Caching layer for Content Machine.

Provides caching for expensive operations like DataForSEO API calls,
WordPress lookups, and content generation.
"""

from __future__ import annotations

import hashlib
import json
import pickle
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional
from datetime import datetime, timedelta

import diskcache as dc

from .config import load_settings


@dataclass
class CacheEntry:
    """Cache entry metadata."""
    key: str
    value: Any
    created_at: float
    expires_at: float
    hits: int = 0
    
    def is_expired(self) -> bool:
        """Check if cache entry has expired."""
        return time.time() > self.expires_at
    
    def touch(self) -> None:
        """Increment hit counter."""
        self.hits += 1


class CacheManager:
    """Multi-layer cache manager using diskcache.
    
    Provides:
    - Keyword data caching (DataForSEO results)
    - WordPress post caching
    - Content generation caching
    - Automatic TTL management
    """
    
    # Default TTLs in seconds
    DEFAULT_TTLS = {
        "keyword_data": 24 * 3600,      # 24 hours for keyword data
        "wordpress_post": 3600,          # 1 hour for WP posts
        "content_generated": 7 * 24 * 3600,  # 7 days for generated content
        "seo_audit": 3600,               # 1 hour for SEO audits
        "api_response": 300,             # 5 minutes for general API responses
    }
    
    def __init__(self, cache_dir: Optional[Path] = None):
        """Initialize cache manager.
        
        Args:
            cache_dir: Directory for cache storage (default: ~/.cache/content_machine)
        """
        if cache_dir is None:
            cache_dir = Path.home() / ".cache" / "content_machine"
        
        self.cache_dir = cache_dir
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        
        # Initialize diskcache
        self._cache = dc.Cache(str(self.cache_dir))
        
        # Stats tracking
        self._stats = {
            "hits": 0,
            "misses": 0,
            "sets": 0,
            "deletes": 0,
        }
    
    def _make_key(self, *parts: str) -> str:
        """Create a cache key from parts.
        
        Args:
            *parts: Key parts to hash
            
        Returns:
            Hashed key string
        """
        key_str = ":".join(str(p) for p in parts)
        return hashlib.sha256(key_str.encode()).hexdigest()[:32]
    
    def get(
        self,
        key: str,
        category: str = "default",
    ) -> Optional[Any]:
        """Get value from cache.
        
        Args:
            key: Cache key
            category: Cache category for namespacing
            
        Returns:
            Cached value or None if not found/expired
        """
        full_key = f"{category}:{key}"
        
        try:
            value = self._cache.get(full_key)
            if value is not None:
                self._stats["hits"] += 1
                return value
            self._stats["misses"] += 1
            return None
        except Exception:
            self._stats["misses"] += 1
            return None
    
    def set(
        self,
        key: str,
        value: Any,
        category: str = "default",
        ttl: Optional[int] = None,
    ) -> bool:
        """Set value in cache.
        
        Args:
            key: Cache key
            value: Value to cache
            category: Cache category
            ttl: Time to live in seconds (default: from DEFAULT_TTLS)
            
        Returns:
            True if successful
        """
        full_key = f"{category}:{key}"
        
        # Get default TTL for category
        if ttl is None:
            ttl = self.DEFAULT_TTLS.get(category, 3600)
        
        try:
            self._cache.set(full_key, value, expire=ttl)
            self._stats["sets"] += 1
            return True
        except Exception as e:
            print(f"Cache set error: {e}")
            return False
    
    def delete(self, key: str, category: str = "default") -> bool:
        """Delete value from cache.
        
        Args:
            key: Cache key
            category: Cache category
            
        Returns:
            True if deleted
        """
        full_key = f"{category}:{key}"
        
        try:
            result = self._cache.delete(full_key)
            if result:
                self._stats["deletes"] += 1
            return result
        except Exception:
            return False
    
    def get_keyword_data(
        self,
        keyword: str,
        location_code: str = "ZA",
        language_code: str = "en",
    ) -> Optional[dict]:
        """Get cached keyword data from DataForSEO.
        
        Args:
            keyword: Search keyword
            location_code: Location code (e.g., ZA, US)
            language_code: Language code (e.g., en, es)
            
        Returns:
            Cached keyword data or None
        """
        key = self._make_key(keyword.lower(), location_code, language_code)
        return self.get(key, category="keyword_data")
    
    def set_keyword_data(
        self,
        keyword: str,
        data: dict,
        location_code: str = "ZA",
        language_code: str = "en",
    ) -> bool:
        """Cache keyword data from DataForSEO.
        
        Args:
            keyword: Search keyword
            data: Keyword data to cache
            location_code: Location code
            language_code: Language code
            
        Returns:
            True if successful
        """
        key = self._make_key(keyword.lower(), location_code, language_code)
        return self.set(key, data, category="keyword_data")
    
    def get_wordpress_post(self, post_id: int) -> Optional[dict]:
        """Get cached WordPress post.
        
        Args:
            post_id: WordPress post ID
            
        Returns:
            Cached post data or None
        """
        key = f"post_{post_id}"
        return self.get(key, category="wordpress_post")
    
    def set_wordpress_post(self, post_id: int, data: dict) -> bool:
        """Cache WordPress post.
        
        Args:
            post_id: WordPress post ID
            data: Post data to cache
            
        Returns:
            True if successful
        """
        key = f"post_{post_id}"
        return self.set(key, data, category="wordpress_post")
    
    def get_generated_content(
        self,
        keyword: str,
        word_count: int,
        tone: str,
    ) -> Optional[str]:
        """Get cached generated content.
        
        Args:
            keyword: Content keyword
            word_count: Target word count
            tone: Content tone
            
        Returns:
            Cached content or None
        """
        key = self._make_key(keyword.lower(), str(word_count), tone)
        return self.get(key, category="content_generated")
    
    def set_generated_content(
        self,
        keyword: str,
        word_count: int,
        tone: str,
        content: str,
    ) -> bool:
        """Cache generated content.
        
        Args:
            keyword: Content keyword
            word_count: Target word count
            tone: Content tone
            content: Generated content
            
        Returns:
            True if successful
        """
        key = self._make_key(keyword.lower(), str(word_count), tone)
        return self.set(key, content, category="content_generated")
    
    def invalidate_category(self, category: str) -> int:
        """Invalidate all entries in a category.
        
        Args:
            category: Category to invalidate
            
        Returns:
            Number of entries cleared
        """
        try:
            # Get all keys with prefix
            prefix = f"{category}:"
            keys_to_delete = [k for k in self._cache.iterkeys() if k.startswith(prefix)]
            
            for key in keys_to_delete:
                self._cache.delete(key)
            
            return len(keys_to_delete)
        except Exception:
            return 0
    
    def clear_all(self) -> bool:
        """Clear entire cache.
        
        Returns:
            True if successful
        """
        try:
            self._cache.clear()
            return True
        except Exception:
            return False
    
    def get_stats(self) -> dict:
        """Get cache statistics.
        
        Returns:
            Cache statistics
        """
        try:
            # Get diskcache stats
            dc_stats = self._cache.stats(enable=False)
            
            return {
                "hits": self._stats["hits"],
                "misses": self._stats["misses"],
                "hit_rate": self._stats["hits"] / (self._stats["hits"] + self._stats["misses"]) * 100
                if (self._stats["hits"] + self._stats["misses"]) > 0 else 0,
                "sets": self._stats["sets"],
                "deletes": self._stats["deletes"],
                "size": self._cache.volume(),  # Approximate size in bytes
                "entries": len(list(self._cache.iterkeys())),
                "diskcache_hits": dc_stats.get("hits", 0),
                "diskcache_misses": dc_stats.get("misses", 0),
            }
        except Exception:
            return self._stats.copy()
    
    def close(self) -> None:
        """Close cache connection."""
        try:
            self._cache.close()
        except Exception:
            pass
    
    def __enter__(self):
        """Context manager entry."""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()


# Global cache instance
_global_cache: Optional[CacheManager] = None


def get_cache() -> CacheManager:
    """Get or create global cache instance."""
    global _global_cache
    if _global_cache is None:
        _global_cache = CacheManager()
    return _global_cache


def cached(
    category: str = "default",
    ttl: Optional[int] = None,
    key_func: Optional[callable] = None,
):
    """Decorator for caching function results.
    
    Args:
        category: Cache category
        ttl: Time to live in seconds
        key_func: Function to generate cache key from arguments
        
    Returns:
        Decorator function
    """
    def decorator(func):
        def wrapper(*args, **kwargs):
            # Generate cache key
            if key_func:
                key = key_func(*args, **kwargs)
            else:
                # Default: hash args and kwargs
                key_parts = [str(a) for a in args] + [f"{k}={v}" for k, v in sorted(kwargs.items())]
                key = hashlib.sha256(":".join(key_parts).encode()).hexdigest()[:16]
            
            cache = get_cache()
            
            # Try to get from cache
            cached_value = cache.get(key, category=category)
            if cached_value is not None:
                return cached_value
            
            # Call function and cache result
            result = func(*args, **kwargs)
            cache.set(key, result, category=category, ttl=ttl)
            return result
        
        return wrapper
    return decorator


# Convenience functions for common operations

def get_cached_keyword_data(keyword: str, **kwargs) -> Optional[dict]:
    """Get cached keyword data."""
    return get_cache().get_keyword_data(keyword, **kwargs)


def set_cached_keyword_data(keyword: str, data: dict, **kwargs) -> bool:
    """Cache keyword data."""
    return get_cache().set_keyword_data(keyword, data, **kwargs)


def get_cached_wordpress_post(post_id: int) -> Optional[dict]:
    """Get cached WordPress post."""
    return get_cache().get_wordpress_post(post_id)


def set_cached_wordpress_post(post_id: int, data: dict) -> bool:
    """Cache WordPress post."""
    return get_cache().set_wordpress_post(post_id, data)
