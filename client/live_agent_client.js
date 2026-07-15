/**
 * LiveAgent Remote Client — JavaScript / Node.js
 * ================================================
 * Connects to LiveAgent running inside Ableton Live.
 *
 * Usage:
 *   const { LiveAgentClient } = require('./live_agent_client');
 *   const client = new LiveAgentClient();
 *   const state = await client.ping();
 *   const tracks = await client.list_tracks();
 *   await client.loadDevice(1, 'Massive');
 *   client.close();
 */

const net = require('net');
const { EventEmitter } = require('events');

class LiveAgentClient {
  constructor(host = '127.0.0.1', port = 8765, timeout = 10000) {
    this.host = host;
    this.port = port;
    this.timeout = timeout;
  }

  _send(command, payload = null) {
    return new Promise((resolve, reject) => {
      const sock = net.createConnection({ host: this.host, port: this.port }, () => {
        const request = payload ? { command, payload } : { command };
        sock.write(JSON.stringify(request) + '\n');
      });

      let buf = '';
      const timer = setTimeout(() => {
        sock.destroy();
        reject(new Error('Connection timed out'));
      }, this.timeout);

      sock.on('data', (data) => {
        buf += data.toString();
        if (buf.includes('\n')) {
          clearTimeout(timer);
          sock.destroy();
          try {
            const resp = JSON.parse(buf.trim());
            if (!resp.ok) {
              reject(new Error(resp.error || 'Unknown error'));
            } else {
              resolve(resp.result);
            }
          } catch (e) {
            reject(e);
          }
        }
      });

      sock.on('error', (err) => {
        clearTimeout(timer);
        reject(err);
      });
    });
  }

  // ── Commands ────────────────────────────────────────────

  ping()                           { return this._send('ping'); }
  getLiveState()                   { return this._send('get_live_state'); }
  listTracks()                     { return this._send('list_tracks'); }
  selectTrack(trackIndex)          { return this._send('select_track', { track_index: trackIndex }); }
  selectScene(sceneIndex)          { return this._send('select_scene', { scene_index: sceneIndex }); }
  selectClip(opts) {
    return this._send('select_clip', {
      track_index: opts.trackIndex,
      slot_index: opts.slotIndex,
    });
  }
  selectDevice(opts) {
    const payload = { track_index: opts.trackIndex };
    if (opts.deviceIndex != null) payload.device_index = opts.deviceIndex;
    if (opts.deviceName) payload.device_name = opts.deviceName;
    return this._send('select_device', payload);
  }
  createMidiTrack(index = -1)      { return this._send('create_midi_track', { index }); }

  // ── Transport & Playback ──────────────────────────────

  getTransportState()              { return this._send('get_transport_state'); }
  startPlaying()                   { return this._send('start_playing'); }
  stopPlaying()                    { return this._send('stop_playing'); }
  stopAllClips()                   { return this._send('stop_all_clips'); }
  stopClip(opts) {
    return this._send('stop_clip', {
      track_index: opts.trackIndex,
      slot_index: opts.slotIndex,
    });
  }
  stopTrackClips(trackIndex)       { return this._send('stop_track_clips', { track_index: trackIndex }); }
  setTempo(tempo)                  { return this._send('set_tempo', { tempo }); }
  tapTempo()                       { return this._send('tap_tempo'); }

  setTimeSignature(opts) {
    const payload = {};
    if (opts.numerator != null) payload.numerator = opts.numerator;
    if (opts.denominator != null) payload.denominator = opts.denominator;
    return this._send('set_time_signature', payload);
  }

  setMetronome(enabled)            { return this._send('set_metronome', { enabled }); }
  setOverdub(enabled)              { return this._send('set_overdub', { enabled }); }
  launchScene(sceneIndex)          { return this._send('launch_scene', { scene_index: sceneIndex }); }

  launchClip(opts) {
    return this._send('launch_clip', {
      track_index: opts.trackIndex,
      slot_index: opts.slotIndex,
    });
  }

  // ── Mixer ──────────────────────────────────────────────

  setTrackVolume(opts) {
    return this._send('set_track_volume', {
      track_index: opts.trackIndex,
      volume: opts.volume,
    });
  }

  setTrackPan(opts) {
    return this._send('set_track_pan', {
      track_index: opts.trackIndex,
      pan: opts.pan,
    });
  }

  setTrackMute(opts) {
    return this._send('set_track_mute', {
      track_index: opts.trackIndex,
      mute: opts.mute,
    });
  }

  setTrackSolo(opts) {
    return this._send('set_track_solo', {
      track_index: opts.trackIndex,
      solo: opts.solo,
    });
  }

  setTrackArm(opts) {
    return this._send('set_track_arm', {
      track_index: opts.trackIndex,
      arm: opts.arm,
    });
  }

  setTrackSend(opts) {
    return this._send('set_track_send', {
      track_index: opts.trackIndex,
      send_index: opts.sendIndex,
      value: opts.value,
    });
  }

  setTrackMonitoring(opts) {
    return this._send('set_track_monitoring', {
      track_index: opts.trackIndex,
      monitoring: opts.monitoring,
    });
  }

  setCrossfader(position) {
    return this._send('set_crossfader', { position });
  }

  // ── Track & Scene Organization ─────────────────────────────

  setTrackName(trackIndex, name) {
    return this._send('set_track_name', { track_index: trackIndex, name });
  }

  setTrackColor(trackIndex, color) {
    return this._send('set_track_color', { track_index: trackIndex, color });
  }

  duplicateTrack(trackIndex) {
    return this._send('duplicate_track', { track_index: trackIndex });
  }

  deleteTrack(trackIndex) {
    return this._send('delete_track', { track_index: trackIndex });
  }

  createScene(opts = {}) {
    const payload = { index: opts.index ?? -1 };
    if (opts.name) payload.name = opts.name;
    if (opts.color != null) payload.color = opts.color;
    return this._send('create_scene', payload);
  }

  setSceneName(sceneIndex, name) {
    return this._send('set_scene_name', { scene_index: sceneIndex, name });
  }

  setSceneColor(sceneIndex, color) {
    return this._send('set_scene_color', { scene_index: sceneIndex, color });
  }

  duplicateScene(sceneIndex) {
    return this._send('duplicate_scene', { scene_index: sceneIndex });
  }

  deleteScene(sceneIndex) {
    return this._send('delete_scene', { scene_index: sceneIndex });
  }

  createSessionClip(opts) {
    return this._send('create_session_clip', {
      track_index: opts.trackIndex,
      slot_index: opts.slotIndex,
      length_beats: opts.lengthBeats || 16,
      name: opts.name || '',
      replace: opts.replace !== false,
    });
  }

  writeMidiNotes(opts) {
    return this._send('write_midi_notes', {
      track_index: opts.trackIndex,
      slot_index: opts.slotIndex,
      notes: opts.notes,
    });
  }

  readClipNotes(opts) {
    return this._send('read_clip_notes', {
      track_index: opts.trackIndex,
      slot_index: opts.slotIndex,
      length_beats: opts.lengthBeats || 16,
    });
  }

  clearClipNotes(opts) {
    return this._send('clear_clip_notes', {
      track_index: opts.trackIndex,
      slot_index: opts.slotIndex,
    });
  }

  listDevices(trackIndex) {
    return this._send('list_devices', { track_index: trackIndex });
  }

  setParameterValue(opts) {
    const payload = { track_index: opts.trackIndex, value: opts.value };
    if (opts.deviceIndex != null) payload.device_index = opts.deviceIndex;
    if (opts.deviceName) payload.device_name = opts.deviceName;
    if (opts.parameterIndex != null) payload.parameter_index = opts.parameterIndex;
    if (opts.parameterName) payload.parameter_name = opts.parameterName;
    return this._send('set_parameter_value', payload);
  }

  writeClipAutomation(opts) {
    const payload = {
      track_index: opts.trackIndex,
      slot_index: opts.slotIndex,
      points: opts.points,
      step_duration: opts.stepDuration || 0.25,
    };
    if (opts.deviceIndex != null) payload.device_index = opts.deviceIndex;
    if (opts.deviceName) payload.device_name = opts.deviceName;
    if (opts.parameterIndex != null) payload.parameter_index = opts.parameterIndex;
    if (opts.parameterName) payload.parameter_name = opts.parameterName;
    return this._send('write_clip_automation', payload);
  }

  loadDevice(trackIndex, deviceName, browserType = 'plug-in') {
    return this._send('load_device', {
      track_index: trackIndex,
      device_name: deviceName,
      browser_type: browserType,
    });
  }

  listBrowserDevices(browserType = 'plug-in', query = '', maxResults = 100) {
    return this._send('list_browser_devices', {
      browser_type: browserType,
      query,
      max_results: maxResults,
    });
  }

  // ── Audio Clips ────────────────────────────────────────────

  createAudioTrack(index = -1) {
    return this._send('create_audio_track', { index });
  }

  importAudioClip(opts) {
    return this._send('import_audio_clip', {
      track_index: opts.trackIndex,
      slot_index: opts.slotIndex,
      file_path: opts.filePath,
    });
  }

  getClipInfo(opts) {
    return this._send('get_clip_info', {
      track_index: opts.trackIndex,
      slot_index: opts.slotIndex,
    });
  }

  setClipProperties(opts) {
    const { trackIndex, slotIndex, ...rest } = opts;
    return this._send('set_clip_properties', {
      track_index: trackIndex,
      slot_index: slotIndex,
      ...rest,
    });
  }

  duplicateClip(opts) {
    const payload = {
      track_index: opts.trackIndex,
      slot_index: opts.slotIndex,
    };
    if (opts.destTrackIndex != null) payload.dest_track_index = opts.destTrackIndex;
    if (opts.destSlotIndex != null) payload.dest_slot_index = opts.destSlotIndex;
    return this._send('duplicate_clip', payload);
  }

  deleteClip(opts) {
    return this._send('delete_clip', {
      track_index: opts.trackIndex,
      slot_index: opts.slotIndex,
    });
  }

  setClipWarp(opts) {
    const payload = {
      track_index: opts.trackIndex,
      slot_index: opts.slotIndex,
    };
    if (opts.warping != null) payload.warping = opts.warping;
    if (opts.warpMode != null) payload.warp_mode = opts.warpMode;
    return this._send('set_clip_warp', payload);
  }

  analyzeAndWarp(opts) {
    const payload = {
      track_index: opts.trackIndex,
      slot_index: opts.slotIndex,
      warp_mode: opts.warpMode ?? 4,
    };
    if (opts.bpm != null) payload.bpm = opts.bpm;
    if (opts.key) payload.key = opts.key;
    return this._send('analyze_and_warp', payload);
  }

  // ── Drum Rack ──────────────────────────────────────────────

  createDrumRack(opts = {}) {
    return this._send('create_drum_rack', {
      track_index: opts.trackIndex ?? -1,
      name: opts.name || 'Drum Rack',
      kit_name: opts.kitName || '808 Core Kit.adg',
      empty: opts.empty === true,
    });
  }

  loadSampleToPad(opts) {
    const payload = {
      track_index: opts.trackIndex,
      pad_index: opts.padIndex,
      file_path: opts.filePath,
      drum_rack_index: opts.drumRackIndex ?? 0,
      reset_effects: opts.resetEffects === true,
    };
    if (opts.padName !== undefined) payload.pad_name = opts.padName;
    return this._send('load_sample_to_pad', payload);
  }

  setDrumPadName(opts) {
    return this._send('set_drum_pad_name', {
      track_index: opts.trackIndex,
      pad_index: opts.padIndex,
      pad_name: opts.padName,
      drum_rack_index: opts.drumRackIndex ?? 0,
    });
  }

  inspectDrumRack(opts) {
    const payload = {
      track_index: opts.trackIndex,
      drum_rack_index: opts.drumRackIndex ?? 0,
    };
    if (opts.padRange) payload.pad_range = opts.padRange;
    return this._send('inspect_drum_rack', payload);
  }
}

/**
 * LiveAgentSubscriber — receive pushed events from LiveAgent.
 *
 * LiveAgent snapshots transport/mixer/clip state and emits change events.
 * This class opens a persistent connection on the subscribe port and emits
 * Node events for each change.
 *
 * Event categories (pass any subset to `events`):
 *   - 'transport'  → 'transport_changed'
 *   - 'mixer'      → 'mixer_changed'
 *   - 'scenes'     → 'clip_launched', 'clip_stopped'
 *
 * Usage:
 *   const { LiveAgentSubscriber } = require('./live_agent_client');
 *   const sub = new LiveAgentSubscriber();
 *   sub.on('transport_changed', (data) => console.log('tempo:', data));
 *   sub.on('*', (name, data) => console.log(name, data));  // catch-all
 *   // ... events fire as state changes in Live ...
 *   sub.close();
 */
class LiveAgentSubscriber extends EventEmitter {
  static DEFAULT_PORT = 8766;

  constructor(host = '127.0.0.1', port = LiveAgentSubscriber.DEFAULT_PORT, events = null) {
    super();
    if (events === null) events = ['transport', 'mixer', 'scenes'];
    this.host = host;
    this.port = port;
    this.events = events;
    this._sock = null;
    this._buffer = '';

    this._sock = net.createConnection({ host, port }, () => {
      const request = JSON.stringify({ command: 'subscribe', payload: { events } }) + '\n';
      this._sock.write(request);
    });

    this._sock.on('data', (data) => {
      this._buffer += data.toString();
      // Dispatch each complete newline-delimited message.
      let idx;
      while ((idx = this._buffer.indexOf('\n')) !== -1) {
        const line = this._buffer.slice(0, idx).trim();
        this._buffer = this._buffer.slice(idx + 1);
        if (!line) continue;
        this._dispatch(line);
      }
    });

    this._sock.on('error', (err) => {
      this.emit('error', err);
    });

    this._sock.on('close', () => {
      this.emit('close');
    });
  }

  _dispatch(raw) {
    let msg;
    try {
      msg = JSON.parse(raw);
    } catch (e) {
      return;
    }
    // Messages from the server are { events: [ {...}, ... ] }.
    const events = msg && msg.events;
    if (!events) return;
    for (const evt of events) {
      const name = evt.event;
      const data = evt.data || {};
      // Emit the specific event name.
      this.emit(name, data);
      // Emit a catch-all so consumers can listen to '*'.
      this.emit('*', name, data);
    }
  }

  close() {
    if (this._sock) {
      this._sock.destroy();
      this._sock = null;
    }
  }
}

module.exports = { LiveAgentClient, LiveAgentSubscriber };
