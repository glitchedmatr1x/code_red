#!/usr/bin/env python3
"""Small GUI command sender for CodeRED_PeerCompanion."""
from __future__ import annotations

import json
import socket
import subprocess
import sys
import time
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, ttk

APP_DIR = Path(__file__).resolve().parent
DEFAULT_PORT = 47667
COMMANDS = [
    ("Spawn Companion", "spawn_companion"),
    ("Despawn Companion", "despawn_companion"),
    ("Follow Player", "follow_player"),
    ("Idle", "idle"),
    ("Friendly", "friendly"),
    ("Neutral", "neutral"),
    ("Hostile", "hostile"),
    ("Guard Player", "guard_player"),
    ("Stop Combat", "stop_combat"),
    ("Teleport Near Player", "teleport_to_player"),
    ("Invincible On", "set_invincible_true"),
    ("Invincible Off", "set_invincible_false"),
    ("Give Basic Weapon", "give_basic_weapon"),
    ("Clear Weapons", "clear_weapons"),
]


def ms() -> int:
    return int(time.time() * 1000)


class PeerApp:
    def __init__(self) -> None:
        self.root = tk.Tk()
        self.root.title("Code RED Peer Companion")
        self.root.geometry("620x560")
        self.server_proc: subprocess.Popen | None = None

        self.game_root = tk.StringVar(value=str(APP_DIR))
        self.host = tk.StringVar(value="127.0.0.1")
        self.port = tk.IntVar(value=DEFAULT_PORT)
        self.peer_id = tk.StringVar(value="peer_1")
        self.status = tk.StringVar(value="Disconnected")

        self.build()
        self.root.protocol("WM_DELETE_WINDOW", self.close)

    def build(self) -> None:
        pad = {"padx": 8, "pady": 5}
        top = ttk.LabelFrame(self.root, text="Connection")
        top.pack(fill="x", padx=10, pady=8)
        ttk.Label(top, text="Game root").grid(row=0, column=0, sticky="w", **pad)
        ttk.Entry(top, textvariable=self.game_root, width=62).grid(row=0, column=1, columnspan=3, sticky="ew", **pad)
        ttk.Label(top, text="Host").grid(row=1, column=0, sticky="w", **pad)
        ttk.Entry(top, textvariable=self.host, width=18).grid(row=1, column=1, sticky="w", **pad)
        ttk.Label(top, text="Port").grid(row=1, column=2, sticky="w", **pad)
        ttk.Entry(top, textvariable=self.port, width=8).grid(row=1, column=3, sticky="w", **pad)
        ttk.Label(top, text="Peer ID").grid(row=2, column=0, sticky="w", **pad)
        ttk.Entry(top, textvariable=self.peer_id, width=18).grid(row=2, column=1, sticky="w", **pad)
        ttk.Button(top, text="Start Local Server", command=self.start_server).grid(row=3, column=0, sticky="ew", **pad)
        ttk.Button(top, text="Connect Test", command=self.connect_test).grid(row=3, column=1, sticky="ew", **pad)
        ttk.Button(top, text="Disconnect", command=self.stop_server).grid(row=3, column=2, sticky="ew", **pad)
        ttk.Label(top, textvariable=self.status).grid(row=3, column=3, sticky="w", **pad)

        body = ttk.LabelFrame(self.root, text="Companion Commands")
        body.pack(fill="both", expand=True, padx=10, pady=8)
        for i, (label, command) in enumerate(COMMANDS):
            ttk.Button(body, text=label, command=lambda c=command: self.send_command(c)).grid(
                row=i // 2, column=i % 2, sticky="ew", padx=8, pady=5
            )
        body.columnconfigure(0, weight=1)
        body.columnconfigure(1, weight=1)

        debug = ttk.LabelFrame(self.root, text="Debug")
        debug.pack(fill="x", padx=10, pady=8)
        ttk.Button(debug, text="Send Heartbeat", command=lambda: self.send_command("heartbeat")).pack(side="left", padx=8, pady=5)
        ttk.Button(debug, text="Request Host Status", command=lambda: self.send_command("request_host_status")).pack(side="left", padx=8, pady=5)

        self.log = tk.Text(self.root, height=8, wrap="word")
        self.log.pack(fill="both", expand=False, padx=10, pady=8)

    def append(self, text: str) -> None:
        self.log.insert("end", text + "\n")
        self.log.see("end")

    def start_server(self) -> None:
        if self.server_proc and self.server_proc.poll() is None:
            self.append("Server already running")
            return
        script = APP_DIR / "CodeRED_Link_Server.py"
        cmd = [
            sys.executable,
            str(script),
            "serve",
            "--game-root",
            self.game_root.get(),
            "--bind",
            self.host.get(),
            "--port",
            str(self.port.get()),
        ]
        self.server_proc = subprocess.Popen(cmd, cwd=str(APP_DIR))
        self.status.set("Server started")
        self.append("Started local server")

    def stop_server(self) -> None:
        if self.server_proc and self.server_proc.poll() is None:
            self.server_proc.terminate()
            self.append("Stopped local server")
        self.status.set("Disconnected")

    def connect_test(self) -> None:
        try:
            response = self.send_packet("heartbeat")
            self.status.set("Connected" if response.get("ok") else "Error")
            self.append(json.dumps(response, indent=2))
        except Exception as exc:
            self.status.set("Connect failed")
            self.append(f"Connect failed: {exc}")

    def send_packet(self, command: str) -> dict:
        packet = {
            "version": 1,
            "peer_id": self.peer_id.get(),
            "time_ms": ms(),
            "command": command,
            "args": {},
        }
        with socket.create_connection((self.host.get(), int(self.port.get())), timeout=5) as sock:
            sock.sendall((json.dumps(packet, separators=(",", ":")) + "\n").encode("utf-8"))
            data = b""
            while not data.endswith(b"\n"):
                chunk = sock.recv(4096)
                if not chunk:
                    break
                data += chunk
        return json.loads(data.decode("utf-8", errors="replace")) if data else {"ok": False, "error": "no response"}

    def send_command(self, command: str) -> None:
        try:
            response = self.send_packet(command)
            self.append(f"{command}: {json.dumps(response, separators=(',', ':'))}")
            self.status.set("Command sent" if response.get("ok") else "Command failed")
        except Exception as exc:
            self.status.set("Command failed")
            self.append(f"{command}: {exc}")

    def close(self) -> None:
        self.stop_server()
        self.root.destroy()

    def run(self) -> None:
        self.root.mainloop()


def main() -> int:
    PeerApp().run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
