"""Static checks for the Ableton Remote Script source.

The Remote Script imports Ableton-only modules, so these checks parse the source
instead of importing it. They catch structural regressions that only show up
when Live loads the script.
"""

import ast
from pathlib import Path

LIVEAGENT_PATH = Path(__file__).resolve().parents[1] / "LiveAgent" / "LiveAgent.py"


def _liveagent_class():
    tree = ast.parse(LIVEAGENT_PATH.read_text(encoding="utf-8"))
    for node in ast.iter_child_nodes(tree):
        if isinstance(node, ast.ClassDef) and node.name == "LiveAgent":
            return node
    raise AssertionError("LiveAgent class not found")


def test_server_thread_has_request_handler():
    """The request socket accept loop must target an implemented method."""
    methods = {
        item.name
        for item in ast.iter_child_nodes(_liveagent_class())
        if isinstance(item, ast.FunctionDef)
    }
    assert "_handle_client" in methods


def test_execute_routes_new_control_commands():
    """New operation tools should be reachable from LiveAgent._execute."""
    source = LIVEAGENT_PATH.read_text(encoding="utf-8")
    for command in (
        "select_track",
        "select_scene",
        "select_clip",
        "select_device",
        "stop_clip",
        "stop_track_clips",
        "set_track_name",
        "duplicate_scene",
        "set_drum_pad_name",
    ):
        assert f'command == "{command}"' in source
