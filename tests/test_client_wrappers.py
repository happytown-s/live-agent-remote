"""Tests for lightweight SDK wrapper payloads.

These tests bypass sockets by constructing the client without ``__init__`` and
patching ``_send``. They verify that public helper methods keep the TCP command
names and payload shapes in sync with the MCP/LiveAgent command surface.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "client"))

from live_agent_client import LiveAgentClient


class Recorder:
    def __init__(self):
        self.calls = []

    def __call__(self, command, payload=None):
        self.calls.append((command, payload))
        return {"command": command, "payload": payload}


def _client():
    client = LiveAgentClient.__new__(LiveAgentClient)
    recorder = Recorder()
    client._send = recorder
    return client, recorder


def test_python_client_selection_payloads():
    client, recorder = _client()

    client.select_track(3)
    client.select_clip(3, 1)
    client.select_device(3, device_name="Massive")

    assert recorder.calls == [
        ("select_track", {"track_index": 3}),
        ("select_clip", {"track_index": 3, "slot_index": 1}),
        ("select_device", {"track_index": 3, "device_name": "Massive"}),
    ]


def test_python_client_track_scene_payloads():
    client, recorder = _client()

    client.set_track_name(1, "Bass")
    client.create_scene(index=-1, name="Drop", color=16711680)
    client.delete_scene(2)

    assert recorder.calls == [
        ("set_track_name", {"track_index": 1, "name": "Bass"}),
        ("create_scene", {"index": -1, "name": "Drop", "color": 16711680}),
        ("delete_scene", {"scene_index": 2}),
    ]


def test_python_client_drum_rack_payloads():
    client, recorder = _client()

    client.create_drum_rack(track_index=-1, name="Kit", kit_name="808 Core Kit.adg")
    client.load_sample_to_pad(4, 36, "/tmp/kick.wav", pad_name="Kick C", reset_effects=True)
    client.set_drum_pad_name(4, 38, "Snare Tight")
    client.inspect_drum_rack(4, pad_range=[36, 52])

    assert recorder.calls == [
        (
            "create_drum_rack",
            {
                "track_index": -1,
                "name": "Kit",
                "kit_name": "808 Core Kit.adg",
                "empty": False,
            },
        ),
        (
            "load_sample_to_pad",
            {
                "track_index": 4,
                "pad_index": 36,
                "file_path": "/tmp/kick.wav",
                "pad_name": "Kick C",
                "drum_rack_index": 0,
                "reset_effects": True,
            },
        ),
        (
            "set_drum_pad_name",
            {
                "track_index": 4,
                "pad_index": 38,
                "pad_name": "Snare Tight",
                "drum_rack_index": 0,
            },
        ),
        ("inspect_drum_rack", {"track_index": 4, "drum_rack_index": 0, "pad_range": [36, 52]}),
    ]
