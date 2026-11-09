from __future__ import annotations

import logging

from pydantic_settings import BaseSettings, SettingsConfigDict

log = logging.getLogger(__name__)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # 数据源：mock / ecode
    provider: str = "mock"

    # 调度
    check_cron: str = "30 8 * * *"
    timezone: str = "Asia/Shanghai"
    run_on_start: bool = True

    # 告警
    threshold_kwh: float = 30.0
    alert_cooldown_hours: int = 20

    # 存储
    db_path: str = "./data/dianfei.db"
    overrides_path: str = "./data/overrides.json"

    # Web 设置页（HTTP Basic）
    admin_user: str = "admin"
    admin_password: str = ""

    # 校园e码通「智能水电」= 完美校园 H5（不需要密码，也不需要微信）
    ecode_base_url: str = "https://xqh5.17wanxiao.com/smartWaterAndElectricityService"
    ecode_account: str = ""
    ecode_customercode: str = ""
    ecode_room: str = ""
    ecode_roomverify: str = ""

    # QQ 邮箱 SMTP
    smtp_host: str = "smtp.qq.com"
    smtp_port: int = 465
    smtp_user: str = ""
    smtp_pass: str = ""
    mail_to: str = ""

    # 手动触发接口
    api_token: str = ""

    # mock 演示值
    mock_remaining_kwh: float = 100.0
    mock_today_kwh: float = 20.0

    @property
    def mail_enabled(self) -> bool:
        return bool(self.smtp_user and self.smtp_pass and self.mail_to)
