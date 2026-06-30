"""Маршрутизация результата распознавания: MQTT или Meshtastic (HAT)."""

from __future__ import annotations

import time
from typing import Any, Dict

from config import HAT, I2C_BUS, MESSAGE_TIMEOUT_SEC
from sender_mqtt import send_to_server_mqtt_sync


class ResultSender:
    """Отправка с throttling для CLEAN в режиме HAT."""

    def __init__(self) -> None:
        self._last_clean_send = 0.0
        self._mesh_sender = None
        self._sensor_panel = None

        if HAT:
            from hat_mesh.meshtastic_sender import MeshtasticSender
            from hat_mesh.sensor_panel import SensorPanel

            self._mesh_sender = MeshtasticSender()
            self._sensor_panel = SensorPanel(i2c_bus=I2C_BUS)
            print(" ResultSender: режим Meshtastic + датчики")
        else:
            print(" ResultSender: режим MQTT")

    @property
    def mesh_sender(self):
        return self._mesh_sender

    def should_send(self, is_detected: bool) -> bool:
        if not HAT:
            return True
        if is_detected:
            return True
        return (time.time() - self._last_clean_send) >= MESSAGE_TIMEOUT_SEC

    def send(self, payload: Dict[str, Any], is_detected: bool) -> bool:
        if not self.should_send(is_detected):
            print(
                f" CLEAN: пропуск отправки "
                f"(следующая через {self._seconds_until_clean_send():.0f} сек)"
            )
            return False

        if HAT:
            ok = self._send_mesh(payload)
        else:
            ok = send_to_server_mqtt_sync(payload)

        if ok and not is_detected:
            self._last_clean_send = time.time()
        return ok

    def _seconds_until_clean_send(self) -> float:
        elapsed = time.time() - self._last_clean_send
        return max(0.0, MESSAGE_TIMEOUT_SEC - elapsed)

    def _send_mesh(self, payload: Dict[str, Any]) -> bool:
        assert self._mesh_sender is not None
        assert self._sensor_panel is not None

        try:
            sensors = self._sensor_panel.read_all().as_dict()
        except Exception as exc:
            print(f" Ошибка опроса датчиков: {exc}")
            sensors = None

        try:
            return self._mesh_sender.send_detection(payload, sensors)
        except Exception as exc:
            print(f" Ошибка отправки Meshtastic: {exc}")
            return False

    def close(self) -> None:
        if self._mesh_sender is not None:
            self._mesh_sender.close()
        if self._sensor_panel is not None:
            self._sensor_panel.close()
