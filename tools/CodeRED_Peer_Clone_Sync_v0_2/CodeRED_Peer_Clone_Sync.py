#!/usr/bin/env python3
"""
Code RED Peer Clone Sync v0.2
Phase 2 public-test relay/client prototype for two-game fake co-op / puppet sync tests.

No external dependencies. Python 3.10+.
- host:    relays JSONL player state between clients
- client:  mock/test client that sends local state and receives remote clone states
- gui:     small Tk launcher for host/client testing
- selftest: local loopback proof with one relay and two mock clients

This does NOT restore official multiplayer. It proves the simplest connection layer:
two clients exchange transform/action snapshots that a future in-game plugin can use
to spawn and update clone actors.
"""

from __future__ import annotations

import argparse
import dataclasses
import json
import math
import os
import queue
import random
import socket
import socketserver
import sys
import threading
import time
import traceback
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

APP_NAME = "Code RED Peer Clone Sync v0.2"
PROTOCOL_VERSION = "codered.peer.clone.v1"
DEFAULT_PORT = 47666
DEFAULT_RATE = 15.0
RUNTIME_DIR = Path(__file__).resolve().parent / "runtime"


def now_ms() -> int:
    return int(time.time() * 1000)


def safe_json(obj: Dict[str, Any]) -> bytes:
    return (json.dumps(obj, separators=(",", ":"), ensure_ascii=False) + "\n").encode("utf-8")


def read_json_lines(sock_file):
    while True:
        line = sock_file.readline()
        if not line:
            return
        try:
            yield json.loads(line.decode("utf-8", "replace").strip())
        except Exception as exc:
            yield {"type": "error", "error": f"bad_json:{exc}"}


def runtime_path(name: str) -> Path:
    RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
    return RUNTIME_DIR / name


def append_jsonl(path: Path, item: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(item, ensure_ascii=False, separators=(",", ":")) + "\n")


@dataclasses.dataclass
class ClientRecord:
    client_id: str
    name: str
    actor: str
    address: Tuple[str, int]
    handler: "RelayHandler"
    connected_ms: int
    last_seen_ms: int


class RelayState:
    def __init__(self):
        self.lock = threading.RLock()
        self.clients: Dict[str, ClientRecord] = {}
        self.started_ms = now_ms()
        self.packet_count = 0
        self.last_states: Dict[str, Dict[str, Any]] = {}

    def snapshot_roster(self) -> List[Dict[str, Any]]:
        with self.lock:
            return [
                {
                    "client_id": c.client_id,
                    "name": c.name,
                    "actor": c.actor,
                    "address": f"{c.address[0]}:{c.address[1]}",
                    "connected_ms": c.connected_ms,
                    "last_seen_ms": c.last_seen_ms,
                }
                for c in self.clients.values()
            ]


class RelayServer(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True

    def __init__(self, server_address, RequestHandlerClass):
        super().__init__(server_address, RequestHandlerClass)
        self.relay_state = RelayState()


class RelayHandler(socketserver.BaseRequestHandler):
    def setup(self):
        self.client_id = ""
        self.name = "unknown"
        self.actor = "ACTOR_player_jack"
        self.alive = True
        self.file = self.request.makefile("rwb")

    def send(self, obj: Dict[str, Any]) -> None:
        try:
            self.file.write(safe_json(obj))
            self.file.flush()
        except Exception:
            self.alive = False

    def broadcast(self, obj: Dict[str, Any], include_self: bool = False) -> None:
        state: RelayState = self.server.relay_state
        with state.lock:
            targets = list(state.clients.values())
        for record in targets:
            if not include_self and record.client_id == self.client_id:
                continue
            record.handler.send(obj)

    def handle_hello(self, msg: Dict[str, Any]) -> bool:
        if msg.get("protocol") != PROTOCOL_VERSION:
            self.send({
                "type": "error",
                "error": "protocol_mismatch",
                "expected": PROTOCOL_VERSION,
                "got": msg.get("protocol"),
                "server_ms": now_ms(),
            })
            return False

        requested = str(msg.get("client_id") or "").strip()
        if not requested:
            requested = f"peer_{random.randint(1000, 9999)}"
        self.client_id = requested[:64]
        self.name = str(msg.get("name") or self.client_id)[:64]
        self.actor = str(msg.get("actor") or "ACTOR_player_jack")[:96]

        state: RelayState = self.server.relay_state
        with state.lock:
            # Kick/replace duplicate by overwriting; old handler will stop when send fails or next read ends.
            state.clients[self.client_id] = ClientRecord(
                client_id=self.client_id,
                name=self.name,
                actor=self.actor,
                address=self.client_address,
                handler=self,
                connected_ms=now_ms(),
                last_seen_ms=now_ms(),
            )
            roster = state.snapshot_roster()

        self.send({
            "type": "welcome",
            "protocol": PROTOCOL_VERSION,
            "server_ms": now_ms(),
            "client_id": self.client_id,
            "your_name": self.name,
            "your_actor": self.actor,
            "roster": roster,
        })
        self.broadcast({
            "type": "peer_joined",
            "server_ms": now_ms(),
            "peer": {
                "client_id": self.client_id,
                "name": self.name,
                "actor": self.actor,
                "address": f"{self.client_address[0]}:{self.client_address[1]}",
            },
            "roster": roster,
        }, include_self=False)
        print(f"[relay] joined {self.client_id} {self.name} from {self.client_address[0]}:{self.client_address[1]}", flush=True)
        return True

    def handle_state(self, msg: Dict[str, Any]) -> None:
        state: RelayState = self.server.relay_state
        msg["type"] = "state"
        msg["protocol"] = PROTOCOL_VERSION
        msg["relay_ms"] = now_ms()
        msg["client_id"] = self.client_id
        msg["name"] = self.name
        msg["actor"] = self.actor

        with state.lock:
            state.packet_count += 1
            if self.client_id in state.clients:
                state.clients[self.client_id].last_seen_ms = now_ms()
            state.last_states[self.client_id] = msg

        # Log compact proof for later review.
        append_jsonl(runtime_path("relay_states.jsonl"), msg)
        self.broadcast(msg, include_self=False)

    def handle_ping(self, msg: Dict[str, Any]) -> None:
        self.send({
            "type": "pong",
            "protocol": PROTOCOL_VERSION,
            "server_ms": now_ms(),
            "client_ms": msg.get("client_ms"),
            "roster": self.server.relay_state.snapshot_roster(),
        })

    def handle(self):
        try:
            first = self.file.readline()
            if not first:
                return
            try:
                hello = json.loads(first.decode("utf-8", "replace").strip())
            except Exception as exc:
                self.send({"type": "error", "error": f"bad_hello_json:{exc}"})
                return
            if hello.get("type") != "hello" or not self.handle_hello(hello):
                return

            for msg in read_json_lines(self.file):
                if not self.alive:
                    break
                typ = msg.get("type")
                if typ == "state":
                    self.handle_state(msg)
                elif typ == "ping":
                    self.handle_ping(msg)
                elif typ == "bye":
                    break
                elif typ == "error":
                    self.send({"type": "error", "error": msg.get("error", "bad_json")})
                else:
                    self.send({"type": "error", "error": f"unknown_type:{typ}"})
        except Exception:
            append_jsonl(runtime_path("relay_errors.jsonl"), {
                "server_ms": now_ms(),
                "client_id": self.client_id,
                "trace": traceback.format_exc(),
            })
        finally:
            state: RelayState = self.server.relay_state
            removed = False
            with state.lock:
                if self.client_id and self.client_id in state.clients and state.clients[self.client_id].handler is self:
                    del state.clients[self.client_id]
                    removed = True
                roster = state.snapshot_roster()
            if removed:
                self.broadcast({
                    "type": "peer_left",
                    "server_ms": now_ms(),
                    "client_id": self.client_id,
                    "name": self.name,
                    "roster": roster,
                }, include_self=False)
                print(f"[relay] left {self.client_id} {self.name}", flush=True)
            try:
                self.file.close()
            except Exception:
                pass


def run_host(bind: str, port: int) -> None:
    RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
    server = RelayServer((bind, port), RelayHandler)
    print(f"# {APP_NAME} Relay")
    print(f"protocol={PROTOCOL_VERSION}")
    print(f"listening={bind}:{port}")
    print("Press Ctrl+C to stop.")
    try:
        server.serve_forever(poll_interval=0.25)
    except KeyboardInterrupt:
        print("\n[relay] stopping")
    finally:
        server.shutdown()
        server.server_close()


class PeerClient:
    def __init__(self, host: str, port: int, client_id: str, name: str, actor: str,
                 rate: float = DEFAULT_RATE, mock: bool = True, log_prefix: str = "client"):
        self.host = host
        self.port = port
        self.client_id = client_id
        self.name = name
        self.actor = actor
        self.rate = max(1.0, min(30.0, rate))
        self.mock = mock
        self.log_prefix = log_prefix
        self.sock: Optional[socket.socket] = None
        self.file = None
        self.stop_event = threading.Event()
        self.remote_states: Dict[str, Dict[str, Any]] = {}
        self.rx_thread: Optional[threading.Thread] = None
        self.connected = False
        self.start_ms = now_ms()

    def connect(self, timeout: float = 8.0) -> None:
        self.sock = socket.create_connection((self.host, self.port), timeout=timeout)
        self.sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        self.file = self.sock.makefile("rwb")
        self.send({
            "type": "hello",
            "protocol": PROTOCOL_VERSION,
            "client_id": self.client_id,
            "name": self.name,
            "actor": self.actor,
            "client_kind": "mock" if self.mock else "game_bridge",
            "client_ms": now_ms(),
        })
        welcome = self.file.readline()
        if not welcome:
            raise RuntimeError("relay closed before welcome")
        msg = json.loads(welcome.decode("utf-8", "replace").strip())
        if msg.get("type") != "welcome":
            raise RuntimeError(f"bad welcome: {msg}")
        self.connected = True
        print(f"[{self.log_prefix}] connected as {msg.get('client_id')} roster={len(msg.get('roster', []))}", flush=True)
        self.rx_thread = threading.Thread(target=self.rx_loop, daemon=True)
        self.rx_thread.start()

    def send(self, obj: Dict[str, Any]) -> None:
        if not self.file:
            raise RuntimeError("not connected")
        self.file.write(safe_json(obj))
        self.file.flush()

    def rx_loop(self) -> None:
        assert self.file is not None
        try:
            for msg in read_json_lines(self.file):
                if self.stop_event.is_set():
                    return
                typ = msg.get("type")
                if typ == "state":
                    cid = str(msg.get("client_id", ""))
                    if cid and cid != self.client_id:
                        self.remote_states[cid] = msg
                        append_jsonl(runtime_path(f"{self.client_id}_remote_states.jsonl"), msg)
                        x, y, z = msg.get("x"), msg.get("y"), msg.get("z")
                        heading = msg.get("heading")
                        print(f"[{self.log_prefix}] remote {cid}: pos=({x:.2f},{y:.2f},{z:.2f}) heading={heading:.1f} action={msg.get('action')}", flush=True)
                elif typ in ("peer_joined", "peer_left"):
                    print(f"[{self.log_prefix}] {typ}: roster={len(msg.get('roster', []))}", flush=True)
                elif typ == "pong":
                    pass
                elif typ == "error":
                    print(f"[{self.log_prefix}] relay error: {msg}", flush=True)
        except Exception as exc:
            if not self.stop_event.is_set():
                print(f"[{self.log_prefix}] rx stopped: {exc}", flush=True)

    def make_mock_state(self, tick: int) -> Dict[str, Any]:
        t = (now_ms() - self.start_ms) / 1000.0
        seed = sum(ord(c) for c in self.client_id) % 360
        angle = t * 0.8 + math.radians(seed)
        radius = 8.0 + (seed % 5)
        x = math.cos(angle) * radius
        y = math.sin(angle) * radius
        z = 0.0
        heading = (math.degrees(angle) + 90.0) % 360.0
        action = "walk" if tick % 40 < 30 else "idle"
        return {
            "type": "state",
            "protocol": PROTOCOL_VERSION,
            "client_ms": now_ms(),
            "seq": tick,
            "x": round(x, 3),
            "y": round(y, 3),
            "z": round(z, 3),
            "heading": round(heading, 2),
            "speed": 1.6 if action == "walk" else 0.0,
            "health": 100,
            "weapon": "WEAPON_REVOLVER",
            "action": action,
            "mount": None,
            "vehicle": None,
        }

    def run_send_loop(self, seconds: float = 0.0) -> None:
        tick = 0
        delay = 1.0 / self.rate
        end_time = time.time() + seconds if seconds and seconds > 0 else None
        while not self.stop_event.is_set():
            if end_time and time.time() >= end_time:
                break
            tick += 1
            if self.mock:
                self.send(self.make_mock_state(tick))
            else:
                # Future game bridge mode reads local_player_state.json written by an in-game plugin.
                path = runtime_path(f"{self.client_id}_local_player_state.json")
                if path.exists():
                    try:
                        state = json.loads(path.read_text(encoding="utf-8"))
                        state["type"] = "state"
                        state["protocol"] = PROTOCOL_VERSION
                        state.setdefault("client_ms", now_ms())
                        self.send(state)
                    except Exception as exc:
                        print(f"[{self.log_prefix}] failed to send bridge state: {exc}", flush=True)
            time.sleep(delay)

    def close(self) -> None:
        self.stop_event.set()
        try:
            if self.file:
                self.file.write(safe_json({"type": "bye", "client_ms": now_ms()}))
                self.file.flush()
        except Exception:
            pass
        try:
            if self.sock:
                self.sock.close()
        except Exception:
            pass


def run_client(host: str, port: int, client_id: str, name: str, actor: str,
               rate: float, mock: bool, seconds: float) -> None:
    client = PeerClient(host, port, client_id, name, actor, rate=rate, mock=mock, log_prefix=client_id)
    try:
        client.connect()
        client.run_send_loop(seconds=seconds)
    except KeyboardInterrupt:
        print(f"\n[{client_id}] stopping")
    finally:
        client.close()


def run_selftest() -> int:
    port = random.randint(49100, 59900)
    server = RelayServer(("127.0.0.1", port), RelayHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    time.sleep(0.2)

    a = PeerClient("127.0.0.1", port, "player_a", "Player A", "ACTOR_player_jack", rate=12, mock=True, log_prefix="selftest-a")
    b = PeerClient("127.0.0.1", port, "player_b", "Player B", "ACTOR_mpplayer01", rate=12, mock=True, log_prefix="selftest-b")
    ok = False
    try:
        a.connect()
        b.connect()
        ta = threading.Thread(target=a.run_send_loop, kwargs={"seconds": 2.0}, daemon=True)
        tb = threading.Thread(target=b.run_send_loop, kwargs={"seconds": 2.0}, daemon=True)
        ta.start(); tb.start()
        ta.join(timeout=4.0); tb.join(timeout=4.0)
        time.sleep(0.5)
        ok = bool(a.remote_states.get("player_b")) and bool(b.remote_states.get("player_a"))
        print(f"# Selftest result: {'PASS' if ok else 'FAIL'}")
        print(f"player_a saw player_b: {bool(a.remote_states.get('player_b'))}")
        print(f"player_b saw player_a: {bool(b.remote_states.get('player_a'))}")
    finally:
        a.close(); b.close()
        server.shutdown(); server.server_close()
    return 0 if ok else 1



def detect_local_ips() -> List[str]:
    ips = []
    try:
        hostname = socket.gethostname()
        for value in socket.gethostbyname_ex(hostname)[2]:
            if value and value not in ips:
                ips.append(value)
    except Exception:
        pass
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        value = s.getsockname()[0]
        s.close()
        if value and value not in ips:
            ips.append(value)
    except Exception:
        pass
    if "127.0.0.1" not in ips:
        ips.append("127.0.0.1")
    return ips


def run_doctor(port: int = DEFAULT_PORT) -> int:
    print(f"# {APP_NAME} Public Test Doctor")
    print(f"python={sys.version.split()[0]}")
    print(f"protocol={PROTOCOL_VERSION}")
    print(f"default_port={port}/tcp")
    print("local_ip_candidates:")
    for ip in detect_local_ips():
        print(f"  - {ip}")
    print("\nGive your tester your LAN/VPN IP, not 127.0.0.1.")
    print("If the tester cannot connect, allow Python through Windows Firewall or use a VPN like Radmin/ZeroTier/Hamachi.")
    print("Run_SelfTest.bat should PASS before a two-PC test.")
    return 0


def run_gui() -> None:
    try:
        import tkinter as tk
        from tkinter import ttk, messagebox
    except Exception as exc:
        print(f"Tkinter unavailable: {exc}")
        return

    root = tk.Tk()
    root.title(APP_NAME)
    root.geometry("780x520")

    log_q: "queue.Queue[str]" = queue.Queue()
    host_thread: Optional[threading.Thread] = None
    client_thread: Optional[threading.Thread] = None
    client_holder: Dict[str, Optional[PeerClient]] = {"client": None}

    def log(text: str):
        log_q.put(text)

    frame = ttk.Frame(root, padding=12)
    frame.pack(fill="both", expand=True)

    ttk.Label(frame, text=APP_NAME, font=("Segoe UI", 16, "bold")).grid(row=0, column=0, columnspan=4, sticky="w")
    ttk.Label(frame, text="First test: one player hosts relay, both players connect as clients.").grid(row=1, column=0, columnspan=4, sticky="w", pady=(0, 10))

    bind_var = tk.StringVar(value="0.0.0.0")
    port_var = tk.StringVar(value=str(DEFAULT_PORT))
    host_var = tk.StringVar(value="127.0.0.1")
    id_var = tk.StringVar(value=f"player_{random.randint(100,999)}")
    name_var = tk.StringVar(value="CodeRED Player")
    actor_var = tk.StringVar(value="ACTOR_player_jack")
    rate_var = tk.StringVar(value=str(DEFAULT_RATE))

    labels = [
        ("Relay bind", bind_var), ("Port", port_var),
        ("Connect host/IP", host_var), ("Client ID", id_var),
        ("Name", name_var), ("Actor", actor_var),
        ("Rate", rate_var),
    ]
    for i, (label, var) in enumerate(labels):
        r = 2 + i // 2
        c = (i % 2) * 2
        ttk.Label(frame, text=label).grid(row=r, column=c, sticky="w", pady=2)
        ttk.Entry(frame, textvariable=var, width=28).grid(row=r, column=c+1, sticky="ew", pady=2)

    text = tk.Text(frame, height=16, wrap="word")
    text.grid(row=7, column=0, columnspan=4, sticky="nsew", pady=(12, 0))
    frame.rowconfigure(7, weight=1)
    frame.columnconfigure(1, weight=1)
    frame.columnconfigure(3, weight=1)

    def pump_log():
        while True:
            try:
                item = log_q.get_nowait()
            except queue.Empty:
                break
            text.insert("end", item + "\n")
            text.see("end")
        root.after(100, pump_log)

    def start_host():
        nonlocal host_thread
        if host_thread and host_thread.is_alive():
            messagebox.showinfo(APP_NAME, "Relay already running in this GUI.")
            return
        bind = bind_var.get().strip()
        port = int(port_var.get())
        def target():
            # GUI host has its own server lifetime until app closes.
            try:
                srv = RelayServer((bind, port), RelayHandler)
                log(f"[gui-relay] listening {bind}:{port}")
                srv.serve_forever(poll_interval=0.25)
            except Exception as exc:
                log(f"[gui-relay] error: {exc}")
        host_thread = threading.Thread(target=target, daemon=True)
        host_thread.start()

    def start_client():
        nonlocal client_thread
        if client_thread and client_thread.is_alive():
            messagebox.showinfo(APP_NAME, "Client already running in this GUI.")
            return
        host = host_var.get().strip()
        port = int(port_var.get())
        cid = id_var.get().strip()
        name = name_var.get().strip()
        actor = actor_var.get().strip()
        rate = float(rate_var.get())
        def target():
            pc = PeerClient(host, port, cid, name, actor, rate=rate, mock=True, log_prefix=cid)
            client_holder["client"] = pc
            try:
                pc.connect()
                log(f"[{cid}] connected to {host}:{port}")
                tick = 0
                delay = 1.0 / max(1.0, min(30.0, rate))
                while not pc.stop_event.is_set():
                    tick += 1
                    pc.send(pc.make_mock_state(tick))
                    if tick % int(max(1, rate)) == 0:
                        log(f"[{cid}] sent tick={tick}; remotes={list(pc.remote_states.keys())}")
                    time.sleep(delay)
            except Exception as exc:
                log(f"[{cid}] client error: {exc}")
            finally:
                pc.close()
        client_thread = threading.Thread(target=target, daemon=True)
        client_thread.start()

    def stop_client():
        c = client_holder.get("client")
        if c:
            c.close()
            log("[gui] client stop requested")

    btns = ttk.Frame(frame)
    btns.grid(row=6, column=0, columnspan=4, sticky="w", pady=(10, 0))
    ttk.Button(btns, text="Start Relay Host", command=start_host).pack(side="left", padx=(0, 8))
    ttk.Button(btns, text="Start Mock Client", command=start_client).pack(side="left", padx=(0, 8))
    ttk.Button(btns, text="Stop Client", command=stop_client).pack(side="left", padx=(0, 8))
    ttk.Button(btns, text="Open Runtime Folder", command=lambda: os.startfile(str(RUNTIME_DIR)) if os.name == "nt" else None).pack(side="left")

    pump_log()
    root.mainloop()


def build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=APP_NAME)
    sub = p.add_subparsers(dest="cmd", required=True)

    ph = sub.add_parser("host", help="Run relay host/server")
    ph.add_argument("--bind", default="0.0.0.0")
    ph.add_argument("--port", type=int, default=DEFAULT_PORT)

    pc = sub.add_parser("client", help="Run mock/game-bridge client")
    pc.add_argument("--host", default="127.0.0.1")
    pc.add_argument("--port", type=int, default=DEFAULT_PORT)
    pc.add_argument("--client-id", default=f"player_{random.randint(1000,9999)}")
    pc.add_argument("--name", default="CodeRED Player")
    pc.add_argument("--actor", default="ACTOR_player_jack")
    pc.add_argument("--rate", type=float, default=DEFAULT_RATE)
    pc.add_argument("--seconds", type=float, default=0.0, help="0 means run until Ctrl+C")
    pc.add_argument("--bridge", action="store_true", help="Read runtime/<client_id>_local_player_state.json instead of mock motion")

    sub.add_parser("gui", help="Open small Tk launcher")
    sub.add_parser("selftest", help="Run local loopback proof")
    pd = sub.add_parser("doctor", help="Show public-test connection info")
    pd.add_argument("--port", type=int, default=DEFAULT_PORT)

    return p


def main(argv: Optional[List[str]] = None) -> int:
    args = build_arg_parser().parse_args(argv)
    if args.cmd == "host":
        run_host(args.bind, args.port)
        return 0
    if args.cmd == "client":
        run_client(args.host, args.port, args.client_id, args.name, args.actor, args.rate, mock=not args.bridge, seconds=args.seconds)
        return 0
    if args.cmd == "gui":
        run_gui()
        return 0
    if args.cmd == "selftest":
        return run_selftest()
    if args.cmd == "doctor":
        return run_doctor(port=args.port)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
