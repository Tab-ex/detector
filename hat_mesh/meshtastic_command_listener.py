"""Приём текстовых команд из канала Meshtastic (telemetry)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from pubsub import pub

from config import MESH_CHANNEL, MESH_CMD_ENABLED, MESH_NODE_ID
from device_id import get_device_id
from hat_mesh.mesh_command_handler import MeshCommandHandler, parse_command

if TYPE_CHECKING:
    from hat_mesh.meshtastic_sender import MeshtasticSender


class MeshtasticCommandListener:
    """Фоновый обработчик команд на канале telemetry."""

    def __init__(self, mesh_sender: "MeshtasticSender") -> None:
        self._sender = mesh_sender
        self._channel_index = MESH_CHANNEL
        self._running = False
        configured_ids = [
            item.strip()
            for item in MESH_NODE_ID.split(",")
            if item.strip()
        ]
        device_id = get_device_id()
        if device_id:
            configured_ids.append(device_id)
        self._handler = MeshCommandHandler(
            configured_ids,
            resolve_ids=self._local_mesh_ids,
        )

    def start(self) -> None:
        if self._running or not MESH_CMD_ENABLED:
            return

        self._sender.connect()
        pub.subscribe(self._on_receive, "meshtastic.receive.text")
        self._running = True
        print(
            f" Meshtastic: слушаем команды на канале {self._channel_index} "
            f"(ids={self._known_ids_label()})"
        )

    def stop(self) -> None:
        if not self._running:
            return
        pub.unsubscribe(self._on_receive, "meshtastic.receive.text")
        self._running = False

    def _known_ids_label(self) -> str:
        ids = set(self._handler._mesh_ids)
        ids.update(self._local_mesh_ids())
        return ",".join(sorted(ids)) or "auto"

    def _local_mesh_ids(self) -> set[str]:
        interface = self._sender.interface
        if interface is None or not getattr(interface, "myInfo", None):
            return set()

        ids: set[str] = set()
        my_num = interface.myInfo.my_node_num
        node = interface.nodesByNum.get(my_num, {})
        user = node.get("user", {})
        for key in ("id", "shortName", "longName"):
            value = user.get(key)
            if value:
                ids.add(str(value).lower().lstrip("!"))
        return ids

    def _on_receive(self, packet: dict, interface) -> None:
        if not self._running or interface is not self._sender.interface:
            return

        if packet.get("channel") != self._channel_index:
            return

        my_num = interface.myInfo.my_node_num
        if packet.get("from") == my_num:
            return

        decoded = packet.get("decoded") or {}
        text = decoded.get("text")
        if not text:
            return

        parsed = parse_command(text)
        if parsed is None:
            return

        mesh_id, command, params = parsed
        reply = self._handler.handle(mesh_id, command, params)
        if reply is None:
            return

        from_id = packet.get("fromId", "?")
        print(f" Meshtastic: команда от {from_id}: {mesh_id},{command},{params}")
        print(f" Meshtastic: ответ: {reply}")

        try:
            self._sender.send_text(reply)
        except Exception as exc:
            print(f" Meshtastic: не удалось отправить ответ: {exc}")
