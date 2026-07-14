#!/usr/bin/env python3
"""Run a small live smoke test against Ableton LiveAgent on 127.0.0.1:8765.

This intentionally mutates the current Live set, but only by creating temporary
objects named with ``LiveAgent Smoke`` and deleting them before exit.
"""

from __future__ import annotations

import json
import socket
import sys
from typing import Any

HOST = "127.0.0.1"
PORT = 8765
TIMEOUT = 10


def send(command: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    request: dict[str, Any] = {"command": command}
    if payload is not None:
        request["payload"] = payload

    with socket.create_connection((HOST, PORT), timeout=TIMEOUT) as sock:
        sock.settimeout(TIMEOUT)
        sock.sendall((json.dumps(request, separators=(",", ":")) + "\n").encode("utf-8"))
        buf = b""
        while b"\n" not in buf:
            chunk = sock.recv(65536)
            if not chunk:
                break
            buf += chunk

    if not buf:
        raise RuntimeError(f"{command}: no response")
    response = json.loads(buf.decode("utf-8").strip())
    if not response.get("ok"):
        raise RuntimeError(f"{command}: {response.get('error')}")
    return response.get("result") or {}


def main() -> int:
    created_track_index: int | None = None
    duplicate_track_index: int | None = None
    created_scene_index: int | None = None
    duplicate_scene_index: int | None = None
    checks: list[str] = []

    try:
        ping = send("ping")
        checks.append(f"ping={bool(ping.get('pong'))}")

        state = send("get_live_state")
        checks.append(f"initial_tracks={len(state.get('tracks', []))}")
        checks.append(f"initial_scenes={len(state.get('scenes', []))}")

        if state.get("tracks"):
            send("select_track", {"track_index": 0})
            checks.append("select_track")
        if state.get("scenes"):
            send("select_scene", {"scene_index": 0})
            checks.append("select_scene")

        created_scene = send("create_scene", {"index": -1, "name": "LiveAgent Smoke Scene"})
        created_scene_index = int(created_scene["scene"]["index"])
        checks.append(f"create_scene={created_scene_index}")

        send("set_scene_name", {"scene_index": created_scene_index, "name": "LiveAgent Smoke Renamed"})
        send("set_scene_color", {"scene_index": created_scene_index, "color": 16753920})
        checks.append("set_scene_name/color")

        duplicated_scene = send("duplicate_scene", {"scene_index": created_scene_index})
        duplicate_scene_index = int(duplicated_scene["new_scene_index"])
        checks.append(f"duplicate_scene={duplicate_scene_index}")

        created_track = send("create_midi_track", {"index": -1})
        tracks = created_track.get("tracks", [])
        created_track_index = int(tracks[-1]["index"])
        checks.append(f"create_midi_track={created_track_index}")

        send("set_track_name", {"track_index": created_track_index, "name": "LiveAgent Smoke Track"})
        send("set_track_color", {"track_index": created_track_index, "color": 65280})
        send("select_track", {"track_index": created_track_index})
        checks.append("set_track_name/color/select")

        send(
            "create_session_clip",
            {
                "track_index": created_track_index,
                "slot_index": created_scene_index,
                "length_beats": 4,
                "name": "LiveAgent Smoke Clip",
                "replace": True,
            },
        )
        send("select_clip", {"track_index": created_track_index, "slot_index": created_scene_index})
        send("stop_clip", {"track_index": created_track_index, "slot_index": created_scene_index})
        send("stop_track_clips", {"track_index": created_track_index})
        checks.append("clip_select/stop")

        live_state = send("list_tracks")
        test_track = live_state["tracks"][created_track_index]
        for key in ("volume", "pan", "sends", "monitoring", "color"):
            if key not in test_track:
                raise RuntimeError(f"list_tracks missing {key}")
        checks.append("list_tracks_mixer_fields")

        duplicated_track = send("duplicate_track", {"track_index": created_track_index})
        duplicate_track_index = int(duplicated_track["new_track_index"])
        checks.append(f"duplicate_track={duplicate_track_index}")

        print(json.dumps({"ok": True, "checks": checks}, indent=2, ensure_ascii=False))
        return 0
    finally:
        cleanup_errors = []
        for index_name, command, index in (
            ("duplicate_track", "delete_track", duplicate_track_index),
            ("created_track", "delete_track", created_track_index),
            ("duplicate_scene", "delete_scene", duplicate_scene_index),
            ("created_scene", "delete_scene", created_scene_index),
        ):
            if index is None:
                continue
            try:
                key = "track_index" if command == "delete_track" else "scene_index"
                send(command, {key: index})
            except Exception as err:  # noqa: BLE001 - best-effort cleanup report
                cleanup_errors.append(f"{index_name}: {err}")
        if cleanup_errors:
            print(json.dumps({"cleanup_errors": cleanup_errors}, indent=2), file=sys.stderr)


if __name__ == "__main__":
    raise SystemExit(main())
