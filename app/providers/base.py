from __future__ import annotations

from typing import Protocol

from ..models import Reading


class Provider(Protocol):
    """数据源接口：实现 fetch() 即可接入新的电费系统。"""

    name: str

    async def fetch(self) -> Reading:
        ...
