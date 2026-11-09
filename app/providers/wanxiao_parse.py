"""完美校园（17wanxiao）智能水电响应的解析逻辑。

单独放一个不依赖 httpx 的模块，方便用真实抓包样本做单元测试。
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from ..models import Reading


class WanxiaoError(RuntimeError):
    pass


def pick_room(
    rooms: list[dict[str, Any]],
    target: str,
    configured_verify: str = "",
) -> dict[str, Any]:
    """从 getbindroom 的结果里挑出目标房间。

    - 配了 roomverify：优先按它匹配；匹配不到也直接用它查详情（接口支持）
    - 没配：按 ECODE_ROOM 的片段匹配，例如 "A栋-101" 会拆成 ["A栋", "101"]
    """
    if configured_verify:
        for room in rooms:
            if room.get("roomverify") == configured_verify:
                return room
        return {"roomverify": configured_verify, "roomfullname": target}

    if not rooms:
        raise WanxiaoError("账号没有绑定任何房间")

    tokens = [token for token in target.replace("_", "-").split("-") if token]
    matches = [
        room
        for room in rooms
        if all(token in (room.get("roomfullname") or "") for token in tokens)
    ]
    if len(matches) == 1:
        return matches[0]
    if not matches:
        names = "、".join(room.get("roomfullname") or "?" for room in rooms)
        raise WanxiaoError(f"没有匹配到房间“{target}”，账号绑定的是：{names}")

    # 多个匹配时优先“学生公寓”，避免选到同名热水/空调表
    preferred = [
        room for room in matches if "学生公寓" in (room.get("roomfullname") or "")
    ]
    return (preferred or matches)[0]


def extract_reading(
    body: dict[str, Any],
    fallback_room: str = "",
    now: datetime | None = None,
) -> Reading:
    """从 h5_getstuindexpage 的 body 里取电表读数。

    modlist 里同时可能有电控和水表：
      - 电控：bussnesstype=0，devicename 类似 "DDS1351电控"
      - 水表：bussnesstype=1，devicename 含 "水表"
    """
    mods = body.get("modlist")
    if not isinstance(mods, list) or not mods:
        raise WanxiaoError("响应里没有 modlist，可能房间号不对")

    electric = [meter for meter in mods if _is_electric(meter)]
    if not electric:
        raise WanxiaoError("响应里没有找到电表")

    meter = electric[0]
    try:
        remaining = float(meter["odd"])
    except (KeyError, TypeError, ValueError) as exc:
        raise WanxiaoError(f"电表读数异常：{meter.get('odd')!r}") from exc

    today = meter.get("todayuse")
    try:
        today_kwh = float(today) if today is not None else None
    except (TypeError, ValueError):
        today_kwh = None

    room = body.get("roomfullname") or fallback_room or ""

    return Reading(
        room=room,
        remaining_kwh=remaining,
        today_kwh=today_kwh,
        fetched_at=now or datetime.now(timezone.utc),
        raw={
            "roomverify": body.get("roomverify"),
            "devicename": meter.get("devicename"),
            "mac": meter.get("mac"),
            "todayuse": today,
            "weekuselist": meter.get("weekuselist", [])[-7:],
        },
    )


def _is_electric(meter: dict[str, Any]) -> bool:
    name = str(meter.get("devicename") or "")
    if "水表" in name:
        return False
    if str(meter.get("bussnesstype")) == "0":
        return True
    return "电" in name and "水" not in name
