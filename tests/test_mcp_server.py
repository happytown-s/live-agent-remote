"""Unit tests for ``mcp_server.py`` — no live Ableton connection required.

These tests exercise:
  * ``DESTRUCTIVE_TOOLS`` dictionary completeness
  * Dry-run interception (returns a preview, never calls TCP)
  * Dry-run stripping before forwarding to LiveAgent
  * Batch dry-run previews
  * eval/exec gating behind ``LIVEAGENT_ENABLE_UNSAFE``
"""

import json
import os

import pytest

import mcp_server
from mcp_server import call_tool

# ── Helpers ──────────────────────────────────────────────────────────────────

async def _call(tool_name, **kwargs):
    """Call the MCP ``call_tool`` handler and parse the JSON response."""
    result = await call_tool(tool_name, kwargs)
    return json.loads(result[0].text)


# ── DESTRUCTIVE_TOOLS ────────────────────────────────────────────────────────

EXPECTED_DESTRUCTIVE_TOOLS = {
    "create_midi_track",
    "create_audio_track",
    "create_session_clip",
    "duplicate_clip",
    "delete_clip",
    "clear_clip_notes",
    "set_parameter_value",
    "load_device",
    "load_sample_to_pad",
    "set_drum_pad_name",
    "create_drum_rack",
    "import_audio_clip",
    "set_clip_properties",
    "set_clip_warp",
    "write_midi_notes",
    "write_clip_automation",
    "analyze_and_warp",
    "create_smart_folder",
    "batch",
    # Transport (destructive: change playback/tempo/signature)
    "stop_all_clips",
    "stop_clip",
    "stop_track_clips",
    "set_tempo",
    "tap_tempo",
    "set_time_signature",
    "set_metronome",
    "set_overdub",
    "launch_scene",
    "launch_clip",
    # Mixer (destructive: change track/master mix state)
    "set_track_volume",
    "set_track_pan",
    "set_track_mute",
    "set_track_solo",
    "set_track_arm",
    "set_track_send",
    "set_track_monitoring",
    "set_crossfader",
    # Track/scene organization
    "set_track_name",
    "set_track_color",
    "duplicate_track",
    "delete_track",
    "create_scene",
    "set_scene_name",
    "set_scene_color",
    "duplicate_scene",
    "delete_scene",
}


def test_destructive_tools_dict():
    """All destructive operations are registered in ``DESTRUCTIVE_TOOLS``."""
    assert isinstance(mcp_server.DESTRUCTIVE_TOOLS, dict)
    # Every expected operation is present.
    for op in EXPECTED_DESTRUCTIVE_TOOLS:
        assert op in mcp_server.DESTRUCTIVE_TOOLS, f"Missing destructive tool: {op}"
    # Each value is a callable lambda.
    for name, preview_fn in mcp_server.DESTRUCTIVE_TOOLS.items():
        assert callable(preview_fn), f"Preview for '{name}' is not callable"


# ── Dry-run interception ─────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_dry_run_intercepts_delete_clip(mock_send):
    """``delete_clip`` with ``dry_run=True`` returns a preview and never hits TCP."""
    data = await _call("delete_clip", track_index=0, slot_index=2, dry_run=True)

    assert data["dry_run"] is True
    assert data["safe"] is True
    assert "Delete" in data["would_do"]
    assert "Track 0" in data["target"]
    assert "Slot 2" in data["target"]
    # The TCP send function must NOT have been called.
    mock_send.assert_not_called()


@pytest.mark.asyncio
async def test_dry_run_intercepts_set_parameter_value(mock_send):
    """``set_parameter_value`` with ``dry_run=True`` returns a preview."""
    data = await _call(
        "set_parameter_value",
        track_index=0,
        device_index=0,
        parameter_index=3,
        value=0.75,
        dry_run=True,
    )

    assert data["dry_run"] is True
    assert data["safe"] is True
    assert "0.75" in data["would_do"]
    assert "Track 0" in data["target"]
    mock_send.assert_not_called()


@pytest.mark.asyncio
async def test_dry_run_strips_before_forwarding(mock_send):
    """When ``dry_run`` is False the flag is removed before forwarding to TCP."""
    await _call(
        "set_parameter_value",
        track_index=0,
        device_index=0,
        parameter_index=1,
        value=0.5,
        dry_run=False,
    )

    mock_send.assert_called_once()
    forwarded_args = mock_send.call_args
    forwarded_payload = forwarded_args[0][1]  # second positional arg (payload dict)

    assert "dry_run" not in forwarded_payload, (
        "dry_run must be stripped before forwarding to LiveAgent"
    )
    assert forwarded_payload["value"] == 0.5


@pytest.mark.asyncio
async def test_dry_run_strips_when_absent(mock_send):
    """Even without dry_run in args, forwarding works and no dry_run leaks."""
    await _call("delete_clip", track_index=3, slot_index=1)

    mock_send.assert_called_once()
    _, forwarded_payload = mock_send.call_args[0]
    assert "dry_run" not in forwarded_payload


@pytest.mark.asyncio
async def test_batch_dry_run(mock_send):
    """``batch`` with ``dry_run=True`` previews all commands without executing."""
    commands = [
        {"command": "create_midi_track", "payload": {"index": -1}},
        {"command": "create_session_clip", "payload": {"track_index": 0, "slot_index": 0}},
        {
            "command": "write_midi_notes",
            "payload": {
                "track_index": 0,
                "slot_index": 0,
                "notes": [{"pitch": 60, "start": 0, "duration": 0.25}],
            },
        },
    ]
    data = await _call("batch", commands=commands, dry_run=True)

    assert data["dry_run"] is True
    assert data["safe"] is True
    assert "3 commands" in data["would_do"]
    assert "create_midi_track" in data["target"]
    assert "create_session_clip" in data["target"]
    assert "write_midi_notes" in data["target"]
    mock_send.assert_not_called()


@pytest.mark.asyncio
async def test_create_midi_track_dry_run_preview(mock_send):
    """``create_midi_track`` with ``dry_run=True`` previews without executing."""
    data = await _call("create_midi_track", index=-1, dry_run=True)

    assert data["dry_run"] is True
    assert data["safe"] is True
    assert "Create MIDI track" in data["would_do"]
    assert "Index -1" in data["target"]
    mock_send.assert_not_called()


@pytest.mark.asyncio
async def test_stop_clip_dry_run_preview(mock_send):
    """``stop_clip`` with ``dry_run=True`` previews the target slot."""
    data = await _call("stop_clip", track_index=2, slot_index=4, dry_run=True)

    assert data["dry_run"] is True
    assert "Stop clip" in data["would_do"]
    assert "Track 2" in data["target"]
    assert "Slot 4" in data["target"]
    mock_send.assert_not_called()


@pytest.mark.asyncio
async def test_set_track_name_dry_run_preview(mock_send):
    """``set_track_name`` with ``dry_run=True`` previews the rename."""
    data = await _call("set_track_name", track_index=1, name="Bass", dry_run=True)

    assert data["dry_run"] is True
    assert "Bass" in data["would_do"]
    assert "Track 1" in data["target"]
    mock_send.assert_not_called()


@pytest.mark.asyncio
async def test_set_drum_pad_name_dry_run_preview(mock_send):
    """``set_drum_pad_name`` with ``dry_run=True`` previews the pad rename."""
    data = await _call("set_drum_pad_name", track_index=2, pad_index=36, pad_name="Kick C", dry_run=True)

    assert data["dry_run"] is True
    assert "Kick C" in data["would_do"]
    assert "Pad 36" in data["target"]
    mock_send.assert_not_called()


@pytest.mark.asyncio
async def test_load_sample_to_pad_forwards_pad_name(mock_send):
    """``load_sample_to_pad`` forwards the optional pad_name field."""
    await _call(
        "load_sample_to_pad",
        track_index=2,
        pad_index=36,
        file_path="/tmp/kick.wav",
        pad_name="Kick C",
    )

    forwarded_command, forwarded_payload = mock_send.call_args[0]
    assert forwarded_command == "load_sample_to_pad"
    assert forwarded_payload["pad_name"] == "Kick C"


# ── eval / exec env-var gating ───────────────────────────────────────────────

@pytest.mark.asyncio
async def test_eval_disabled_by_default(mock_send_eval, env_cleanup):
    """eval returns an error when ``LIVEAGENT_ENABLE_UNSAFE`` is not set."""
    assert os.environ.get("LIVEAGENT_ENABLE_UNSAFE") is None

    data = await _call("eval", expr="1 + 1")

    assert "error" in data
    assert "disabled" in data["error"].lower()
    # The mock was still called (mcp_server forwards eval/exec).
    mock_send_eval.assert_called_once()


@pytest.mark.asyncio
async def test_eval_enabled_with_env_var(mock_send_eval, monkeypatch):
    """eval succeeds when ``LIVEAGENT_ENABLE_UNSAFE=1`` is set."""
    monkeypatch.setenv("LIVEAGENT_ENABLE_UNSAFE", "1")

    data = await _call("eval", expr="1 + 1")

    assert "error" not in data
    assert data.get("result") == 2
    mock_send_eval.assert_called_once()


@pytest.mark.asyncio
async def test_exec_disabled_by_default(mock_send_eval, env_cleanup):
    """exec returns an error when ``LIVEAGENT_ENABLE_UNSAFE`` is not set."""
    data = await _call("exec", stmt="x = 1")

    assert "error" in data
    assert "disabled" in data["error"].lower()


@pytest.mark.asyncio
async def test_exec_enabled_with_env_var(mock_send_eval, monkeypatch):
    """exec succeeds when ``LIVEAGENT_ENABLE_UNSAFE=1`` is set."""
    monkeypatch.setenv("LIVEAGENT_ENABLE_UNSAFE", "1")

    data = await _call("exec", stmt="x = 1")

    assert "error" not in data


# ── Transport commands ──────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_start_playing_forwards(mock_send):
    """``start_playing`` forwards to LiveAgent with no payload mutation."""
    await _call("start_playing")

    mock_send.assert_called_once()
    forwarded_command, forwarded_payload = mock_send.call_args[0]
    assert forwarded_command == "start_playing"
    assert "dry_run" not in forwarded_payload


@pytest.mark.asyncio
async def test_stop_playing_forwards(mock_send):
    """``stop_playing`` forwards to LiveAgent."""
    await _call("stop_playing")

    forwarded_command, _ = mock_send.call_args[0]
    assert forwarded_command == "stop_playing"


@pytest.mark.asyncio
async def test_set_tempo_forwards_value(mock_send):
    """``set_tempo`` forwards the tempo value verbatim."""
    await _call("set_tempo", tempo=124.0)

    forwarded_command, forwarded_payload = mock_send.call_args[0]
    assert forwarded_command == "set_tempo"
    assert forwarded_payload["tempo"] == 124.0
    assert "dry_run" not in forwarded_payload


@pytest.mark.asyncio
async def test_set_tempo_dry_run_preview(mock_send):
    """``set_tempo`` with ``dry_run=True`` returns a preview without executing."""
    data = await _call("set_tempo", tempo=140.0, dry_run=True)

    assert data["dry_run"] is True
    assert data["safe"] is True
    assert "140.0" in data["would_do"]
    assert "transport" in data["target"].lower()
    mock_send.assert_not_called()


@pytest.mark.asyncio
async def test_launch_scene_forwards_index(mock_send):
    """``launch_scene`` forwards the scene_index."""
    await _call("launch_scene", scene_index=3)

    forwarded_command, forwarded_payload = mock_send.call_args[0]
    assert forwarded_command == "launch_scene"
    assert forwarded_payload["scene_index"] == 3


@pytest.mark.asyncio
async def test_launch_scene_dry_run_preview(mock_send):
    """``launch_scene`` with ``dry_run=True`` previews without executing."""
    data = await _call("launch_scene", scene_index=2, dry_run=True)

    assert data["dry_run"] is True
    assert data["safe"] is True
    assert "2" in data["would_do"]
    mock_send.assert_not_called()


@pytest.mark.asyncio
async def test_launch_clip_forwards(mock_send):
    """``launch_clip`` forwards track and slot indices."""
    await _call("launch_clip", track_index=1, slot_index=0)

    forwarded_command, forwarded_payload = mock_send.call_args[0]
    assert forwarded_command == "launch_clip"
    assert forwarded_payload["track_index"] == 1
    assert forwarded_payload["slot_index"] == 0


@pytest.mark.asyncio
async def test_set_time_signature_forwards(mock_send):
    """``set_time_signature`` forwards both numerator and denominator."""
    await _call("set_time_signature", numerator=6, denominator=8)

    forwarded_command, forwarded_payload = mock_send.call_args[0]
    assert forwarded_command == "set_time_signature"
    assert forwarded_payload["numerator"] == 6
    assert forwarded_payload["denominator"] == 8


@pytest.mark.asyncio
async def test_get_transport_state_is_not_destructive(mock_send):
    """``get_transport_state`` is read-only: dry_run is stripped, not previewed."""
    data = await _call("get_transport_state", dry_run=True)

    # Not in DESTRUCTIVE_TOOLS, so dry_run is ignored (stripped, forwarded).
    mock_send.assert_called_once()
    forwarded_command, forwarded_payload = mock_send.call_args[0]
    assert forwarded_command == "get_transport_state"
    assert "dry_run" not in forwarded_payload
    # The response is whatever liveagent_send returned.
    assert data == {"status": "ok"}


@pytest.mark.asyncio
async def test_select_track_is_not_destructive(mock_send):
    """View-selection helpers are forwarded normally and do not get dry-run previews."""
    data = await _call("select_track", track_index=4, dry_run=True)

    mock_send.assert_called_once()
    forwarded_command, forwarded_payload = mock_send.call_args[0]
    assert forwarded_command == "select_track"
    assert forwarded_payload["track_index"] == 4
    assert "dry_run" not in forwarded_payload
    assert data == {"status": "ok"}


# ── Mixer commands ──────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_set_track_volume_forwards(mock_send):
    """``set_track_volume`` forwards track_index and volume verbatim."""
    await _call("set_track_volume", track_index=2, volume=0.75)

    forwarded_command, forwarded_payload = mock_send.call_args[0]
    assert forwarded_command == "set_track_volume"
    assert forwarded_payload["track_index"] == 2
    assert forwarded_payload["volume"] == 0.75
    assert "dry_run" not in forwarded_payload


@pytest.mark.asyncio
async def test_set_track_volume_dry_run_preview(mock_send):
    """``set_track_volume`` with ``dry_run=True`` previews without executing."""
    data = await _call("set_track_volume", track_index=1, volume=0.5, dry_run=True)

    assert data["dry_run"] is True
    assert data["safe"] is True
    assert "0.5" in data["would_do"]
    assert "Track 1" in data["target"]
    mock_send.assert_not_called()


@pytest.mark.asyncio
async def test_set_track_pan_forwards(mock_send):
    """``set_track_pan`` forwards track_index and pan."""
    await _call("set_track_pan", track_index=0, pan=-0.5)

    forwarded_command, forwarded_payload = mock_send.call_args[0]
    assert forwarded_command == "set_track_pan"
    assert forwarded_payload["pan"] == -0.5


@pytest.mark.asyncio
async def test_set_track_mute_dry_run_preview(mock_send):
    """``set_track_mute`` with ``dry_run=True`` previews the mute state."""
    data = await _call("set_track_mute", track_index=3, mute=True, dry_run=True)

    assert data["dry_run"] is True
    assert "True" in data["would_do"]
    assert "Track 3" in data["target"]
    mock_send.assert_not_called()


# ── Track/scene organization ────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_set_track_name_forwards(mock_send):
    """``set_track_name`` forwards track_index and name."""
    await _call("set_track_name", track_index=2, name="Lead")

    forwarded_command, forwarded_payload = mock_send.call_args[0]
    assert forwarded_command == "set_track_name"
    assert forwarded_payload == {"track_index": 2, "name": "Lead"}


@pytest.mark.asyncio
async def test_delete_scene_dry_run_preview(mock_send):
    """``delete_scene`` with ``dry_run=True`` previews the scene target."""
    data = await _call("delete_scene", scene_index=1, dry_run=True)

    assert data["dry_run"] is True
    assert "Delete scene" in data["would_do"]
    assert "Scene 1" in data["target"]
    mock_send.assert_not_called()


@pytest.mark.asyncio
async def test_set_track_solo_forwards(mock_send):
    """``set_track_solo`` forwards the solo flag."""
    await _call("set_track_solo", track_index=1, solo=True)

    forwarded_command, forwarded_payload = mock_send.call_args[0]
    assert forwarded_command == "set_track_solo"
    assert forwarded_payload["solo"] is True


@pytest.mark.asyncio
async def test_set_track_arm_forwards(mock_send):
    """``set_track_arm`` forwards the arm flag."""
    await _call("set_track_arm", track_index=0, arm=True)

    forwarded_command, forwarded_payload = mock_send.call_args[0]
    assert forwarded_command == "set_track_arm"
    assert forwarded_payload["arm"] is True


@pytest.mark.asyncio
async def test_set_track_send_forwards_all_params(mock_send):
    """``set_track_send`` forwards track_index, send_index, and value."""
    await _call("set_track_send", track_index=1, send_index=0, value=0.6)

    forwarded_command, forwarded_payload = mock_send.call_args[0]
    assert forwarded_command == "set_track_send"
    assert forwarded_payload["send_index"] == 0
    assert forwarded_payload["value"] == 0.6


@pytest.mark.asyncio
async def test_set_track_monitoring_forwards_enum(mock_send):
    """``set_track_monitoring`` forwards the monitoring int (0/1/2)."""
    await _call("set_track_monitoring", track_index=2, monitoring=1)

    forwarded_command, forwarded_payload = mock_send.call_args[0]
    assert forwarded_command == "set_track_monitoring"
    assert forwarded_payload["monitoring"] == 1


@pytest.mark.asyncio
async def test_set_crossfader_forwards(mock_send):
    """``set_crossfader`` forwards the position value."""
    await _call("set_crossfader", position=0.0)

    forwarded_command, forwarded_payload = mock_send.call_args[0]
    assert forwarded_command == "set_crossfader"
    assert forwarded_payload["position"] == 0.0


@pytest.mark.asyncio
async def test_set_crossfader_dry_run_preview(mock_send):
    """``set_crossfader`` with ``dry_run=True`` previews without executing."""
    data = await _call("set_crossfader", position=1.0, dry_run=True)

    assert data["dry_run"] is True
    assert "1.0" in data["would_do"]
    assert "crossfader" in data["target"].lower()
    mock_send.assert_not_called()
