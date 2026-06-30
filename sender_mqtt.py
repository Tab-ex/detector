import paho.mqtt.client as mqtt
import json
import time
from typing import Optional, Dict, Any

from config import MQTT_BROKER, MQTT_PORT, MQTT_TIMEOUT, MQTT_TOPIC_PREFIX
from device_id import get_device_id

_seq_counter = 0


def get_next_seq() -> int:
    global _seq_counter
    _seq_counter += 1
    return _seq_counter


def send_to_server_mqtt_sync(
    payload: Dict[str, Any],
    device_id: Optional[str] = None,
    broker_ip: str = MQTT_BROKER,
    broker_port: int = MQTT_PORT,
    timeout: int = MQTT_TIMEOUT,
) -> bool:
    """Отправляет статус на MQTT сервер (синхронная версия)."""
    if device_id is None:
        device_id = get_device_id()

    if device_id is None:
        print(" Не удалось получить ID устройства")
        return False

    topic = f"{MQTT_TOPIC_PREFIX}/{device_id}/raw"
    mqtt_payload = {
        "id": device_id,
        "value": payload.get("confidence_max", 0),
        "ts": int(time.time() * 1000),
        "state": 1 if payload.get("moped_detected", False) else 0,
        "seq": get_next_seq(),
        "extra": {
            "status": payload.get("status"),
            "confidence_avg": payload.get("confidence_avg"),
            "iteration": payload.get("iteration"),
            "positive_windows": payload.get("positive_windows"),
            "total_windows": payload.get("total_windows"),
        },
    }

    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)

    try:
        print(f" Подключение к MQTT брокеру {broker_ip}:{broker_port}...")
        client.connect(broker_ip, broker_port, keepalive=timeout)

        result = client.publish(
            topic,
            payload=json.dumps(mqtt_payload, ensure_ascii=False),
            qos=1,
            retain=False,
        )

        if result.rc == mqtt.MQTT_ERR_SUCCESS:
            print(" Данные отправлены на сервер")
            print(f"   Топик: {topic}")
            print(f"   ID: {device_id}, Seq: {mqtt_payload['seq']}")
            return True

        print(f" Ошибка публикации: код {result.rc}")
        return False

    except ConnectionRefusedError:
        print(f" Отказано в соединении: {broker_ip}:{broker_port}")
        return False

    except OSError as e:
        print(f" Ошибка сети: {e}")
        return False

    except Exception as e:
        print(f" Ошибка при отправке: {e}")
        return False

    finally:
        client.disconnect()
