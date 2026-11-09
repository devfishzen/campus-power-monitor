from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass(slots=True)
class Reading:
    """一次电表读数。"""

    room: str
    remaining_kwh: float
    today_kwh: float | None
    fetched_at: datetime
    raw: dict[str, Any] = field(default_factory=dict)
