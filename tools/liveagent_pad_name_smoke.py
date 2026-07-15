#!/usr/bin/env python3
"""Smoke-test Drum Rack sample loading plus visible pad naming in LiveAgent."""

from __future__ import annotations

import json
import math
import socket
import struct
import sys
import tempfile
import wave
from pathlib import Path
from typing import Any

HOST = "127.0.0.1"
PORT = 8765
TIMEOUT = 30
PAD_INDEX = 36
PAD_NAME = "Smoke Kick Pad"
RENAMED_PAD_NAME = "Smoke Kick Renamed"


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


def write_test_wav(path: Path) -> None:
    sample_rate = 44_100
    duration = 0.12
    frames = int(sample_rate * duration)
    with wave.open(str(path), "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(sample_rate)
        for frame in range(frames):
            amp = 0.45 * math.sin(2.0 * math.pi * 90.0 * frame / sample_rate)
            wav.writeframes(struct.pack("<h", int(amp * 32767)))


def _pad_names(track_index: int) -> set[str]:
    inspected = send(
        "inspect_drum_rack",
        {"track_index": track_index, "drum_rack_index": 0, "pad_range": [PAD_INDEX, PAD_INDEX + 1]},
    )
    pads = inspected.get("pads", [])
    if not pads:
        raise RuntimeError("inspect_drum_rack returned no pads")
    pad = pads[0]
    return {str(name) for name in (pad.get("name"), pad.get("chain_name")) if name}


def main() -> int:
    created_track_index: int | None = None
    sample_path = Path(tempfile.gettempdir()) / "liveagent_pad_name_smoke.wav"
    checks: list[str] = []

    try:
        write_test_wav(sample_path)
        checks.append(f"sample={sample_path}")

        ping = send("ping")
        checks.append(f"ping={bool(ping.get('pong'))}")

        created = send(
            "create_drum_rack",
            {"track_index": -1, "name": "LiveAgent Pad Name Smoke", "kit_name": "808 Core Kit.adg"},
        )
        created_track_index = int(created["track_index"])
        checks.append(f"create_drum_rack={created_track_index}")

        loaded = send(
            "load_sample_to_pad",
            {
                "track_index": created_track_index,
                "pad_index": PAD_INDEX,
                "file_path": str(sample_path),
                "pad_name": PAD_NAME,
                "reset_effects": False,
            },
        )
        if not loaded.get("loaded"):
            raise RuntimeError(f"load_sample_to_pad did not report loaded=True: {loaded}")
        if PAD_NAME not in _pad_names(created_track_index):
            raise RuntimeError(f"pad name after load did not include {PAD_NAME!r}")
        checks.append("load_sample_to_pad+pad_name")

        renamed = send(
            "set_drum_pad_name",
            {
                "track_index": created_track_index,
                "pad_index": PAD_INDEX,
                "pad_name": RENAMED_PAD_NAME,
            },
        )
        if not renamed.get("pad_name_set"):
            raise RuntimeError(f"set_drum_pad_name did not report pad_name_set=True: {renamed}")
        if RENAMED_PAD_NAME not in _pad_names(created_track_index):
            raise RuntimeError(f"pad name after rename did not include {RENAMED_PAD_NAME!r}")
        checks.append("set_drum_pad_name")

        print(json.dumps({"ok": True, "checks": checks}, indent=2, ensure_ascii=False))
        return 0
    finally:
        cleanup_errors = []
        if created_track_index is not None:
            try:
                send("delete_track", {"track_index": created_track_index})
            except Exception as err:  # noqa: BLE001 - best-effort cleanup report
                cleanup_errors.append(f"created_track: {err}")
        try:
            sample_path.unlink(missing_ok=True)
        except Exception as err:  # noqa: BLE001 - best-effort cleanup report
            cleanup_errors.append(f"sample_file: {err}")
        if cleanup_errors:
            print(json.dumps({"cleanup_errors": cleanup_errors}, indent=2), file=sys.stderr)


if __name__ == "__main__":
    raise SystemExit(main())
