"""不依赖 FastAPI 的核心逻辑自检：SQLite + 阈值判断 + 告警冷却。

用法（项目根目录）：
    python -m scripts.selftest
"""

from __future__ import annotations

import asyncio
import os
import sys
from datetime import datetime, timezone
from types import SimpleNamespace

from app.overrides import load_overrides, save_overrides
from app.providers.mock import MockProvider
from app.providers.wanxiao_parse import extract_reading, pick_room
from app.service import MonitorService
from app.store import Store


class FakeNotifier:
    def __init__(self) -> None:
        self.sent: list[tuple[str, float]] = []

    async def send_low_battery(self, reading, threshold) -> bool:  # noqa: ANN001
        self.sent.append(("low", reading.remaining_kwh))
        return True

    async def send_failure(self, error: str) -> bool:
        self.sent.append(("failure", 0.0))
        return True


async def main() -> int:
    db_path = os.path.join("data", "selftest.db")
    for suffix in ("", "-wal", "-shm"):
        try:
            os.remove(db_path + suffix)
        except FileNotFoundError:
            pass

    try:
        store = Store(db_path)
        settings = SimpleNamespace(
            threshold_kwh=30.0,
            alert_cooldown_hours=20,
            ecode_room="A栋-101",
            mock_remaining_kwh=12.0,
            mock_today_kwh=20.0,
        )
        notifier = FakeNotifier()
        service = MonitorService(
            settings, store, MockProvider(settings), notifier
        )

        reading = await service.run_once()
        assert store.latest() is not None
        assert store.latest().remaining_kwh == 12.0
        assert notifier.sent == [("low", 12.0)], notifier.sent

        # 冷却期内第二次不重复告警
        await service.run_once()
        assert len(notifier.sent) == 1, notifier.sent

        # 历史能读到两条
        assert len(store.history(days=1)) == 2

        # 解析真实接口的返回结构：电控 + 水表，必须选电控
        rooms = [
            {
                "roomfullname": "A栋宿舍_学生公寓A栋_1层_101房间",
                "roomverify": "1-2--3-101",
            }
        ]
        assert pick_room(rooms, "A栋-101")["roomverify"] == "1-2--3-101"
        assert (
            pick_room([], "A栋-101", "1-2--3-101")["roomverify"]
            == "1-2--3-101"
        )

        body = {
            "roomfullname": "学生公寓A栋-101房间",
            "roomverify": "1-2--3-101",
            "modlist": [
                {
                    "devicename": "DDS1351电控",
                    "bussnesstype": 0,
                    "odd": "100.5",
                    "todayuse": 12,
                    "mac": 1,
                },
                {
                    "devicename": "CJ/T188-2004水表",
                    "bussnesstype": 1,
                    "odd": "50.0",
                    "todayuse": 0.2,
                    "mac": 2,
                },
            ],
        }
        parsed = extract_reading(
            body, now=datetime(2026, 1, 1, tzinfo=timezone.utc)
        )
        assert parsed.remaining_kwh == 100.5, parsed
        assert parsed.today_kwh == 12.0, parsed
        assert parsed.room == "学生公寓A栋-101房间", parsed

        # Web 设置页的覆盖值：只认白名单键，更新时保留其他键
        ov_path = os.path.join("data", "overrides-test.json")
        save_overrides(
            ov_path,
            {"threshold_kwh": 25.5, "smtp_pass": "test-code", "ignored": 1},
        )
        overrides = load_overrides(ov_path)
        assert overrides["threshold_kwh"] == 25.5, overrides
        assert overrides["smtp_pass"] == "test-code", overrides
        assert "ignored" not in overrides, overrides

        save_overrides(ov_path, {"threshold_kwh": 30})
        assert load_overrides(ov_path)["smtp_pass"] == "test-code"

        print("SELFTEST_OK", reading.remaining_kwh, parsed.remaining_kwh)
        return 0
    finally:
        for suffix in ("", "-wal", "-shm"):
            try:
                os.remove(db_path + suffix)
            except FileNotFoundError:
                pass
        try:
            os.remove(os.path.join("data", "overrides-test.json"))
        except FileNotFoundError:
            pass


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
