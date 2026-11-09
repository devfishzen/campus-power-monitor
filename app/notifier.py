from __future__ import annotations

import asyncio
import logging
import smtplib
from email.message import EmailMessage
from email.utils import formataddr
from typing import TYPE_CHECKING

from .models import Reading

if TYPE_CHECKING:
    from .config import Settings

log = logging.getLogger(__name__)


class Notifier:
    """邮件通知。QQ 邮箱走 smtp.qq.com:465 + 授权码。"""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    async def send(self, subject: str, body: str) -> bool:
        if not self.settings.mail_enabled:
            log.warning("邮件未配置（SMTP_USER/SMTP_PASS/MAIL_TO），跳过：%s", subject)
            return False

        msg = EmailMessage()
        msg["From"] = formataddr(("电费监控", self.settings.smtp_user))
        msg["To"] = self.settings.mail_to
        msg["Subject"] = subject
        msg.set_content(body)

        try:
            await asyncio.to_thread(self._send_sync, msg)
            log.info("邮件已发送：%s", subject)
            return True
        except Exception:
            log.exception("邮件发送失败：%s", subject)
            return False

    def _send_sync(self, msg: EmailMessage) -> None:
        with smtplib.SMTP_SSL(
            self.settings.smtp_host, self.settings.smtp_port, timeout=20
        ) as smtp:
            smtp.login(self.settings.smtp_user, self.settings.smtp_pass)
            smtp.send_message(msg)

    async def send_low_battery(self, reading: Reading, threshold: float) -> bool:
        subject = (
            f"【电费提醒】{reading.room} 剩余电量 {reading.remaining_kwh:g} 度"
        )
        today = (
            f"{reading.today_kwh:g} 度"
            if reading.today_kwh is not None
            else "未知"
        )
        body = (
            f"房间：{reading.room}\n"
            f"剩余电量：{reading.remaining_kwh:g} 度（阈值 {threshold:g} 度）\n"
            f"今日用电：{today}\n"
            f"查询时间：{reading.fetched_at.astimezone().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
            "请及时充值，避免断电。\n"
        )
        return await self.send(subject, body)

    async def send_failure(self, error: str) -> bool:
        subject = "【电费监控】查询失败"
        body = (
            "连续查询失败，可能是登录态失效或接口变更，请检查。\n\n"
            f"错误：{error}\n"
        )
        return await self.send(subject, body)
