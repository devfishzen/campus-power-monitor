"""不依赖 FastAPI / pydantic 的实网查询，直接读 .env。

在 Windows 或服务器上都可以先跑这个确认接口通不通：

    python -m scripts.livecheck
"""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path
from types import SimpleNamespace

from app.providers.ecode import EcodeProvider

try:  # Windows 控制台默认不是 UTF-8，避免中文乱码
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:  # pragma: no cover
    pass

DEFAULT_BASE = "https://xqh5.17wanxiao.com/smartWaterAndElectricityService"


def load_env(path: str = ".env") -> dict[str, str]:
    # 容器里没有 .env 文件，环境变量由 docker compose 注入
    env: dict[str, str] = dict(os.environ)
    file = Path(path)
    if not file.exists():
        return env
    for raw in file.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        env[key.strip()] = value.strip()
    return env


async def main() -> int:
    env = load_env()
    if not env.get("ECODE_ACCOUNT"):
        print("请先在 .env 填 ECODE_ACCOUNT（学号）")
        return 1
    if not env.get("ECODE_CUSTOMERCODE"):
        print("请先在 .env 填 ECODE_CUSTOMERCODE（学校编号）")
        return 1
    if not env.get("ECODE_ROOM"):
        print("请先在 .env 填 ECODE_ROOM（例如 A栋-101）")
        return 1

    settings = SimpleNamespace(
        ecode_base_url=env.get("ECODE_BASE_URL", DEFAULT_BASE),
        ecode_account=env["ECODE_ACCOUNT"],
        ecode_customercode=env["ECODE_CUSTOMERCODE"],
        ecode_room=env["ECODE_ROOM"],
        ecode_roomverify=env.get("ECODE_ROOMVERIFY", ""),
    )

    reading = await EcodeProvider(settings).fetch()
    today = f"{reading.today_kwh:g}" if reading.today_kwh is not None else "未知"
    print(f"房间：{reading.room}")
    print(f"剩余电量：{reading.remaining_kwh:g} 度")
    print(f"今日用电：{today} 度")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
