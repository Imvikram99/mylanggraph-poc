"""Simple in-memory rate limiter."""

from __future__ import annotations

import time
from collections import defaultdict
from typing import DefaultDict, Tuple


class RateLimiter:
    def __init__(self, default_rpm: int = 60) -> None:
        self.default_rpm = default_rpm
        self.calls: DefaultDict[Tuple[str, int], int] = defaultdict(int)

    def allow(self, tenant_id: str, rpm: int | None = None) -> bool:
        window = int(time.time() // 60)
        key = (tenant_id, window)
        self.calls[key] += 1
        limit = rpm or self.default_rpm
        return self.calls[key] <= limit
