"""Разбор и выполнение команд управления RPi из Meshtastic."""

from __future__ import annotations

import re
import subprocess
import threading
from typing import Callable, Iterable, Optional

SERVICE_ACTIONS = frozenset({"start", "stop", "restart", "enable", "disable", "status"})
SERVICE_NAME_RE = re.compile(r"^[a-zA-Z0-9_.-]+$")


def normalize_mesh_id(value: str) -> str:
    return value.strip().lower().lstrip("!")


def parse_command(text: str) -> Optional[tuple[str, str, list[str]]]:
    """mesh_id, команда [, параметры...]."""
    line = text.strip()
    if not line or line.startswith("{"):
        return None

    parts = [part.strip() for part in line.split(",") if part.strip()]
    if len(parts) < 2:
        return None

    mesh_id, command = parts[0], parts[1].lower()
    params = [part.strip() for part in parts[2:] if part.strip()]
    return mesh_id, command, params


class MeshCommandHandler:
    """Выполняет команды, адресованные этому узлу."""

    def __init__(
        self,
        mesh_ids: Iterable[str],
        *,
        resolve_ids: Optional[Callable[[], set[str]]] = None,
    ) -> None:
        self._mesh_ids = {normalize_mesh_id(item) for item in mesh_ids if item.strip()}
        self._resolve_ids = resolve_ids
        self._lock = threading.Lock()

    def accepts(self, mesh_id: str) -> bool:
        target = normalize_mesh_id(mesh_id)
        allowed = set(self._mesh_ids)
        if self._resolve_ids is not None:
            allowed.update(self._resolve_ids())
        return target in allowed

    def handle(self, mesh_id: str, command: str, params: list[str]) -> Optional[str]:
        if not self.accepts(mesh_id):
            return None

        with self._lock:
            if command == "reboot":
                return self._reboot()
            if command == "service":
                return self._service(params)
            return f"err:unknown command {command}"

    def _reboot(self) -> str:
        subprocess.Popen(
            ["sudo", "reboot"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return "ok:reboot scheduled"

    def _service(self, params: list[str]) -> str:
        if len(params) < 2:
            return "err:usage service,NAME,ACTION"

        name, action = params[0], params[1].lower()
        if not SERVICE_NAME_RE.match(name):
            return f"err:invalid service name {name}"
        if action not in SERVICE_ACTIONS:
            return f"err:invalid action {action}"

        try:
            result = subprocess.run(
                ["sudo", "service", name, action],
                capture_output=True,
                text=True,
                timeout=30,
                check=False,
            )
        except subprocess.TimeoutExpired:
            return f"err:service {name} {action} timeout"
        except OSError as exc:
            return f"err:{exc}"

        output = (result.stdout or result.stderr or "").strip()
        if len(output) > 120:
            output = output[:117] + "..."

        if result.returncode == 0:
            if output:
                return f"ok:service {name} {action}: {output}"
            return f"ok:service {name} {action}"

        if output:
            return f"err:service {name} {action} rc={result.returncode}: {output}"
        return f"err:service {name} {action} rc={result.returncode}"
