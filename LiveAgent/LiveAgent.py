from __future__ import absolute_import, print_function

import json
import os
import socket
import threading
import time
import traceback

try:
    import queue
except ImportError:
    import Queue as queue

from _Framework.ControlSurface import ControlSurface


HOST = "127.0.0.1"
PORT = 8765
SUBSCRIBE_PORT = 8766

# How often (seconds) the event-pusher snapshots Live state and diffs it.
PUSH_INTERVAL = 0.25


def _event_in_category(event_name, categories):
    """Map an event name to its subscription category.

    Pure function (module-level for testability). Categories are the strings
    a subscriber passes in ``events``: ``transport``, ``mixer``, ``scenes``.
    """
    if "transport" in categories and event_name == "transport_changed":
        return True
    if "mixer" in categories and event_name == "mixer_changed":
        return True
    if "scenes" in categories and event_name in ("clip_launched", "clip_stopped"):
        return True
    return False


class LiveAgent(ControlSurface):
    """Small JSON socket bridge for chat-driven Ableton commands.

    Socket threads never touch Live's object model. They enqueue requests, then
    the ControlSurface drains them on Live's main thread with schedule_message.
    """

    def __init__(self, c_instance):
        ControlSurface.__init__(self, c_instance)
        self._running = True
        self._server_socket = None
        self._subscribe_socket = None
        self._command_queue = queue.Queue()
        # SECURITY: eval/exec disabled by default. Enable with LIVEAGENT_ENABLE_UNSAFE=1
        self._unsafe_enabled = os.environ.get("LIVEAGENT_ENABLE_UNSAFE", "0") == "1"
        self._server_thread = threading.Thread(target=self._run_server)
        self._server_thread.daemon = True
        self._server_thread.start()
        # Event push: subscriber registry and state diffing (main-thread only).
        self._subscribers = []
        self._last_snapshot = {}
        self._last_push_time = 0.0
        self._baseline_set = False
        self._subscribe_thread = threading.Thread(target=self._run_subscribe_server)
        self._subscribe_thread.daemon = True
        self._subscribe_thread.start()
        self.log_message("[LiveAgent] listening on %s:%s (unsafe=%s)" % (HOST, PORT, self._unsafe_enabled))
        self.log_message("[LiveAgent] event push on %s:%s" % (HOST, SUBSCRIBE_PORT))
        self.schedule_message(1, self._drain_commands)

    def disconnect(self):
        self._running = False
        try:
            if self._server_socket:
                self._server_socket.close()
        except Exception:
            pass
        try:
            if self._subscribe_socket:
                self._subscribe_socket.close()
        except Exception:
            pass
        self.log_message("[LiveAgent] disconnected")
        ControlSurface.disconnect(self)

    def _run_server(self):
        try:
            server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            server.bind((HOST, PORT))
            server.listen(8)
            server.settimeout(0.5)
            self._server_socket = server
        except Exception:
            self._log_exception("server startup failed")
            return

        while self._running:
            try:
                conn, _addr = self._server_socket.accept()
                thread = threading.Thread(target=self._handle_client, args=(conn,))
                thread.daemon = True
                thread.start()
            except socket.timeout:
                continue
            except Exception:
                if self._running:
                    self._log_exception("accept failed")
                break

    def _run_subscribe_server(self):
        """Listen on SUBSCRIBE_PORT for event-push subscribers.

        A subscriber sends one line (the ``subscribe`` command); the connection
        is then flipped into push-only mode by the main thread. The socket
        thread keeps the connection alive and reads (discarding) any further
        client bytes so disconnects are detected promptly.
        """
        try:
            server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            server.bind((HOST, SUBSCRIBE_PORT))
            server.listen(8)
            server.settimeout(0.5)
            self._subscribe_socket = server
        except Exception:
            self._log_exception("subscribe server startup failed")
            return

        while self._running:
            try:
                conn, _addr = self._subscribe_socket.accept()
                thread = threading.Thread(target=self._handle_subscriber, args=(conn,))
                thread.daemon = True
                thread.start()
            except socket.timeout:
                continue
            except Exception:
                if self._running:
                    self._log_exception("subscribe accept failed")
                break

    def _handle_client(self, conn):
        """Read newline-delimited request/response commands from one client."""
        conn.settimeout(10)
        buffer = b""
        try:
            while self._running:
                chunk = conn.recv(65536)
                if not chunk:
                    break
                buffer += chunk
                while b"\n" in buffer:
                    line, buffer = buffer.split(b"\n", 1)
                    if not line.strip():
                        continue
                    try:
                        request = json.loads(line.decode("utf-8"))
                    except Exception as err:
                        self._send_response(conn, {"ok": False, "error": "Invalid JSON: %s" % err})
                        continue
                    self._command_queue.put((request, conn))
        except Exception:
            pass
        finally:
            try:
                conn.close()
            except Exception:
                pass

    def _handle_subscriber(self, conn):
        """Read the subscribe handshake, register the connection, then keep it
        alive until the client disconnects or Live shuts down."""
        conn.settimeout(10)
        buffer = b""
        try:
            # Read at least one line: the subscribe command.
            while self._running and b"\n" not in buffer:
                chunk = conn.recv(65536)
                if not chunk:
                    return
                buffer += chunk
            line, buffer = buffer.split(b"\n", 1)
            if not line.strip():
                return
            try:
                request = json.loads(line.decode("utf-8"))
            except Exception as err:
                self._send_response(conn, {"ok": False, "error": "Invalid JSON: %s" % err})
                return
            # Enqueue for the main thread to register the subscriber.
            self._command_queue.put((request, conn))

            # Keep the connection open: detect disconnect via recv returning b"".
            # We discard any further client bytes (subscribers are push-only).
            conn.settimeout(2.0)
            while self._running:
                try:
                    chunk = conn.recv(65536)
                    if not chunk:
                        break
                except socket.timeout:
                    continue
                except Exception:
                    break
        except Exception:
            pass
        finally:
            try:
                conn.close()
            except Exception:
                pass

    def _drain_commands(self):
        handled = 0
        while self._running and handled < 50:
            try:
                request, conn = self._command_queue.get(False)
            except queue.Empty:
                break

            response = self._safe_execute(request, conn)
            self._send_response(conn, response)
            handled += 1

        # Event push: snapshot + diff + notify subscribers on a throttle.
        if self._running and self._subscribers:
            self._maybe_push_events()

        if self._running:
            self.schedule_message(1, self._drain_commands)

    def _safe_execute(self, request, conn=None):
        request_id = request.get("id")
        try:
            result = self._execute(request, conn)
            return {"id": request_id, "ok": True, "result": result}
        except Exception as err:
            self._log_exception("command failed")
            return {
                "id": request_id,
                "ok": False,
                "error": str(err),
                "traceback": traceback.format_exc(),
            }

    def _send_response(self, conn, response):
        try:
            payload = (json.dumps(response, separators=(",", ":")) + "\n").encode("utf-8")
            conn.sendall(payload)
        except Exception:
            pass

    def _execute(self, request, conn=None):
        command = request.get("command")
        payload = request.get("payload") or {}

        # Event subscription: register/unregister the calling connection.
        # Handled here (main thread) so the subscriber list is single-threaded.
        if command == "subscribe":
            return self._subscribe(payload, conn)
        if command == "unsubscribe":
            return self._unsubscribe(payload, conn)

        if command == "ping":
            return {"pong": True, "time": time.time()}
        if command == "get_live_state":
            return self._live_state()
        if command == "get_transport_state":
            return self._transport_state()
        if command == "list_tracks":
            return {"tracks": self._track_summaries()}
        if command == "select_track":
            return self._select_track(payload)
        if command == "select_scene":
            return self._select_scene(payload)
        if command == "select_clip":
            return self._select_clip(payload)
        if command == "select_device":
            return self._select_device(payload)
        if command == "create_midi_track":
            return self._create_midi_track(payload)
        if command == "set_track_name":
            return self._set_track_name(payload)
        if command == "set_track_color":
            return self._set_track_color(payload)
        if command == "duplicate_track":
            return self._duplicate_track(payload)
        if command == "delete_track":
            return self._delete_track(payload)
        if command == "create_scene":
            return self._create_scene(payload)
        if command == "set_scene_name":
            return self._set_scene_name(payload)
        if command == "set_scene_color":
            return self._set_scene_color(payload)
        if command == "duplicate_scene":
            return self._duplicate_scene(payload)
        if command == "delete_scene":
            return self._delete_scene(payload)
        if command == "create_session_clip":
            return self._create_session_clip(payload)
        if command == "write_midi_notes":
            return self._write_midi_notes(payload)
        if command == "read_clip_notes":
            return self._read_clip_notes(payload)
        if command == "clear_clip_notes":
            return self._clear_clip_notes(payload)
        if command == "list_devices":
            return self._list_devices(payload)
        if command == "set_parameter_value":
            return self._set_parameter_value(payload)
        if command == "write_clip_automation":
            return self._write_clip_automation(payload)
        if command == "load_device":
            return self._load_device(payload)
        if command == "list_browser_devices":
            return self._list_browser_devices(payload)
        if command == "import_audio_clip":
            return self._import_audio_clip(payload)
        if command == "get_clip_info":
            return self._get_clip_info(payload)
        if command == "set_clip_properties":
            return self._set_clip_properties(payload)
        if command == "duplicate_clip":
            return self._duplicate_clip(payload)
        if command == "delete_clip":
            return self._delete_clip(payload)
        if command == "create_audio_track":
            return self._create_audio_track(payload)
        if command == "set_clip_warp":
            return self._set_clip_warp(payload)
        if command == "analyze_and_warp":
            return self._analyze_and_warp(payload)
        if command == "create_drum_rack":
            return self._create_drum_rack(payload)
        if command == "load_sample_to_pad":
            return self._load_sample_to_pad(payload)
        if command == "set_drum_pad_name":
            return self._set_drum_pad_name(payload)

        if command == "inspect_drum_rack":
            return self._inspect_drum_rack(payload)

        if command == "start_playing":
            return self._start_playing(payload)
        if command == "stop_playing":
            return self._stop_playing(payload)
        if command == "stop_all_clips":
            return self._stop_all_clips(payload)
        if command == "stop_clip":
            return self._stop_clip(payload)
        if command == "stop_track_clips":
            return self._stop_track_clips(payload)
        if command == "set_tempo":
            return self._set_tempo(payload)
        if command == "tap_tempo":
            return self._tap_tempo(payload)
        if command == "set_time_signature":
            return self._set_time_signature(payload)
        if command == "set_metronome":
            return self._set_metronome(payload)
        if command == "set_overdub":
            return self._set_overdub(payload)
        if command == "launch_scene":
            return self._launch_scene(payload)
        if command == "launch_clip":
            return self._launch_clip(payload)

        if command == "set_track_volume":
            return self._set_track_volume(payload)
        if command == "set_track_pan":
            return self._set_track_pan(payload)
        if command == "set_track_mute":
            return self._set_track_mute(payload)
        if command == "set_track_solo":
            return self._set_track_solo(payload)
        if command == "set_track_arm":
            return self._set_track_arm(payload)
        if command == "set_track_send":
            return self._set_track_send(payload)
        if command == "set_track_monitoring":
            return self._set_track_monitoring(payload)
        if command == "set_crossfader":
            return self._set_crossfader(payload)

        if command == "begin_undo_step":
            return self._begin_undo_step()
        if command == "end_undo_step":
            return self._end_undo_step()
        if command == "batch":
            return self._batch(payload)

        if command == "eval":
            return self._eval(payload)
        if command == "exec":
            return self._exec(payload)

        raise Exception("Unknown command: %s" % command)

    # ── Undo Group Support ──────────────────────────────────────────

    def _begin_undo_step(self):
        """Begin an undo group. All subsequent operations will be grouped
        into a single undoable step once end_undo_step is called."""
        self.song().begin_undo_step()
        return {"undo_step_started": True}

    def _end_undo_step(self):
        """End the current undo group. All operations since begin_undo_step
        can now be undone with a single Ctrl+Z."""
        self.song().end_undo_step()
        return {"undo_step_ended": True}

    def _batch(self, payload):
        """Execute multiple commands as a single undo step.

        payload.commands: list of {command: str, payload: dict}
        All commands execute within begin_undo_step/end_undo_step.
        If a command fails, execution stops and the partial results are returned,
        but the undo step is still ended (user can Ctrl+Z to undo everything done).
        """
        commands = payload.get("commands", [])
        if not commands:
            return {"results": [], "count": 0}

        results = []
        self.song().begin_undo_step()
        try:
            for i, cmd_spec in enumerate(commands):
                cmd = cmd_spec.get("command")
                cmd_payload = cmd_spec.get("payload") or {}
                try:
                    result = self._execute({"command": cmd, "payload": cmd_payload})
                    results.append({"index": i, "command": cmd, "ok": True, "result": result})
                except Exception as err:
                    results.append({"index": i, "command": cmd, "ok": False, "error": str(err)})
                    # Stop on first error — user can undo everything done so far
                    break
        finally:
            self.song().end_undo_step()

        return {"results": results, "count": len(results)}

    def _exec(self, payload):
        """Execute Python statement in LiveAgent context.

        SECURITY: Disabled by default. Enable with LIVEAGENT_ENABLE_UNSAFE=1
        environment variable before launching Ableton.
        """
        if not self._unsafe_enabled:
            return {
                "error": "exec is disabled. Set LIVEAGENT_ENABLE_UNSAFE=1 environment variable to enable.",
                "security": "This command allows arbitrary code execution and is disabled by default."
            }
        stmt = payload.get("stmt", "")
        try:
            import Live
            ns = {
                "Live": Live,
                "song": self.song(),
                "app": Live.Application.get_application(),
                "os": __import__("os"),
                "json": __import__("json"),
            }
            exec(stmt, ns)
            return {"result": "ok"}
        except Exception as e:
            return {"error": str(e), "type": type(e).__name__}

    def _eval(self, payload):
        """Evaluate Python expression in LiveAgent context.

        SECURITY: Disabled by default. Enable with LIVEAGENT_ENABLE_UNSAFE=1
        environment variable before launching Ableton.
        """
        if not self._unsafe_enabled:
            return {
                "error": "eval is disabled. Set LIVEAGENT_ENABLE_UNSAFE=1 environment variable to enable.",
                "security": "This command allows arbitrary code execution and is disabled by default."
            }
        expr = payload.get("expr", "")
        try:
            import Live
            result = eval(expr, {"__builtins__": {}}, {
                "Live": Live,
                "song": self.song(),
                "app": Live.Application.get_application(),
                "os": __import__("os"),
                "json": __import__("json"),
                "len": len,
                "str": str,
                "int": int,
                "float": float,
                "list": list,
                "dict": dict,
                "range": range,
                "enumerate": enumerate,
                "type": type,
                "dir": dir,
                "getattr": getattr,
                "hasattr": hasattr,
                "repr": repr,
                "isinstance": isinstance,
                "True": True,
                "False": False,
                "None": None,
            })
            # Try to serialize
            if isinstance(result, (str, int, float, bool, type(None))):
                return {"result": result}
            elif isinstance(result, (list, dict, tuple)):
                return {"result": result}
            else:
                return {"result": repr(result)}
        except Exception as e:
            return {"error": str(e), "type": type(e).__name__}

    # ── Selection Control ───────────────────────────────────────

    def _select_track(self, payload):
        track = self._track_by_index(payload.get("track_index", 0))
        self.song().view.selected_track = track
        return {"selected_track_index": self._track_index(track), "name": track.name}

    def _select_scene(self, payload):
        scene = self._scene_by_index(payload.get("scene_index", 0))
        self.song().view.selected_scene = scene
        return {"selected_scene_index": self._scene_index(scene), "name": scene.name}

    def _select_clip(self, payload):
        track, slot = self._existing_track_and_slot(payload)
        if not slot.has_clip:
            raise Exception(
                "No clip at track %s slot %s"
                % (payload.get("track_index"), payload.get("slot_index"))
            )
        song = self.song()
        song.view.selected_track = track
        song.view.selected_scene = self._scene_by_index(payload.get("slot_index", 0))
        try:
            song.view.detail_clip = slot.clip
        except Exception:
            pass
        return {
            "selected_track_index": self._track_index(track),
            "selected_scene_index": int(payload.get("slot_index", 0)),
            "clip": self._clip_summary(slot.clip),
        }

    def _select_device(self, payload):
        track = self._track_by_index(payload.get("track_index", 0))
        device = self._find_by_index_or_name(
            track.devices,
            payload.get("device_index"),
            payload.get("device_name"),
            "device",
        )
        song = self.song()
        song.view.selected_track = track
        selected = False
        try:
            song.view.select_device(device)
            selected = True
        except Exception:
            pass
        return {
            "selected_track_index": self._track_index(track),
            "device": device.name,
            "device_index": self._device_index(track, device),
            "selected_device": selected,
        }

    def _live_state(self):
        song = self.song()
        return {
            "application": "Ableton Live",
            "tempo": song.tempo,
            "is_playing": song.is_playing,
            "tracks": self._track_summaries(),
            "scenes": [self._scene_summary(i, scene) for i, scene in enumerate(song.scenes)],
            "selected_track_index": self._track_index(song.view.selected_track),
            "selected_scene_index": self._scene_index(self._safe_attr(song.view, "selected_scene", None)),
        }

    # ── Transport & Playback Control ──────────────────────────────

    def _transport_state(self):
        """Return transport-related state. Uses _safe_attr so that attributes
        absent on some Live versions are reported as None rather than raising."""
        song = self.song()
        return {
            "tempo": self._safe_attr(song, "tempo", None),
            "is_playing": self._safe_attr(song, "is_playing", None),
            "signature_numerator": self._safe_attr(song, "signature_numerator", None),
            "signature_denominator": self._safe_attr(song, "signature_denominator", None),
            "metronome": self._safe_attr(song, "metronome", None),
            "overdub": self._safe_attr(song, "overdub", None),
            "song_time": self._safe_attr(song, "current_song_time", None),
        }

    def _start_playing(self, payload):
        song = self.song()
        song.start_playing()
        return {"is_playing": True}

    def _stop_playing(self, payload):
        song = self.song()
        song.stop_playing()
        return {"is_playing": False}

    def _stop_all_clips(self, payload):
        song = self.song()
        song.stop_all_clips()
        return {"stopped_all_clips": True}

    def _stop_clip(self, payload):
        _track, slot = self._existing_track_and_slot(payload)
        if not slot.has_clip:
            return {
                "stopped_clip": False,
                "track_index": payload.get("track_index", 0),
                "slot_index": int(payload.get("slot_index", 0)),
                "reason": "empty_slot",
            }
        slot.stop()
        return {
            "stopped_clip": True,
            "track_index": payload.get("track_index", 0),
            "slot_index": int(payload.get("slot_index", 0)),
        }

    def _stop_track_clips(self, payload):
        track = self._track_by_index(payload.get("track_index", 0))
        stopped = False
        if hasattr(track, "stop_all_clips"):
            track.stop_all_clips()
            stopped = True
        else:
            for slot in getattr(track, "clip_slots", []):
                if self._safe_attr(slot, "has_clip", False):
                    try:
                        slot.stop()
                        stopped = True
                    except Exception:
                        pass
        return {
            "stopped_track_clips": stopped,
            "track_index": self._track_index(track),
            "track_name": track.name,
        }

    def _set_tempo(self, payload):
        if "tempo" not in payload:
            raise Exception("set_tempo requires a 'tempo' parameter (BPM, 20-999)")
        tempo = float(payload.get("tempo"))
        if tempo < 20.0 or tempo > 999.0:
            raise Exception("tempo must be between 20 and 999 BPM, got %s" % tempo)
        song = self.song()
        song.tempo = tempo
        return {"tempo": song.tempo}

    def _tap_tempo(self, payload):
        song = self.song()
        song.tap_tempo()
        return {"tapped": True, "tempo": self._safe_attr(song, "tempo", None)}

    def _set_time_signature(self, payload):
        song = self.song()
        updated = {}
        if "numerator" in payload:
            numerator = int(payload.get("numerator"))
            if numerator < 1 or numerator > 16:
                raise Exception("numerator must be 1-16, got %s" % numerator)
            song.signature_numerator = numerator
            updated["signature_numerator"] = song.signature_numerator
        if "denominator" in payload:
            denominator = int(payload.get("denominator"))
            if denominator not in (1, 2, 4, 8, 16):
                raise Exception("denominator must be 1, 2, 4, 8, or 16, got %s" % denominator)
            song.signature_denominator = denominator
            updated["signature_denominator"] = song.signature_denominator
        if not updated:
            raise Exception(
                "set_time_signature requires 'numerator' and/or 'denominator' parameters"
            )
        return updated

    def _set_metronome(self, payload):
        if "enabled" not in payload:
            raise Exception("set_metronome requires an 'enabled' parameter (bool)")
        song = self.song()
        song.metronome = bool(payload.get("enabled"))
        return {"metronome": self._safe_attr(song, "metronome", None)}

    def _set_overdub(self, payload):
        if "enabled" not in payload:
            raise Exception("set_overdub requires an 'enabled' parameter (bool)")
        song = self.song()
        song.overdub = bool(payload.get("enabled"))
        return {"overdub": self._safe_attr(song, "overdub", None)}

    def _launch_scene(self, payload):
        if "scene_index" not in payload:
            raise Exception("launch_scene requires a 'scene_index' parameter")
        song = self.song()
        scene_index = int(payload.get("scene_index"))
        scenes = list(song.scenes)
        if scene_index < 0 or scene_index >= len(scenes):
            raise Exception(
                "Scene index out of range: %s (have %s scenes)" % (scene_index, len(scenes))
            )
        scene = scenes[scene_index]
        scene.fire()
        return {"launched_scene": scene_index, "name": scene.name}

    def _launch_clip(self, payload):
        track = self._track_by_index(payload.get("track_index", 0))
        slot_index = int(payload.get("slot_index", 0))
        clip_slots = list(getattr(track, "clip_slots", []))
        if slot_index < 0 or slot_index >= len(clip_slots):
            raise Exception(
                "Slot index out of range: %s (track has %s slots)" % (slot_index, len(clip_slots))
            )
        slot = clip_slots[slot_index]
        slot.fire()
        return {"launched_clip": True, "track_index": payload.get("track_index", 0), "slot_index": slot_index}

    # ── Mixer Control ─────────────────────────────────────────────
    # Volume/Pan/Send use mixer_device.<param>.value (a normalized float).
    # Mute/Solo/Arm are direct track booleans. Monitoring is an int enum.

    def _set_track_volume(self, payload):
        if "volume" not in payload:
            raise Exception("set_track_volume requires a 'volume' parameter (0.0-1.0)")
        volume = float(payload.get("volume"))
        if volume < 0.0 or volume > 1.0:
            raise Exception("volume must be between 0.0 and 1.0, got %s" % volume)
        track = self._track_by_index(payload.get("track_index", 0))
        track.mixer_device.volume.value = volume
        return {"track_index": payload.get("track_index", 0), "volume": track.mixer_device.volume.value}

    def _set_track_pan(self, payload):
        if "pan" not in payload:
            raise Exception("set_track_pan requires a 'pan' parameter (-1.0 to 1.0)")
        pan = float(payload.get("pan"))
        if pan < -1.0 or pan > 1.0:
            raise Exception("pan must be between -1.0 and 1.0, got %s" % pan)
        track = self._track_by_index(payload.get("track_index", 0))
        track.mixer_device.panning.value = pan
        return {"track_index": payload.get("track_index", 0), "pan": track.mixer_device.panning.value}

    def _set_track_mute(self, payload):
        if "mute" not in payload:
            raise Exception("set_track_mute requires a 'mute' parameter (bool)")
        track = self._track_by_index(payload.get("track_index", 0))
        track.mute = bool(payload.get("mute"))
        return {"track_index": payload.get("track_index", 0), "mute": self._safe_attr(track, "mute", None)}

    def _set_track_solo(self, payload):
        if "solo" not in payload:
            raise Exception("set_track_solo requires a 'solo' parameter (bool)")
        track = self._track_by_index(payload.get("track_index", 0))
        track.solo = bool(payload.get("solo"))
        return {"track_index": payload.get("track_index", 0), "solo": self._safe_attr(track, "solo", None)}

    def _set_track_arm(self, payload):
        if "arm" not in payload:
            raise Exception("set_track_arm requires an 'arm' parameter (bool)")
        track = self._track_by_index(payload.get("track_index", 0))
        if not self._safe_attr(track, "can_be_armed", False):
            raise Exception('Track "%s" cannot be armed (not an armable track type)' % track.name)
        track.arm = bool(payload.get("arm"))
        return {"track_index": payload.get("track_index", 0), "arm": self._safe_attr(track, "arm", None)}

    def _set_track_send(self, payload):
        """Set a send level. send_index identifies which send bus (0=A, 1=B, ...)."""
        if "send_index" not in payload:
            raise Exception("set_track_send requires a 'send_index' parameter (int)")
        if "value" not in payload:
            raise Exception("set_track_send requires a 'value' parameter (0.0-1.0)")
        send_index = int(payload.get("send_index"))
        value = float(payload.get("value"))
        if value < 0.0 or value > 1.0:
            raise Exception("send value must be between 0.0 and 1.0, got %s" % value)
        track = self._track_by_index(payload.get("track_index", 0))
        sends = list(getattr(track.mixer_device, "sends", []))
        if send_index < 0 or send_index >= len(sends):
            raise Exception(
                "Send index out of range: %s (track has %s sends)" % (send_index, len(sends))
            )
        sends[send_index].value = value
        return {
            "track_index": payload.get("track_index", 0),
            "send_index": send_index,
            "value": sends[send_index].value,
        }

    def _set_track_monitoring(self, payload):
        """Set monitoring state: 0=In, 1=Auto, 2=Off."""
        if "monitoring" not in payload:
            raise Exception("set_track_monitoring requires a 'monitoring' parameter (0=In, 1=Auto, 2=Off)")
        monitoring = int(payload.get("monitoring"))
        if monitoring not in (0, 1, 2):
            raise Exception("monitoring must be 0 (In), 1 (Auto), or 2 (Off), got %s" % monitoring)
        track = self._track_by_index(payload.get("track_index", 0))
        track.current_monitoring_state = monitoring
        return {
            "track_index": payload.get("track_index", 0),
            "monitoring": self._safe_attr(track, "current_monitoring_state", None),
        }

    def _set_crossfader(self, payload):
        """Set the master crossfader position (-1.0 = A, 0.0 = center, 1.0 = B)."""
        if "position" not in payload:
            raise Exception("set_crossfader requires a 'position' parameter (-1.0 to 1.0)")
        position = float(payload.get("position"))
        if position < -1.0 or position > 1.0:
            raise Exception("crossfader position must be between -1.0 and 1.0, got %s" % position)
        song = self.song()
        song.crossfader = position
        return {"crossfader": self._safe_attr(song, "crossfader", None)}

    # ── Event Push (subscriber registry + snapshot/diff) ─────────
    # All subscriber-list mutation and all LOM reads happen on the main
    # thread (inside _drain_commands), so no locking is needed. Dead
    # subscribers are pruned when a push fails (send errors are swallowed
    # by _send_response, so we track success explicitly).

    def _subscribe(self, payload, conn):
        if conn is None:
            raise Exception("subscribe requires a live connection (use port %s)" % SUBSCRIBE_PORT)
        events = payload.get("events") or ["transport", "mixer", "scenes"]
        entry = {"conn": conn, "events": set(events)}
        if entry not in self._subscribers:
            self._subscribers.append(entry)
        self.log_message("[LiveAgent] subscriber added (%s total)" % len(self._subscribers))
        return {"subscribed": True, "events": sorted(events)}

    def _unsubscribe(self, payload, conn):
        if conn is None:
            raise Exception("unsubscribe requires a live connection")
        before = len(self._subscribers)
        self._subscribers = [s for s in self._subscribers if s["conn"] != conn]
        self.log_message("[LiveAgent] subscriber removed (%s -> %s)" % (before, len(self._subscribers)))
        return {"unsubscribed": True}

    def _snapshot_state(self):
        """Capture all watchable state for diffing. Runs on main thread."""
        song = self.song()
        transport = {
            "tempo": self._safe_attr(song, "tempo", None),
            "is_playing": self._safe_attr(song, "is_playing", None),
            "signature_numerator": self._safe_attr(song, "signature_numerator", None),
            "signature_denominator": self._safe_attr(song, "signature_denominator", None),
            "metronome": self._safe_attr(song, "metronome", None),
            "overdub": self._safe_attr(song, "overdub", None),
        }
        tracks = []
        for index, track in enumerate(self.song().tracks):
            mixer = self._safe_attr(track, "mixer_device", None)
            volume = self._safe_attr(self._safe_attr(mixer, "volume", None), "value", None) if mixer else None
            pan = self._safe_attr(self._safe_attr(mixer, "panning", None), "value", None) if mixer else None
            slots = []
            for slot in getattr(track, "clip_slots", []):
                slots.append({
                    "is_playing": self._safe_attr(slot, "is_playing", False),
                    "is_triggered": self._safe_attr(slot, "is_triggered", False),
                })
            tracks.append({
                "index": index,
                "volume": volume,
                "pan": pan,
                "mute": self._safe_attr(track, "mute", None),
                "solo": self._safe_attr(track, "solo", None),
                "arm": self._safe_attr(track, "arm", None),
                "slots": slots,
            })
        return {"transport": transport, "tracks": tracks}

    @staticmethod
    def _diff_state(old, new):
        """Compare two snapshots and return a list of event dicts.

        Pure function — no LOM access, no side effects. Easy to unit test.
        """
        events = []

        # Transport changes
        old_t = old.get("transport", {}) if old else {}
        new_t = new.get("transport", {})
        t_changes = {k: new_t[k] for k in new_t if old_t.get(k) != new_t.get(k)}
        if t_changes:
            events.append({"event": "transport_changed", "data": t_changes})

        # Per-track mixer + slot changes
        old_tracks = {t["index"]: t for t in (old.get("tracks", []) if old else [])}
        for track in new.get("tracks", []):
            idx = track["index"]
            old_track = old_tracks.get(idx, {})
            # Mixer changes (volume/pan/mute/solo/arm)
            m_changes = {}
            for key in ("volume", "pan", "mute", "solo", "arm"):
                old_val = old_track.get(key)
                new_val = track.get(key)
                if old_val != new_val and not (old_val is None and new_val is None):
                    m_changes[key] = new_val
            if m_changes:
                events.append({"event": "mixer_changed", "data": {"track_index": idx, "changes": m_changes}})

            # Clip slot changes (launch/stop)
            old_slots = old_track.get("slots", [])
            new_slots = track.get("slots", [])
            for s_idx, slot in enumerate(new_slots):
                old_slot = old_slots[s_idx] if s_idx < len(old_slots) else {}
                was_playing = old_slot.get("is_playing", False)
                now_playing = slot.get("is_playing", False)
                if now_playing and not was_playing:
                    events.append({"event": "clip_launched", "data": {"track_index": idx, "slot_index": s_idx}})
                elif was_playing and not now_playing:
                    events.append({"event": "clip_stopped", "data": {"track_index": idx, "slot_index": s_idx}})

        return events

    def _maybe_push_events(self):
        """Throttled snapshot/diff/push. Called from _drain_commands."""
        now = time.time()
        if now - self._last_push_time < PUSH_INTERVAL:
            return
        self._last_push_time = now

        try:
            snapshot = self._snapshot_state()
        except Exception:
            self._log_exception("event snapshot failed")
            return

        events = self._diff_state(self._last_snapshot, snapshot)
        self._last_snapshot = snapshot

        # The very first snapshot primes the baseline without emitting events,
        # so subscribers don't receive a flood of "everything changed" on connect.
        if not self._baseline_set:
            self._baseline_set = True
            return

        if not events:
            return

        # Broadcast to subscribers, pruning any that fail to receive.
        alive = []
        dead = []
        for sub in self._subscribers:
            wanted = sub["events"]
            relevant = [e for e in events if _event_in_category(e["event"], wanted)]
            if not relevant:
                alive.append(sub)
                continue
            payload = json.dumps(
                {"events": relevant}, separators=(",", ":")
            ).encode("utf-8") + b"\n"
            try:
                sub["conn"].sendall(payload)
                alive.append(sub)
            except Exception:
                dead.append(sub)
        if dead:
            self._subscribers = alive
            self.log_message("[LiveAgent] pruned %s dead subscriber(s)" % len(dead))

    def _track_summaries(self):
        return [self._track_summary(i, track) for i, track in enumerate(self.song().tracks)]

    def _track_summary(self, index, track):
        track_type = "midi" if self._safe_attr(track, "has_midi_input", False) else "audio"
        mixer = self._safe_attr(track, "mixer_device", None)
        volume = self._safe_attr(self._safe_attr(mixer, "volume", None), "value", None) if mixer else None
        pan = self._safe_attr(self._safe_attr(mixer, "panning", None), "value", None) if mixer else None
        sends = []
        if mixer:
            for send_index, send in enumerate(self._safe_attr(mixer, "sends", [])):
                sends.append({
                    "index": send_index,
                    "name": self._safe_attr(send, "name", ""),
                    "value": self._safe_attr(send, "value", None),
                    "min": self._safe_attr(send, "min", None),
                    "max": self._safe_attr(send, "max", None),
                })
        devices = []
        for device_index, device in enumerate(getattr(track, "devices", [])):
            devices.append(
                {
                    "index": device_index,
                    "name": device.name,
                    "class_name": self._safe_attr(device, "class_name", ""),
                    "parameters": [
                        {
                            "index": parameter_index,
                            "name": parameter.name,
                            "value": self._safe_attr(parameter, "value", None),
                            "min": self._safe_attr(parameter, "min", None),
                            "max": self._safe_attr(parameter, "max", None),
                            "is_enabled": self._safe_attr(parameter, "is_enabled", True),
                        }
                        for parameter_index, parameter in enumerate(getattr(device, "parameters", []))
                    ],
                }
            )

        clip_slots = []
        for slot_index, slot in enumerate(getattr(track, "clip_slots", [])):
            clip = slot.clip if slot.has_clip else None
            clip_slots.append(
                {
                    "index": slot_index,
                    "has_clip": bool(slot.has_clip),
                    "clip": self._clip_summary(clip) if clip else None,
                }
            )

        return {
            "index": index,
            "name": track.name,
            "type": track_type,
            "has_midi_input": self._safe_attr(track, "has_midi_input", False),
            "has_audio_input": self._safe_attr(track, "has_audio_input", False),
            "can_be_armed": self._safe_attr(track, "can_be_armed", False),
            "arm": self._safe_attr(track, "arm", False),
            "mute": self._safe_attr(track, "mute", False),
            "solo": self._safe_attr(track, "solo", False),
            "color": self._safe_attr(track, "color", None),
            "volume": volume,
            "pan": pan,
            "sends": sends,
            "monitoring": self._safe_attr(track, "current_monitoring_state", None),
            "crossfade_assign": self._safe_attr(mixer, "crossfade_assign", None) if mixer else None,
            "devices": devices,
            "clip_slots": clip_slots,
        }

    def _scene_summary(self, index, scene):
        return {
            "index": index,
            "name": scene.name,
            "color": self._safe_attr(scene, "color", None),
        }

    def _clip_summary(self, clip):
        return {
            "name": clip.name,
            "length": self._safe_attr(clip, "length", None),
            "loop_start": self._safe_attr(clip, "loop_start", None),
            "loop_end": self._safe_attr(clip, "loop_end", None),
            "is_midi_clip": self._safe_attr(clip, "is_midi_clip", False),
            "color": self._safe_attr(clip, "color", None),
        }

    def _create_midi_track(self, payload):
        index = int(payload.get("index", -1))
        self.song().create_midi_track(index)
        return {"tracks": self._track_summaries()}

    def _set_track_name(self, payload):
        if "name" not in payload:
            raise Exception("set_track_name requires a 'name' parameter")
        track = self._track_by_index(payload.get("track_index", 0))
        track.name = str(payload.get("name"))
        return {"track_index": self._track_index(track), "name": track.name}

    def _set_track_color(self, payload):
        if "color" not in payload:
            raise Exception("set_track_color requires a 'color' parameter")
        track = self._track_by_index(payload.get("track_index", 0))
        track.color = int(payload.get("color"))
        return {"track_index": self._track_index(track), "color": self._safe_attr(track, "color", None)}

    def _duplicate_track(self, payload):
        index = int(payload.get("track_index", 0))
        self._track_by_index(index)
        self.song().duplicate_track(index)
        new_index = min(index + 1, len(self.song().tracks) - 1)
        return {"source_track_index": index, "new_track_index": new_index, "track": self._track_summary(new_index, self.song().tracks[new_index])}

    def _delete_track(self, payload):
        index = int(payload.get("track_index", 0))
        track = self._track_by_index(index)
        name = track.name
        self.song().delete_track(index)
        return {"deleted": True, "track_index": index, "name": name}

    def _create_scene(self, payload):
        index = int(payload.get("index", -1))
        self.song().create_scene(index)
        actual_index = index if index >= 0 else len(self.song().scenes) - 1
        scene = self.song().scenes[actual_index]
        if payload.get("name"):
            scene.name = str(payload.get("name"))
        if payload.get("color") is not None:
            scene.color = int(payload.get("color"))
        return {"scene": self._scene_summary(actual_index, scene)}

    def _set_scene_name(self, payload):
        if "name" not in payload:
            raise Exception("set_scene_name requires a 'name' parameter")
        scene = self._scene_by_index(payload.get("scene_index", 0))
        scene.name = str(payload.get("name"))
        return {"scene_index": self._scene_index(scene), "name": scene.name}

    def _set_scene_color(self, payload):
        if "color" not in payload:
            raise Exception("set_scene_color requires a 'color' parameter")
        scene = self._scene_by_index(payload.get("scene_index", 0))
        scene.color = int(payload.get("color"))
        return {"scene_index": self._scene_index(scene), "color": self._safe_attr(scene, "color", None)}

    def _duplicate_scene(self, payload):
        index = int(payload.get("scene_index", 0))
        self._scene_by_index(index)
        self.song().duplicate_scene(index)
        new_index = min(index + 1, len(self.song().scenes) - 1)
        return {"source_scene_index": index, "new_scene_index": new_index, "scene": self._scene_summary(new_index, self.song().scenes[new_index])}

    def _delete_scene(self, payload):
        index = int(payload.get("scene_index", 0))
        scene = self._scene_by_index(index)
        name = scene.name
        self.song().delete_scene(index)
        return {"deleted": True, "scene_index": index, "name": name}

    def _create_session_clip(self, payload):
        track, slot = self._track_and_slot(payload)
        self._require_midi_track(track)

        length = float(payload.get("length_beats", 16))
        replace = bool(payload.get("replace", False))

        if slot.has_clip:
            if not replace:
                raise Exception("Clip slot already contains a clip")
            slot.delete_clip()

        slot.create_clip(length)
        clip = slot.clip
        clip.loop_start = 0
        clip.loop_end = length
        if payload.get("name"):
            clip.name = payload.get("name")
        if payload.get("color") is not None:
            clip.color = int(payload.get("color"))
        return {"clip": self._clip_summary(clip)}

    def _write_midi_notes(self, payload):
        track, slot = self._track_and_slot(payload)
        self._require_midi_track(track)
        if not slot.has_clip:
            length = float(payload.get("length_beats", 16))
            slot.create_clip(length)
        clip = slot.clip
        if not self._safe_attr(clip, "is_midi_clip", False):
            raise Exception("Target clip is not a MIDI clip")

        notes = []
        for note in payload.get("notes", []):
            notes.append(
                (
                    int(note.get("pitch")),
                    float(note.get("start")),
                    float(note.get("duration")),
                    int(note.get("velocity", 96)),
                    bool(note.get("muted", False)),
                )
            )

        clip.select_all_notes()
        clip.replace_selected_notes(tuple(notes))
        clip.deselect_all_notes()
        return {"clip": self._clip_summary(clip), "note_count": len(notes)}

    def _read_clip_notes(self, payload):
        _track, slot = self._track_and_slot(payload)
        if not slot.has_clip:
            return {"notes": []}
        clip = slot.clip
        end = float(payload.get("length_beats", self._safe_attr(clip, "length", 16)))
        raw_notes = clip.get_notes(0, 0, end, 128)
        notes = [
            {
                "pitch": int(note[0]),
                "start": float(note[1]),
                "duration": float(note[2]),
                "velocity": int(note[3]),
                "muted": bool(note[4]),
            }
            for note in raw_notes
        ]
        return {"notes": notes}

    def _clear_clip_notes(self, payload):
        _track, slot = self._track_and_slot(payload)
        if not slot.has_clip:
            return {"note_count": 0}
        clip = slot.clip
        clip.select_all_notes()
        clip.replace_selected_notes(tuple())
        clip.deselect_all_notes()
        return {"clip": self._clip_summary(clip), "note_count": 0}

    def _list_devices(self, payload):
        track = self._track_by_index(payload.get("track_index", 0))
        return {"track": self._track_summary(self._track_index(track), track)}

    def _set_parameter_value(self, payload):
        device, parameter = self._device_and_parameter(payload)
        value = float(payload.get("value"))
        parameter.value = value
        return {
            "device": device.name,
            "parameter": parameter.name,
            "value": parameter.value,
        }

    def _write_clip_automation(self, payload):
        _track, slot = self._track_and_slot(payload)
        if not slot.has_clip:
            raise Exception("Target slot has no clip")
        clip = slot.clip
        device, parameter = self._device_and_parameter(payload)
        points = payload.get("points", [])
        step_duration = float(payload.get("step_duration", 0.25))

        if hasattr(clip, "clear_envelope"):
            try:
                clip.clear_envelope(parameter)
            except Exception:
                pass

        envelope = None
        if hasattr(clip, "create_automation_envelope"):
            try:
                envelope = clip.create_automation_envelope(parameter)
            except Exception:
                envelope = None

        if envelope is None and hasattr(clip, "automation_envelope"):
            envelope = clip.automation_envelope(parameter)

        if envelope is None or not hasattr(envelope, "insert_step"):
            raise Exception(
                "Clip automation envelope writing is not available in this Live Python API. "
                "Parameter listing and set_parameter_value still work."
            )

        inserted = 0
        for point in points:
            envelope.insert_step(float(point.get("time")), step_duration, float(point.get("value")))
            inserted += 1

        return {
            "clip": self._clip_summary(clip),
            "device": device.name,
            "parameter": parameter.name,
            "point_count": inserted,
        }

    def _browser_root(self, browser, browser_type):
        """Return the Live Browser root for a friendly browser_type string."""
        bt = str(browser_type or "").lower().replace("-", "_").replace(" ", "_")
        if bt in ("plugin", "plugins", "plug_in", "plug_ins", "vst", "vst3"):
            return browser.plugins
        if bt in ("instrument", "instruments"):
            return browser.instruments
        if bt in ("drum", "drums"):
            return browser.drums
        if bt in ("audio_effect", "audio_effects", "audio"):
            return browser.audio_effects
        if bt in ("midi_effect", "midi_effects", "midi"):
            return browser.midi_effects
        if bt in ("sample", "samples"):
            return browser.samples
        raise Exception("Unknown browser_type '%s'" % browser_type)

    def _load_device(self, payload):
        """Load a device onto a track via Ableton's browser tree.

        Uses the Live Browser API to navigate Plugins/Instruments and load
        the specified device onto the target track.
        """
        import Live
        track = self._track_by_index(payload.get("track_index", 0))
        device_name = payload.get("device_name", "")
        browser_type = payload.get("browser_type", "plug-in")  # plug-in, instrument, audio_effect, midi_effect

        if not device_name:
            raise Exception("device_name is required")

        # Select the target track so the browser loads onto it
        song = self.song()
        song.view.selected_track = track

        # Navigate Ableton's browser to find and load the device.
        # Browser belongs to the Application object, not Song.
        browser = Live.Application.get_application().browser
        
        target_category = self._browser_root(browser, browser_type)

        # Search for the device in the category tree
        device_item = self._find_browser_item(target_category, device_name)

        if device_item is None:
            raise Exception(
                "Could not find device '%s' in category '%s'"
                % (device_name, target_category.name)
            )

        # Load the device onto the selected track
        browser.load_item(device_item)
        
        # Small wait then check if device appeared
        time.sleep(0.3)
        
        # Return updated track info
        idx = self._track_index(track)
        return {
            "track": self._track_summary(idx, track),
            "loaded_device": device_name,
        }

    def _list_browser_devices(self, payload):
        """List available devices from Ableton's browser.

        Optionally filter by browser_type and search query.
        """
        browser_type = payload.get("browser_type", "plug-in")
        query = payload.get("query", "").lower()
        max_results = int(payload.get("max_results", 100))

        import Live
        browser = Live.Application.get_application().browser
        target_category = self._browser_root(browser, browser_type)

        # Collect all loadable devices from the browser tree
        devices = []
        self._collect_browser_items(target_category, devices, query, max_results, path=[])

        return {
            "category": target_category.name,
            "query": payload.get("query", ""),
            "count": len(devices),
            "devices": devices,
        }

    def _collect_browser_items(self, node, results, query, max_results, path):
        """Recursively collect loadable items from browser tree."""
        if len(results) >= max_results:
            return

        node_name = self._safe_attr(node, "name", "")

        # Build current path
        current_path = path + [node_name] if node_name else path

        # Check if this node is loadable
        is_loadable = self._safe_attr(node, "is_loadable", False)
        if is_loadable and node_name:
            if not query or query in node_name.lower():
                results.append({
                    "name": node_name,
                    "path": " > ".join(current_path),
                })
                if len(results) >= max_results:
                    return

        # Recurse into children
        children = self._safe_attr(node, "children", None)
        if children:
            for child in children:
                self._collect_browser_items(child, results, query, max_results, current_path)
                if len(results) >= max_results:
                    return

        # Check items list
        items = self._safe_attr(node, "items", None)
        if items:
            for item in items:
                if len(results) >= max_results:
                    return
                item_name = self._safe_attr(item, "name", "")
                item_loadable = self._safe_attr(item, "is_loadable", False)
                if item_loadable and item_name:
                    if not query or query in item_name.lower():
                        results.append({
                            "name": item_name,
                            "path": " > ".join(current_path + [item_name]),
                        })

    def _find_browser_item(self, category, target_name):
        """Recursively search browser tree for a device by name."""
        target_lower = target_name.lower()
        
        # Check items directly in this category
        if hasattr(category, "children"):
            for child in category.children:
                result = self._search_browser_node(child, target_lower)
                if result is not None:
                    return result
        
        # Some categories have items directly
        if hasattr(category, "items"):
            for item in category.items:
                if hasattr(item, "name") and item.name and target_lower in item.name.lower():
                    if self._safe_attr(item, "is_loadable", True):
                        return item

        return None

    def _search_browser_node(self, node, target_lower):
        """Recursively search a browser node."""
        node_name = self._safe_attr(node, "name", "")
        
        if node_name and target_lower in node_name.lower():
            if self._safe_attr(node, "is_loadable", True):
                return node

        # Check children
        children = self._safe_attr(node, "children", None)
        if children:
            for child in children:
                result = self._search_browser_node(child, target_lower)
                if result is not None:
                    return result

        # Check items
        items = self._safe_attr(node, "items", None)
        if items:
            for item in items:
                item_name = self._safe_attr(item, "name", "")
                if item_name and target_lower in item_name.lower():
                    if self._safe_attr(item, "is_loadable", True):
                        return item

        return None

    def _track_and_slot(self, payload):
        track = self._track_by_index(payload.get("track_index", 0))
        slot_index = int(payload.get("slot_index", 0))
        self._ensure_scene(slot_index)
        return track, track.clip_slots[slot_index]

    def _existing_track_and_slot(self, payload):
        track = self._track_by_index(payload.get("track_index", 0))
        slot_index = int(payload.get("slot_index", 0))
        clip_slots = list(getattr(track, "clip_slots", []))
        if slot_index < 0 or slot_index >= len(clip_slots):
            raise Exception(
                "Slot index out of range: %s (track has %s slots)"
                % (slot_index, len(clip_slots))
            )
        return track, clip_slots[slot_index]

    def _track_by_index(self, index):
        tracks = list(self.song().tracks)
        index = int(index)
        if index < 0 or index >= len(tracks):
            raise Exception("Track index out of range: %s" % index)
        return tracks[index]

    def _scene_by_index(self, index):
        scenes = list(self.song().scenes)
        index = int(index)
        if index < 0 or index >= len(scenes):
            raise Exception("Scene index out of range: %s" % index)
        return scenes[index]

    def _ensure_scene(self, slot_index):
        song = self.song()
        while slot_index >= len(song.scenes):
            song.create_scene(-1)

    def _require_midi_track(self, track):
        if not self._safe_attr(track, "has_midi_input", False):
            raise Exception('Track "%s" is not a MIDI track' % track.name)

    def _device_and_parameter(self, payload):
        track = self._track_by_index(payload.get("track_index", 0))
        device = self._find_by_index_or_name(
            track.devices,
            payload.get("device_index"),
            payload.get("device_name"),
            "device",
        )
        parameter = self._find_by_index_or_name(
            device.parameters,
            payload.get("parameter_index"),
            payload.get("parameter_name"),
            "parameter",
        )
        return device, parameter

    def _find_by_index_or_name(self, items, index, name, label):
        items = list(items)
        if index is not None:
            index = int(index)
            if index < 0 or index >= len(items):
                raise Exception("%s index out of range: %s" % (label, index))
            return items[index]

        if name:
            target = str(name).lower()
            for item in items:
                if item.name.lower() == target:
                    return item
            for item in items:
                if target in item.name.lower():
                    return item

        raise Exception("Could not find %s: %s" % (label, name if name else index))

    def _track_index(self, track):
        for index, candidate in enumerate(self.song().tracks):
            if candidate == track:
                return index
        return None

    def _scene_index(self, scene):
        if scene is None:
            return None
        for index, candidate in enumerate(self.song().scenes):
            if candidate == scene:
                return index
        return None

    def _device_index(self, track, device):
        for index, candidate in enumerate(getattr(track, "devices", [])):
            if candidate == device:
                return index
        return None

    def _safe_attr(self, obj, attr, default):
        try:
            return getattr(obj, attr)
        except Exception:
            return default

    def _log_exception(self, label):
        try:
            self.log_message("[LiveAgent] %s: %s" % (label, traceback.format_exc()))
        except Exception:
            pass

    # ── Audio Clip Commands ──────────────────────────────────

    def _create_audio_track(self, payload):
        """Create a new audio track."""
        index = int(payload.get("index", -1))
        song = self.song()
        song.create_audio_track(index)
        actual_index = index if index >= 0 else len(song.tracks) - 1
        track = song.tracks[actual_index]
        return {"track_index": actual_index, "name": track.name}

    def _import_audio_clip(self, payload):
        """Import an audio file into a track slot."""
        import os
        file_path = payload.get("file_path", "")
        if not file_path or not os.path.isfile(file_path):
            raise Exception("Audio file not found: %s" % file_path)

        track_index = int(payload.get("track_index", 0))
        slot_index = int(payload.get("slot_index", 0))
        track = self._track_by_index(track_index)
        self._ensure_scene(slot_index)
        slot = track.clip_slots[slot_index]

        # Use Ableton's browser to import - set view focus then drag
        # The reliable method: create clip via Live's file import
        song = self.song()
        song.view.selected_track = track
        song.view.selected_scene = song.scenes[slot_index]

        # Import using Live's internal command
        # Live 11: we can use the browser's file system import
        # Most reliable: use set_file_path if available, or browser drag
        import Live
        Live.Application.get_application().open_document(file_path)

        return {
            "track_index": track_index,
            "slot_index": slot_index,
            "file": os.path.basename(file_path),
            "status": "imported",
        }

    def _get_clip_info(self, payload):
        """Get detailed info about a clip (audio or MIDI)."""
        track, slot = self._track_and_slot(payload)
        if not slot.has_clip:
            return {"has_clip": False}

        clip = slot.clip
        info = {
            "has_clip": True,
            "name": clip.name,
            "color": clip.color,
            "is_audio_clip": self._safe_attr(clip, "is_audio_clip", False),
            "is_midi_clip": self._safe_attr(clip, "is_midi_clip", False),
            "looping": clip.looping,
            "loop_start": clip.loop_start,
            "loop_end": clip.loop_end,
            "start_marker": clip.start_marker,
            "end_marker": clip.end_marker,
            "pitch": self._safe_attr(clip, "pitch_coarse", 0),
            "gain": self._safe_attr(clip, "gain", 1.0),
        }

        # Audio-specific properties
        if self._safe_attr(clip, "is_audio_clip", False):
            info["warping"] = clip.warping
            info["warp_mode"] = str(self._safe_attr(clip, "warp_mode", ""))
            info["file_path"] = self._safe_attr(clip, "file_path", "")
            info["sample_length"] = self._safe_attr(clip, "sample_length", 0.0)

        return info

    def _set_clip_properties(self, payload):
        """Set clip properties: name, color, loop, start/end, pitch, gain."""
        track, slot = self._track_and_slot(payload)
        if not slot.has_clip:
            raise Exception("No clip at track %s slot %s" % (payload.get("track_index"), payload.get("slot_index")))
        clip = slot.clip

        if "name" in payload:
            clip.name = payload["name"]
        if "color" in payload:
            clip.color = int(payload["color"])
        if "looping" in payload:
            clip.looping = bool(payload["looping"])
        if "loop_start" in payload:
            clip.loop_start = float(payload["loop_start"])
        if "loop_end" in payload:
            clip.loop_end = float(payload["loop_end"])
        if "start_marker" in payload:
            clip.start_marker = float(payload["start_marker"])
        if "end_marker" in payload:
            clip.end_marker = float(payload["end_marker"])

        # Audio-specific
        if self._safe_attr(clip, "is_audio_clip", False):
            if "pitch_coarse" in payload:
                clip.pitch_coarse = int(payload["pitch_coarse"])
            if "pitch_fine" in payload:
                clip.pitch_fine = float(payload["pitch_fine"])
            if "gain" in payload:
                clip.gain = float(payload["gain"])

        return {"updated": True, "clip": self._get_clip_info(payload)}

    def _duplicate_clip(self, payload):
        """Duplicate a clip to another slot (same or different track)."""
        src_track = self._track_by_index(int(payload.get("track_index", 0)))
        src_slot_idx = int(payload.get("slot_index", 0))
        self._ensure_scene(src_slot_idx)
        src_slot = src_track.clip_slots[src_slot_idx]
        if not src_slot.has_clip:
            raise Exception("No clip at source slot %s" % src_slot_idx)

        dst_track_idx = int(payload.get("dest_track_index", payload.get("track_index", 0)))
        dst_slot_idx = int(payload.get("dest_slot_index", src_slot_idx + 1))
        dst_track = self._track_by_index(dst_track_idx)
        self._ensure_scene(dst_slot_idx)
        dst_slot = dst_track.clip_slots[dst_slot_idx]

        src_slot.clip.duplicate_clip_to(dst_slot)

        return {
            "source": {"track": int(payload.get("track_index", 0)), "slot": src_slot_idx},
            "destination": {"track": dst_track_idx, "slot": dst_slot_idx},
        }

    def _delete_clip(self, payload):
        """Delete a clip from a slot."""
        track, slot = self._track_and_slot(payload)
        if not slot.has_clip:
            raise Exception("No clip at track %s slot %s" % (payload.get("track_index"), payload.get("slot_index")))
        clip_name = slot.clip.name
        slot.delete_clip()
        return {"deleted": True, "clip_name": clip_name}

    def _set_clip_warp(self, payload):
        """Set warp properties on an audio clip."""
        track, slot = self._track_and_slot(payload)
        if not slot.has_clip:
            raise Exception("No clip at track %s slot %s" % (payload.get("track_index"), payload.get("slot_index")))
        clip = slot.clip

        if not self._safe_attr(clip, "is_audio_clip", False):
            raise Exception("Clip is not an audio clip")

        if "warping" in payload:
            clip.warping = bool(payload["warping"])
        if "warp_mode" in payload:
            # Warp modes: 0=beats, 1=tones, 2=texture, 3=re-pitch, 4=complex, 5=complex pro
            clip.warp_mode = int(payload["warp_mode"])

        return {
            "warping": clip.warping,
            "warp_mode": str(clip.warp_mode),
        }

    def _analyze_and_warp(self, payload):
        """Analyze audio clip for BPM/key and auto-set warp markers.

        Uses Ableton's built-in warping with detected BPM as hint.
        The analysis runs via the external audio_analyzer.py tool,
        but this command handles the Ableton-side warp setup.
        """
        track, slot = self._track_and_slot(payload)
        if not slot.has_clip:
            raise Exception("No clip at track %s slot %s" % (payload.get("track_index"), payload.get("slot_index")))
        clip = slot.clip

        if not self._safe_attr(clip, "is_audio_clip", False):
            raise Exception("Clip is not an audio clip")

        detected_bpm = payload.get("bpm")
        detected_key = payload.get("key")
        warp_mode = int(payload.get("warp_mode", 4))  # default: complex

        # Enable warping
        clip.warping = True

        # Set warp mode
        clip.warp_mode = warp_mode

        # Set clip name with key info if detected
        if detected_key:
            original_name = clip.name
            if not any(k in original_name for k in ["maj", "min", "m "]):
                clip.name = "%s [%s]" % (original_name, detected_key)

        # Set loop to match detected length
        sample_length = self._safe_attr(clip, "sample_length", 0.0)

        result = {
            "warping": True,
            "warp_mode": warp_mode,
            "clip_name": clip.name,
            "sample_length": sample_length,
        }

        if detected_bpm:
            result["detected_bpm"] = detected_bpm
        if detected_key:
            result["detected_key"] = detected_key

        return result

    # ── Drum Rack Commands ──────────────────────────────────

    def _create_drum_rack(self, payload):
        """Create a Drum Rack on a MIDI track.

        Creates a new MIDI track and loads a Drum Rack device via the
        browser Instruments category. Returns track index and device info.
        """
        import Live

        track_index = payload.get("track_index", -1)
        name = payload.get("name", "Drum Rack")
        kit_name = payload.get("kit_name", "808 Core Kit.adg")
        empty = bool(payload.get("empty", False))

        song = self.song()

        # Create MIDI track
        if track_index >= 0:
            song.create_midi_track(track_index)
            track = song.tracks[track_index]
        else:
            idx = len(song.tracks)
            song.create_midi_track(-1)
            track = song.tracks[idx]
            track_index = idx

        track.name = name

        # Select the track so browser loads onto it
        song.view.selected_track = track

        # Load a usable Drum Rack template by default. Empty Drum Racks have no
        # pad chains, and Live's Python API exposes copy_pad but no create_pad.
        browser = Live.Application.get_application().browser
        loaded = False

        target_category = browser.instruments if empty else browser.drums
        target_name = "Drum Rack" if empty else kit_name

        if target_category is not None:
            device_item = self._find_browser_item(target_category, target_name)
            if device_item is not None:
                browser.load_item(device_item)
                time.sleep(0.3)
                loaded = True

        # Find the loaded device
        devices = []
        for i, d in enumerate(track.devices):
            devices.append({
                "index": i,
                "name": str(d.name),
                "class_name": str(d.class_name) if self._safe_attr(d, "class_name", None) else "",
            })

        # Find Drum Rack device
        drum_rack_index = None
        for d in devices:
            if "drum" in d["name"].lower() or "drum" in d.get("class_name", "").lower():
                drum_rack_index = d["index"]
                break

        return {
            "track_index": track_index,
            "track_name": name,
            "devices": devices,
            "drum_rack_index": drum_rack_index,
            "loaded": loaded or drum_rack_index is not None,
            "loaded_item": target_name if loaded else None,
            "empty": empty,
        }

    def _find_browser_sample_by_name(self, browser, sample_name):
        """Find a BrowserSample by name from browser.samples (flat list)."""
        return self._find_browser_item_by_names(browser.samples, [sample_name])

    def _find_browser_item_by_names(self, root, names):
        """Find a loadable browser item by exact or partial name match."""
        exact_names = set([n for n in names if n])
        lowered = [n.lower() for n in exact_names]

        def visit(node):
            node_name = str(self._safe_attr(node, "name", ""))
            node_lower = node_name.lower()
            if node_name in exact_names and self._safe_attr(node, "is_loadable", False):
                return node
            if node_lower and any(n in node_lower for n in lowered):
                if self._safe_attr(node, "is_loadable", False):
                    return node

            children = self._safe_attr(node, "children", None)
            if children:
                for child in children:
                    found = visit(child)
                    if found is not None:
                        return found

            items = self._safe_attr(node, "items", None)
            if items:
                for item in items:
                    found = visit(item)
                    if found is not None:
                        return found
            return None

        return visit(root)

    def _apply_drum_pad_name(self, pad, chains, pad_name):
        """Best-effort rename for Live drum pads.

        Different Live versions expose the visible Drum Rack pad label via
        either DrumPad.name or the first pad chain name, so try both.
        """
        name = str(pad_name or "").strip()
        result = {
            "requested": name,
            "applied": False,
            "targets": [],
            "errors": [],
        }
        if not name:
            result["visible_name"] = str(self._safe_attr(pad, "name", ""))
            return result

        try:
            pad.name = name
            result["targets"].append("pad")
        except Exception as e:
            result["errors"].append("pad.name: %s" % str(e))

        if chains is not None and len(chains) > 0:
            try:
                chains[0].name = name
                result["targets"].append("chain")
            except Exception as e:
                result["errors"].append("chain.name: %s" % str(e))

        result["visible_name"] = str(self._safe_attr(pad, "name", ""))
        if chains is not None and len(chains) > 0:
            result["chain_name"] = str(self._safe_attr(chains[0], "name", ""))
        result["applied"] = bool(result["targets"])
        return result

    def _load_sample_to_pad(self, payload):
        """Load a browser-indexed sample onto a Drum Rack pad."""
        import os
        import Live

        track_index = int(payload["track_index"])
        pad_index = int(payload.get("pad_index", payload.get("note", 36)))
        file_path = payload["file_path"]
        reset_effects = payload.get("reset_effects", False)
        pad_name = payload.get("pad_name")

        if not os.path.isfile(file_path):
            raise Exception("File not found: %s" % file_path)

        song = self.song()
        track = song.tracks[track_index]

        # Find Drum Rack device
        drum_rack_index = int(payload.get("drum_rack_index", 0))
        if drum_rack_index >= len(track.devices):
            raise Exception("No device at index %d on track %d" % (drum_rack_index, track_index))
        drum_rack = track.devices[drum_rack_index]

        drum_pads = self._safe_attr(drum_rack, "drum_pads", None)
        if drum_pads is None:
            raise Exception("No drum_pads on device (not a Drum Rack?)")

        pad = drum_pads[pad_index]
        was_empty = False

        # Check if pad has an existing chain
        chains = self._safe_attr(pad, "chains", None)
        if chains is None or len(chains) == 0:
            # Empty pad — find a template pad to copy from
            was_empty = True
            template_idx = None
            for i in range(128):
                test_chains = self._safe_attr(drum_pads[i], "chains", None)
                if test_chains is not None and len(test_chains) > 0:
                    template_idx = i
                    break

            if template_idx is None:
                raise Exception(
                    "No pad with existing chain found. Load a kit (.adg) first to create a template."
                )

            # Copy template pad to target pad
            drum_rack.copy_pad(template_idx, pad_index)

            # Re-fetch pad after copy
            pad = drum_pads[pad_index]
            chains = self._safe_attr(pad, "chains", None)

            if chains is None or len(chains) == 0:
                raise Exception("copy_pad failed to create chain on pad %d" % pad_index)

        chain = chains[0]
        devices = self._safe_attr(chain, "devices", [])

        if len(devices) == 0:
            raise Exception("Pad %d chain has no devices" % pad_index)

        first_device = devices[0]

        inner_chains = self._safe_attr(first_device, "chains", None)
        if inner_chains is not None and len(inner_chains) > 0:
            inner_chain = inner_chains[0]
        else:
            inner_chain = chain

        browser = Live.Application.get_application().browser
        sample_names = [os.path.basename(file_path)]
        real_name = os.path.basename(os.path.realpath(file_path))
        if real_name not in sample_names:
            sample_names.append(real_name)
        # Search browser.samples first (factory content)
        browser_item = self._find_browser_item_by_names(browser.samples, sample_names)

        # Fallback: search user_folders (user-added Places folders)
        if browser_item is None:
            user_folders = self._safe_attr(browser, "user_folders", [])
            for uf in user_folders:
                browser_item = self._find_browser_item_by_names(uf, sample_names)
                if browser_item is not None:
                    break

        temp_track_index = len(song.tracks)
        song.create_midi_track(-1)
        temp_track = song.tracks[temp_track_index]
        temp_track.name = "LiveAgent sample temp"
        song.view.selected_track = temp_track

        loaded_via_browser = False
        if browser_item is not None:
            try:
                browser.load_item(browser_item)
                time.sleep(0.5)
                loaded_via_browser = True
            except Exception:
                pass

        if not loaded_via_browser or len(temp_track.devices) == 0:
            # Fallback: use open_document to load sample directly
            try:
                import Live
                Live.Application.get_application().open_document(file_path)
                time.sleep(1.0)
            except Exception:
                pass

        if len(temp_track.devices) == 0:
            song.delete_track(temp_track_index)
            raise Exception(
                "Could not load sample: %s. Neither browser.load_item nor open_document succeeded. "
                "Try expanding the folder in Ableton's browser to trigger indexing."
                % os.path.basename(file_path)
            )

        new_device = temp_track.devices[0]

        current_devices = list(self._safe_attr(inner_chain, "devices", []))
        if reset_effects:
            for idx in range(len(current_devices) - 1, -1, -1):
                try:
                    inner_chain.delete_device(idx)
                except Exception:
                    pass
        elif len(current_devices) > 0:
            inner_chain.delete_device(0)

        try:
            song.move_device(new_device, inner_chain, 0)
        finally:
            for idx in range(len(song.tracks) - 1, -1, -1):
                try:
                    if song.tracks[idx] == temp_track:
                        song.delete_track(idx)
                        break
                except Exception:
                    pass

        pad_name_result = None
        if pad_name:
            pad = drum_pads[pad_index]
            chains = self._safe_attr(pad, "chains", None)
            pad_name_result = self._apply_drum_pad_name(pad, chains, pad_name)

        final_pad_name = str(self._safe_attr(drum_pads[pad_index], "name", ""))
        return {
            "track_index": track_index,
            "pad_index": pad_index,
            "file": os.path.basename(file_path),
            "loaded": True,
            "method": "browser_load_move_device",
            "was_empty_pad": was_empty,
            "reset_effects": reset_effects,
            "pad_name": final_pad_name,
            "requested_pad_name": str(pad_name) if pad_name else None,
            "pad_name_set": bool(pad_name_result and pad_name_result.get("applied")),
            "pad_name_result": pad_name_result,
        }

    def _set_drum_pad_name(self, payload):
        """Rename a Drum Rack pad without loading a sample."""
        track_index = int(payload["track_index"])
        drum_rack_index = int(payload.get("drum_rack_index", 0))
        pad_index = int(payload.get("pad_index", payload.get("note", 36)))
        pad_name = payload["pad_name"]

        song = self.song()
        track = song.tracks[track_index]

        if drum_rack_index >= len(track.devices):
            raise Exception("No device at index %d on track %d" % (drum_rack_index, track_index))
        drum_rack = track.devices[drum_rack_index]

        drum_pads = self._safe_attr(drum_rack, "drum_pads", None)
        if drum_pads is None:
            raise Exception("No drum_pads on device (not a Drum Rack?)")
        if pad_index < 0 or pad_index >= len(drum_pads):
            raise Exception("Pad index out of range: %d" % pad_index)

        pad = drum_pads[pad_index]
        chains = self._safe_attr(pad, "chains", None)
        name_result = self._apply_drum_pad_name(pad, chains, pad_name)
        if not name_result.get("applied"):
            raise Exception("Could not set drum pad name: %s" % "; ".join(name_result.get("errors", [])))

        return {
            "track_index": track_index,
            "drum_rack_index": drum_rack_index,
            "pad_index": pad_index,
            "pad_name": name_result.get("visible_name", str(self._safe_attr(pad, "name", ""))),
            "requested_pad_name": str(pad_name),
            "pad_name_set": True,
            "pad_name_result": name_result,
        }

    def _inspect_drum_rack(self, payload):
        """Debug: inspect drum rack pad structure."""
        track_index = int(payload["track_index"])
        drum_rack_index = int(payload.get("drum_rack_index", 0))
        pad_range = payload.get("pad_range", [0, 16])

        song = self.song()
        track = song.tracks[track_index]
        device = track.devices[drum_rack_index]
        drum_pads = self._safe_attr(device, "drum_pads", None)

        pads_info = []
        if drum_pads is not None:
            for i in range(max(0, pad_range[0]), min(128, pad_range[1])):
                try:
                    pad = drum_pads[i]
                    chains = self._safe_attr(pad, "chains", None)
                    has_chain = chains is not None and len(chains) > 0
                    pad_info = {
                        "index": i,
                        "name": str(self._safe_attr(pad, "name", "")),
                        "active": bool(self._safe_attr(pad, "active", False)),
                        "mute": bool(self._safe_attr(pad, "mute", False)),
                        "solo": bool(self._safe_attr(pad, "solo", False)),
                        "has_chain": has_chain,
                    }
                    if has_chain:
                        chain = chains[0]
                        pad_info["chain_name"] = str(self._safe_attr(chain, "name", ""))
                        chain_devices = self._safe_attr(chain, "devices", [])
                        devs = []
                        for cd in chain_devices:
                            cn = str(self._safe_attr(cd, "name", ""))
                            ccn = str(self._safe_attr(cd, "class_name", ""))
                            dev_info = {"name": cn, "class_name": ccn}
                            # Check sample attribute
                            sample = self._safe_attr(cd, "sample", None)
                            if sample is not None:
                                fp = self._safe_attr(sample, "file_path", None)
                                dev_info["sample_file_path"] = fp
                                # Check if file_path is settable
                                try:
                                    sample.file_path
                                    dev_info["file_path_readable"] = True
                                except Exception:
                                    dev_info["file_path_readable"] = False
                            devs.append(dev_info)
                        pad_info["chain_devices"] = devs
                    pads_info.append(pad_info)
                except Exception as e:
                    pads_info.append({"index": i, "error": str(e)})

        return {
            "track_index": track_index,
            "device_name": str(self._safe_attr(device, "name", "")),
            "device_class": str(self._safe_attr(device, "class_name", "")),
            "drum_pads_available": drum_pads is not None,
            "pad_count": len(drum_pads) if drum_pads is not None else 0,
            "pads": pads_info,
        }
