from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING

from ..models import Reading

if TYPE_CHECKING:
    from ..config import Settings


class MockProvider:
    """演示数据源，用来在抓包前把整条链路跑通。"""

    name = "mock"

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    async def fetch(self) -> Reading:
        return Reading(
            room=self.settings.ecode_room,
            remaining_kwh=self.settings.mock_remaining_kwh,
            today_kwh=self.settings.mock_today_kwh,
            fetched_at=datetime.now(timezone.utc),
            raw={"provider": "mock"},
        )
