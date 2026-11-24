"""
UnfollowX Safety Engine & Adaptive Rate Controller
Tracks Trust Score (0-100), warm-up status, dynamic backoff delays, and strict verification.
"""

import time
import math
import random
from datetime import datetime, timedelta

class SafetyEngine:
    def __init__(self, storage_manager=None, storage=None):
        self.storage = storage_manager if storage_manager is not None else storage
        self.trust_score = 100 # Default baseline trust score
        self.consecutive_fails = 0
        self.last_action_time = 0
        self.cooldown_until = 0
        self._load_state()

    def _load_state(self):
        if not self.storage or not hasattr(self.storage, "get_metric"):
            return
        try:
            ts = self.storage.get_metric("trust_score", default_num=100)["val_num"]
            cf = self.storage.get_metric("consecutive_fails", default_num=0)["val_num"]
            cd = self.storage.get_metric("cooldown_until", default_num=0)["val_num"]
            self.trust_score = max(0, min(100, int(ts)))
            self.consecutive_fails = max(0, int(cf))
            self.cooldown_until = max(0.0, float(cd))
        except Exception:
            pass

    def _persist_state(self):
        if not self.storage or not hasattr(self.storage, "set_metric"):
            return
        try:
            self.storage.set_metric("trust_score", val_num=float(self.trust_score))
            self.storage.set_metric("consecutive_fails", val_num=float(self.consecutive_fails))
            self.storage.set_metric("cooldown_until", val_num=float(self.cooldown_until))
        except Exception:
            pass

    def evaluate_threat(self, status_code, response_text):
        """
        Assess API response health and adjust trust score immediately.
        """
        lower = (response_text or "").lower()
        threat_level = "safe"
        penalty = 0

        if status_code == 429:
            threat_level = "rate_limit"
            penalty = 35
            # Force 15-30 mins cooldown
            self.cooldown_until = time.time() + random.uniform(900, 1800)
        elif status_code in (401, 403):
            threat_level = "permission_blocked"
            penalty = 40
            self.cooldown_until = time.time() + random.uniform(1800, 3600)
        elif any(k in lower for k in ["checkpoint_required", "challenge_required"]):
            threat_level = "checkpoint"
            penalty = 60
            self.cooldown_until = time.time() + 7200 # 2 hours
        elif any(k in lower for k in ["feedback_required", "action_blocked", "spam"]):
            threat_level = "action_blocked"
            penalty = 50
            self.cooldown_until = time.time() + 3600 # 1 hour
        elif status_code != 200 and not ("ok" in lower):
            threat_level = "soft_fail"
            penalty = 5

        # Update trust score with floor at 0
        self.trust_score = max(0, self.trust_score - penalty)

        if penalty == 0:
            # Gradual trust recovery (+1 per safe request, capped at 100)
            self.trust_score = min(100, self.trust_score + 1)
            self.consecutive_fails = 0
        else:
            self.consecutive_fails += 1

        self._persist_state()

        return {
            "threat_level": threat_level,
            "penalty": penalty,
            "trust_score": self.trust_score,
            "cooldown_seconds": max(0, int(self.cooldown_until - time.time())),
            "is_critical": self.trust_score < 40 or self.consecutive_fails >= 3 or threat_level in ("checkpoint", "action_blocked")
        }

    def get_adaptive_delay(self, base_mode="ultimate_safe"):
        """
        Calculates dynamic delay based on Trust Score and Speed Mode.
        Turbo Fast: 3.5s - 7.5s (Maximum throughput)
        Fast: 8.0s - 16.0s (Fast & smooth)
        Balanced: 18.0s - 32.0s
        Safe: 30.0s - 50.0s
        """
        mode_str = str(base_mode).lower()
        if "turbo" in mode_str:
            min_d, max_d = 3.5, 7.5
        elif "fast" in mode_str:
            min_d, max_d = 8.0, 16.0
        elif "balanced" in mode_str:
            min_d, max_d = 18.0, 32.0
        else:
            min_d, max_d = 30.0, 50.0

        # Trust factor: 100 trust = 1.0x delay, 50 trust = 1.4x delay, 20 trust = 2.0x delay
        trust_ratio = max(0.2, self.trust_score / 100.0)
        multiplier = 1.0 / (trust_ratio ** 0.5)

        target_min = min_d * multiplier
        target_max = max_d * multiplier

        mean = (target_min + target_max) / 2.0
        std = (target_max - target_min) / 4.0
        sampled = random.gauss(mean, std)
        return max(target_min, min(target_max, sampled))

    def get_daily_quota(self, is_warmup=False):
        """
        Calculates maximum allowed unfollows today.
        Warm-up: 8
        Low Trust (<60): 15
        Standard Safe: 40-50
        """
        if is_warmup:
            return 8
        if self.trust_score < 60:
            return 15
        return 50

    def is_in_cooldown(self):
        return time.time() < self.cooldown_until

    def get_remaining_cooldown(self):
        return max(0, int(self.cooldown_until - time.time()))
