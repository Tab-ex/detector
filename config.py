import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent / ".env")


def _env_bool(key: str, default: bool) -> bool:
    value = os.getenv(key)
    if value is None:
        return default
    return value.strip().lower() in ("1", "true", "yes", "on")


def _env_int(key: str, default: int) -> int:
    value = os.getenv(key)
    return int(value) if value is not None else default


def _env_float(key: str, default: float) -> float:
    value = os.getenv(key)
    return float(value) if value is not None else default


# Детектор
MODEL_PATH = os.getenv("MODEL_PATH", "my_model_1.pkl")
SERVER_URL = os.getenv("SERVER_URL", "http://192.168.1.100:5000/api/detect")
CONFIDENCE_THRESHOLD = _env_float("CONFIDENCE_THRESHOLD", 0.75)
LOOP_DELAY = _env_int("LOOP_DELAY", 1)
SAMPLE_RATE = _env_int("SAMPLE_RATE", 48000)
WINDOW_SIZE = _env_float("WINDOW_SIZE", 1.0)

# Метрики
METRICS_ENABLED = _env_bool("METRICS_ENABLED", True)
METRICS_USER_ID = os.getenv("METRICS_USER_ID", "user_001")
METRICS_FILE = os.getenv("METRICS_FILE", "metrics_log.jsonl")

# Запись звука
AUDIO_TARGET = os.getenv(
    "AUDIO_TARGET",
    "alsa_input.usb-GeneralPlus_USB_Audio_Device-00.mono-fallback",
)
AUDIO_CHANNELS = os.getenv("AUDIO_CHANNELS", "1")
AUDIO_RATE = _env_int("AUDIO_RATE", 48000)
AUDIO_FORMAT = os.getenv("AUDIO_FORMAT", "s32")
RECORD_DURATION_SEC = _env_int("RECORD_DURATION_SEC", 5)

# MQTT
MQTT_BROKER = os.getenv("MQTT_BROKER", "172.17.3.237")
MQTT_PORT = _env_int("MQTT_PORT", 1883)
MQTT_TIMEOUT = _env_int("MQTT_TIMEOUT", 5)
MQTT_TOPIC_PREFIX = os.getenv("MQTT_TOPIC_PREFIX", "sensors")

# HAT / Meshtastic
HAT = _env_bool("HAT", False)
MESSAGE_TIMEOUT_SEC = _env_int("MESSAGE_TIMEOUT_SEC", 60)
MESH_CHANNEL = _env_int("MESH_CHANNEL", 1)
MESH_ENCRYPTION_KEY = os.getenv("MESH_ENCRYPTION_KEY", "")
MESH_HOST = os.getenv("MESH_HOST", "127.0.0.1")
MESH_PORT = _env_int("MESH_PORT", 4403)
MESH_NODE_ID = os.getenv("MESH_NODE_ID", "")
MESH_CMD_ENABLED = _env_bool("MESH_CMD_ENABLED", True)
I2C_BUS = _env_int("I2C_BUS", 1)
