import os
from pathlib import Path
from typing import Optional

_PREFERRED_INTERFACES = ("eth0", "wlan0", "end0", "enp0s31f6")


def get_mac_address(iface: Optional[str] = None) -> Optional[str]:
    """MAC-адрес интерфейса без двоеточий (нижний регистр)."""
    if iface:
        path = Path(f"/sys/class/net/{iface}/address")
        if path.exists():
            mac = path.read_text().strip()
            if _is_valid_mac(mac):
                return mac.replace(":", "").lower()
        return None

    for name in _PREFERRED_INTERFACES:
        mac = get_mac_address(name)
        if mac:
            return mac

    net_dir = Path("/sys/class/net")
    if not net_dir.exists():
        return None

    for entry in sorted(net_dir.iterdir()):
        if entry.name == "lo":
            continue
        path = entry / "address"
        if not path.exists():
            continue
        mac = path.read_text().strip()
        if _is_valid_mac(mac):
            return mac.replace(":", "").lower()

    return None


def _is_valid_mac(mac: str) -> bool:
    return bool(mac) and mac != "00:00:00:00:00:00"


def get_device_id() -> Optional[str]:
    """ID устройства: DEVICE_ID из .env или MAC без двоеточий."""
    override = os.getenv("DEVICE_ID", "").strip()
    if override:
        return override.replace(":", "").lower()
    return get_mac_address()
