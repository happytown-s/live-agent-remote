# Connecting MCP Clients to LiveAgent Remote

LiveAgent Remote ships with a built-in **MCP (Model Context Protocol) server**
that exposes all Ableton Live commands as tools. Any MCP-compatible client can
connect to it.

- **Transport:** stdio
- **Entry point:** `mcp_server.py`
- **Command:** `python3 mcp_server.py` (or use the project venv's Python)

## Prerequisites

1. **Clone and set up the project:**
   ```bash
   git clone https://github.com/happytown-s/live-agent-remote.git
   cd live-agent-remote

   # Create a virtual environment with the MCP library
   python3 -m venv .venv
   .venv/bin/pip install "mcp[cli]" librosa soundfile numpy scipy
   ```

2. **Ableton Live must be running** with the LiveAgent control surface active
   (Preferences → Link/Tempo/MIDI → Control Surface: LiveAgent).

3. **Note your absolute paths.** Replace `<repo>` in the configs below with the
   real path to your `live-agent-remote` directory, e.g.
   `/Users/yourname/projects/live-agent-remote`.

---

## Quick Reference: Config Snippet

All clients use the same core config. The only difference is the file location
and JSON/YAML format.

**Core config (stdio transport):**

| Field    | Value                                      |
|----------|--------------------------------------------|
| Command  | `<repo>/.venv/bin/python3`                 |
| Args     | `[<repo>/mcp_server.py]`                   |
| Transport| `stdio` (implicit for most clients)        |

> **Important:** Always use the **absolute path** to the venv Python, not
> `python` or `python3` from your shell. The system Python may not have the
> `mcp` package installed.

---

## 1. Claude Desktop

**Config file:**
```
~/Library/Application Support/Claude/claude_desktop_config.json
```
(macOS) — create the file if it doesn't exist.

**Config:**
```json
{
  "mcpServers": {
    "ableton-live": {
      "command": "/absolute/path/to/live-agent-remote/.venv/bin/python3",
      "args": [
        "/absolute/path/to/live-agent-remote/mcp_server.py"
      ]
    }
  }
}
```

**Steps:**
1. Fully quit Claude Desktop (`Cmd+Q`).
2. Edit (or create) `claude_desktop_config.json`.
3. Paste the config above, replacing the paths.
4. Relaunch Claude Desktop.
5. Start a new conversation — the Ableton Live tools will appear as
   `mcp_liveagent_*` functions.

**Verification:**
- Click the **tools icon** (plug icon) in Claude Desktop to confirm the server
  is connected.
- Ask Claude: *"Check if Ableton Live is connected."* — it should call
  `mcp_liveagent_ping`.

**Troubleshooting:**
- If the server shows as failed, check the paths are absolute and the venv
  Python exists.
- View logs at `~/Library/Logs/Claude/mcp-server-ableton-live.log`.
- See [troubleshooting.md](troubleshooting.md#8-mcp-server-not-starting) for
  more.

---

## 2. Cursor

**Config file:**
```
<project-root>/.cursor/mcp.json
```
Create this in your project directory (Cursor reads it per-project).

**Config:**
```json
{
  "mcpServers": {
    "ableton-live": {
      "command": "/absolute/path/to/live-agent-remote/.venv/bin/python3",
      "args": [
        "/absolute/path/to/live-agent-remote/mcp_server.py"
      ]
    }
  }
}
```

**Steps:**
1. Open your project in Cursor.
2. Create `.cursor/mcp.json` in the project root.
3. Paste the config above, replacing the paths.
4. Reload the Cursor window (`Cmd+Shift+P` → "Developer: Reload Window").
5. The tools will be available in Cursor's chat / agent mode.

**Verification:**
- Open Cursor Settings → MCP to confirm the server status is "connected".
- In agent mode, ask Cursor to *"list all tracks in Ableton Live."*

**Note:** You can also place the config at `~/.cursor/mcp.json` for global
availability across all projects.

---

## 3. Codex CLI

[Codex CLI](https://github.com/openai/codex) supports MCP servers via its
configuration file.

**Config file:**
```
~/.codex/config.json
```
(or `~/.codex/config.toml` depending on your Codex version)

**Config (JSON):**
```json
{
  "mcpServers": {
    "ableton-live": {
      "command": "/absolute/path/to/live-agent-remote/.venv/bin/python3",
      "args": [
        "/absolute/path/to/live-agent-remote/mcp_server.py"
      ]
    }
  }
}
```

**Config (TOML — some Codex versions):**
```toml
[mcp_servers.ableton-live]
command = "/absolute/path/to/live-agent-remote/.venv/bin/python3"
args = ["/absolute/path/to/live-agent-remote/mcp_server.py"]
```

**Steps:**
1. Install Codex CLI: `npm install -g @openai/codex`
2. Create/edit the config file.
3. Restart your terminal or Codex session.
4. Run `codex` and verify the Ableton tools are available.

**Verification:**
```bash
codex --list-tools
```
Look for `mcp_liveagent_ping` and other `mcp_liveagent_*` tools.

---

## 4. Hermes Agent

[Hermes Agent](https://hermes-agent.nousresearch.com/) supports MCP servers
via its profile configuration.

**Config file:**
```
~/.hermes/profiles/<profile-name>/config.yaml
```

**Config (YAML):**
```yaml
mcp_servers:
  ableton-live:
    command: /absolute/path/to/live-agent-remote/.venv/bin/python3
    args:
      - /absolute/path/to/live-agent-remote/mcp_server.py
    env:
      LIVEAGENT_HOST: 127.0.0.1
      LIVEAGENT_PORT: "8765"
```

**Steps:**
1. Identify your active Hermes profile (default: `default`).
2. Edit `~/.hermes/profiles/<profile>/config.yaml`.
3. Add the `mcp_servers` block above under the top level.
4. Reload the profile or restart Hermes Agent.

**Verification:**
```bash
# List available MCP tools
hermes tools list | grep liveagent
```

**Note:** The `env` block is optional — the MCP server defaults to
`127.0.0.1:8765`. Include it only if you need to override the host or port.

---

## 5. OpenClaw

[OpenClaw](https://github.com/openclaw/openclaw) supports MCP servers through
its configuration file.

**Config file:**
```
~/.openclaw/config.json
```
(or the path specified by your OpenClaw installation)

**Config:**
```json
{
  "mcpServers": {
    "ableton-live": {
      "command": "/absolute/path/to/live-agent-remote/.venv/bin/python3",
      "args": [
        "/absolute/path/to/live-agent-remote/mcp_server.py"
      ]
    }
  }
}
```

**Steps:**
1. Install OpenClaw per its documentation.
2. Create/edit `~/.openclaw/config.json`.
3. Add the `mcpServers` block above.
4. Restart OpenClaw or reload its configuration.

**Verification:**
- Check OpenClaw's tool list for `mcp_liveagent_*` tools.
- Send a test command: *"Ping Ableton Live and tell me the current tempo."*

---

## Generic Connection (Any MCP Client)

For any MCP-compatible client not listed above, the connection parameters are:

| Parameter  | Value                                            |
|------------|--------------------------------------------------|
| Transport  | `stdio`                                          |
| Command    | `<repo>/.venv/bin/python3`                       |
| Args       | `[<repo>/mcp_server.py]`                         |
| Server name| `ableton-live` (or any name your client expects) |

Most MCP clients follow the same JSON schema:

```json
{
  "mcpServers": {
    "<your-server-name>": {
      "command": "<repo>/.venv/bin/python3",
      "args": ["<repo>/mcp_server.py"]
    }
  }
}
```

---

## Available Tools (43)

Once connected, the following tools are exposed:

<!-- BEGIN TOOL GROUPS -->
- **Session & State:** `ping`, `get_live_state`, `list_tracks`, `get_transport_state`, `select_track`, `select_scene`, `select_clip`, `select_device`
- **Transport:** `start_playing`, `stop_playing`, `stop_all_clips`, `stop_clip`, `stop_track_clips`, `set_tempo`, `tap_tempo`, `set_time_signature`, `set_metronome`, `set_overdub`, `launch_scene`, `launch_clip`
- **Mixer:** `set_track_volume`, `set_track_pan`, `set_track_mute`, `set_track_solo`, `set_track_arm`, `set_track_send`, `set_track_monitoring`, `set_crossfader`
- **Track & Scene Organization:** `set_track_name`, `set_track_color`, `duplicate_track`, `delete_track`, `create_scene`, `set_scene_name`, `set_scene_color`, `duplicate_scene`, `delete_scene`
- **MIDI:** `create_midi_track`, `create_session_clip`, `write_midi_notes`, `read_clip_notes`, `clear_clip_notes`
- **Devices & Parameters:** `list_devices`, `set_parameter_value`, `write_clip_automation`, `load_device`, `list_browser_devices`
- **Audio Clips:** `create_audio_track`, `import_audio_clip`, `get_clip_info`, `set_clip_properties`, `duplicate_clip`, `delete_clip`, `set_clip_warp`, `analyze_and_warp`
- **Audio Analysis (standalone, no Live needed):** `analyze_audio_file`, `detect_pitch`, `analyze_folder`, `find_compatible_samples`, `create_smart_folder`
- **Drum Rack:** `create_drum_rack`, `load_sample_to_pad`, `set_drum_pad_name`, `inspect_drum_rack`
- **Advanced / Batching:** `batch`, `eval`, `exec`
<!-- END TOOL GROUPS -->

All tools are prefixed with `mcp_liveagent_` in most clients (e.g.,
`mcp_liveagent_ping`, `mcp_liveagent_write_midi_notes`).

---

## Testing the Connection

After configuring any client, verify the connection works:

1. **Ensure Ableton Live is running** with LiveAgent selected as a Control
   Surface.

2. **Ask your AI agent to ping Ableton:**
   > "Check if Ableton Live is connected."

   Expected: The agent calls `ping` and reports success.

3. **Ask for the current state:**
   > "What's the current tempo and how many tracks are there?"

   Expected: The agent calls `get_live_state` and reads the result.

4. **If the connection fails,** see
   [troubleshooting.md](troubleshooting.md) for common issues.

---

## Security Notes

- The MCP server connects to Ableton via **localhost TCP** (`127.0.0.1:8765`).
  It cannot reach Ableton on a remote machine.
- `eval` and `exec` are **disabled by default**. See
  [security.md](security.md) for how to enable them.
- Destructive operations support `dry_run: true` for safe previewing.
- Use `batch()` to group multiple operations into a single undo step.

For the full security model, see [security.md](security.md).
