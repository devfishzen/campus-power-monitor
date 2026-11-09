"""用 QQ 邮箱 SMTP 发一封测试邮件，不依赖第三方库。

在 Windows 上先验证授权码是否可用：

    python -m scripts.mailcheck
"""

from __future__ import annotations

import smtplib
import sys
from email.message import EmailMessage
from email.utils import formataddr

from scripts.livecheck import load_env

try:  # Windows 控制台默认不是 UTF-8
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:  # pragma: no cover
    pass


def main() -> int:
    env = load_env()
    user = env.get("SMTP_USER", "").strip()
    password = env.get("SMTP_PASS", "").strip()
    to = env.get("MAIL_TO", "").strip() or user
    host = env.get("SMTP_HOST", "smtp.qq.com").strip()
    port = int(env.get("SMTP_PORT", "465"))

    if not user or not password or not to:
        print("请先在 .env 填 SMTP_USER、SMTP_PASS（授权码）、MAIL_TO")
        return 1

    msg = EmailMessage()
    msg["From"] = formataddr(("电费监控", user))
    msg["To"] = to
    msg["Subject"] = "【测试】电费监控邮件"
    msg.set_content("如果你收到这封邮件，说明 QQ 邮箱 SMTP 配置正确。\n")

    try:
        with smtplib.SMTP_SSL(host, port, timeout=20) as smtp:
            smtp.login(user, password)
            smtp.send_message(msg)
    except Exception as exc:
        print(f"发送失败：{exc}")
        return 1

    print(f"已发送到 {to}，请检查收件箱和垃圾箱")
    return 0


if __name__ == "__main__":
    sys.exit(main())
