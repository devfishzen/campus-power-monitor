from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING

from .models import Reading
from .notifier import Notifier
from .providers.base import Provider
from .store import Store

if TYPE_CHECKING:
    from .config import Settings

log = logging.getLogger(__name__)


class MonitorService:
    def __init__(
        self,
        settings: Settings,
        store: Store,
        provider: Provider,
        notifier: Notifier,
    ) -> None:
        self.settings = settings
        self.store = store
        self.provider = provider
        self.notifier = notifier
        self._consecutive_failures = 0

    async def run_once(self) -> Reading:
        reading = await self.provider.fetch()
        self.store.save_reading(reading)
        self._consecutive_failures = 0
        log.info(
            "查询成功：%s 剩余 %.1f 度（今日 %s 度）",
            reading.room,
            reading.remaining_kwh,
            reading.today_kwh,
        )
        if reading.remaining_kwh <= self.settings.threshold_kwh:
            await self._maybe_alert_low(reading)
        return reading

    async def _maybe_alert_low(self, reading: Reading) -> None:
        last = self.store.last_alert_at("low")
        cooldown = timedelta(hours=self.settings.alert_cooldown_hours)
        if last and datetime.now(timezone.utc) - last < cooldown:
            log.info("低电量告警仍在冷却期，跳过")
            return

        if await self.notifier.send_low_battery(
            reading, self.settings.threshold_kwh
        ):
            self.store.record_alert("low", f"remaining={reading.remaining_kwh}")
        else:
            # 没发出去就不记录，下一轮还会重试
            log.warning("低电量告警未发送成功")

    async def run_guarded(self) -> None:
        """调度器入口：吞掉异常，连续失败才告警。"""
        try:
            await self.run_once()
        except Exception as exc:
            self._consecutive_failures += 1
            log.exception("查询失败（连续 %d 次）", self._consecutive_failures)
            if self._consecutive_failures < 2:
                return

            last = self.store.last_alert_at("failure")
            cooldown = timedelta(hours=self.settings.alert_cooldown_hours)
            if last and datetime.now(timezone.utc) - last < cooldown:
                return

            if await self.notifier.send_failure(str(exc)):
                self.store.record_alert("failure", str(exc)[:500])
