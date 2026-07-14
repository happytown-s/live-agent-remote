"""
LiveAgent Remote Client — Python
=================================
Connects to LiveAgent running inside Ableton Live and sends JSON commands.

Usage:
    from live_agent_client import LiveAgentClient

    client = LiveAgentClient()
    state = client.ping()
    tracks = client.list_tracks()
    client.load_device(track_index=1, device_name="Massive")
    client.close()
"""

import json
import socket
import threading


class LiveAgentClient:
    """Thin wrapper around the LiveAgent socket protocol."""

    def __init__(self, host="127.0.0.1", port=8765, timeout=10):
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._sock.settimeout(timeout)
        self._sock.connect((host, port))

    # ── low-level ──────────────────────────────────────────────

    def _send(self, command, payload=None):
        request = {"command": command}
        if payload:
            request["payload"] = payload
        data = (json.dumps(request, separators=(",", ":")) + "\n").encode()
        self._sock.sendall(data)

        buf = b""
        while True:
            chunk = self._sock.recv(65536)
            if not chunk:
                break
            buf += chunk
            if b"\n" in buf:
                break

        resp = json.loads(buf.decode().strip())
        if not resp.get("ok"):
            raise Exception(resp.get("error", "Unknown error"))
        return resp.get("result")

    # ── commands ───────────────────────────────────────────────

    def ping(self):
        return self._send("ping")

    def get_live_state(self):
        return self._send("get_live_state")

    def list_tracks(self):
        return self._send("list_tracks")

    def select_track(self, track_index):
        return self._send("select_track", {"track_index": track_index})

    def select_scene(self, scene_index):
        return self._send("select_scene", {"scene_index": scene_index})

    def select_clip(self, track_index, slot_index):
        return self._send("select_clip", {
            "track_index": track_index,
            "slot_index": slot_index,
        })

    def select_device(self, track_index, device_index=None, device_name=None):
        payload = {"track_index": track_index}
        if device_index is not None:
            payload["device_index"] = device_index
        if device_name:
            payload["device_name"] = device_name
        return self._send("select_device", payload)

    # ── Transport & Playback ───────────────────────────────────

    def get_transport_state(self):
        return self._send("get_transport_state")

    def start_playing(self):
        return self._send("start_playing")

    def stop_playing(self):
        return self._send("stop_playing")

    def stop_all_clips(self):
        return self._send("stop_all_clips")

    def stop_clip(self, track_index, slot_index):
        return self._send("stop_clip", {
            "track_index": track_index,
            "slot_index": slot_index,
        })

    def stop_track_clips(self, track_index):
        return self._send("stop_track_clips", {"track_index": track_index})

    def set_tempo(self, tempo):
        return self._send("set_tempo", {"tempo": tempo})

    def tap_tempo(self):
        return self._send("tap_tempo")

    def set_time_signature(self, numerator=None, denominator=None):
        payload = {}
        if numerator is not None:
            payload["numerator"] = numerator
        if denominator is not None:
            payload["denominator"] = denominator
        return self._send("set_time_signature", payload)

    def set_metronome(self, enabled):
        return self._send("set_metronome", {"enabled": enabled})

    def set_overdub(self, enabled):
        return self._send("set_overdub", {"enabled": enabled})

    def launch_scene(self, scene_index):
        return self._send("launch_scene", {"scene_index": scene_index})

    def launch_clip(self, track_index, slot_index):
        return self._send("launch_clip", {"track_index": track_index, "slot_index": slot_index})

    # ── Mixer ──────────────────────────────────────────────────

    def set_track_volume(self, track_index, volume):
        return self._send("set_track_volume", {"track_index": track_index, "volume": volume})

    def set_track_pan(self, track_index, pan):
        return self._send("set_track_pan", {"track_index": track_index, "pan": pan})

    def set_track_mute(self, track_index, mute):
        return self._send("set_track_mute", {"track_index": track_index, "mute": mute})

    def set_track_solo(self, track_index, solo):
        return self._send("set_track_solo", {"track_index": track_index, "solo": solo})

    def set_track_arm(self, track_index, arm):
        return self._send("set_track_arm", {"track_index": track_index, "arm": arm})

    def set_track_send(self, track_index, send_index, value):
        return self._send("set_track_send", {
            "track_index": track_index, "send_index": send_index, "value": value,
        })

    def set_track_monitoring(self, track_index, monitoring):
        return self._send("set_track_monitoring", {"track_index": track_index, "monitoring": monitoring})

    def set_crossfader(self, position):
        return self._send("set_crossfader", {"position": position})

    def create_midi_track(self, index=-1):
        return self._send("create_midi_track", {"index": index})

    def set_track_name(self, track_index, name):
        return self._send("set_track_name", {"track_index": track_index, "name": name})

    def set_track_color(self, track_index, color):
        return self._send("set_track_color", {"track_index": track_index, "color": color})

    def duplicate_track(self, track_index):
        return self._send("duplicate_track", {"track_index": track_index})

    def delete_track(self, track_index):
        return self._send("delete_track", {"track_index": track_index})

    def create_scene(self, index=-1, name="", color=None):
        payload = {"index": index}
        if name:
            payload["name"] = name
        if color is not None:
            payload["color"] = color
        return self._send("create_scene", payload)

    def set_scene_name(self, scene_index, name):
        return self._send("set_scene_name", {"scene_index": scene_index, "name": name})

    def set_scene_color(self, scene_index, color):
        return self._send("set_scene_color", {"scene_index": scene_index, "color": color})

    def duplicate_scene(self, scene_index):
        return self._send("duplicate_scene", {"scene_index": scene_index})

    def delete_scene(self, scene_index):
        return self._send("delete_scene", {"scene_index": scene_index})

    def create_session_clip(self, track_index, slot_index, length_beats=16,
                            name="", color=None, replace=True):
        payload = {
            "track_index": track_index,
            "slot_index": slot_index,
            "length_beats": length_beats,
            "replace": replace,
        }
        if name:
            payload["name"] = name
        if color is not None:
            payload["color"] = color
        return self._send("create_session_clip", payload)

    def write_midi_notes(self, track_index, slot_index, notes):
        """
        notes: list of dicts with keys: pitch, start, duration, velocity (optional), muted (optional)
        """
        return self._send("write_midi_notes", {
            "track_index": track_index,
            "slot_index": slot_index,
            "notes": notes,
        })

    def read_clip_notes(self, track_index, slot_index, length_beats=16):
        return self._send("read_clip_notes", {
            "track_index": track_index,
            "slot_index": slot_index,
            "length_beats": length_beats,
        })

    def clear_clip_notes(self, track_index, slot_index):
        return self._send("clear_clip_notes", {
            "track_index": track_index,
            "slot_index": slot_index,
        })

    def list_devices(self, track_index):
        return self._send("list_devices", {"track_index": track_index})

    def set_parameter_value(self, track_index, device_index=None, device_name=None,
                            parameter_index=None, parameter_name=None, value=0.0):
        payload = {"track_index": track_index, "value": value}
        if device_index is not None:
            payload["device_index"] = device_index
        if device_name:
            payload["device_name"] = device_name
        if parameter_index is not None:
            payload["parameter_index"] = parameter_index
        if parameter_name:
            payload["parameter_name"] = parameter_name
        return self._send("set_parameter_value", payload)

    def write_clip_automation(self, track_index, slot_index, points,
                              device_index=None, device_name=None,
                              parameter_index=None, parameter_name=None,
                              step_duration=0.25):
        payload = {
            "track_index": track_index,
            "slot_index": slot_index,
            "points": points,
            "step_duration": step_duration,
        }
        if device_index is not None:
            payload["device_index"] = device_index
        if device_name:
            payload["device_name"] = device_name
        if parameter_index is not None:
            payload["parameter_index"] = parameter_index
        if parameter_name:
            payload["parameter_name"] = parameter_name
        return self._send("write_clip_automation", payload)

    def load_device(self, track_index, device_name, browser_type="plug-in"):
        return self._send("load_device", {
            "track_index": track_index,
            "device_name": device_name,
            "browser_type": browser_type,
        })

    def list_browser_devices(self, browser_type="plug-in", query="", max_results=100):
        return self._send("list_browser_devices", {
            "browser_type": browser_type,
            "query": query,
            "max_results": max_results,
        })

    # ── lifecycle ──────────────────────────────────────────────

    # ── Audio Clip Commands ──────────────────────────────────

    def create_audio_track(self, index=-1):
        return self._send("create_audio_track", {"index": index})

    def import_audio_clip(self, track_index, slot_index, file_path):
        return self._send("import_audio_clip", {
            "track_index": track_index,
            "slot_index": slot_index,
            "file_path": file_path,
        })

    def get_clip_info(self, track_index, slot_index):
        return self._send("get_clip_info", {
            "track_index": track_index,
            "slot_index": slot_index,
        })

    def set_clip_properties(self, track_index, slot_index, **kwargs):
        payload = {"track_index": track_index, "slot_index": slot_index}
        payload.update(kwargs)
        return self._send("set_clip_properties", payload)

    def duplicate_clip(self, track_index, slot_index, dest_track_index=None, dest_slot_index=None):
        payload = {"track_index": track_index, "slot_index": slot_index}
        if dest_track_index is not None:
            payload["dest_track_index"] = dest_track_index
        if dest_slot_index is not None:
            payload["dest_slot_index"] = dest_slot_index
        return self._send("duplicate_clip", payload)

    def delete_clip(self, track_index, slot_index):
        return self._send("delete_clip", {
            "track_index": track_index,
            "slot_index": slot_index,
        })

    def set_clip_warp(self, track_index, slot_index, warping=None, warp_mode=None):
        payload = {"track_index": track_index, "slot_index": slot_index}
        if warping is not None:
            payload["warping"] = warping
        if warp_mode is not None:
            payload["warp_mode"] = warp_mode
        return self._send("set_clip_warp", payload)

    # ── Drum Rack Commands ──────────────────────────────────

    def create_drum_rack(self, track_index=-1, name="Drum Rack",
                         kit_name="808 Core Kit.adg", empty=False):
        return self._send("create_drum_rack", {
            "track_index": track_index,
            "name": name,
            "kit_name": kit_name,
            "empty": empty,
        })

    def load_sample_to_pad(self, track_index, pad_index, file_path,
                           pad_name=None,
                           drum_rack_index=0, reset_effects=False):
        payload = {
            "track_index": track_index,
            "pad_index": pad_index,
            "file_path": file_path,
            "drum_rack_index": drum_rack_index,
            "reset_effects": reset_effects,
        }
        if pad_name is not None:
            payload["pad_name"] = pad_name
        return self._send("load_sample_to_pad", payload)

    def set_drum_pad_name(self, track_index, pad_index, pad_name, drum_rack_index=0):
        return self._send("set_drum_pad_name", {
            "track_index": track_index,
            "pad_index": pad_index,
            "pad_name": pad_name,
            "drum_rack_index": drum_rack_index,
        })

    def inspect_drum_rack(self, track_index, drum_rack_index=0, pad_range=None):
        payload = {
            "track_index": track_index,
            "drum_rack_index": drum_rack_index,
        }
        if pad_range is not None:
            payload["pad_range"] = pad_range
        return self._send("inspect_drum_rack", payload)

    def analyze_and_warp(self, track_index, slot_index, bpm=None, key=None, warp_mode=4):
        payload = {
            "track_index": track_index,
            "slot_index": slot_index,
            "warp_mode": warp_mode,
        }
        if bpm is not None:
            payload["bpm"] = bpm
        if key is not None:
            payload["key"] = key
        return self._send("analyze_and_warp", payload)

    # ── lifecycle ──────────────────────────────────────────────

    def close(self):
        try:
            self._sock.close()
        except Exception:
            pass


class LiveAgentSubscriber:
    """Receive pushed events from LiveAgent over a dedicated subscribe port.

    LiveAgent snapshots transport/mixer/clip state and pushes change events
    to subscribers. This class opens a persistent connection, registers for
    the requested event categories, and dispatches incoming events to
    callbacks registered via :meth:`on`.

    Event categories (pass any subset to ``events``):
        - ``transport``  → ``transport_changed``
        - ``mixer``      → ``mixer_changed``
        - ``scenes``     → ``clip_launched``, ``clip_stopped``

    Usage::

        sub = LiveAgentSubscriber()
        sub.on("transport_changed", lambda data: print("tempo:", data))
        sub.listen()  # starts a background thread; returns immediately
        # ... events fire callbacks ...
        sub.close()

    You can also register a catch-all handler with ``on("*", cb)`` which
    receives ``(event_name, data)`` for every event.
    """

    DEFAULT_PORT = 8766

    def __init__(self, host="127.0.0.1", port=DEFAULT_PORT, events=None, timeout=10):
        if events is None:
            events = ["transport", "mixer", "scenes"]
        self._host = host
        self._port = port
        self._events = events
        self._handlers = {}  # event_name -> list of callbacks
        self._wildcard_handlers = []
        self._sock = None
        self._thread = None
        self._running = False
        # Connect and send the subscribe handshake.
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._sock.settimeout(timeout)
        self._sock.connect((host, port))
        request = json.dumps(
            {"command": "subscribe", "payload": {"events": events}},
            separators=(",", ":"),
        ) + "\n"
        self._sock.sendall(request.encode("utf-8"))
        # Read the ack (one line).
        buf = b""
        while b"\n" not in buf:
            chunk = self._sock.recv(65536)
            if not chunk:
                raise ConnectionError("subscribe handshake failed: connection closed")
            buf += chunk
        ack = json.loads(buf.split(b"\n", 1)[0].decode("utf-8").strip())
        if not ack.get("ok"):
            raise ConnectionError(f"subscribe rejected: {ack.get('error', 'unknown')}")
        # Reuse the leftover buffer (after the ack line) for the listener.
        self._leftover = buf.split(b"\n", 1)[1] if b"\n" in buf else b""

    def on(self, event_name, callback):
        """Register a callback for an event name (or ``"*"`` for all)."""
        if event_name == "*":
            self._wildcard_handlers.append(callback)
        else:
            self._handlers.setdefault(event_name, []).append(callback)

    def listen(self):
        """Start a background thread that reads and dispatches events."""
        if self._thread is not None:
            return
        self._running = True
        self._sock.settimeout(None)  # blocking read
        self._thread = threading.Thread(target=self._read_loop, daemon=True)
        self._thread.start()

    def _read_loop(self):
        buf = self._leftover
        self._leftover = b""
        try:
            while self._running:
                chunk = self._sock.recv(65536)
                if not chunk:
                    break
                buf += chunk
                # Dispatch each complete line as an event message.
                while b"\n" in buf:
                    line, buf = buf.split(b"\n", 1)
                    line = line.strip()
                    if not line:
                        continue
                    self._dispatch(line.decode("utf-8"))
        except Exception:
            pass

    def _dispatch(self, raw):
        try:
            msg = json.loads(raw)
        except Exception:
            return
        # Messages from the server are {"events": [ {...}, ... ]}.
        events = msg.get("events") if isinstance(msg, dict) else None
        if not events:
            return
        for evt in events:
            name = evt.get("event")
            data = evt.get("data", {})
            for cb in self._handlers.get(name, []):
                try:
                    cb(data)
                except Exception:
                    pass
            for cb in self._wildcard_handlers:
                try:
                    cb(name, data)
                except Exception:
                    pass

    def close(self):
        """Stop the listener and close the connection."""
        self._running = False
        try:
            if self._sock:
                self._sock.close()
        except Exception:
            pass
        if self._thread is not None:
            self._thread.join(timeout=1.0)
            self._thread = None
