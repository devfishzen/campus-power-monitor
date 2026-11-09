from __future__ import annotations

import logging
import secrets
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from fastapi import Depends, FastAPI, Header, HTTPException, Query
from fastapi.responses import HTMLResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from pydantic import BaseModel, Field

from .config import Settings
from .models import Reading
from .notifier import Notifier
from .overrides import load_overrides, save_overrides
from .providers.ecode import EcodeProvider
from .providers.mock import MockProvider
from .service import MonitorService
from .store import Store
from .webui import dashboard, settings_page as render_settings_page

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger("dianfei")

settings = Settings()

# Web 设置页保存的覆盖值优先于 .env
_overrides = load_overrides(settings.overrides_path)
if "threshold_kwh" in _overrides:
    try:
        settings.threshold_kwh = float(_overrides["threshold_kwh"])
    except (TypeError, ValueError):
        logger.warning("overrides.json 里的 threshold_kwh 无效，忽略")
if _overrides.get("smtp_pass"):
    settings.smtp_pass = str(_overrides["smtp_pass"])

store = Store(settings.db_path)

if settings.provider == "ecode":
    provider = EcodeProvider(settings)
else:
    provider = MockProvider(settings)

notifier = Notifier(settings)
service = MonitorService(settings, store, provider, notifier)

security = HTTPBasic(auto_error=False)


@asynccontextmanager
async def lifespan(_: FastAPI):
    scheduler = AsyncIOScheduler(timezone=settings.timezone)
    scheduler.add_job(
        service.run_guarded,
        CronTrigger.from_crontab(settings.check_cron, timezone=settings.timezone),
        id="scheduled-check",
        max_instances=1,
        coalesce=True,
        misfire_grace_time=3600,
    )
    scheduler.start()
    logger.info(
        "调度启动：cron=%s tz=%s provider=%s threshold=%s",
        settings.check_cron,
        settings.timezone,
        provider.name,
        settings.threshold_kwh,
    )

    if settings.run_on_start:
        scheduler.add_job(
            service.run_guarded,
            "date",
            run_date=datetime.now(timezone.utc) + timedelta(seconds=3),
            id="startup-check",
        )

    try:
        yield
    finally:
        scheduler.shutdown(wait=False)


app = FastAPI(title="电费监控", version="0.2.0", lifespan=lifespan)


def require_token(x_api_token: str | None = Header(default=None)) -> None:
    if settings.api_token and x_api_token != settings.api_token:
        raise HTTPException(status_code=401, detail="invalid token")


def require_admin(
    credentials: HTTPBasicCredentials | None = Depends(security),
) -> None:
    if not settings.admin_password:
        raise HTTPException(
            status_code=403,
            detail="设置页未启用：请在 .env 设置 ADMIN_PASSWORD 后重启",
        )
    ok_user = credentials is not None and secrets.compare_digest(
        credentials.username.encode("utf-8"),
        settings.admin_user.encode("utf-8"),
    )
    ok_pass = credentials is not None and secrets.compare_digest(
        credentials.password.encode("utf-8"),
        settings.admin_password.encode("utf-8"),
    )
    if not (ok_user and ok_pass):
        raise HTTPException(
            status_code=401,
            detail="需要登录",
            headers={"WWW-Authenticate": 'Basic realm="dianfei"'},
        )


class SettingsPayload(BaseModel):
    threshold_kwh: float | None = Field(default=None, ge=0, le=10000)
    smtp_pass: str | None = Field(default=None, max_length=256)


def reading_payload(reading: Reading) -> dict:
    return {
        "room": reading.room,
        "remaining_kwh": reading.remaining_kwh,
        "today_kwh": reading.today_kwh,
        "fetched_at": reading.fetched_at.astimezone(timezone.utc).isoformat(),
        "threshold_kwh": settings.threshold_kwh,
        "is_low": reading.remaining_kwh <= settings.threshold_kwh,
    }


@app.get("/healthz")
def healthz() -> dict:
    return {"ok": True, "provider": provider.name}


@app.get("/api/current")
def current() -> dict:
    reading = store.latest()
    if not reading:
        raise HTTPException(status_code=404, detail="no data yet")
    return reading_payload(reading)


@app.get("/api/history")
def history(days: int = Query(default=30, ge=1, le=365)) -> list[dict]:
    return [reading_payload(reading) for reading in store.history(days)]


@app.post("/api/run", dependencies=[Depends(require_token)])
async def run_now() -> dict:
    try:
        reading = await service.run_once()
    except NotImplementedError as exc:
        raise HTTPException(status_code=501, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("手动查询失败")
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return reading_payload(reading)


@app.get(
    "/settings",
    response_class=HTMLResponse,
    dependencies=[Depends(require_admin)],
)
def settings_page() -> str:
    return render_settings_page(
        threshold=settings.threshold_kwh,
        smtp_pass_set=bool(settings.smtp_pass),
        mail_to=settings.mail_to,
        mail_enabled=settings.mail_enabled,
    )


@app.post("/api/settings", dependencies=[Depends(require_admin)])
def update_settings(payload: SettingsPayload) -> dict:
    updates: dict[str, object] = {}
    if payload.threshold_kwh is not None:
        updates["threshold_kwh"] = payload.threshold_kwh
    if payload.smtp_pass is not None:
        smtp_pass = payload.smtp_pass.strip()
        if smtp_pass:
            updates["smtp_pass"] = smtp_pass

    if updates:
        try:
            save_overrides(settings.overrides_path, updates)
        except OSError as exc:
            logger.exception("保存设置失败")
            raise HTTPException(status_code=500, detail="保存设置失败") from exc

        if "threshold_kwh" in updates:
            settings.threshold_kwh = float(updates["threshold_kwh"])
        if "smtp_pass" in updates:
            settings.smtp_pass = str(updates["smtp_pass"])
        logger.info("Web 设置已更新：%s", ", ".join(updates))

    return {
        "ok": True,
        "changed": sorted(updates),
        "threshold_kwh": settings.threshold_kwh,
        "smtp_pass_set": bool(settings.smtp_pass),
    }


@app.post("/api/settings/test-email", dependencies=[Depends(require_admin)])
async def test_email() -> dict:
    if not settings.mail_enabled:
        raise HTTPException(
            status_code=400,
            detail="邮件未配置：请填写授权码，并确认 SMTP_USER / MAIL_TO 已在 .env 设置",
        )
    ok = await notifier.send(
        "【测试】电费监控邮件",
        "如果你收到这封邮件，说明 QQ 邮箱 SMTP 配置正确。\n",
    )
    if not ok:
        raise HTTPException(status_code=502, detail="发送失败，请查看容器日志")
    return {"ok": True}


@app.get("/", response_class=HTMLResponse)
def index() -> str:
    return dashboard(
        reading=store.latest(),
        threshold=settings.threshold_kwh,
        mail_enabled=settings.mail_enabled,
        admin_enabled=bool(settings.admin_password),
    )
