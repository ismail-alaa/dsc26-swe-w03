import time
from collections.abc import Callable
from dataclasses import dataclass, field


@dataclass
class Settings:
    database_url: str = "sqlite+pysqlite:///./rawaj.db"
    api_tokens: dict[str, str] = field(default_factory=dict)  # token -> customer_id
    rate_limit_capacity: int = 5
    rate_limit_refill_per_second: float = 1.0
    max_transfer_piastres: int = 2_000_000
    clock: Callable[[], float] = time.monotonic
