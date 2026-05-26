#!/usr/bin/env python3
"""Code RED peer command relay for CodeRED_PeerCompanion.asi.

The server is intentionally small: it accepts JSON command packets over TCP,
writes the newest command to data/codered/link/peer_command_inbox.json, and
keeps a text log. The host ASI consumes commands only after F11 enables peer
control in-game.
"""
from __future__ import annotations

import argparse
import json
import socketserver
import threading
import time
import uuid
from pathlib import Path

DEFAULT_PORT = 47667
ALLOWED_COMMANDS = {
    "spawn_companion",
    "despawn_companion",
    "follow_player",
    "idle",
    "friendly",
    "neutral",
    "hostile",
    "guard_player",
    "stop_combat",
    "teleport_to_player",
    "set_invincible_true",
    "set_invincible_false",
    "give_basic_weapon",
    "clear_weapons",
    "heartbeat",
    "request_host_status",
}


def ms() -> int:
    return int(time.time() * 1000)


def atomic_write(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    tmp.replace(path)


def append_log(path: Path, line: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(f"{ms()} {line}\n")


class RelayState:
    def __init__(self, game_root: Path):
        self.lock = threading.RLock()
        self.game_root = game_root
        self.link_dir = game_root / "data" / "codered" / "link"
        self.inbox = self.link_dir / "peer_command_inbox.json"
        self.peer_log = self.link_dir / "peer_log.txt"
        self.host_status = self.link_dir / "host_status.json"
        self.last_command: dict | None = None

    def write_command(self, peer_id: str, command: str, args: dict | None = None) -> dict:
        if command not in ALLOWED_COMMANDS:
            raise ValueError(f"unsupported command: {command}")
        payload = {
            "version": 1,
            "command_id": f"{peer_id}_{ms()}_{uuid.uuid4().hex[:8]}",
            "peer_id": peer_id,
            "time_ms": ms(),
            "command": command,
            "args": args or {},
        }
        with self.lock:
            atomic_write(self.inbox, payload)
            self.last_command = payload
            append_log(self.peer_log, f"command peer={peer_id} command={command} id={payload['command_id']}")
        return payload

    def read_host_status(self) -> dict:
        if not self.host_status.exists():
            return {"available": False, "path": str(self.host_status)}
        try:
            data = json.loads(self.host_status.read_text(encoding="utf-8"))
            data["available"] = True
            return data
        except Exception as exc:
            return {"available": False, "error": str(exc), "path": str(self.host_status)}


class Handler(socketserver.StreamRequestHandler):
    def handle(self) -> None:
        state: RelayState = self.server.state  # type: ignore[attr-defined]
        peer_id = f"{self.client_address[0]}:{self.client_address[1]}"
        append_log(state.peer_log, f"connect peer={peer_id}")
        for raw in self.rfile:
            try:
                packet = json.loads(raw.decode("utf-8", errors="replace"))
                command = str(packet.get("command") or "")
                peer = str(packet.get("peer_id") or peer_id)
                if command == "request_host_status":
                    response = {"ok": True, "type": "host_status", "host_status": state.read_host_status()}
                else:
                    written = state.write_command(peer, command, packet.get("args") or {})
                    response = {"ok": True, "type": "command_written", "command_id": written["command_id"]}
            except Exception as exc:
                response = {"ok": False, "error": str(exc)}
            self.wfile.write((json.dumps(response, separators=(",", ":")) + "\n").encode("utf-8"))
            self.wfile.flush()
        append_log(state.peer_log, f"disconnect peer={peer_id}")


class ThreadingServer(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True


def serve(game_root: Path, bind: str, port: int) -> None:
    state = RelayState(game_root)
    state.link_dir.mkdir(parents=True, exist_ok=True)
    with ThreadingServer((bind, port), Handler) as server:
        server.state = state  # type: ignore[attr-defined]
        print(f"CodeRED_Link_Server listening on {bind}:{port}")
        print(f"Game root: {game_root}")
        print(f"Inbox: {state.inbox}")
        append_log(state.peer_log, f"server_start bind={bind} port={port} game_root={game_root}")
        try:
            server.serve_forever(poll_interval=0.25)
        except KeyboardInterrupt:
            print("\nStopping CodeRED_Link_Server")
        finally:
            append_log(state.peer_log, "server_stop")


def send(host: str, port: int, peer_id: str, command: str) -> dict:
    import socket

    packet = {"version": 1, "peer_id": peer_id, "time_ms": ms(), "command": command, "args": {}}
    with socket.create_connection((host, port), timeout=5) as sock:
        sock.sendall((json.dumps(packet, separators=(",", ":")) + "\n").encode("utf-8"))
        data = b""
        while not data.endswith(b"\n"):
            chunk = sock.recv(4096)
            if not chunk:
                break
            data += chunk
    return json.loads(data.decode("utf-8", errors="replace")) if data else {"ok": False, "error": "no response"}


def main() -> int:
    parser = argparse.ArgumentParser(description="Code RED peer companion command relay")
    sub = parser.add_subparsers(dest="cmd", required=True)
    serve_p = sub.add_parser("serve")
    serve_p.add_argument("--game-root", default=".", help="Folder containing RDR.exe")
    serve_p.add_argument("--bind", default="127.0.0.1")
    serve_p.add_argument("--port", type=int, default=DEFAULT_PORT)
    send_p = sub.add_parser("send")
    send_p.add_argument("command", choices=sorted(ALLOWED_COMMANDS))
    send_p.add_argument("--host", default="127.0.0.1")
    send_p.add_argument("--port", type=int, default=DEFAULT_PORT)
    send_p.add_argument("--peer-id", default="peer_1")
    args = parser.parse_args()
    if args.cmd == "serve":
        serve(Path(args.game_root).resolve(), args.bind, args.port)
        return 0
    print(json.dumps(send(args.host, args.port, args.peer_id, args.command), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
