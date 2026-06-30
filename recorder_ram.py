import subprocess
import numpy as np

from config import (
    AUDIO_TARGET,
    AUDIO_CHANNELS,
    AUDIO_RATE,
    AUDIO_FORMAT,
    RECORD_DURATION_SEC,
)

_BYTES_PER_SAMPLE = {"s32": 4, "s16": 2, "s24": 3, "s8": 1}


def record_5s_to_ram():
    """
    Записывает аудио с микрофона напрямую в RAM через pw-record в raw режиме.
    Автоматически обрезает лишние байты (если есть).
    Возвращает: (numpy_array, sample_rate) или (None, None) при ошибке.
    """
    cmd = [
        "pw-record",
        "--target", AUDIO_TARGET,
        "--channels", AUDIO_CHANNELS,
        "--rate", str(AUDIO_RATE),
        "--format", AUDIO_FORMAT,
        "--raw",
        "-",
    ]

    bytes_per_sample = _BYTES_PER_SAMPLE.get(AUDIO_FORMAT, 4)
    bytes_per_second = AUDIO_RATE * bytes_per_sample
    expected_bytes = RECORD_DURATION_SEC * bytes_per_second

    try:
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        raw_data = proc.stdout.read(expected_bytes + bytes_per_second)

        proc.terminate()
        try:
            proc.wait(timeout=1)
        except subprocess.TimeoutExpired:
            proc.kill()

    except Exception as e:
        print(f"❌ Ошибка pw-record: {e}")
        return None, None

    if not raw_data:
        return None, None

    if len(raw_data) > expected_bytes:
        raw_data = raw_data[:expected_bytes]
    elif len(raw_data) < expected_bytes:
        print(f"⚠️  Получено меньше данных: {len(raw_data)} байт, ожидалось {expected_bytes}")
        return None, None

    samples = np.frombuffer(raw_data, dtype=np.int32).astype(np.float32) / (2**31)
    return samples, AUDIO_RATE
