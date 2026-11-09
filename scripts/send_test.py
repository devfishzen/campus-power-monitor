"""发一封测试邮件，验证 QQ 邮箱 SMTP 配置。

用法（容器内）：
    docker compose exec dianfei python scripts/send_test.py
"""

from __future__ import annotations

import asyncio
import sys

from app.config import Settings
from app.notifier import Notifier


async def main() -> int:
    settings = Settings()
    if not settings.mail_enabled:
        print("邮件未配置：请在 .env 填写 SMTP_USER / SMTP_PASS / MAIL_TO")
        return 1

    notifier = Notifier(settings)
    ok = await notifier.send(
        "【测试】电费监控邮件",
        "如果你收到这封邮件，说明 QQ 邮箱 SMTP 配置正确。\n",
    )
    print("已发送，请检查收件箱（含垃圾箱）" if ok else "发送失败，请看容器日志")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
