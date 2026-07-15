#!/usr/bin/env python3
"""Generate documentation artifacts from the MCP tool definitions.

The MCP ``Tool(inputSchema=...)`` definitions in ``mcp_server.py`` are the
single source of truth for the command surface. This script derives:

  1. The English command-reference table for ``README.md``
     (between ``<!-- BEGIN COMMAND TABLE -->`` and ``<!-- END COMMAND TABLE -->``).
  2. The total command count, written into any ``<!-- COMMAND COUNT -->``
     placeholders in the README and ``docs/mcp-clients.md``.
  3. The grouped tool list for ``docs/mcp-clients.md``
     (between ``<!-- BEGIN TOOL GROUPS -->`` and ``<!-- END TOOL GROUPS -->``).

It also runs a consistency check: every tool registered in
``DESTRUCTIVE_TOOLS`` must have a ``dry_run`` property in its inputSchema
(automatically injected by ``_inject_dry_run``), and vice-versa.

Usage::

    python tools/generate_docs.py            # rewrite docs in place
    python tools/generate_docs.py --check    # exit 1 if docs are out of date

The script is idempotent: running it twice produces identical output.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

REPO_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_DIR))

from mcp.types import Tool  # noqa: E402

import mcp_server  # noqa: E402  (path set up above)

# ── Grouping metadata ─────────────────────────────────────────────────────
# The only hand-maintained metadata: which tool names belong to which doc
# group, and the order groups appear in. Tool names not listed here are
# collected under "Other". Keep this in sync with tool definitions in
# mcp_server.py — run ``--check`` to catch drift.
TOOL_GROUPS: list[tuple[str, list[str]]] = [
    ("Session & State", [
        "ping",
        "get_live_state",
        "list_tracks",
        "get_transport_state",
        "select_track",
        "select_scene",
        "select_clip",
        "select_device",
    ]),
    ("Transport", [
        "start_playing",
        "stop_playing",
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
    ]),
    ("Mixer", [
        "set_track_volume",
        "set_track_pan",
        "set_track_mute",
        "set_track_solo",
        "set_track_arm",
        "set_track_send",
        "set_track_monitoring",
        "set_crossfader",
    ]),
    ("Track & Scene Organization", [
        "set_track_name",
        "set_track_color",
        "duplicate_track",
        "delete_track",
        "create_scene",
        "set_scene_name",
        "set_scene_color",
        "duplicate_scene",
        "delete_scene",
    ]),
    ("MIDI", [
        "create_midi_track",
        "create_session_clip",
        "write_midi_notes",
        "read_clip_notes",
        "clear_clip_notes",
    ]),
    ("Devices & Parameters", [
        "list_devices",
        "set_parameter_value",
        "write_clip_automation",
        "load_device",
        "list_browser_devices",
    ]),
    ("Audio Clips", [
        "create_audio_track",
        "import_audio_clip",
        "get_clip_info",
        "set_clip_properties",
        "duplicate_clip",
        "delete_clip",
        "set_clip_warp",
        "analyze_and_warp",
    ]),
    ("Audio Analysis (standalone, no Live needed)", [
        "analyze_audio_file",
        "detect_pitch",
        "analyze_folder",
        "find_compatible_samples",
        "create_smart_folder",
    ]),
    ("Drum Rack", [
        "create_drum_rack",
        "load_sample_to_pad",
        "set_drum_pad_name",
        "inspect_drum_rack",
    ]),
    ("Advanced / Batching", [
        "batch",
        "eval",
        "exec",
    ]),
]


# ── Helpers ───────────────────────────────────────────────────────────────


async def fetch_tools() -> list[Tool]:
    """Return the full tool list as the MCP server advertises it."""
    return await mcp_server.list_tools()


def _param_summary(tool: Tool) -> str:
    """Render a compact ``key (type)`` summary of a tool's parameters."""
    schema = tool.inputSchema or {}
    props = schema.get("properties") or {}
    required = set(schema.get("required") or [])
    parts = []
    for name in sorted(props):
        if name == "dry_run":
            continue
        spec = props[name]
        ptype = spec.get("type", "?")
        marker = "*" if name in required else ""
        parts.append(f"`{name}`{marker} ({ptype})")
    return ", ".join(parts) if parts else "—"


def render_command_table(tools: list[Tool]) -> str:
    """Render the README English command-reference table body (rows only)."""
    lines = [
        "| Command | Description | Key Parameters |",
        "|---|---|---|",
    ]
    for tool in tools:
        # Keep descriptions to a single line and strip trailing periods.
        desc = tool.description.strip().rstrip(".").replace("\n", " ")
        # Truncate over-long descriptions for the table.
        if len(desc) > 100:
            desc = desc[:97] + "..."
        lines.append(f"| `{tool.name}` | {desc} | {_param_summary(tool)} |")
    return "\n".join(lines)


def render_tool_groups(tools: list[Tool]) -> str:
    """Render the grouped tool list used in docs/mcp-clients.md."""
    by_name = {t.name: t for t in tools}
    all_names = set(by_name)
    seen: set[str] = set()
    lines = []
    for group_name, names in TOOL_GROUPS:
        present = [n for n in names if n in by_name]
        if not present:
            continue
        seen.update(present)
        rendered = ", ".join(f"`{n}`" for n in present)
        lines.append(f"- **{group_name}:** {rendered}")
    others = sorted(all_names - seen)
    if others:
        rendered = ", ".join(f"`{n}`" for n in others)
        lines.append(f"- **Other:** {rendered}")
    return "\n".join(lines)


def _replace_block(text: str, begin_marker: str, end_marker: str, content: str) -> str:
    """Replace the content between two marker comments (markers preserved)."""
    prefix = f"<!-- {begin_marker} -->"
    suffix = f"<!-- {end_marker} -->"
    if prefix not in text or suffix not in text:
        raise ValueError(f"Markers not found: {begin_marker} / {end_marker}")
    head, _mid = text.split(prefix, 1)
    _mid2, tail = _mid.split(suffix, 1)
    return f"{head}{prefix}\n{content}\n{suffix}{tail}"


def _replace_placeholders(text: str, count: int) -> str:
    """Replace command-count placeholders with the live count.

    Uses an idempotent marker form ``<!-- COMMAND COUNT:NN -->`` so the
    placeholder survives regeneration. If a bare ``<!-- COMMAND COUNT -->``
    is found (legacy form), it is upgraded to the marker form.
    """
    import re

    marker_re = re.compile(r"<!-- COMMAND COUNT:\s*\d+\s*-->")
    bare = "<!-- COMMAND COUNT -->"
    replacement = f"<!-- COMMAND COUNT:{count} -->"
    # Upgrade any legacy bare placeholders to the marker form first.
    text = text.replace(bare, replacement)
    # Then refresh the count in any existing markers.
    text = marker_re.sub(replacement, text)
    return text


# ── Consistency check ────────────────────────────────────────────────────


def check_dry_run_consistency(tools: list[Tool]) -> list[str]:
    """Return a list of human-readable inconsistency messages (empty = OK)."""
    problems: list[str] = []
    destructive = set(mcp_server.DESTRUCTIVE_TOOLS)
    has_dry_run = {
        t.name
        for t in tools
        if "dry_run" in ((t.inputSchema or {}).get("properties") or {})
    }
    for name in sorted(destructive - has_dry_run):
        problems.append(f"{name}: in DESTRUCTIVE_TOOLS but missing dry_run schema")
    for name in sorted(has_dry_run - destructive):
        problems.append(f"{name}: has dry_run schema but not in DESTRUCTIVE_TOOLS")
    # Every defined tool must appear in a group (or "Other") — drift detection.
    by_name = {t.name for t in tools}
    grouped = {n for _g, names in TOOL_GROUPS for n in names}
    for name in sorted(by_name - grouped):
        problems.append(f"{name}: tool defined but not assigned to any group")
    for name in sorted(grouped - by_name):
        problems.append(f"{name}: listed in a group but no tool definition exists")
    return problems


# ── Main ─────────────────────────────────────────────────────────────────


def update_file(path: Path, new_text: str) -> bool:
    """Write new_text to path if it differs. Return True if changed."""
    old_text = path.read_text(encoding="utf-8")
    if old_text == new_text:
        return False
    path.write_text(new_text, encoding="utf-8")
    return True


async def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="Exit with code 1 if any doc is out of date (does not write).",
    )
    args = parser.parse_args(argv)

    tools = await fetch_tools()
    count = len(tools)

    # Consistency check first — surface schema/grouping drift loudly.
    problems = check_dry_run_consistency(tools)
    if problems:
        print("Consistency check failed:", file=sys.stderr)
        for p in problems:
            print(f"  - {p}", file=sys.stderr)
        return 1

    table = render_command_table(tools)
    groups = render_tool_groups(tools)

    targets = [
        REPO_DIR / "README.md",
        REPO_DIR / "docs" / "mcp-clients.md",
    ]

    changed_any = False
    for target in targets:
        if not target.exists():
            print(f"skip (missing): {target}", file=sys.stderr)
            continue
        text = target.read_text(encoding="utf-8")
        original = text
        if "<!-- BEGIN COMMAND TABLE -->" in text:
            text = _replace_block(text, "BEGIN COMMAND TABLE", "END COMMAND TABLE", table)
        if "<!-- BEGIN TOOL GROUPS -->" in text:
            text = _replace_block(text, "BEGIN TOOL GROUPS", "END TOOL GROUPS", groups)
        text = _replace_placeholders(text, count)
        if text != original:
            changed_any = True
            if args.check:
                print(f"out of date: {target}", file=sys.stderr)
            else:
                target.write_text(text, encoding="utf-8")
                print(f"updated: {target}")

    print(f"\n{count} commands registered.")
    if args.check and changed_any:
        print("\nDocs are out of date. Run: python tools/generate_docs.py", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
