import re
from collections import OrderedDict
from typing import Optional, Dict, Any

class TicketCache:
    def __init__(self, maxsize: int = 1000):
        self.cache: OrderedDict = OrderedDict()
        self.maxsize = maxsize
        self.hits = 0
        self.misses = 0

    def _normalize_message(self, message: str) -> str:
        """
        Normalizes the support ticket message to increase cache hit rates:
        - Convert to lowercase
        - Remove non-alphanumeric/non-bengali characters
        - Normalize whitespaces
        """
        msg = message.lower().strip()
        # Keep letters, numbers, Bengali characters, and spaces
        msg = re.sub(r"[^\w\s\u0980-\u09ff]", "", msg)
        msg = re.sub(r"\s+", " ", msg)
        return msg.strip()

    def get(self, message: str) -> Optional[Dict[str, Any]]:
        """
        Gets a cached classification dictionary for a message.
        """
        norm_msg = self._normalize_message(message)
        if norm_msg in self.cache:
            self.hits += 1
            # Move to end (MRU)
            self.cache.move_to_end(norm_msg)
            return self.cache[norm_msg]
        
        self.misses += 1
        return None

    def set(self, message: str, classification: Dict[str, Any]):
        """
        Stores a classification dictionary for a message.
        """
        norm_msg = self._normalize_message(message)
        if norm_msg in self.cache:
            self.cache.move_to_end(norm_msg)
        self.cache[norm_msg] = classification
        
        # Evict oldest if full
        if len(self.cache) > self.maxsize:
            self.cache.popitem(last=False)

    def get_stats(self) -> Dict[str, Any]:
        """
        Returns cache metrics for observability.
        """
        total = self.hits + self.misses
        hit_ratio = (self.hits / total) if total > 0 else 0.0
        return {
            "size": len(self.cache),
            "maxsize": self.maxsize,
            "hits": self.hits,
            "misses": self.misses,
            "hit_ratio": round(hit_ratio, 2)
        }

# Global cache instance
global_cache = TicketCache(maxsize=1000)
