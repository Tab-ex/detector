"""Отправка результата распознавания через Meshtastic."""

from __future__ import annotations

import json
import re
import threading
import time
from typing import Any, Dict, List, Optional

from config import MESH_CHANNEL, MESH_HOST, MESH_PORT
from device_id import get_device_id

MAX_JSON_LEN = 200

_seq_counter = 0


def get_next_seq() -> int:
    global _seq_counter
    _seq_counter += 1
    return _seq_counter


def _ads_to_channels(ads: dict[str, Any]) -> List[float]:
    """A0..A3 -> [v0, v1, v2, v3] без буквенных ключей."""
    values: list[tuple[int, float]] = []
    for key, voltage in ads.items():
        match = re.fullmatch(r"A?(\d+)", str(key), re.IGNORECASE)
        if not match:
            continue
        values.append((int(match.group(1)), float(voltage)))

    values.sort(key=lambda item: item[0])
    return [voltage for _, voltage in values]


def build_detection_payload(
    detection: Dict[str, Any],
    sensors: Optional[Dict[str, Any]] = None,
    device_id: Optional[str] = None,
) -> dict[str, Any]:
    """JSON в формате id/value/seq + датчики."""
    payload: dict[str, Any] = {
        "id": device_id or get_device_id() or "",
        "value": round(float(detection.get("confidence_max", 0)), 3),
        "ts": int(time.time() * 1000),
        "st": 1 if detection.get("moped_detected") else 0,
        "seq": get_next_seq(),
    }
    if sensors:
        ads = sensors.get("ads")
        if ads:
            payload["ads"] = _ads_to_channels(ads)
        bmp = sensors.get("bmp")
        if bmp:
            payload["bmp"] = bmp
    return payload


def payload_to_json(payload: dict[str, Any]) -> str:
    return json.dumps(payload, separators=(",", ":"), ensure_ascii=True)


class MeshtasticSender:
    """Отправка JSON через TCP API локального meshtasticd."""

    def __init__(
        self,
        host: str = MESH_HOST,
        port: int = MESH_PORT,
        channel_index: int = MESH_CHANNEL,
    ) -> None:
        self._host = host
        self._port = port
        self._channel_index = channel_index
        self._interface = None
        self._lock = threading.Lock()

    @property
    def interface(self):
        return self._interface

    def connect(self) -> None:
        from meshtastic.tcp_interface import TCPInterface

        self._interface = TCPInterface(hostname=self._host, portNumber=self._port)
        print(f" Meshtastic: подключено к {self._host}:{self._port}")

    def send_detection(
        self,
        detection: Dict[str, Any],
        sensors: Optional[Dict[str, Any]] = None,
    ) -> bool:
        payload = build_detection_payload(detection, sensors)
        text = payload_to_json(payload)

        if len(text) > MAX_JSON_LEN:
            compact = build_detection_payload(detection)
            text = payload_to_json(compact)
            print(
                f" Meshtastic: JSON с датчиками {len(payload_to_json(payload))} байт, "
                f"отправляем без датчиков ({len(text)} байт)"
            )

        return self.send_text(text, channel_index=self._channel_index)

    def send_text(
        self,
        text: str,
        channel_index: Optional[int] = None,
    ) -> bool:
        if self._interface is None:
            self.connect()
        assert self._interface is not None

        index = self._channel_index if channel_index is None else channel_index
        with self._lock:
            self._interface.sendText(text, channelIndex=index)
        print(f" Meshtastic: отправлено {text}")
        return True

    def close(self) -> None:
        if self._interface is not None:
            self._interface.close()
            self._interface = None

    def __enter__(self) -> "MeshtasticSender":
        self.connect()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()
