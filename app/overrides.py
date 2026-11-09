from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any

ALLOWED_KEYS = {"threshold_kwh", "smtp_pass"}


def load_overrides(path: str) -> dict[str, Any]:
    """读取 Web 设置页写入的覆盖值；文件不存在/损坏时返回空字典。"""
    file = Path(path)
    if not file.exists():
        return {}
    try:
        data = json.loads(file.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    if not isinstance(data, dict):
        return {}
    return {key: data[key] for key in ALLOWED_KEYS if key in data}


def save_overrides(path: str, updates: dict[str, Any]) -> dict[str, Any]:
    """原子写入覆盖值，保留未修改的键。"""
    file = Path(path)
    current = load_overrides(path)
    current.update(
        {key: value for key, value in updates.items() if key in ALLOWED_KEYS}
    )

    file.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(
        dir=str(file.parent), prefix=".overrides-", suffix=".tmp"
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(current, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
        os.chmod(tmp_name, 0o600)
        os.replace(tmp_name, file)
    finally:
        if os.path.exists(tmp_name):
            os.unlink(tmp_name)
    return current
