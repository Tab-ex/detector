"""BMP280 через smbus2 (без adafruit-blinka)."""

from __future__ import annotations

import time
from typing import Optional

from .i2c_bus import SMBus

try:
    from smbus2 import i2c_msg
except ImportError:
    i2c_msg = None  # type: ignore[assignment,misc]

_REG_CHIP_ID = 0xD0
_REG_RESET = 0xE0
_REG_STATUS = 0xF3
_REG_CALIB = 0x88
_REG_CTRL_MEAS = 0xF4
_REG_CONFIG = 0xF5
_REG_PRESS = 0xF7

_CHIP_ID = 0x58
_CTRL_MEAS_FORCED = 0x25
BMP280_ADDRESSES = (0x76, 0x77)


class Bmp280:
    def __init__(
        self,
        bus: SMBus,
        address: int = 0x76,
        sea_level_pressure_pa: Optional[float] = None,
    ) -> None:
        self._bus = bus
        self._address = address
        self._sea_level_pressure_pa = sea_level_pressure_pa

        if self._bus.read_byte_data(self._address, _REG_CHIP_ID) != _CHIP_ID:
            raise ValueError(f"устройство 0x{address:02x} не BMP280")

        self._bus.write_byte_data(self._address, _REG_RESET, 0xB6)
        time.sleep(0.01)
        self._load_calibration()
        self._bus.write_byte_data(self._address, _REG_CONFIG, 0x00)
        self._t_fine = 0
        # Первое измерение после reset часто некорректно — сбрасываем.
        self.read()

    @classmethod
    def open_first(
        cls,
        bus: SMBus,
        preferred_address: Optional[int] = None,
        sea_level_pressure_pa: Optional[float] = None,
    ) -> "Bmp280":
        candidates: list[int] = []
        if preferred_address is not None:
            candidates.append(preferred_address)
        candidates.extend(addr for addr in BMP280_ADDRESSES if addr not in candidates)

        last_error: Exception | None = None
        for address in candidates:
            try:
                return cls(bus, address, sea_level_pressure_pa)
            except (ValueError, OSError) as exc:
                last_error = exc

        raise RuntimeError(
            "BMP280 не найден на шине I2C (ожидаются адреса 0x76 или 0x77)."
        ) from last_error

    def _load_calibration(self) -> None:
        cal = self._bus.read_i2c_block_data(self._address, _REG_CALIB, 24)

        def u16(offset: int) -> int:
            return cal[offset] | (cal[offset + 1] << 8)

        def s16(offset: int) -> int:
            value = u16(offset)
            return value - 65536 if value >= 32768 else value

        self._t1 = u16(0)
        self._t2 = s16(2)
        self._t3 = s16(4)
        self._p1 = u16(6)
        self._p2 = s16(8)
        self._p3 = s16(10)
        self._p4 = s16(12)
        self._p5 = s16(14)
        self._p6 = s16(16)
        self._p7 = s16(18)
        self._p8 = s16(20)
        self._p9 = s16(22)

    def _wait_measurement(self) -> None:
        """Ждать завершения forced-измерения (status bit 3)."""
        # После записи CTRL_MEAS бит measuring может быть ещё 0 — не выходим сразу.
        start_deadline = time.monotonic() + 0.05
        while time.monotonic() < start_deadline:
            if self._bus.read_byte_data(self._address, _REG_STATUS) & 0x08:
                break
            time.sleep(0.001)

        done_deadline = time.monotonic() + 0.1
        while time.monotonic() < done_deadline:
            if (self._bus.read_byte_data(self._address, _REG_STATUS) & 0x08) == 0:
                return
            time.sleep(0.002)

        time.sleep(0.01)

    def _read_raw(self) -> tuple[int, int]:
        if i2c_msg is not None:
            write = i2c_msg.write(self._address, [_REG_PRESS])
            read = i2c_msg.read(self._address, 6)
            self._bus.i2c_rdwr(write, read)
            data = list(read)
        else:
            data = self._bus.read_i2c_block_data(self._address, _REG_PRESS, 6)

        press_raw = (data[0] << 12) | (data[1] << 4) | (data[2] >> 4)
        temp_raw = (data[3] << 12) | (data[4] << 4) | (data[5] >> 4)
        return press_raw, temp_raw

    def _compensate_temperature(self, raw: int) -> float:
        var1 = (raw / 16384.0 - self._t1 / 1024.0) * self._t2
        var2 = ((raw / 131072.0 - self._t1 / 8192.0) ** 2) * self._t3
        self._t_fine = var1 + var2
        return self._t_fine / 5120.0

    def _compensate_pressure(self, raw: int) -> float:
        var1 = self._t_fine / 2.0 - 64000.0
        var2 = var1 * var1 * self._p6 / 32768.0
        var2 = var2 + var1 * self._p5 * 2.0
        var2 = var2 / 4.0 + self._p4 * 65536.0
        var1 = (self._p3 * var1 * var1 / 524288.0 + self._p2 * var1) / 524288.0
        var1 = (1.0 + var1 / 32768.0) * self._p1
        if var1 == 0.0:
            return 0.0
        pressure = 1048576.0 - raw
        pressure = (pressure - var2 / 4096.0) * 6250.0 / var1
        var1 = self._p9 * pressure * pressure / 2147483648.0
        var2 = pressure * self._p8 / 32768.0
        return pressure + (var1 + var2 + self._p7) / 16.0

    def read(self) -> tuple[float, float]:
        self._bus.write_byte_data(self._address, _REG_CTRL_MEAS, _CTRL_MEAS_FORCED)
        self._wait_measurement()
        press_raw, temp_raw = self._read_raw()
        temperature_c = self._compensate_temperature(temp_raw)
        pressure_pa = self._compensate_pressure(press_raw)
        return temperature_c, pressure_pa
