"""ADS1115 через smbus2 (без adafruit-blinka)."""

from __future__ import annotations

import time
from enum import IntEnum
from typing import Sequence

from .i2c_bus import SMBus

DEFAULT_CHANNEL_DIVIDERS = (2.0, 2.0, 11.0, 11.0)


class AdsGain(IntEnum):
    FS_6_144V = 0
    FS_4_096V = 1
    FS_2_048V = 2
    FS_1_024V = 3
    FS_0_512V = 4
    FS_0_256V = 5


_FS_VOLTAGE = {
    AdsGain.FS_6_144V: 6.144,
    AdsGain.FS_4_096V: 4.096,
    AdsGain.FS_2_048V: 2.048,
    AdsGain.FS_1_024V: 1.024,
    AdsGain.FS_0_512V: 0.512,
    AdsGain.FS_0_256V: 0.256,
}

_REG_CONVERSION = 0x00
_REG_CONFIG = 0x01
_CONFIG_COMP_DISABLED = 0x0003
_CONFIG_DR_128SPS = 0x0080
_CONFIG_MODE_SINGLE = 0x0100


class Ads1115:
    def __init__(
        self,
        bus: SMBus,
        address: int = 0x48,
        gain: AdsGain = AdsGain.FS_4_096V,
        channel_dividers: Sequence[float] = DEFAULT_CHANNEL_DIVIDERS,
    ) -> None:
        dividers = tuple(float(x) for x in channel_dividers)
        if len(dividers) != 4:
            raise ValueError("channel_dividers должен содержать 4 коэффициента (A0..A3)")

        self._bus = bus
        self._address = address
        self._gain = AdsGain(gain)
        self._fs_voltage = _FS_VOLTAGE[self._gain]
        self._channel_dividers = dividers

    def _config_word(self, channel: int) -> int:
        os_bit = 0x8000
        mux = (0x4 + channel) << 12
        pga = int(self._gain) << 9
        return (
            os_bit
            | mux
            | pga
            | _CONFIG_MODE_SINGLE
            | _CONFIG_DR_128SPS
            | _CONFIG_COMP_DISABLED
        )

    def _wait_conversion(self) -> None:
        for _ in range(200):
            data = self._bus.read_i2c_block_data(self._address, _REG_CONFIG, 2)
            if data[0] & 0x80:
                return
            time.sleep(0.001)
        time.sleep(0.01)

    def read_raw(self, channel: int) -> int:
        if channel not in range(4):
            raise ValueError("channel must be 0..3")

        config = self._config_word(channel)
        self._bus.write_i2c_block_data(
            self._address,
            _REG_CONFIG,
            [(config >> 8) & 0xFF, config & 0xFF],
        )
        self._wait_conversion()

        data = self._bus.read_i2c_block_data(self._address, _REG_CONVERSION, 2)
        raw = (data[0] << 8) | data[1]
        if raw & 0x8000:
            raw -= 1 << 16
        return raw

    def read_adc_voltage(self, channel: int) -> float:
        raw = self.read_raw(channel)
        if raw < 0:
            raw = 0
        return (raw / 32768.0) * self._fs_voltage

    def read_voltage(self, channel: int) -> float:
        return self.read_adc_voltage(channel) * self._channel_dividers[channel]

    def read_all_voltages(self) -> dict[str, float]:
        return {f"A{i}": self.read_voltage(i) for i in range(4)}
