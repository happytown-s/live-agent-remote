<div align="center">

# 🎹 LiveAgent Remote

**Programmable control surface for Ableton Live**

Control tracks, clips, MIDI notes, devices, and automation from any external script or AI agent via a simple JSON socket protocol.

<p>
  <a href="https://happytown-s.github.io/live-agent-remote/"><b>🌐 Landing Page</b></a> · <a href="https://happytown-s.github.io/sample-librarian/"><b>🔍 sample-librarian</b></a>
</p>

![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)
![Python](https://img.shields.io/badge/Python-3.10+-green.svg)
![Ableton Live](https://img.shields.io/badge/Ableton%20Live-11%20%7C%2012-orange.svg)
![MCP Compatible](https://img.shields.io/badge/MCP-Compatible-purple.svg)
![Platform](https://img.shields.io/badge/Platform-macOS%20%7C%20Windows-lightgrey.svg)

[English](#english) | [日本語](#日本語) | [中文](#中文) | [한국어](#한국어) | [Español](#español) | [Français](#français)

</div>

---

## English

### What is this?

LiveAgent is a MIDI Remote Script that runs **inside** Ableton Live and opens a TCP socket (`127.0.0.1:8765`). Any external program can send JSON commands to control Ableton programmatically — no additional software, plugins, or DAW modifications needed.

### Features

- 🎵 Create MIDI tracks, clips, and write notes programmatically
- 🎛️ Load plugins/devices, read and set parameters
- 🥁 Create Drum Racks and load samples onto pads
- 🔊 Import audio clips, auto-warp with BPM/key detection
- 🎯 Pitch detection & Camelot Wheel harmonic matching
- 🤖 Perfect for AI agent integration (ChatGPT, Claude, custom bots)
- 📊 Read clip automation and write envelope points
- 🔌 Works with any language that supports TCP sockets
- ⚡ Sub-millisecond latency, no MIDI routing needed

### Installation

**Quick Setup:**
```bash
git clone https://github.com/happytown-s/live-agent-remote.git
cd live-agent-remote
./setup.sh
```

**Manual Setup:**
1. Copy the `LiveAgent` folder into your Ableton MIDI Remote Scripts directory:

**macOS:**
```
/Applications/Ableton Live [version]/Contents/App-Resources/MIDI Remote Scripts/
```

**Windows:**
```
C:\ProgramData\Ableton\Live [version]\Resources\MIDI Remote Scripts\
```

2. Restart Ableton Live
3. Go to **Preferences → Link/Tempo/MIDI**
4. In the **Control Surface** dropdown, select **LiveAgent**
5. Done! The agent is now listening on `127.0.0.1:8765`

### Quick Start (Python)

```bash
pip install live-agent-remote
```

```python
from live_agent_client import LiveAgentClient

client = LiveAgentClient()

# Check connection
print(client.ping())

# List all tracks
tracks = client.list_tracks()

# Create a clip with notes
client.create_session_clip(track_index=1, slot_index=0, length_beats=16)
client.write_midi_notes(track_index=1, slot_index=0, notes=[
    {"pitch": 60, "start": 0.0, "duration": 1.0, "velocity": 96},
    {"pitch": 64, "start": 1.0, "duration": 1.0, "velocity": 96},
])

# Load a plugin
client.load_device(track_index=1, device_name="Massive")

# Set a parameter
client.set_parameter_value(track_index=1, device_name="Massive", parameter_name="MASTER-VOLUME", value=0.7)

client.close()
```

### Quick Start (Node.js)

```javascript
const { LiveAgentClient } = require('./client/live_agent_client');

const client = new LiveAgentClient();

async function main() {
  const state = await client.ping();
  console.log('Connected:', state);

  const tracks = await client.listTracks();
  console.log('Tracks:', tracks);

  await client.loadDevice(1, 'Massive');
}

main();
```

### Quick Start (curl / any TCP client)

Send a JSON line followed by newline to `127.0.0.1:8765`:

```bash
echo '{"command":"ping"}' | nc 127.0.0.1 8765
```

### Command Reference

<!-- BEGIN COMMAND TABLE -->
| Command | Description | Key Parameters |
|---|---|---|
| `ping` | Check if Ableton Live is connected and responding via LiveAgent | — |
| `get_live_state` | Get the full state of Ableton Live: tempo, tracks, scenes, playing status, selected track | — |
| `list_tracks` | List all tracks in the current Ableton Live set with their devices, clips, and settings | — |
| `select_track` | Select a track in Ableton Live's UI so subsequent browser/device operations target it | `track_index`* (integer) |
| `select_scene` | Select a scene in Ableton Live's session view | `scene_index`* (integer) |
| `select_clip` | Select a clip by track and session slot, focusing it in the detail view when Live exposes that se... | `slot_index`* (integer), `track_index`* (integer) |
| `select_device` | Select a device on a track by index or name, useful before hotswap and browser operations | `device_index` (integer), `device_name` (string), `track_index`* (integer) |
| `get_transport_state` | Get transport state: tempo, playing status, time signature, metronome, overdub | — |
| `start_playing` | Start playback of the Ableton Live transport | — |
| `stop_playing` | Stop playback of the Ableton Live transport | — |
| `stop_all_clips` | Stop all currently playing clips in the session view | — |
| `stop_clip` | Stop a specific clip slot without stopping other clips | `slot_index`* (integer), `track_index`* (integer) |
| `stop_track_clips` | Stop all clips playing on one track without stopping the rest of the set | `track_index`* (integer) |
| `set_tempo` | Set the project tempo (BPM) | `tempo`* (number) |
| `tap_tempo` | Tap the tempo. Call repeatedly in rhythm to set the tempo by tapping | — |
| `set_time_signature` | Set the time signature (e.g. 4/4, 3/4, 6/8) | `denominator` (integer), `numerator` (integer) |
| `set_metronome` | Turn the metronome on or off | `enabled`* (boolean) |
| `set_overdub` | Enable or disable MIDI overdub recording (new notes added without replacing existing) | `enabled`* (boolean) |
| `launch_scene` | Launch (fire) a scene in session view, starting all clips in that row | `scene_index`* (integer) |
| `launch_clip` | Launch (fire) a clip in a specific track and session slot | `slot_index`* (integer), `track_index`* (integer) |
| `set_track_volume` | Set a track's volume fader (0.0 = silent, 1.0 = max) | `track_index`* (integer), `volume`* (number) |
| `set_track_pan` | Set a track's pan position (-1.0 = hard left, 0.0 = center, 1.0 = hard right) | `pan`* (number), `track_index`* (integer) |
| `set_track_mute` | Mute or unmute a track | `mute`* (boolean), `track_index`* (integer) |
| `set_track_solo` | Solo or unsolo a track | `solo`* (boolean), `track_index`* (integer) |
| `set_track_arm` | Arm or disarm a track for recording. Only works on armable track types (MIDI/audio) | `arm`* (boolean), `track_index`* (integer) |
| `set_track_send` | Set a track's send level to a return bus (0=A, 1=B, etc.). Value is 0.0-1.0 | `send_index`* (integer), `track_index`* (integer), `value`* (number) |
| `set_track_monitoring` | Set a track's monitoring state: 0=In, 1=Auto, 2=Off | `monitoring`* (integer), `track_index`* (integer) |
| `set_crossfader` | Set the master crossfader position (-1.0 = A, 0.0 = center, 1.0 = B) | `position`* (number) |
| `create_midi_track` | Create a new MIDI track in Ableton Live | `index` (integer) |
| `set_track_name` | Rename a track | `name`* (string), `track_index`* (integer) |
| `set_track_color` | Set a track color using Ableton's integer RGB color value | `color`* (integer), `track_index`* (integer) |
| `duplicate_track` | Duplicate a track, including its devices and clips | `track_index`* (integer) |
| `delete_track` | Delete a track from the Live set | `track_index`* (integer) |
| `create_scene` | Create a new scene in session view | `color` (integer), `index` (integer), `name` (string) |
| `set_scene_name` | Rename a scene | `name`* (string), `scene_index`* (integer) |
| `set_scene_color` | Set a scene color using Ableton's integer RGB color value | `color`* (integer), `scene_index`* (integer) |
| `duplicate_scene` | Duplicate a scene in session view | `scene_index`* (integer) |
| `delete_scene` | Delete a scene from the Live set | `scene_index`* (integer) |
| `create_session_clip` | Create a new MIDI clip in session view on a specific track and slot | `length_beats` (number), `name` (string), `replace` (boolean), `slot_index`* (integer), `track_index`* (integer) |
| `write_midi_notes` | Write MIDI notes to a clip. Notes are specified as an array of {pitch, start, duration, velocity} | `notes`* (array), `slot_index`* (integer), `track_index`* (integer) |
| `read_clip_notes` | Read all MIDI notes from a clip | `length_beats` (number), `slot_index`* (integer), `track_index`* (integer) |
| `clear_clip_notes` | Clear all notes from a MIDI clip | `slot_index`* (integer), `track_index`* (integer) |
| `list_devices` | List all devices (plugins, built-in effects) on a track with their parameters | `track_index`* (integer) |
| `set_parameter_value` | Set a parameter value on a device. Identify device/parameter by index or name | `device_index` (integer), `device_name` (string), `parameter_index` (integer), `parameter_name` (string), `track_index`* (integer), `value`* (number) |
| `write_clip_automation` | Write automation envelope points to a clip for a specific device parameter | `device_index` (integer), `device_name` (string), `parameter_index` (integer), `parameter_name` (string), `points`* (array), `slot_index`* (integer), `step_duration` (number), `track_index`* (integer) |
| `load_device` | Load a plugin/device onto a track by searching Ableton's browser. Supports VST/AU plugins, built-... | `browser_type` (string), `device_name`* (string), `track_index`* (integer) |
| `list_browser_devices` | Search and list available devices/plugins from Ableton's browser. Use this to find what's install... | `browser_type` (string), `max_results` (integer), `query` (string) |
| `create_audio_track` | Create a new audio track in Ableton Live | `index` (integer) |
| `import_audio_clip` | Import an audio file (wav, aiff, mp3, etc.) into a track slot. The file must exist on disk | `file_path`* (string), `slot_index`* (integer), `track_index`* (integer) |
| `get_clip_info` | Get detailed info about a clip: name, type (audio/MIDI), loop settings, warp, pitch, gain, file p... | `slot_index`* (integer), `track_index`* (integer) |
| `set_clip_properties` | Set clip properties: name, color, loop start/end, start/end markers, pitch, gain | `color` (integer), `end_marker` (number), `gain` (number), `loop_end` (number), `loop_start` (number), `looping` (boolean), `name` (string), `pitch_coarse` (integer), `pitch_fine` (number), `slot_index`* (integer), `start_marker` (number), `track_index`* (integer) |
| `duplicate_clip` | Duplicate a clip to another slot (same or different track) | `dest_slot_index` (integer), `dest_track_index` (integer), `slot_index`* (integer), `track_index`* (integer) |
| `delete_clip` | Delete a clip from a track slot | `slot_index`* (integer), `track_index`* (integer) |
| `set_clip_warp` | Set warp properties on an audio clip. Warp modes: 0=beats, 1=tones, 2=texture, 3=re-pitch, 4=comp... | `slot_index`* (integer), `track_index`* (integer), `warp_mode` (integer), `warping` (boolean) |
| `analyze_and_warp` | Analyze an audio clip for BPM and key, then auto-set warp markers. Pass detected BPM and key from... | `bpm` (number), `key` (string), `slot_index`* (integer), `track_index`* (integer), `warp_mode` (integer) |
| `analyze_audio_file` | Analyze an audio file on disk for BPM, musical key, duration, and beat positions. Uses librosa fo... | `file_path`* (string) |
| `detect_pitch` | Detect the fundamental pitch of a one-shot audio sample (kick, snare, etc). Returns note name, fr... | `file_path`* (string) |
| `analyze_folder` | Analyze all audio files in a folder for BPM, key, pitch, and sample type (oneshot/loop classifica... | `folder_path`* (string), `mode` (string), `sample_type` (string) |
| `find_compatible_samples` | Find samples in a folder that are harmonically compatible with a target key using the Camelot Whe... | `folder_path`* (string), `mode` (string), `target_key`* (string) |
| `create_smart_folder` | Create a smart folder in Ableton's browser with symlinks to samples that are harmonically compati... | `base_path` (string), `categories` (array), `target_key`* (string) |
| `create_drum_rack` | Create a MIDI track with a usable Drum Rack. By default loads 808 Core Kit.adg so pads 36-51 alre... | `empty` (boolean), `kit_name` (string), `name` (string), `track_index` (integer) |
| `load_sample_to_pad` | Load a browser-indexed sample file onto a Drum Rack pad by loading it as a Simpler then moving it... | `drum_rack_index` (integer), `file_path`* (string), `pad_index`* (integer), `pad_name` (string), `reset_effects` (boolean), `track_index`* (integer) |
| `set_drum_pad_name` | Rename a Drum Rack pad without loading a new sample. Use after librarian_search/librarian_load_to... | `drum_rack_index` (integer), `pad_index`* (integer), `pad_name`* (string), `track_index`* (integer) |
| `inspect_drum_rack` | Inspect a Drum Rack's pad structure. Returns pad names, active state, chain devices, and sample f... | `drum_rack_index` (integer), `pad_range` (array), `track_index`* (integer) |
| `eval` | Evaluate a Python expression in LiveAgent's Ableton Live context. Returns the result. Available v... | `expr`* (string) |
| `exec` | Execute a Python statement in LiveAgent's Ableton Live context. Available variables: Live, song, ... | `stmt`* (string) |
| `batch` | Execute multiple LiveAgent commands as a single undo step. All operations can be undone with one ... | `commands`* (array) |
<!-- END COMMAND TABLE -->

### Note Format

```json
{
  "pitch": 60,
  "start": 0.0,
  "duration": 1.0,
  "velocity": 96,
  "muted": false
}
```

### Architecture

```
External Script / AI Agent
        │
        ▼
   TCP Socket (127.0.0.1:8765)
        │
        ▼
   LiveAgent.py (Ableton Control Surface)
        │
        ▼
   Ableton Live API (LOM)
```

### Event Push (Real-time State Notifications)

LiveAgent can **push** state-change events to subscribers in real time, so
external scripts can react to tempo changes, play/stop, mixer moves, and
clip launches without polling.

**How it works:** LiveAgent snapshots transport + mixer + clip state every
250ms, diffs it against the previous snapshot, and pushes a JSON event to
every subscriber. A separate port (`8766`) is used so the request/response
channel (`8765`) is unaffected.

> **Note:** Event push is available to the **Python/JS SDK clients** and raw
> TCP clients only. MCP clients (Claude Desktop, Cursor) cannot receive
> pushed events — MCP is request/response only.

**Python:**
```python
from live_agent_client import LiveAgentSubscriber

sub = LiveAgentSubscriber()  # connects to 127.0.0.1:8766
sub.on("transport_changed", lambda data: print("tempo:", data))
sub.on("mixer_changed", lambda data: print("mixer:", data))
sub.on("clip_launched", lambda data: print("launched:", data))
sub.listen()  # background thread; callbacks fire on state changes
```

**Event types:** `transport_changed`, `mixer_changed`, `clip_launched`,
`clip_stopped`. Subscribe to categories: `["transport", "mixer", "scenes"]`.

See `examples/events_demo.py` for a runnable demo.

### Audio Analyzer

Built-in audio analysis powered by [librosa](https://librosa.org/):

- **BPM Detection** — `librosa.beat.beat_track` for tempo extraction
- **Key Detection** — Krumhansl-Schmuckler algorithm for all 24 keys
- **Pitch Detection** — `pyin` monophonic pitch detection for one-shot samples (kicks, snares, etc.)
- **Sample Type Classification** — Auto-classify by duration: One-Shot (<2s), Short Loop (2-5s), Medium Loop (5-15s), Long Loop (>15s)
- **Camelot Wheel** — Harmonic compatibility matching for DJ-style key mixing
- **Batch Analysis** — Analyze entire folders, sort by pitch or key, filter by sample type
- **Smart Folders** — Auto-generate symlinks of compatible samples visible in Ableton's browser
- **Auto-Warp** — Detect BPM/key and auto-apply warp settings in Ableton

**CLI usage:**
```bash
# Analyze a single file
python audio_analyzer.py kick.wav

# Detect pitch of a one-shot
python audio_analyzer.py snare.wav --pitch-only

# Analyze all files in a folder (sorted by pitch)
python audio_analyzer.py ./Kicks/ --folder --mode pitch

# Find samples compatible with Fm (Camelot Wheel)
python audio_analyzer.py ./Kicks/ --compatible Fm
```

**Python API:**
```python
from audio_analyzer import AudioAnalyzer

# Single file
result = AudioAnalyzer.analyze("loop.wav")
# {"bpm": 128.5, "key": "Fm", "beat_count": 32, ...}

# One-shot pitch (includes duration + sample type)
pitch = AudioAnalyzer.detect_pitch("kick.wav")
# {"pitch": "C1", "frequency": 32.7, "is_atonal": False, "duration_seconds": 0.45, "sample_type": "oneshot", "sample_type_label": "One-Shot"}

# Filter folder by sample type (only one-shots)
results = AudioAnalyzer.analyze_folder("./Kicks", mode="pitch")
oneshots = [r for r in results if r.get("sample_type") == "oneshot"]

# Find compatible samples
matches = AudioAnalyzer.find_compatible_samples("./Kicks", "Fm")
# {"compatible_count": 142, "compatible": [...]}
```

### MCP Server (Claude Desktop / Cursor / etc.)

LiveAgent includes a built-in **MCP (Model Context Protocol) server** that lets AI agents control Ableton directly.

**Setup:**

1. Install dependencies:
```bash
cd live-agent-remote
python3 -m venv .venv
.venv/bin/pip install "mcp[cli]"
```

2. Add to your MCP client config:

**Claude Desktop** (`~/Library/Application Support/Claude/claude_desktop_config.json`):
```json
{
  "mcpServers": {
    "ableton-live": {
      "command": "/absolute/path/to/live-agent-remote/.venv/bin/python3",
      "args": ["/absolute/path/to/live-agent-remote/mcp_server.py"]
    }
  }
}
```

**Cursor** (`.cursor/mcp.json`):
```json
{
  "mcpServers": {
    "ableton-live": {
      "command": "/absolute/path/to/live-agent-remote/.venv/bin/python3",
      "args": ["/absolute/path/to/live-agent-remote/mcp_server.py"]
    }
  }
}
```

3. Restart your MCP client. All <!-- COMMAND COUNT:67 --> commands are now available as tools!

---

## 日本語

### これは何？

LiveAgentはAbleton Liveの**内部**で動作するMIDI Remote Scriptです。TCPソケット（`127.0.0.1:8765`）を開き、外部プログラムからJSONコマンドでAbletonを操作できるようにします。追加ソフトウェアやプラグイン不要です。

### 特徴

- 🎵 トラック作成、クリップ作成、MIDIノート書き込みをプログラムで実行
- 🎛️ プラグイン/デバイスのロード、パラメータ読み取り・設定
- 🤖 AIエージェント（ChatGPT、Claude等）との統合に最適
- 📊 オートメーションの読み取り・書き込み
- 🔌 TCPソケット対応の任意の言語から使用可能
- ⚡ ミリ秒未満のレイテンシ

### インストール手順

1. `LiveAgent`フォルダをAbletonのMIDI Remote Scriptsディレクトリにコピー：

**macOS:**
```
/Applications/Ableton Live [バージョン]/Contents/App-Resources/MIDI Remote Scripts/
```

**Windows:**
```
C:\ProgramData\Ableton\Live [バージョン]\Resources\MIDI Remote Scripts\
```

2. Ableton Liveを再起動
3. **Preferences → Link/Tempo/MIDI** を開く
4. **Control Surface** のドロップダウンから **LiveAgent** を選択
5. 完了！`127.0.0.1:8765`で待受開始

### クイックスタート（Python）

```python
from live_agent_client import LiveAgentClient

client = LiveAgentClient()

# 接続確認
print(client.ping())

# トラック一覧取得
tracks = client.list_tracks()

# クリップ作成＋ノート書き込み
client.create_session_clip(track_index=1, slot_index=0, length_beats=16)
client.write_midi_notes(track_index=1, slot_index=0, notes=[
    {"pitch": 60, "start": 0.0, "duration": 1.0, "velocity": 96},
    {"pitch": 64, "start": 1.0, "duration": 1.0, "velocity": 96},
])

# プラグイン読み込み
client.load_device(track_index=1, device_name="Massive")

client.close()
```

### コマンド一覧

| コマンド | 説明 |
|---|---|
| `ping` | 接続確認 |
| `get_live_state` | テンポ・トラック・シーン・再生状態を取得 |
| `list_tracks` | 全トラック情報を取得 |
| `get_transport_state` | トランスポート状態取得（テンポ・拍子・メトロノーム等） |
| `start_playing` | 再生開始 |
| `stop_playing` | 再生停止 |
| `stop_all_clips` | 全クリップ停止 |
| `set_tempo` | テンポ（BPM）設定 |
| `tap_tempo` | タップテンポ |
| `set_time_signature` | 拍子記号設定 |
| `set_metronome` | メトロノームON/OFF |
| `set_overdub` | オーバーダブON/OFF |
| `launch_scene` | シーンを起動（その行のクリップを再生） |
| `launch_clip` | クリップを起動 |
| `set_track_volume` | トラックの音量設定（0.0〜1.0） |
| `set_track_pan` | トラックのパン設定（-1.0〜1.0） |
| `set_track_mute` | トラックのミュートON/OFF |
| `set_track_solo` | トラックのソロON/OFF |
| `set_track_arm` | トラックのアーム（録音待機）ON/OFF |
| `set_track_send` | トラックのセンドレベル設定 |
| `set_track_monitoring` | トラックのモニタリング状態設定（In/Auto/Off） |
| `set_crossfader` | マスタークロスフェーダー位置設定 |
| `create_midi_track` | MIDIトラック作成 |
| `create_session_clip` | セッションビューにクリップ作成 |
| `write_midi_notes` | クリップにMIDIノート書き込み |
| `read_clip_notes` | クリップのノート読み取り |
| `clear_clip_notes` | クリップのノート全削除 |
| `list_devices` | トラックのデバイス一覧 |
| `set_parameter_value` | デバイスパラメータ設定 |
| `write_clip_automation` | オートメーション書き込み |
| `load_device` | プラグインをトラックにロード |
| `list_browser_devices` | プラグイン一覧検索 |
| `create_audio_track` | オーディオトラック作成 |
| `import_audio_clip` | オーディオファイルをトラックにインポート |
| `get_clip_info` | クリップ詳細取得（名前、タイプ、ループ、ワープ） |
| `set_clip_properties` | クリップ名・色・ループ・ピッチ・ゲイン設定 |
| `duplicate_clip` | クリップを別スロットに複製 |
| `delete_clip` | クリップ削除 |
| `set_clip_warp` | ワープON/OFF・ワープモード設定 |
| `analyze_and_warp` | BPM/キー検出結果で自動ワープ設定 |
| `analyze_audio_file` | オーディオファイルのBPM・キー・ビート解析 |
| `detect_pitch` | ワンショットサンプルのピッチ検出 |
| `analyze_folder` | フォルダ一括解析（ピッチ順ソート） |
| `find_compatible_samples` | Camelot Wheelでキー互換サンプル検索 |
| `create_smart_folder` | Abletonブラウザに互換サンプルのスマートフォルダ作成 |
| `create_drum_rack` | MIDIトラックにDrum Rack作成 |
| `load_sample_to_pad` | Drum Rackパッドにサンプルをロード |
| `inspect_drum_rack` | Drum Rackパッド構造の検査（デバッグ用） |
| `eval` | LiveコンテキストでPython式を評価 |
| `exec` | LiveコンテキストでPython文を実行 |

### イベントPush（リアルタイム状態通知）

LiveAgentは状態変化を**リアルタイムにpush**通知できます。テンポ変更・再生/停止・ミキサー操作・クリップ起動を、ポーリングなしで外部スクリプトに通知します。

**仕組み:** LiveAgentが250ms毎にトランスポート+ミキサー+クリップ状態をスナップショットし、前回との差分をJSONイベントとして全subscriberにpushします。専用ポート（`8766`）を使用するため、request/responseチャネル（`8765`）への影響はありません。

> **注意:** イベントpushは **Python/JS SDKクライアント** と raw TCPクライアントのみ利用可能です。MCPクライアント（Claude Desktop、Cursor）はpushを受信できません（MCPはrequest/response専用）。

```python
from live_agent_client import LiveAgentSubscriber

sub = LiveAgentSubscriber()  # 127.0.0.1:8766 に接続
sub.on("transport_changed", lambda data: print("テンポ:", data))
sub.on("mixer_changed", lambda data: print("ミキサー:", data))
sub.on("clip_launched", lambda data: print("起動:", data))
sub.listen()  # バックグラウンドスレッド; コールバックが状態変化で発火
```

**イベント種別:** `transport_changed`, `mixer_changed`, `clip_launched`, `clip_stopped`。カテゴリ購読: `["transport", "mixer", "scenes"]`。実行例は `examples/events_demo.py` を参照。

### オーディオ解析

[librosa](https://librosa.org/)による内蔵オーディオ解析：

- **BPM検出** — `librosa.beat.beat_track`でテンポ抽出
- **キー検出** — Krumhansl-Schmucklerアルゴリズムで全24調を判定
- **ピッチ検出** — `pyin`でワンショット（キック・スネア等）の基本音高を検出
- **サンプル分類** — 長さで自動分類: One-Shot（2秒未満）, Short Loop（2〜5秒）, Medium Loop（5〜15秒）, Long Loop（15秒超）
- **Camelot Wheel** — DJスタイルのキーマッチング
- **一括解析** — フォルダ全体を解析、ピッチ順でソート、サンプルタイプでフィルタ可能
- **スマートフォルダ** — 互換サンプルのシンボリックリンクを自動生成、Abletonブラウザから直接閲覧可能
- **自動ワープ** — BPM/キー検出→Abletonにワープ自動適用

**CLI使用例:**
```bash
python audio_analyzer.py kick.wav                  # 単一ファイル解析
python audio_analyzer.py snare.wav --pitch-only    # ピッチ検出のみ
python audio_analyzer.py ./Kicks/ --folder --mode pitch  # フォルダ一括（ピッチ順）
python audio_analyzer.py ./Kicks/ --compatible Fm  # Fmと互換するサンプル検索
```

### MCPサーバー（Claude Desktop / Cursor等）

LiveAgentは**MCPサーバー**を内蔵しており、AIエージェントからAbletonを直接操作できます。

**セットアップ:**

1. 依存パッケージをインストール：
```bash
cd live-agent-remote
python3 -m venv .venv
.venv/bin/pip install "mcp[cli]" librosa
```

2. MCPクライアントの設定ファイルに追加：

**Claude Desktop** (`~/Library/Application Support/Claude/claude_desktop_config.json`):
```json
{
  "mcpServers": {
    "ableton-live": {
      "command": "/absolute/path/to/live-agent-remote/.venv/bin/python3",
      "args": ["/absolute/path/to/live-agent-remote/mcp_server.py"]
    }
  }
}
```

3. MCPクライアントを再起動。全51コマンドがツールとして利用可能！

---

## 中文

### 这是什么？

LiveAgent 是一个运行在 Ableton Live **内部** 的 MIDI Remote Script。它通过 TCP 套接字（`127.0.0.1:8765`）接收 JSON 命令，让你可以用任何外部程序控制 Ableton。无需额外软件或插件。

### 安装步骤

1. 将 `LiveAgent` 文件夹复制到 Ableton 的 MIDI Remote Scripts 目录：

**macOS:**
```
/Applications/Ableton Live [版本]/Contents/App-Resources/MIDI Remote Scripts/
```

**Windows:**
```
C:\ProgramData\Ableton\Live [版本]\Resources\MIDI Remote Scripts\
```

2. 重启 Ableton Live
3. 打开 **Preferences → Link/Tempo/MIDI**
4. 在 **Control Surface** 下拉菜单中选择 **LiveAgent**
5. 完成！现在可以通过 `127.0.0.1:8765` 发送命令

### 快速开始（Python）

```python
from live_agent_client import LiveAgentClient

client = LiveAgentClient()
print(client.ping())                    # 检查连接
tracks = client.list_tracks()           # 列出所有轨道
client.load_device(track_index=1, device_name="Massive")  # 加载插件
client.close()
```

### 命令列表

| 命令 | 说明 |
|---|---|
| `ping` | 连接检查 |
| `get_live_state` | 获取速度、轨道、场景、播放状态 |
| `list_tracks` | 列出所有轨道 |
| `get_transport_state` | 获取传输状态（速度、拍号、节拍器等） |
| `start_playing` | 开始播放 |
| `stop_playing` | 停止播放 |
| `stop_all_clips` | 停止所有剪辑 |
| `set_tempo` | 设置速度（BPM） |
| `tap_tempo` | 敲击速度 |
| `set_time_signature` | 设置拍号 |
| `set_metronome` | 节拍器开关 |
| `set_overdub` | 叠录开关 |
| `launch_scene` | 启动场景（播放该行所有剪辑） |
| `launch_clip` | 启动剪辑 |
| `set_track_volume` | 设置轨道音量（0.0-1.0） |
| `set_track_pan` | 设置轨道声相（-1.0到1.0） |
| `set_track_mute` | 轨道静音开关 |
| `set_track_solo` | 轨道独奏开关 |
| `set_track_arm` | 轨道预备录音开关 |
| `set_track_send` | 设置轨道发送电平 |
| `set_track_monitoring` | 设置轨道监听状态（In/Auto/Off） |
| `set_crossfader` | 设置主交叉推子位置 |
| `create_midi_track` | 创建MIDI轨道 |
| `create_session_clip` | 创建Session剪辑 |
| `write_midi_notes` | 写入MIDI音符 |
| `read_clip_notes` | 读取音符 |
| `clear_clip_notes` | 清除所有音符 |
| `list_devices` | 列出设备 |
| `set_parameter_value` | 设置参数值 |
| `write_clip_automation` | 写入自动化 |
| `load_device` | 加载插件到轨道 |
| `list_browser_devices` | 搜索/列出可用插件 |
| `create_audio_track` | 创建音频轨道 |
| `import_audio_clip` | 导入音频文件到轨道 |
| `get_clip_info` | 获取剪辑详情（名称、类型、循环、Warp） |
| `set_clip_properties` | 设置剪辑名称、颜色、循环、音高、增益 |
| `duplicate_clip` | 复制剪辑到其他位置 |
| `delete_clip` | 删除剪辑 |
| `set_clip_warp` | 设置Warp开关和模式 |
| `analyze_and_warp` | 使用BPM/调性检测结果自动设置Warp |
| `analyze_audio_file` | 分析音频文件的BPM、调性、节拍 |
| `detect_pitch` | 检测单次采样（Kick/Snare等）的音高 |
| `analyze_folder` | 批量分析文件夹，按音高排序 |
| `find_compatible_samples` | 使用Camelot Wheel搜索调性兼容的采样 |
| `create_smart_folder` | 在Ableton浏览器中创建兼容采样的智能文件夹 |
| `create_drum_rack` | 在MIDI轨道上创建Drum Rack |
| `load_sample_to_pad` | 将采样加载到Drum Rack打击垫 |
| `inspect_drum_rack` | 检查Drum Rack打击垫结构（调试用） |
| `eval` | 在Live上下文中评估Python表达式 |
| `exec` | 在Live上下文中执行Python语句 |

### 事件推送（实时状态通知）

LiveAgent可以将状态变化**实时推送**给订阅者。节奏变化、播放/停止、混音操作、剪辑启动无需轮询即可通知外部脚本。

**原理：** LiveAgent每250ms对传输+混音+剪辑状态进行快照，与上次比较后将差异作为JSON事件推送给所有订阅者。使用专用端口（`8766`），不影响请求/响应通道（`8765`）。

> **注意：** 事件推送仅适用于 **Python/JS SDK客户端** 和原始TCP客户端。MCP客户端（Claude Desktop、Cursor）无法接收推送（MCP仅支持请求/响应）。

```python
from live_agent_client import LiveAgentSubscriber

sub = LiveAgentSubscriber()  # 连接到 127.0.0.1:8766
sub.on("transport_changed", lambda data: print("节奏:", data))
sub.on("mixer_changed", lambda data: print("混音:", data))
sub.listen()  # 后台线程；状态变化时触发回调
```

**事件类型：** `transport_changed`、`mixer_changed`、`clip_launched`、`clip_stopped`。可运行示例见 `examples/events_demo.py`。

### 音频分析

基于 [librosa](https://librosa.org/) 的内置音频分析：

- **BPM检测** — `librosa.beat.beat_track` 节拍提取
- **调性检测** — Krumhansl-Schmuckler算法，支持全部24个调
- **音高检测** — `pyin` 单音检测，适用于Kick/Snare等单次采样
- **采样分类** — 按时长自动分类: One-Shot（<2秒）、Short Loop（2-5秒）、Medium Loop（5-15秒）、Long Loop（>15秒）
- **Camelot Wheel** — DJ风格的调性兼容匹配
- **批量分析** — 分析整个文件夹，按音高排序，可按采样类型筛选
- **智能文件夹** — 自动生成兼容采样的符号链接，可在Ableton浏览器中直接查看
- **自动Warp** — 检测BPM/调性后自动应用Warp设置

**CLI使用：**
```bash
python audio_analyzer.py kick.wav                  # 分析单个文件
python audio_analyzer.py snare.wav --pitch-only    # 仅检测音高
python audio_analyzer.py ./Kicks/ --folder --mode pitch  # 批量分析（按音高排序）
python audio_analyzer.py ./Kicks/ --compatible Fm  # 搜索与Fm兼容的采样
```

### MCP服务器（Claude Desktop / Cursor等）

LiveAgent内置 **MCP服务器**，支持AI代理直接控制Ableton。

**安装：**

1. 安装依赖：
```bash
cd live-agent-remote
python3 -m venv .venv
.venv/bin/pip install "mcp[cli]" librosa
```

2. 添加到MCP客户端配置：

**Claude Desktop** (`~/Library/Application Support/Claude/claude_desktop_config.json`):
```json
{
  "mcpServers": {
    "ableton-live": {
      "command": "/path/to/live-agent-remote/.venv/bin/python3",
      "args": ["/path/to/live-agent-remote/mcp_server.py"]
    }
  }
}
```

3. 重启MCP客户端，全部51个命令即可作为工具使用！

---

## 한국어

### 이것은 무엇인가요?

LiveAgent는 Ableton Live **내부**에서 실행되는 MIDI Remote Script입니다. TCP 소켓(`127.0.0.1:8765`)을 열어 외부 프로그램에서 JSON 명령으로 Ableton을 제어할 수 있습니다.

### 설치 방법

1. `LiveAgent` 폴더를 MIDI Remote Scripts 디렉토리에 복사:

**macOS:**
```
/Applications/Ableton Live [버전]/Contents/App-Resources/MIDI Remote Scripts/
```

**Windows:**
```
C:\ProgramData\Ableton\Live [버전]\Resources\MIDI Remote Scripts\
```

2. Ableton Live 재시작
3. **Preferences → Link/Tempo/MIDI** 열기
4. **Control Surface** 드롭다운에서 **LiveAgent** 선택
5. 완료!

### 빠른 시작 (Python)

```python
from live_agent_client import LiveAgentClient

client = LiveAgentClient()
print(client.ping())                    # 연결 확인
tracks = client.list_tracks()           # 트랙 목록
client.load_device(track_index=1, device_name="Massive")  # 플러그인 로드
client.close()
```

### 명령 목록

| 명령 | 설명 |
|---|---|
| `ping` | 연결 확인 |
| `get_live_state` | 템포, 트랙, 씬, 재생 상태 가져오기 |
| `list_tracks` | 모든 트랙 나열 |
| `get_transport_state` | 트랜스포트 상태 가져오기 (템포, 박자, 메트로놈 등) |
| `start_playing` | 재생 시작 |
| `stop_playing` | 재생 중지 |
| `stop_all_clips` | 모든 클립 중지 |
| `set_tempo` | 템포(BPM) 설정 |
| `tap_tempo` | 탭 템포 |
| `set_time_signature` | 박자표 설정 |
| `set_metronome` | 메트로놈 켜기/끄기 |
| `set_overdub` | 오버더빙 켜기/끄기 |
| `launch_scene` | 씬 실행 (해당 행의 모든 클립 재생) |
| `launch_clip` | 클립 실행 |
| `set_track_volume` | 트랙 볼륨 설정 (0.0-1.0) |
| `set_track_pan` | 트랙 팬 설정 (-1.0 ~ 1.0) |
| `set_track_mute` | 트랙 음소거 켜기/끄기 |
| `set_track_solo` | 트랙 솔로 켜기/끄기 |
| `set_track_arm` | 트랙 녹음 대기(암) 켜기/끄기 |
| `set_track_send` | 트랙 센드 레벨 설정 |
| `set_track_monitoring` | 트랙 모니터링 상태 설정 (In/Auto/Off) |
| `set_crossfader` | 마스터 크로스페이더 위치 설정 |
| `create_midi_track` | MIDI 트랙 생성 |
| `create_session_clip` | 세션 클립 생성 |
| `write_midi_notes` | MIDI 노트 쓰기 |
| `read_clip_notes` | 노트 읽기 |
| `clear_clip_notes` | 노트 전체 삭제 |
| `list_devices` | 디바이스 나열 |
| `set_parameter_value` | 파라미터 값 설정 |
| `write_clip_automation` | 오토메이션 쓰기 |
| `load_device` | 플러그인 로드 |
| `list_browser_devices` | 사용 가능한 플러그인 검색 |
| `create_audio_track` | 오디오 트랙 생성 |
| `import_audio_clip` | 오디오 파일을 트랙에 임포트 |
| `get_clip_info` | 클립 상세 정보 (이름, 유형, 루프, 워프) |
| `set_clip_properties` | 클립 이름, 색상, 루프, 피치, 게인 설정 |
| `duplicate_clip` | 클립을 다른 슬롯에 복제 |
| `delete_clip` | 클립 삭제 |
| `set_clip_warp` | 워프 ON/OFF 및 모드 설정 |
| `analyze_and_warp` | BPM/키 분석 결과로 자동 워프 설정 |
| `analyze_audio_file` | 오디오 파일의 BPM, 키, 비트 분석 |
| `detect_pitch` | 원샷 샘플의 피치 감지 |
| `analyze_folder` | 폴더 일괄 분석 (피치순 정렬) |
| `find_compatible_samples` | Camelot Wheel로 키 호환 샘플 검색 |
| `create_smart_folder` | Ableton 브라우저에 호환 샘플 스마트 폴더 생성 |
| `create_drum_rack` | MIDI 트랙에 Drum Rack 생성 |
| `load_sample_to_pad` | Drum Rack 패드에 샘플 로드 |
| `inspect_drum_rack` | Drum Rack 패드 구조 검사 (디버그용) |
| `eval` | Live 컨텍스트에서 Python 표현식 평가 |
| `exec` | Live 컨텍스트에서 Python 문 실행 |

### 이벤트 Push (실시간 상태 알림)

LiveAgent는 상태 변화를 **실시간으로 push**할 수 있습니다. 템포 변경, 재생/정지, 믹서 조작, 클립 실행을 폴링 없이 외부 스크립트에 알립니다.

**원리:** LiveAgent가 250ms마다 트랜스포트+믹서+클립 상태를 스냅샷하여 이전과 비교한 차이를 JSON 이벤트로 모든 구독자에게 push합니다. 전용 포트(`8766`)를 사용하므로 요청/응답 채널(`8765`)에 영향을 주지 않습니다.

> **참고:** 이벤트 push는 **Python/JS SDK 클라이언트**와 raw TCP 클라이언트만 사용할 수 있습니다. MCP 클라이언트(Claude Desktop, Cursor)는 push를 받을 수 없습니다(MCP는 요청/응답 전용).

```python
from live_agent_client import LiveAgentSubscriber

sub = LiveAgentSubscriber()  # 127.0.0.1:8766 에 연결
sub.on("transport_changed", lambda data: print("템포:", data))
sub.on("mixer_changed", lambda data: print("믹서:", data))
sub.listen()  # 백그라운드 스레드; 상태 변화 시 콜백 발생
```

**이벤트 종류:** `transport_changed`, `mixer_changed`, `clip_launched`, `clip_stopped`. 실행 예제는 `examples/events_demo.py`를 참조.

### 오디오 분석

[librosa](https://librosa.org/) 기반 내장 오디오 분석:

- **BPM 감지** — `librosa.beat.beat_track` 템포 추출
- **키 감지** — Krumhansl-Schmuckler 알고리즘으로 24개 키 판정
- **피치 감지** — `pyin`으로 원샷 (킥, 스네어 등)의 기본 음높이 감지
- **샘플 분류** — 길이별 자동 분류: One-Shot (<2초), Short Loop (2-5초), Medium Loop (5-15초), Long Loop (>15초)
- **Camelot Wheel** — DJ 스타일 키 매칭
- **일괄 분석** — 폴더 전체 분석, 피치순 정렬, 샘플 타입 필터 가능
- **스마트 폴더** — 호환 샘플의 심볼릭 링크 자동 생성, Ableton 브라우저에서 직접 탐색 가능
- **자동 워프** — BPM/키 감지 후 Ableton에 워프 자동 적용

### MCP 서버 (Claude Desktop / Cursor 등)

LiveAgent에 **MCP 서버**가 내장되어 있어 AI 에이전트에서 Ableton을 직접 제어할 수 있습니다.

**설정:**

```bash
cd live-agent-remote
python3 -m venv .venv
.venv/bin/pip install "mcp[cli]" librosa
```

**Claude Desktop** 설정에 추가 후 재시작하면 51개 명령을 도구로 사용할 수 있습니다!

---

## Español

### ¿Qué es esto?

LiveAgent es un MIDI Remote Script que se ejecuta **dentro** de Ableton Live. Abre un socket TCP (`127.0.0.1:8765`) para recibir comandos JSON desde cualquier programa externo.

### Instalación

1. Copia la carpeta `LiveAgent` al directorio de MIDI Remote Scripts:

**macOS:** `/Applications/Ableton Live [versión]/Contents/App-Resources/MIDI Remote Scripts/`
**Windows:** `C:\ProgramData\Ableton\Live [versión]\Resources\MIDI Remote Scripts\`

2. Reinicia Ableton Live
3. **Preferences → Link/Tempo/MIDI**
4. Selecciona **LiveAgent** en **Control Surface**
5. ¡Listo!

### Inicio rápido (Python)

```python
from live_agent_client import LiveAgentClient

client = LiveAgentClient()
print(client.ping())
tracks = client.list_tracks()
client.load_device(track_index=1, device_name="Massive")
client.close()
```

### Comandos

| Comando | Descripción |
|---|---|
| `ping` | Verificar conexión |
| `get_live_state` | Obtener tempo, pistas, escenas, estado de reproducción |
| `list_tracks` | Listar todas las pistas |
| `get_transport_state` | Obtener estado del transporte (tempo, compás, metrónomo) |
| `start_playing` | Iniciar reproducción |
| `stop_playing` | Detener reproducción |
| `stop_all_clips` | Detener todos los clips |
| `set_tempo` | Establecer tempo (BPM) |
| `tap_tempo` | Tactear tempo |
| `set_time_signature` | Establecer compás |
| `set_metronome` | Activar/desactivar metrónomo |
| `set_overdub` | Activar/desactivar overdub |
| `launch_scene` | Lanzar escena (reproduce todos los clips de esa fila) |
| `launch_clip` | Lanzar clip |
| `set_track_volume` | Establecer volumen de pista (0.0-1.0) |
| `set_track_pan` | Establecer paneo de pista (-1.0 a 1.0) |
| `set_track_mute` | Silenciar/activar pista |
| `set_track_solo` | Solo/activar pista |
| `set_track_arm` | Armar/desarmar pista para grabación |
| `set_track_send` | Establecer nivel de envío de pista |
| `set_track_monitoring` | Establecer monitorización de pista (In/Auto/Off) |
| `set_crossfader` | Establecer posición del crossfader maestro |
| `create_midi_track` | Crear pista MIDI |
| `create_session_clip` | Crear clip en vista de sesión |
| `write_midi_notes` | Escribir notas MIDI |
| `read_clip_notes` | Leer notas del clip |
| `clear_clip_notes` | Eliminar todas las notas |
| `list_devices` | Listar dispositivos |
| `set_parameter_value` | Establecer valor de parámetro |
| `write_clip_automation` | Escribir automatización |
| `load_device` | Cargar plugin en pista |
| `list_browser_devices` | Buscar/listar plugins disponibles |
| `create_audio_track` | Crear pista de audio |
| `import_audio_clip` | Importar archivo de audio a pista |
| `get_clip_info` | Detalles del clip (nombre, tipo, loop, warp) |
| `set_clip_properties` | Nombre, color, loop, pitch, ganancia del clip |
| `duplicate_clip` | Duplicar clip en otro slot |
| `delete_clip` | Eliminar clip |
| `set_clip_warp` | Activar/desactivar Warp y modo |
| `analyze_and_warp` | Auto-warp con BPM/tonalidad detectados |
| `analyze_audio_file` | Analizar BPM, tonalidad, beats de archivo |
| `detect_pitch` | Detectar pitch de muestra one-shot |
| `analyze_folder` | Análisis por lotes, ordenar por pitch |
| `find_compatible_samples` | Buscar muestras compatibles (Camelot Wheel) |
| `create_smart_folder` | Carpeta inteligente de muestras compatibles en el navegador de Ableton |
| `create_drum_rack` | Crear Drum Rack en pista MIDI |
| `load_sample_to_pad` | Cargar sample en pad de Drum Rack |
| `inspect_drum_rack` | Inspeccionar estructura de pads del Drum Rack (depuración) |
| `eval` | Evaluar expresión Python en contexto de Live |
| `exec` | Ejecutar sentencia Python en contexto de Live |

### Push de Eventos (Notificaciones de Estado en Tiempo Real)

LiveAgent puede **enviar (push)** eventos de cambio de estado a suscriptores en tiempo real. Los cambios de tempo, play/stop, movimientos del mezclador y lanzamiento de clips se notifican sin necesidad de polling.

**Cómo funciona:** LiveAgent captura el estado de transporte + mezclador + clips cada 250ms, lo compara con la captura anterior y envía un evento JSON a cada suscriptor. Usa un puerto dedicado (`8766`) para no afectar el canal request/response (`8765`).

> **Nota:** El push de eventos está disponible solo para **clientes SDK Python/JS** y clientes TCP sin procesar. Los clientes MCP (Claude Desktop, Cursor) no pueden recibir push (MCP es solo request/response).

```python
from live_agent_client import LiveAgentSubscriber

sub = LiveAgentSubscriber()  # se conecta a 127.0.0.1:8766
sub.on("transport_changed", lambda data: print("tempo:", data))
sub.on("mixer_changed", lambda data: print("mixer:", data))
sub.listen()  # hilo en segundo plano; los callbacks se disparan al cambiar el estado
```

**Tipos de evento:** `transport_changed`, `mixer_changed`, `clip_launched`, `clip_stopped`. Ejemplo ejecutable en `examples/events_demo.py`.

### Analizador de Audio

Análisis de audio integrado con [librosa](https://librosa.org/):

- **Detección de BPM** — Extracción de tempo
- **Detección de tonalidad** — Algoritmo Krumhansl-Schmuckler, 24 tonalidades
- **Detección de pitch** — Para muestras one-shot (kicks, snares)
- **Clasificación de muestras** — Clasificación automática por duración: One-Shot (<2s), Short Loop (2-5s), Medium Loop (5-15s), Long Loop (>15s)
- **Camelot Wheel** — Coincidencia armónica estilo DJ
- **Análisis por lotes** — Analizar carpetas enteras, ordenar por pitch, filtrar por tipo de muestra
- **Carpetas inteligentes** — Generación automática de symlinks de muestras compatibles, visibles en el navegador de Ableton
- **Auto-Warp** — Detectar BPM/tonalidad y aplicar Warp automáticamente

### Servidor MCP (Claude Desktop / Cursor etc.)

LiveAgent incluye un **servidor MCP** que permite a agentes de IA controlar Ableton directamente.

**Configuración:**

```bash
cd live-agent-remote
python3 -m venv .venv
.venv/bin/pip install "mcp[cli]" librosa
```

¡Agrega a la configuración de tu cliente MCP y reinicia para usar los 51 comandos como herramientas!

---

## Français

### Qu'est-ce que c'est ?

LiveAgent est un MIDI Remote Script qui s'exécute **à l'intérieur** d'Ableton Live. Il ouvre un socket TCP (`127.0.0.1:8765`) pour recevoir des commandes JSON depuis n'importe quel programme externe.

### Installation

1. Copiez le dossier `LiveAgent` dans le répertoire MIDI Remote Scripts :

**macOS :** `/Applications/Ableton Live [version]/Contents/App-Resources/MIDI Remote Scripts/`
**Windows :** `C:\ProgramData\Ableton\Live [version]\Resources\MIDI Remote Scripts\`

2. Redémarrez Ableton Live
3. **Preferences → Link/Tempo/MIDI**
4. Sélectionnez **LiveAgent** dans **Control Surface**
5. C'est prêt !

### Démarrage rapide (Python)

```python
from live_agent_client import LiveAgentClient

client = LiveAgentClient()
print(client.ping())
tracks = client.list_tracks()
client.load_device(track_index=1, device_name="Massive")
client.close()
```

### Commandes

| Commande | Description |
|---|---|
| `ping` | Vérifier la connexion |
| `get_live_state` | Tempo, pistes, scènes, état de lecture |
| `list_tracks` | Lister toutes les pistes |
| `get_transport_state` | Obtenir l'état du transport (tempo, signature, métronome) |
| `start_playing` | Démarrer la lecture |
| `stop_playing` | Arrêter la lecture |
| `stop_all_clips` | Arrêter tous les clips |
| `set_tempo` | Définir le tempo (BPM) |
| `tap_tempo` | Taper le tempo |
| `set_time_signature` | Définir la signature rythmique |
| `set_metronome` | Activer/désactiver le métronome |
| `set_overdub` | Activer/désactiver l'overdub |
| `launch_scene` | Lancer une scène (lance tous les clips de la ligne) |
| `launch_clip` | Lancer un clip |
| `set_track_volume` | Définir le volume de piste (0.0-1.0) |
| `set_track_pan` | Définir le panoramique de piste (-1.0 à 1.0) |
| `set_track_mute` | Muter/activer la piste |
| `set_track_solo` | Activer/désactiver le solo de piste |
| `set_track_arm` | Armer/désarmer la piste pour l'enregistrement |
| `set_track_send` | Définir le niveau d'envoi de piste |
| `set_track_monitoring` | Définir le monitoring de piste (In/Auto/Off) |
| `set_crossfader` | Définir la position du crossfader master |
| `create_midi_track` | Créer une piste MIDI |
| `create_session_clip` | Créer un clip en vue session |
| `write_midi_notes` | Écrire des notes MIDI |
| `read_clip_notes` | Lire les notes du clip |
| `clear_clip_notes` | Supprimer toutes les notes |
| `list_devices` | Lister les appareils |
| `set_parameter_value` | Définir la valeur d'un paramètre |
| `write_clip_automation` | Écrire l'automation |
| `load_device` | Charger un plugin sur une piste |
| `list_browser_devices` | Rechercher/lister les plugins disponibles |
| `create_audio_track` | Créer une piste audio |
| `import_audio_clip` | Importer un fichier audio dans une piste |
| `get_clip_info` | Détails du clip (nom, type, boucle, warp) |
| `set_clip_properties` | Nom, couleur, boucle, pitch, gain du clip |
| `duplicate_clip` | Dupliquer le clip vers un autre emplacement |
| `delete_clip` | Supprimer le clip |
| `set_clip_warp` | Activer/désactiver le Warp et le mode |
| `analyze_and_warp` | Auto-warp avec BPM/tonalité détectés |
| `analyze_audio_file` | Analyser le BPM, la tonalité et les beats |
| `detect_pitch` | Détecter le pitch d'un sample one-shot |
| `analyze_folder` | Analyse par lot, trier par pitch |
| `find_compatible_samples` | Rechercher des samples compatibles (Camelot Wheel) |
| `create_smart_folder` | Dossier intelligent de samples compatibles dans le navigateur Ableton |
| `create_drum_rack` | Créer un Drum Rack sur une piste MIDI |
| `load_sample_to_pad` | Charger un sample sur un pad du Drum Rack |
| `inspect_drum_rack` | Inspecter la structure des pads du Drum Rack (débogage) |
| `eval` | Évaluer une expression Python dans le contexte Live |
| `exec` | Exécuter une instruction Python dans le contexte Live |

### Push d'Événements (Notifications d'État en Temps Réel)

LiveAgent peut **pusher** des événements de changement d'état aux abonnés en temps réel. Les changements de tempo, play/stop, mouvements du mixeur et lancement de clips sont notifiés sans polling.

**Comment ça marche :** LiveAgent capture l'état du transport + mixeur + clips toutes les 250ms, le compare à la capture précédente et pousse un événement JSON à chaque abonné. Utilise un port dédié (`8766`) pour ne pas affecter le canal request/response (`8765`).

> **Note :** Le push d'événements est disponible uniquement pour les **clients SDK Python/JS** et clients TCP bruts. Les clients MCP (Claude Desktop, Cursor) ne peuvent pas recevoir de push (MCP est uniquement request/response).

```python
from live_agent_client import LiveAgentSubscriber

sub = LiveAgentSubscriber()  # se connecte à 127.0.0.1:8766
sub.on("transport_changed", lambda data: print("tempo:", data))
sub.on("mixer_changed", lambda data: print("mixeur:", data))
sub.listen()  # thread d'arrière-plan ; les callbacks se déclenchent au changement d'état
```

**Types d'événement :** `transport_changed`, `mixer_changed`, `clip_launched`, `clip_stopped`. Exemple exécutable dans `examples/events_demo.py`.

### Analyseur Audio

Analyse audio intégrée avec [librosa](https://librosa.org/) :

- **Détection BPM** — Extraction du tempo
- **Détection de tonalité** — Algorithme Krumhansl-Schmuckler, 24 tonalités
- **Détection de pitch** — Pour les samples one-shot (kicks, snares)
- **Classification des samples** — Classification automatique par durée : One-Shot (<2s), Short Loop (2-5s), Medium Loop (5-15s), Long Loop (>15s)
- **Camelot Wheel** — Correspondance harmonique style DJ
- **Analyse par lot** — Analyser des dossiers entiers, trier par pitch, filtrer par type de sample
- **Dossiers intelligents** — Génération automatique de symlinks de samples compatibles, visibles dans le navigateur Ableton
- **Auto-Warp** — Détecter BPM/tonalité et appliquer le Warp automatiquement

### Serveur MCP (Claude Desktop / Cursor etc.)

LiveAgent inclut un **serveur MCP** permettant aux agents IA de contrôler Ableton directement.

**Configuration :**

```bash
cd live-agent-remote
python3 -m venv .venv
.venv/bin/pip install "mcp[cli]" librosa
```

Ajoutez à la configuration de votre client MCP et redémarrez pour utiliser les 51 commandes comme outils !

---

## License

<div align="center">

Made with 💙 by Yuuka & Shota

</div>
