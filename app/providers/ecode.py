"""校园e码通「智能水电」数据源。

e码通的智能水电入口实际由完美校园（新开普）H5 提供：

    POST https://xqh5.17wanxiao.com/smartWaterAndElectricityService/SWAEServlet

两步：
  1. getbindroom         -> 拿房间 roomverify（同时建立 acw_tc / SERVERID 会话）
  2. h5_getstuindexpage  -> modlist 里 bussnesstype=0 / devicename 含“电控”的是电表
                            odd = 剩余电量，todayuse = 今日用电

只需要「学号 + 学校编号 + 房间号」，不需要校园卡密码，也不需要微信。
用标准库 urllib 而不是 httpx：每天两次请求，没必要为一个 HTTP 客户端加依赖。
"""

from __future__ import annotations

import asyncio
import http.cookiejar
import json
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime
from typing import Any

from ..models import Reading
from .wanxiao_parse import WanxiaoError, extract_reading, pick_room

DEFAULT_BASE = "https://xqh5.17wanxiao.com/smartWaterAndElectricityService"
API_PATH = "/SWAEServlet"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Linux; Android 14; REP-AN00 Build/HONORREP-AN00; wv) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 "
        "Chrome/127.0.6533.103 Mobile Safari/537.36 Wanxiao/5.8.6"
    ),
    "X-Requested-With": "com.newcapec.mobile.ncp",
    "Referer": "https://xqh5.17wanxiao.com/userwaterelecmini/index.html",
    "Origin": "https://xqh5.17wanxiao.com",
    "Accept": "*/*",
}


class EcodeProvider:
    name = "ecode"

    def __init__(self, settings: Any) -> None:
        self.settings = settings
        self.base_url = (settings.ecode_base_url or DEFAULT_BASE).rstrip("/")

    async def fetch(self) -> Reading:
        if not self.settings.ecode_account:
            raise WanxiaoError("ECODE_ACCOUNT 未配置")
        if not self.settings.ecode_customercode:
            raise WanxiaoError("ECODE_CUSTOMERCODE 未配置")
        if not self.settings.ecode_room and not self.settings.ecode_roomverify:
            raise WanxiaoError("ECODE_ROOM 未配置")

        opener = self._new_opener()
        rooms = await self._bound_rooms(opener)
        room = pick_room(
            rooms,
            self.settings.ecode_room,
            self.settings.ecode_roomverify,
        )
        roomverify = room.get("roomverify") or self.settings.ecode_roomverify
        if not roomverify:
            raise WanxiaoError("没有拿到房间 roomverify")
        body = await self._room_detail(opener, roomverify)

        return extract_reading(
            body,
            fallback_room=room.get("roomfullname") or self.settings.ecode_room,
        )

    @staticmethod
    def _new_opener() -> urllib.request.OpenerDirector:
        jar = http.cookiejar.CookieJar()
        opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(jar)
        )
        opener.addheaders = list(HEADERS.items())
        return opener

    async def _bound_rooms(
        self, opener: urllib.request.OpenerDirector
    ) -> list[dict[str, Any]]:
        body = await self._post(
            opener,
            {"cmd": "getbindroom", "account": self.settings.ecode_account},
            "getbindroom",
        )
        rooms = body.get("roomlist")
        if isinstance(rooms, list) and rooms:
            return rooms
        # 有的学校/账号直接返回单个房间对象，而不是 roomlist
        if body.get("roomverify") or body.get("roomfullname"):
            return [body]
        return []

    async def _room_detail(
        self,
        opener: urllib.request.OpenerDirector,
        roomverify: str,
    ) -> dict[str, Any]:
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S000")
        return await self._post(
            opener,
            {
                "cmd": "h5_getstuindexpage",
                "roomverify": roomverify,
                "account": self.settings.ecode_account,
                "timestamp": timestamp,
            },
            "h5_getstuindexpage",
            command="JBSWaterElecService",
        )

    async def _post(
        self,
        opener: urllib.request.OpenerDirector,
        param: dict[str, Any],
        method: str,
        command: str | None = None,
    ) -> dict[str, Any]:
        return await asyncio.to_thread(
            self._post_sync, opener, param, method, command
        )

    def _post_sync(
        self,
        opener: urllib.request.OpenerDirector,
        param: dict[str, Any],
        method: str,
        command: str | None,
    ) -> dict[str, Any]:
        params: dict[str, str] = {
            "param": json.dumps(param, separators=(",", ":"), ensure_ascii=False),
            "customercode": self.settings.ecode_customercode,
            "method": method,
        }
        if command:
            params["command"] = command

        url = f"{self.base_url}{API_PATH}?{urllib.parse.urlencode(params)}"
        request = urllib.request.Request(
            url,
            data=b"",
            method="POST",
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )

        try:
            with opener.open(request, timeout=25) as response:
                status = response.getcode()
                raw = response.read().decode("utf-8", "replace")
        except urllib.error.HTTPError as exc:
            raise WanxiaoError(f"{method} 返回 HTTP {exc.code}") from exc
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            raise WanxiaoError(f"请求 {method} 失败：{exc}") from exc

        if status != 200:
            raise WanxiaoError(f"{method} 返回 HTTP {status}")

        try:
            payload = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise WanxiaoError(f"{method} 返回的不是 JSON") from exc

        if payload.get("code_") not in (0, "0"):
            raise WanxiaoError(
                f"{method} 失败：{payload.get('message_') or payload.get('code_')}"
            )
        if str(payload.get("result_")).lower() != "true":
            raise WanxiaoError(
                f"{method} 失败：{payload.get('message_') or payload.get('result_')}"
            )

        body = payload.get("body")
        if isinstance(body, str):
            try:
                body = json.loads(body)
            except json.JSONDecodeError as exc:
                raise WanxiaoError(f"{method} 的 body 不是 JSON") from exc
        if not isinstance(body, dict):
            raise WanxiaoError(f"{method} 的 body 格式异常")

        result = body.get("result")
        if result is not None and str(result) != "0":
            raise WanxiaoError(
                f"{method} 业务失败：{body.get('message') or result}"
            )
        return body
