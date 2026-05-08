#!/usr/bin/env python3
"""Dry-run bridge reader for Code RED Peer Clone Game Bridge v0.1."""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent
DEFAULT_BRIDGE = ROOT / "bridge"
DEFAULT_RUNTIME = ROOT / "runtime"


def now_ms() -> int:
    return int(time.time() * 1000)


def append_jsonl(path: Path, event: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    event.setdefault("schema", "codered.peer_clone.game_bridge.event.v1")
    event.setdefault("updated_ms", now_ms())
    event.setdefault("mode", "dry-run")
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(event, ensure_ascii=False, sort_keys=True) + "\n")


def write_status(path: Path, status: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema": "codered.bridge.status.v1",
        "source": "CodeRED_Peer_Clone_Game_Bridge_DryRun_v0_1",
        "updated_ms": now_ms(),
        "mode": "dry-run",
        "allow_spawn": False,
        "startup_delay_ms": 30000,
        "kill_switch": False,
        **status,
    }
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def load_remote(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(path)
    payload = json.loads(path.read_text(encoding="utf-8"))
    players = payload.get("players", {})
    if isinstance(players, list):
        players = {str(i): item for i, item in enumerate(players)}
    if not isinstance(players, dict):
        raise ValueError("players must be an object or list")
    return players


def main() -> int:
    parser = argparse.ArgumentParser(description="Read remote_players_state.json and log what the ASI would spawn.")
    parser.add_argument("--bridge", type=Path, default=DEFAULT_BRIDGE, help="Bridge folder containing remote/local/status JSON.")
    parser.add_argument("--runtime", type=Path, default=DEFAULT_RUNTIME, help="Runtime log folder.")
    parser.add_argument("--once", action="store_true", help="Run once and exit.")
    parser.add_argument("--interval", type=float, default=1.0, help="Watch interval in seconds.")
    args = parser.parse_args()

    bridge = args.bridge.resolve()
    runtime = args.runtime.resolve()
    remote_path = bridge / "remote_players_state.json"
    status_path = bridge / "bridge_status.json"
    log_path = runtime / "codered_peer_clone_game_bridge.jsonl"

    while True:
        try:
            players = load_remote(remote_path)
            first_key = next(iter(players), None)
            first = players.get(first_key) if first_key is not None else None
            if first:
                event = {
                    "event": "dry_run_would_spawn_or_move",
                    "remote_count": len(players),
                    "client_id": first.get("client_id", first_key),
                    "name": first.get("name", ""),
                    "x": first.get("x", 0),
                    "y": first.get("y", 0),
                    "z": first.get("z", 0),
                    "heading": first.get("heading", 0),
                    "note": "spawn-test would create one human clone; move-test would interpolate it toward these remote coordinates",
                }
                append_jsonl(log_path, event)
                write_status(
                    status_path,
                    {
                        "phase": "dry_run_remote_seen",
                        "remote_count": len(players),
                        "spawned": False,
                        "no_spawn_fallback": False,
                        "last_error": "",
                        "jsonl_log": str(log_path),
                    },
                )
                print(f"[dry-run] remote_count={len(players)} first={event['client_id']} pos=({event['x']}, {event['y']}, {event['z']})")
            else:
                append_jsonl(log_path, {"event": "dry_run_no_remote_players", "remote_count": 0})
                write_status(status_path, {"phase": "dry_run_no_remote_players", "remote_count": 0, "last_error": ""})
                print("[dry-run] no remote players")
        except Exception as exc:  # noqa: BLE001 - this is a diagnostics tool.
            append_jsonl(log_path, {"event": "dry_run_error", "last_error": str(exc)})
            write_status(status_path, {"phase": "dry_run_error", "remote_count": 0, "last_error": str(exc)})
            print(f"[dry-run] error: {exc}")
            if args.once:
                return 1

        if args.once:
            return 0
        time.sleep(max(0.1, args.interval))


if __name__ == "__main__":
    raise SystemExit(main())
