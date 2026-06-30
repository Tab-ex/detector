"""Опрос ADS1115 и BMP280 по I2C на Raspberry Pi."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Optional, Sequence

from .i2c_bus import SMBus
from .i2c_ads1115 import DEFAULT_CHANNEL_DIVIDERS, Ads1115, AdsGain
from .i2c_bmp280 import Bmp280

DEFAULT_ADS1115_ADDRESS = 0x48
DEFAULT_BMP280_ADDRESS = 0x76


@dataclass(frozen=True)
class AdsChannelReading:
    channel: str
    voltage_v: float


@dataclass(frozen=True)
class AdsReading:
    channels: tuple[AdsChannelReading, ...] = field(default_factory=tuple)

    def as_dict(self) -> dict[str, float]:
        return {item.channel: item.voltage_v for item in self.channels}


@dataclass(frozen=True)
class BmpReading:
    temperature_c: float
    pressure_pa: float


@dataclass(frozen=True)
class SensorReadings:
    ads: AdsReading
    bmp: BmpReading
    timestamp: float

    def as_dict(self) -> dict[str, Any]:
        return {
            "ads": self.ads.as_dict(),
            "bmp": {
                "t_c": round(self.bmp.temperature_c, 2),
                "p_pa": round(self.bmp.pressure_pa, 0),
            },
        }


class SensorPanel:
    """Доступ к ADS1115 и BMP280 через I2C."""

    def __init__(
        self,
        i2c_bus: int = 1,
        ads1115_address: int = DEFAULT_ADS1115_ADDRESS,
        bmp280_address: Optional[int] = DEFAULT_BMP280_ADDRESS,
        ads_gain: AdsGain | int = AdsGain.FS_4_096V,
        ads_channel_dividers: Sequence[float] = DEFAULT_CHANNEL_DIVIDERS,
    ) -> None:
        self._bus = SMBus(i2c_bus)
        self._ads = Ads1115(
            self._bus,
            address=ads1115_address,
            gain=AdsGain(ads_gain),
            channel_dividers=ads_channel_dividers,
        )
        self._bmp = Bmp280.open_first(
            self._bus,
            preferred_address=bmp280_address,
        )

    def read_ads1115(self) -> AdsReading:
        voltages = self._ads.read_all_voltages()
        channels = tuple(
            AdsChannelReading(channel=name, voltage_v=round(voltage, 2))
            for name, voltage in voltages.items()
        )
        return AdsReading(channels=channels)

    def read_bmp280(self) -> BmpReading:
        temperature_c, pressure_pa = self._bmp.read()
        return BmpReading(temperature_c=temperature_c, pressure_pa=pressure_pa)

    def read_all(self) -> SensorReadings:
        return SensorReadings(
            ads=self.read_ads1115(),
            bmp=self.read_bmp280(),
            timestamp=time.time(),
        )

    def close(self) -> None:
        self._bus.close()

    def __enter__(self) -> "SensorPanel":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()
