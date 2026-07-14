---
name: liveagent-remote
description: Control Ableton Live via LiveAgent Remote — MCP tools or TCP socket (127.0.0.1:8765). Create MIDI clips, write notes, manage tracks, load devices, control Drum Racks, load Sample Librarian search results into kits, rename pads, analyze audio, and handle Ableton save/crash/restart popups. Works with any AI agent that supports MCP or TCP.
---

# LiveAgent Remote — Ableton Live Control for AI Agents

## ⚠️ CRITICAL RULES (read FIRST, every session)

1. **ALWAYS use MCP tools (`mcp_liveagent_*`) for LiveAgent commands.** Do NOT use raw TCP sockets (`nc`, Python `socket`) for routine commands. Raw TCP is ONLY for `eval`/`exec` LOM exploration during debugging. If MCP tools are available in your toolset, use them — they handle framing, timeouts, and error recovery automatically.

2. **MINIMIZE Ableton restarts.** Test via `eval`/`exec` FIRST. Every restart requires dismissing a save dialog. Only restart after confirming the approach works via eval.

3. **Do NOT make cascading changes when debugging.** When something breaks, diagnose the ROOT CAUSE first. Do NOT shotgun multiple fixes at once. **Rule: ONE targeted fix per restart.**

4. **After ANY LiveAgent.py modification, verify `eval` still works** — patches can introduce syntax errors that break the eval handler.

5. **`open file.nmsv` creates a NEW Live set** — it does NOT load a preset into the existing VST instance. To load a VST preset, use Ableton's browser or drag-and-drop.

## Architecture

```
AI Agent → MCP tools (mcp_liveagent_*) OR TCP 127.0.0.1:8765 → LiveAgent.py (in Ableton) → Ableton Live API
```

- **MCP Server:** `<repo>/mcp_server.py`
- **Control Surface Script:** `<repo>/LiveAgent/LiveAgent.py` → deployed to Ableton's MIDI Remote Scripts
- **Protocol:** JSON over TCP (port 8765)
- **Audio Analyzer:** `<repo>/audio_analyzer.py` (librosa-based, standalone — not through Ableton)

## Requirements

- Ableton Live 11+ (Standard or Suite)
- LiveAgent.py installed as a Control Surface Script
- Python 3.10+ (for MCP server), 3.7 is what Ableton uses internally
- For audio analysis: librosa (in project venv)

## Connection

Ableton must be running with LiveAgent enabled as a Control Surface:
- Preferences → Link/Tempo/MIDI → Control Surface: LiveAgent
- Input/Output: LiveAgent (or None)

Port 8765 is only available while Ableton is running with LiveAgent active.

### Proactive Ableton Launch

When MCP tools fail to connect, launch Ableton yourself:
```bash
open -a "Ableton Live 11 Standard"
```
Then wait 15-30 seconds and retry.

### Save/Crash Popup Handling

Ableton can block LiveAgent initialization with modal dialogs after quit, crash,
or Remote Script reload attempts. Always inspect the UI before assuming
LiveAgent is broken.

- If a save dialog appears (`Save changes?`, Japanese UI: `閉じる前に...保存しますか?`), do not click `Save` or `Don't Save` unless the user explicitly approved that choice for the current set. Press `Esc` / `Cancel` to back out if the dialog was opened by accident.
- If a crash recovery dialog appears, report the exact options. Do not discard or overwrite a recovered set without explicit user direction.
- Do not force-quit Ableton just to reload a script when the set may contain unsaved user work.
- After any modal is dismissed, wait 10-20 seconds and retry `mcp_liveagent_ping`.
- If the screen is locked, global coordinate clicks may not work. Prefer app accessibility state and keyboard actions; ask the user to unlock or choose the save/recovery option when needed.

Remote Script reload checklist:
```bash
cp LiveAgent/LiveAgent.py "/Applications/Ableton Live 11 Standard.app/Contents/App-Resources/MIDI Remote Scripts/LiveAgent/LiveAgent.py"
rm -rf "/Applications/Ableton Live 11 Standard.app/Contents/App-Resources/MIDI Remote Scripts/LiveAgent/__pycache__"
```
Then reselect the LiveAgent Control Surface or restart Ableton. If restart shows
a save dialog, stop and ask for the user's save/discard decision.

## Available MCP Tools (67 total)

### Session
- `mcp_liveagent_ping` — Check connection
- `mcp_liveagent_get_live_state` — Tempo, tracks, scenes, playing state
- `mcp_liveagent_list_tracks` — All tracks with devices and clips
- `mcp_liveagent_get_transport_state` — Transport state and song time
- `mcp_liveagent_select_track` — Select a track in Live's UI
- `mcp_liveagent_select_scene` — Select a scene
- `mcp_liveagent_select_clip` — Select/focus a clip
- `mcp_liveagent_select_device` — Select a device on a track
- `mcp_liveagent_eval` — Evaluate Python expression in LOM context (debug/exploration)
- `mcp_liveagent_exec` — Execute Python statement in LOM context (assignments)

### Transport
- `mcp_liveagent_start_playing` — Start playback
- `mcp_liveagent_stop_playing` — Stop playback
- `mcp_liveagent_stop_all_clips` — Stop all session clips
- `mcp_liveagent_stop_clip` — Stop one clip slot
- `mcp_liveagent_stop_track_clips` — Stop clips on one track
- `mcp_liveagent_set_tempo` — Set BPM
- `mcp_liveagent_tap_tempo` — Tap tempo
- `mcp_liveagent_set_time_signature` — Set time signature
- `mcp_liveagent_set_metronome` — Toggle metronome
- `mcp_liveagent_set_overdub` — Toggle MIDI overdub
- `mcp_liveagent_launch_scene` — Launch a scene
- `mcp_liveagent_launch_clip` — Launch one clip

### Mixer
- `mcp_liveagent_set_track_volume` — Set track volume
- `mcp_liveagent_set_track_pan` — Set track pan
- `mcp_liveagent_set_track_mute` — Mute/unmute track
- `mcp_liveagent_set_track_solo` — Solo/unsolo track
- `mcp_liveagent_set_track_arm` — Arm/disarm track
- `mcp_liveagent_set_track_send` — Set send level
- `mcp_liveagent_set_track_monitoring` — Set monitoring state
- `mcp_liveagent_set_crossfader` — Set master crossfader

### Track & Scene Organization
- `mcp_liveagent_set_track_name` — Rename track
- `mcp_liveagent_set_track_color` — Set track color
- `mcp_liveagent_duplicate_track` — Duplicate track
- `mcp_liveagent_delete_track` — Delete track
- `mcp_liveagent_create_scene` — Create scene
- `mcp_liveagent_set_scene_name` — Rename scene
- `mcp_liveagent_set_scene_color` — Set scene color
- `mcp_liveagent_duplicate_scene` — Duplicate scene
- `mcp_liveagent_delete_scene` — Delete scene

### MIDI
- `mcp_liveagent_create_midi_track` — Create MIDI track at index (-1 = end)
- `mcp_liveagent_create_session_clip` — Create MIDI clip on track/slot
- `mcp_liveagent_write_midi_notes` — Write notes array to clip
- `mcp_liveagent_read_clip_notes` — Read notes from clip
- `mcp_liveagent_clear_clip_notes` — Clear all notes from clip

### Devices
- `mcp_liveagent_list_devices` — List all devices on a track
- `mcp_liveagent_set_parameter_value` — Set device parameter by index or name
- `mcp_liveagent_write_clip_automation` — Write automation envelope to clip
- `mcp_liveagent_load_device` — Load VST/AU plugin by name from browser
- `mcp_liveagent_list_browser_devices` — Search browser for available devices

### Audio Clips
- `mcp_liveagent_create_audio_track` — Create audio track
- `mcp_liveagent_import_audio_clip` — Import audio file to track/slot
- `mcp_liveagent_get_clip_info` — Get clip details (warp, pitch, gain, etc.)
- `mcp_liveagent_set_clip_properties` — Set clip name, color, loop, pitch, gain
- `mcp_liveagent_duplicate_clip` — Duplicate clip to another slot
- `mcp_liveagent_delete_clip` — Delete clip from track/slot
- `mcp_liveagent_set_clip_warp` — Set warp on/off and warp mode
- `mcp_liveagent_analyze_and_warp` — Auto-detect BPM/key and set warp markers

### Drum Rack
- `mcp_liveagent_create_drum_rack` — Create Drum Rack on MIDI track
- `mcp_liveagent_load_sample_to_pad` — Load sample onto Drum Rack pad; pass `pad_name` to label the pad at load time
- `mcp_liveagent_set_drum_pad_name` — Rename a Drum Rack pad without loading a sample
- `mcp_liveagent_inspect_drum_rack` — Debug: inspect pad structure

### Audio Analysis (librosa, standalone)
- `mcp_liveagent_analyze_audio_file` — Full analysis: BPM, key, beats, duration
- `mcp_liveagent_detect_pitch` — Fundamental pitch detection for one-shots
- `mcp_liveagent_analyze_folder` — Batch analyze folder (pitch, BPM, key)
- `mcp_liveagent_find_compatible_samples` — Camelot Wheel key matching
- `mcp_liveagent_create_smart_folder` — Generate key-matched symlink folder

### Advanced / Batching
- `mcp_liveagent_batch` — Execute multiple LiveAgent commands as one undo step

## MIDI Note Format

```json
{"pitch": 60, "start": 0.0, "duration": 1.0, "velocity": 96}
```

- `pitch`: MIDI note number (0-127). Middle C = 60
- `start`: Beat position (0.0 = clip start)
- `duration`: Length in beats
- `velocity`: 0-127

## Common Pitch Reference

| Note | Octave 2 | Octave 3 | Octave 4 | Octave 5 |
|------|----------|----------|----------|----------|
| C    | 36       | 48       | 60       | 72       |
| C#/Db| 37       | 49       | 61       | 73       |
| D    | 38       | 50       | 62       | 74       |
| D#/Eb| 39       | 51       | 63       | 75       |
| E    | 40       | 52       | 64       | 76       |
| F    | 41       | 53       | 65       | 77       |
| F#/Gb| 42       | 54       | 66       | 78       |
| G    | 43       | 55       | 67       | 79       |
| G#/Ab| 44       | 56       | 68       | 80       |
| A    | 45       | 57       | 69       | 81       |
| A#/Bb| 46       | 58       | 70       | 82       |
| B    | 47       | 59       | 71       | 83       |

## Standard Drum Pad Map

| Pad | MIDI Note | Drum |
|-----|-----------|------|
| 36  | C1        | Kick |
| 38  | D1        | Snare |
| 40  | E1        | Snare alt |
| 42  | F#1       | Closed Hi-Hat |
| 44  | G#1       | Pedal Hi-Hat |
| 46  | A#1       | Open Hi-Hat |
| 48  | C2        | Tom 1 / Sampler |
| 49  | C#2       | Crash |
| 51  | D#2       | Ride |

## Warp Modes

| Index | Mode |
|-------|------|
| 0     | Beats |
| 1     | Tones |
| 2     | Texture |
| 3     | Re-Pitch |
| 4     | Complex |
| 5     | Complex Pro |

## LOM Exploration via eval/exec

LiveAgent exposes `eval` and `exec` commands for runtime LOM (Live Object Model) exploration.

### eval — Evaluate expression, return result
```python
# Via MCP tool
mcp_liveagent_eval(expr="song.tracks[4].devices[0].class_name")
# → {"result": "DrumGroupDevice"}
```

Available names: `Live`, `song`, `app`, `os`, `json`, `len`, `str`, `int`, `float`, `list`, `dict`, `range`, `enumerate`, `type`, `dir`, `getattr`, `hasattr`, `repr`, `isinstance`, `True`, `False`, `None`.

### exec — Execute statement (for assignments)
```python
mcp_liveagent_exec(stmt="song.view.selected_track = song.tracks[4]")
```

Available names: `Live`, `song`, `app`, `os`, `json`.

### Key LOM Objects
- `song` — the Live set (`Live.Song`)
- `app` — the application (`Live.Application.get_application()`)
- `app.browser` — the browser (NOT `song.browser` — does NOT exist in CS scripts)
- `song.view` — view selection (selected_track, selected_chain, select_device)

## Browser API

**IMPORTANT:** Use `app.browser` (via `Live.Application.get_application().browser`). `song.browser` does NOT exist in Control Surface scripts and raises `AttributeError`.

### Browser Structure
- `browser.instruments` — BrowserItem (instruments)
- `browser.drums` — BrowserItem (drum kits)
- `browser.audio_effects` — BrowserItem
- `browser.midi_effects` — BrowserItem
- `browser.plugins` — BrowserItem (VST/AU)
- `browser.samples` — BrowserItem (~2500 built-in samples)
- `browser.user_folders` — BrowserItemVector (user-added Places)
- `browser.user_library` — BrowserItem

**⚠️ `browser.categories` does NOT exist** — always use the property-based `cat_map` pattern:
```python
cat_map = {
    "plug-in": browser.plugins,
    "instrument": browser.instruments,
    "audio_effect": browser.audio_effects,
    "midi_effect": browser.midi_effects,
    "drum": browser.drums,
    "sample": browser.samples,
}
```

### BrowserItem Attributes
- `.name` — display name
- `.uri` — internal URI
- `.is_loadable` — bool
- `.is_folder` — bool
- `.is_device` — bool
- `.children` — BrowserItemVector of children
- `.iter_children()` — iterator

### Key Methods
- `browser.load_item(item)` — load item onto selected track/device
- `browser.preview_item = item` / `browser.stop_preview()` — audio preview
- `browser.hotswap_target = device` — set hot-swap target for sample replacement

**⚠️ `BrowserItem` has NO `.load()` method** — always use `browser.load_item(item)`.
**⚠️ Set `browser.preview_item = item` BEFORE `browser.load_item(item)`** — without preview, load may silently no-op.

## Drum Rack Workflow

### Creating a Drum Rack

```python
# Select target track, then load Drum Rack from browser instruments
mcp_liveagent_exec(stmt='song.view.selected_track = song.tracks[N]')
# Then via browser:
mcp_liveagent_eval(expr='[c for c in app.browser.instruments.children if c.name == "Drum Rack"]')
mcp_liveagent_exec(stmt='app.browser.load_item([c for c in app.browser.instruments.children if c.name == "Drum Rack"][0])')
```

**Practical pads: 36 (C1) through 51** for the visible 4×4 pad bank.

### Empty Drum Racks CANNOT Receive Samples Directly

Empty pads have no chains, and `drum_pads[N].chains` Vector is read-only (cannot `append()`).

**Solution:** Use a preset kit (.adg) like "808 Core Kit" as a template — it provides pre-existing chains on pads 36-51. Then hotswap individual pad samples.

### Loading Samples onto Pads (hotswap_target technique)

```python
browser = Live.Application.get_application().browser

# 1. Navigate to the Simpler in the target pad
pad = drum_rack.drum_pads[PAD]
chain = pad.chains[0]
first_device = chain.devices[0]
inner_chains = getattr(first_device, 'chains', None)
simpler = inner_chains[0].devices[0] if inner_chains else first_device

# 2. Clear previous hotswap (REQUIRED)
browser.hotswap_target = None

# 3. Select pad AND chain (BOTH required)
drum_rack.view.selected_drum_pad = pad
song.view.selected_chain = chain

# 4. Set hotswap target
browser.hotswap_target = simpler

# 5. Find and load the sample
browser.load_item(sample)  # swaps sample IN the Simpler, Rack survives!

# 6. Clean up
browser.hotswap_target = None
```

The `load_sample_to_pad` MCP tool handles sample replacement automatically.
For normal agent work, prefer the MCP tool over hand-written LOM hotswap code.

### Loading Search Results as a Named Kit

Use this path when Sample Librarian returns search results that should become a
Live Drum Rack kit:

1. Create a usable template rack, not an empty rack:
   ```python
   mcp_liveagent_create_drum_rack(name="Sample Librarian Kit", kit_name="808 Core Kit.adg")
   ```
2. Map results to MIDI pads. Common defaults: Kick=36, Snare=38, Clap=39, Percussion=40, Closed Hat=42, Shaker=44, Open Hat=46, Crash=49.
3. Load each sample with a visible pad label:
   ```python
   mcp_liveagent_load_sample_to_pad(
       track_index=T,
       pad_index=36,
       file_path="/absolute/path/kick.wav",
       pad_name="Kick C",
   )
   ```
4. Rename without replacing the sample when needed:
   ```python
   mcp_liveagent_set_drum_pad_name(track_index=T, pad_index=36, pad_name="Kick C")
   ```
5. Verify with `mcp_liveagent_inspect_drum_rack(track_index=T, pad_range=[36, 52])`.
   Check both `name` and `chain_name`; Live versions differ on which one drives
   the visible pad label.

Sample Librarian bridge support:
- `librarian.live_agent_bridge.load_to_drum_pad(..., pad_name="...")` forwards `pad_name`.
- `build_drum_rack_for_key()` passes each selected sample's `name` as `pad_name`.
- If a user provides raw search results, use the result `name` for `pad_name` unless they request shorter role labels.

After changing pad-name code in `LiveAgent.py`, reload the Control Surface and run:
```bash
python tools/liveagent_pad_name_smoke.py
```
This creates a temporary Drum Rack, loads a temporary WAV onto pad 36, verifies
`pad_name`, verifies `set_drum_pad_name`, then deletes the temporary track.

## Audio Analysis

Standalone librosa-based analysis (does NOT require Ableton running):

```bash
VENV_PY="<repo>/.venv/bin/python3"
ANALYZER="<repo>/audio_analyzer.py"

# Full analysis (BPM + key)
$VENV_PY $ANALYZER file.wav

# Pitch detection only (for one-shots)
$VENV_PY $ANALYZER file.wav --pitch-only

# Batch folder analysis (sorted by pitch)
$VENV_PY $ANALYZER ./folder/ --folder --mode pitch

# Camelot Wheel key matching
$VENV_PY $ANALYZER ./folder/ --compatible Fm
```

### Sample Type Classification
| Type | Duration | Typical Content |
|------|----------|----------------|
| `oneshot` | < 2s | Kicks, snares, hi-hats |
| `short_loop` | 2-5s | Toms, bells, FX |
| `medium_loop` | 5-15s | Pads, strings |
| `long_loop` | > 15s | Ambience, full phrases |

### Analysis Cache
Results are persisted to `.analysis_cache/` as per-file JSON (keyed by path + mtime + size MD5). Cache survives across sessions and auto-invalidates on file changes.

## Key-Matched Drum Kit Workflow

1. Run `find_compatible_samples(folder_path=category_dir, target_key="Fm", mode="pitch")` per category
2. Select best match per pad role (highest confidence, correct pitch range)
3. Load via `load_sample_to_pad(track_index, pad_index, file_path, pad_name=sample_name)`
4. Verify via `inspect_drum_rack`; accept either `name` or `chain_name` matching the requested pad label

## Configuration

The repo is fully portable — no hardcoded user paths.

- **`config.example.py`** — Template with empty fields (committed)
- **`config.local.py`** — User-specific paths (gitignored)
- **`config.py`** — Loader: reads `config.local.py`, then env vars, then defaults
- **`setup.sh`** — One-command setup: venv, pip install, config creation, LiveAgent.py deployment

```bash
# Setup
cd live-agent-remote
bash setup.sh

# Or manually
cp config.example.py config.local.py
# Edit config.local.py with your paths
/opt/homebrew/bin/python3 -m venv .venv
.venv/bin/pip install librosa mcp soundfile numpy scipy
```

## Registering MCP Server

### Hermes Agent
Add to `~/.hermes/profiles/<profile>/config.yaml`:
```yaml
mcp_servers:
  liveagent:
    command: <repo>/.venv/bin/python3
    args: [<repo>/mcp_server.py]
    env:
      LIVEAGENT_HOST: 127.0.0.1
      LIVEAGENT_PORT: "8765"
```

### Other MCP Clients
Point your MCP client to:
```
Command: <repo>/.venv/bin/python3
Args: [<repo>/mcp_server.py]
```

## Music Theory Quick Reference

### Common Chord Voicings (C Minor context)

| Chord  | Notes (MIDI)                |
|--------|------------------------------|
| Cm     | 48, 55, 63                   |
| Cm7    | 48, 55, 63, 66               |
| Fm     | 41, 48, 56                   |
| Fm7    | 41, 48, 56, 59               |
| Gm7b5  | 43, 55, 58, 61               |
| Abmaj7 | 44, 56, 59, 63               |
| Bbm9   | 46, 53, 58, 63, 65, 68       |

### UK Garage Stab Pattern (8 bars)
- Chord hits on off-beats (beat 0.5, 1.5, 2.5, etc.) with velocity variation
- Accent pattern: louder on 2nd and 4th beats
- Chord progression: Fm9 → Bbm9 → Dbmaj9 → Cm9 (2 bars each)

### 2-Step Drum Pattern
- Kick on beats 1 and 3 (or syncopated)
- Snare on beat 2 (classic garage) or shuffled
- Ghost notes on 16ths with swing
- Hi-hat patterns with swing/shuffle feel

## Pitfalls (Read These!)

### Connection
- Port 8765 only available while Ableton is running with LiveAgent active
- After Ableton launches, wait 15-30 seconds before connecting
- Killing Ableton may leave a "Save changes?" popup that blocks LiveAgent init
- Copying `LiveAgent.py` into MIDI Remote Scripts does not update the already-running script; reselect the Control Surface or restart Ableton
- If a new command returns `Unknown command` after copying the file, the running Live process still has the old Remote Script loaded
- Never choose `Save` / `Don't Save` in a Live modal unless the user has approved that exact action for the current set

### Browser
- **`song.browser` does NOT exist** — use `app.browser` via `Live.Application.get_application().browser`
- **`browser.categories` does NOT exist** — use the `cat_map` dict pattern
- **`BrowserItem` has NO `.load()` method** — use `browser.load_item(item)`
- **`browser.samples` only has built-in indexed samples** — for user libraries, search `browser.user_folders`
- **Ableton browser does NOT resolve symlinks** — add real paths to Library.cfg, not symlink chains
- **`browser.preview_item = item` is REQUIRED before `browser.load_item(item)`**
- **`BrowserItem.children` is fragile** — call `list(node.children)` ONCE and reuse the list

### Drum Rack
- **Empty Drum Racks CANNOT receive samples** — always start with a preset kit (.adg)
- **`drum_pads[N].chains` is READ-ONLY** — cannot append to empty pads
- **`copy_pad` works** but copied pads may reject `hotswap_target` — test empirically
- **`browser.load_item` on MIDI tracks DESTROYS Drum Rack** — use `hotswap_target` technique instead
- **Pad names may surface as `name` or `chain_name`** — check both after `pad_name` / `set_drum_pad_name`
- **Recovery: `song.undo()`** reverses accidental load_item replacements

### VST Plugins
- **VST params only expose 1 at a time via Configure** — Ableton registers only the LAST touched parameter
- **VST GUIs are invisible to macOS Accessibility** — cannot read knobs/sliders via AX
- **No LOM API to load .nmsv into existing plugin instance** — use browser or drag-and-drop

### eval/exec
- **NO access to `self` or LiveAgent module** — only `Live`, `song`, `app`, `os`, `json`
- **`eval` can break after LiveAgent.py patches** — syntax errors in the file break the eval handler
- **Keep eval expressions simple** — one attribute per call, avoid complex comprehensions
- **`replace_selected_notes` format** — must be `tuple(tuple([pitch, start, duration, velocity, mute]))`, NOT dict

### Audio Analysis
- **`find_compatible_samples` may timeout on large folders (5K+ files)** — use `mode='pitch'` for speed, or target smaller subfolders
- **`aubio` fails on Python 3.14** — use librosa only
- **Background Python output buffering** — use `-u` flag AND `PYTHONUNBUFFERED=1`

### General
- **Track indices are 0-based** — track 0 = first track
- **Clip slots are 0-based** — slot 0 = first clip slot
- **Single TCP commands are immediate** — use `batch` when multiple mutations should share one undo step
- **`write_midi_notes` — always use `slot_index`** (not `clip_slot_index`)
- **MCP `inputSchema` required on ALL tools** — even zero-arg tools like `ping`
- **Large note arrays** — for 200+ notes, write JSON to temp file first (shell arg limits)

## Workflow: Generate MIDI Pattern

1. **Check state:** `mcp_liveagent_get_live_state` — verify connection
2. **Create clip:** `mcp_liveagent_create_session_clip(track_index, slot_index, length_beats, name)`
3. **Build notes** — generate note array programmatically
4. **Write notes:** `mcp_liveagent_write_midi_notes(track_index, slot_index, notes)`
5. **Verify:** `mcp_liveagent_read_clip_notes(track_index, slot_index)`

## Client Usage (Python, for non-MCP environments)

```python
import socket, json

def liveagent_send(command, payload=None):
    payload = payload or {}
    payload["command"] = command
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.connect(("127.0.0.1", 8765))
    sock.sendall((json.dumps(payload) + "\n").encode())
    data = b""
    while True:
        chunk = sock.recv(8192)
        if not chunk:
            break
        data += chunk
    sock.close()
    return json.loads(data.decode())

# Example
result = liveagent_send("get_live_state")
print(result)
```

## Git Operations

When pushing from AI agent environments, use the user's HOME for credentials:
```bash
HOME=/Users/<username> git push origin main
```

If `git push` fails from the agent environment, ask the user to push from their terminal.
