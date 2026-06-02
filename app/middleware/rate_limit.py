"""Rate limiting via slowapi — protege contra DDoS e abuso de custo da Claude API."""
from __future__ import annotations

from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address, default_limits=["60/minute"])
