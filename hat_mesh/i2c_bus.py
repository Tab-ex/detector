"""Доступ к I2C: smbus2 (pip) или smbus (apt, system Python)."""

from __future__ import annotations

try:
    from smbus2 import SMBus
except ImportError:
    try:
        from smbus import SMBus
    except ImportError as exc:
        raise ImportError(
            "Модуль smbus2 не найден в этом окружении Python.\n"
            "В venv:  pip install smbus2\n"
            "Либо пересоздайте venv с системными пакетами:\n"
            "  python3 -m venv --system-site-packages venv"
        ) from exc

__all__ = ["SMBus"]
