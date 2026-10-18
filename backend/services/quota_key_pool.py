"""
quota_key_pool.py — Quota-Aware LLM API Key Pool with Cooldowns
===============================================================
Shared request/monitoring pools with observed outcomes and key cooldowns.
This tracks process-local request health, not provider billing or remaining quota.

Features:
- Tracks per-key failure timestamps and error types
- On 429: puts key on cooldown for `cooldown_seconds` (default 60s)
- On 5xx: short retry backoff per key
- Selects key with fewest recent failures and longest idle time
- Separate pools for NVIDIA and Groq keys
- Thread-safe via threading.Lock
- Health status endpoint for monitoring
"""

import logging
import threading
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class KeyStats:
    key: str
    provider: str
    total_requests: int = 0
    total_successes: int = 0
    total_failures: int = 0
    consecutive_failures: int = 0
    last_used_at: float = 0.0
    cooldown_until: float = 0.0
    rate_limit_hits: int = 0
    error_history: List[Dict] = field(default_factory=list)
    recent_requests: List[tuple] = field(default_factory=list)

    @property
    def is_available(self) -> bool:
        return time.time() >= self.cooldown_until

    @property
    def cooldown_remaining(self) -> float:
        return max(0.0, self.cooldown_until - time.time())

    @property
    def success_rate(self) -> Optional[float]:
        if self.total_requests == 0:
            return None
        return self.total_successes / self.total_requests

    @property
    def idle_seconds(self) -> float:
        if self.last_used_at == 0:
            return float("inf")
        return time.time() - self.last_used_at


class QuotaAwareKeyPool:
    """
    Thread-safe API key pool with quota tracking and cooldowns.
    
    Usage:
        pool = QuotaAwareKeyPool(groq_keys, provider="groq")
        key = pool.get_key()         # Get best available key
        pool.report_success(key)     # After successful call
        pool.report_failure(key, 429)  # After rate limit
        pool.report_failure(key, 500)  # After server error
    """

    RATE_LIMIT_COOLDOWN = 65       # seconds to cool down after 429
    SERVER_ERROR_COOLDOWN = 15     # seconds after 5xx error
    AUTH_ERROR_COOLDOWN = 3600     # 1 hour after 401/403
    MAX_CONSECUTIVE_FAILURES = 5   # mark key as degraded after this many

    def __init__(self, api_keys: List[str], provider: str = "unknown", cooldown_seconds: int = 65):
        self._lock = threading.Lock()
        self.provider = provider
        self.RATE_LIMIT_COOLDOWN = cooldown_seconds
        self._stats: Dict[str, KeyStats] = {
            key.strip(): KeyStats(key=key.strip(), provider=provider)
            for key in api_keys
            if key and key.strip()
        }
        logger.info(f"[KeyPool:{provider}] Initialized with {len(self._stats)} keys")

    def get_key(self, *, rpm_limit=None, token_budget=None, request_tokens=0, max_in_flight=None) -> Optional[str]:
        """
        Select the best available key.
        
        Selection priority:
        1. Keys not on cooldown
        2. Among those: fewest consecutive failures
        3. Then: longest idle (least recently used)
        
        Returns None if ALL keys are on cooldown.
        """
        with self._lock:
            now = time.time()
            for stats in self._stats.values():
                stats.recent_requests = [(at,tokens) for at,tokens in stats.recent_requests if at > now-60]
            def capacity(stats):
                if max_in_flight is not None and stats.total_requests-stats.total_successes-stats.total_failures >= max_in_flight:
                    return False
                if rpm_limit is not None and len(stats.recent_requests) >= rpm_limit:
                    return False
                return token_budget is None or sum(tokens for _,tokens in stats.recent_requests)+request_tokens <= token_budget
            available = [
                s for s in self._stats.values()
                if s.is_available and s.consecutive_failures < self.MAX_CONSECUTIVE_FAILURES and capacity(s)
            ]

            if not available:
                # All ideal keys exhausted — try degraded keys as last resort
                available = [s for s in self._stats.values() if s.is_available and capacity(s)]

            if not available:
                # Respect cooldowns; callers can try another provider immediately.
                return None

            # Sort: fewest consecutive failures, then longest idle
            best = sorted(available, key=lambda s: (s.consecutive_failures, -s.idle_seconds))[0]
            best.last_used_at = time.time()
            best.total_requests += 1
            best.recent_requests.append((now,request_tokens))
            return best.key

    def report_success(self, key: str):
        """Record a successful API call."""
        with self._lock:
            stats = self._stats.get(key)
            if stats:
                stats.total_successes += 1
                stats.consecutive_failures = 0

    def report_failure(self, key: str, http_status: int, error_msg: str = "", retry_after_seconds=0):
        """
        Record a failed API call and apply appropriate cooldown.
        
        Args:
            key: The API key that failed
            http_status: HTTP status code (429, 500, 401, etc.)
            error_msg: Optional error message for logging
        """
        with self._lock:
            stats = self._stats.get(key)
            if not stats:
                return

            stats.total_failures += 1
            stats.consecutive_failures += 1
            stats.error_history.append({
                "ts": time.time(),
                "status": http_status,
                "msg": error_msg[:100],
            })
            # Keep last 20 errors
            stats.error_history = stats.error_history[-20:]
            if retry_after_seconds > 0:
                stats.cooldown_until = max(stats.cooldown_until, time.time()+min(retry_after_seconds,86400))

            if http_status == 429:
                stats.rate_limit_hits += 1
                stats.cooldown_until = max(stats.cooldown_until, time.time() + self.RATE_LIMIT_COOLDOWN)
                logger.warning(
                    f"[KeyPool:{self.provider}] Key ...{key[-6:]} rate-limited (429). "
                    f"Cooldown {self.RATE_LIMIT_COOLDOWN}s. "
                    f"Total rate-limit hits: {stats.rate_limit_hits}"
                )
            elif http_status == 0 or 500 <= http_status < 600:
                stats.cooldown_until = max(stats.cooldown_until, time.time() + self.SERVER_ERROR_COOLDOWN)
                logger.warning(
                    f"[KeyPool:{self.provider}] Key ...{key[-6:]} server error ({http_status}). "
                    f"Cooldown {self.SERVER_ERROR_COOLDOWN}s."
                )
            elif http_status in (401, 403):
                stats.cooldown_until = max(stats.cooldown_until, time.time() + self.AUTH_ERROR_COOLDOWN)
                logger.error(
                    f"[KeyPool:{self.provider}] Key ...{key[-6:]} auth failure ({http_status}). "
                    f"Cooling down for 1 hour — key may be revoked."
                )

    def health_report(self) -> Dict:
        """Return health status of all keys — for monitoring endpoint."""
        with self._lock:
            keys_info = []
            for key, stats in self._stats.items():
                keys_info.append({
                    "key_suffix": f"...{key[-6:]}",
                    "available": stats.is_available,
                    "cooldown_remaining_s": round(stats.cooldown_remaining, 1),
                    "success_rate": round(stats.success_rate, 3) if stats.success_rate is not None else None,
                    "total_requests": stats.total_requests,
                    "total_successes": stats.total_successes,
                    "total_failures": stats.total_failures,
                    "in_flight_requests": max(0, stats.total_requests-stats.total_successes-stats.total_failures),
                    "consecutive_failures": stats.consecutive_failures,
                    "rate_limit_hits": stats.rate_limit_hits,
                    "idle_seconds": round(min(stats.idle_seconds, 999999), 1),
                })

            available_count = sum(1 for s in self._stats.values() if s.is_available)
            return {
                "provider": self.provider,
                "total_keys": len(self._stats),
                "available_keys": available_count,
                "all_exhausted": available_count == 0,
                "total_requests": sum(s.total_requests for s in self._stats.values()),
                "total_successes": sum(s.total_successes for s in self._stats.values()),
                "total_failures": sum(s.total_failures for s in self._stats.values()),
                "keys": keys_info,
            }

    def __len__(self) -> int:
        return len(self._stats)
