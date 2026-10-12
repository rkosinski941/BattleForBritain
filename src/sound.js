// Procedural campaign audio. The title theme is Lyric Loop's D Dorian
// march, synthesized here — no audio files. Eight bars at 72 BPM is about
// 27 seconds; it fades and does not loop.

const KEY = "bfb-sound";
const BEAT = 60 / 72;
const BAR = BEAT * 4;

const NOTE = {
  D2: 73.416,
  A2: 110,
  A3: 220,
  C4: 261.626,
  D4: 293.665,
  E4: 329.628,
  F4: 349.228,
  G4: 392,
  A4: 440,
  D5: 587.33,
  A5: 880,
};

const db = (n) => Math.pow(10, n / 20);

let ctx = null;
let bus = null;
let themeNodes = [];
let galeNodes = [];
let themeState = "idle";
let galeWanted = false;
let breakBusyUntil = 0;
let noiseCache = new Map();

function prefs() {
  let raw = {};
  try {
    raw = JSON.parse(localStorage.getItem(KEY) || "{}");
  } catch {
    raw = {};
  }
  return {
    muted: !!raw.muted,
    volume: Number.isFinite(raw.volume) ? Math.min(1, Math.max(0, raw.volume)) : 0.75,
  };
}

function savePrefs(p) {
  localStorage.setItem(KEY, JSON.stringify({ muted: !!p.muted, volume: p.volume }));
}

function applyMaster() {
  if (!bus) return;
  const p = prefs();
  bus.master.gain.value = p.muted ? 0 : p.volume;
}

export function muted() {
  return prefs().muted;
}

export function volume() {
  return prefs().volume;
}

export function setMuted(on) {
  const p = prefs();
  p.muted = !!on;
  savePrefs(p);
  applyMaster();
  refreshGale();
}

export function setVolume(v) {
  const p = prefs();
  p.volume = Math.min(1, Math.max(0, v));
  if (p.volume > 0) p.muted = false;
  savePrefs(p);
  applyMaster();
  refreshGale();
}

export function toggleMuted() {
  setMuted(!muted());
  return muted();
}

function makeIR(audio, seconds) {
  const n = Math.floor(audio.sampleRate * seconds);
  const buf = audio.createBuffer(2, n, audio.sampleRate);
  for (let c = 0; c < 2; c++) {
    const data = buf.getChannelData(c);
    for (let i = 0; i < n; i++) {
      const t = i / n;
      data[i] = (Math.random() * 2 - 1) * Math.pow(1 - t, 2.5);
    }
  }
  return buf;
}

function noiseBuffer(audio, seconds) {
  const key = audio.sampleRate + ":" + seconds;
  if (noiseCache.has(key)) return noiseCache.get(key);
  const n = Math.max(1, Math.floor(audio.sampleRate * seconds));
  const buf = audio.createBuffer(1, n, audio.sampleRate);
  const data = buf.getChannelData(0);
  for (let i = 0; i < n; i++) data[i] = Math.random() * 2 - 1;
  noiseCache.set(key, buf);
  return buf;
}

function createBus(audio) {
  const compressor = audio.createDynamicsCompressor();
  compressor.threshold.value = -18;
  compressor.knee.value = 8;
  compressor.ratio.value = 3;
  compressor.attack.value = 0.01;
  compressor.release.value = 0.22;
  const master = audio.createGain();
  master.gain.value = 1;
  compressor.connect(master);
  master.connect(audio.destination);
  const verb = audio.createConvolver();
  verb.buffer = makeIR(audio, 2.5);
  verb.connect(compressor);
  return { audio, compressor, master, verb };
}

function ensure() {
  if (ctx) return bus;
  const AudioCtx = window.AudioContext || window.webkitAudioContext;
  if (!AudioCtx) return null;
  ctx = new AudioCtx();
  bus = createBus(ctx);
  applyMaster();
  return bus;
}

export function armAudio() {
  const live = ensure();
  if (live && ctx.state === "suspended") ctx.resume();
  refreshGale();
  return live;
}

function track(list, node) {
  list.push(node);
  return node;
}

function stopList(list, when) {
  for (const node of list) {
    try {
      node.stop(when);
    } catch {
      /* already stopped */
    }
  }
  list.length = 0;
}

function envGain(audio, t, attack, hold, release, level) {
  const g = audio.createGain();
  g.gain.setValueAtTime(0.0001, t);
  g.gain.exponentialRampToValueAtTime(Math.max(level, 0.0001), t + attack);
  g.gain.setValueAtTime(Math.max(level, 0.0001), t + attack + hold);
  g.gain.exponentialRampToValueAtTime(0.0001, t + attack + hold + release);
  return g;
}

function horn(live, t, freq, dur, opts = {}) {
  const { audio, compressor, verb } = live;
  const level = db(opts.gainDb ?? -10);
  const amp = envGain(audio, t, 0.06, Math.max(0.02, dur - 0.06), 0.16, level);
  const filter = audio.createBiquadFilter();
  filter.type = "lowpass";
  filter.Q.value = 0.8;
  filter.frequency.setValueAtTime(900, t);
  filter.frequency.linearRampToValueAtTime(2200, t + 0.08);
  filter.frequency.linearRampToValueAtTime(1400, t + 0.22);
  const mix = audio.createGain();
  mix.gain.value = 0.45;
  const saw = audio.createOscillator();
  saw.type = "sawtooth";
  saw.frequency.value = freq;
  const square = audio.createOscillator();
  square.type = "square";
  square.frequency.value = freq;
  const vib = audio.createOscillator();
  vib.frequency.value = 4.5;
  const vibAmt = audio.createGain();
  vibAmt.gain.setValueAtTime(0, t);
  vibAmt.gain.setValueAtTime(0, t + 0.3);
  vibAmt.gain.linearRampToValueAtTime(12, t + 0.42);
  vib.connect(vibAmt);
  vibAmt.connect(saw.detune);
  vibAmt.connect(square.detune);
  saw.connect(mix);
  square.connect(mix);
  mix.connect(filter);
  filter.connect(amp);
  amp.connect(compressor);
  const send = audio.createGain();
  send.gain.value = opts.wet ?? 0.3;
  amp.connect(send);
  send.connect(verb);
  if (opts.echo) {
    const into = audio.createGain();
    into.gain.value = 1;
    amp.connect(into);
    into.connect(opts.echo);
  }
  const stop = t + dur + 0.4;
  for (const node of [saw, square, vib]) {
    node.start(t);
    node.stop(stop);
    if (opts.keep) opts.keep.push(node);
  }
}

function lead(live, t, freq, dur, opts = {}) {
  const { audio, compressor, verb } = live;
  const level = db(opts.gainDb ?? -12);
  const amp = envGain(audio, t, 0.03, Math.max(0.02, dur - 0.03), 0.12, level);
  const tri = audio.createOscillator();
  tri.type = "triangle";
  tri.frequency.value = freq;
  const saw = audio.createOscillator();
  saw.type = "sawtooth";
  saw.frequency.value = freq * 2;
  const sawGain = audio.createGain();
  sawGain.gain.value = db(-18);
  const vib = audio.createOscillator();
  vib.frequency.value = 5;
  const vibAmt = audio.createGain();
  vibAmt.gain.value = 6;
  vib.connect(vibAmt);
  vibAmt.connect(tri.detune);
  vibAmt.connect(saw.detune);
  tri.connect(amp);
  saw.connect(sawGain);
  sawGain.connect(amp);
  amp.connect(compressor);
  const send = audio.createGain();
  send.gain.value = opts.wet ?? 0.3;
  amp.connect(send);
  send.connect(verb);
  const stop = t + dur + 0.3;
  for (const node of [tri, saw, vib]) {
    node.start(t);
    node.stop(stop);
    if (opts.keep) opts.keep.push(node);
  }
}

function drum(live, t, heavy, gainDb = -14) {
  const { audio, compressor } = live;
  const level = db(gainDb);
  const osc = audio.createOscillator();
  osc.type = "sine";
  osc.frequency.setValueAtTime(80, t);
  osc.frequency.exponentialRampToValueAtTime(50, t + 0.12);
  const amp = audio.createGain();
  amp.gain.setValueAtTime(level, t);
  amp.gain.exponentialRampToValueAtTime(0.0001, t + 0.28);
  osc.connect(amp);
  amp.connect(compressor);
  osc.start(t);
  osc.stop(t + 0.32);
  const src = audio.createBufferSource();
  src.buffer = noiseBuffer(audio, 0.04);
  const bp = audio.createBiquadFilter();
  bp.type = "bandpass";
  bp.frequency.value = 180;
  bp.Q.value = 0.9;
  const ng = audio.createGain();
  ng.gain.setValueAtTime(level, t);
  ng.gain.exponentialRampToValueAtTime(0.0001, t + 0.04);
  src.connect(bp);
  bp.connect(ng);
  ng.connect(compressor);
  src.start(t);
  src.stop(t + 0.05);
  const extra = [osc, src];
  if (heavy) {
    const sub = audio.createOscillator();
    sub.type = "sine";
    sub.frequency.setValueAtTime(40, t);
    sub.frequency.exponentialRampToValueAtTime(25, t + 0.14);
    const sg = audio.createGain();
    sg.gain.setValueAtTime(level, t);
    sg.gain.exponentialRampToValueAtTime(0.0001, t + 0.34);
    sub.connect(sg);
    sg.connect(compressor);
    sub.start(t);
    sub.stop(t + 0.36);
    extra.push(sub);
  }
  return extra;
}

function drone(live, t0, tBoost, tFade, tEnd, opts = {}) {
  const { audio, compressor, verb } = live;
  const base = db(opts.gainDb ?? -20);
  const amp = audio.createGain();
  const fadeIn = opts.fadeIn ?? 2;
  amp.gain.setValueAtTime(0.0001, t0);
  amp.gain.exponentialRampToValueAtTime(base, t0 + fadeIn);
  let level = base;
  if (tBoost > t0 + fadeIn + 0.05) {
    amp.gain.setValueAtTime(base, tBoost);
    level = base * db(3);
    amp.gain.linearRampToValueAtTime(level, tBoost + 0.08);
  }
  const fadeAt = Math.max(tFade, t0 + fadeIn + 0.02);
  amp.gain.setValueAtTime(level, fadeAt);
  amp.gain.exponentialRampToValueAtTime(0.0001, Math.max(tEnd, fadeAt + 0.05));
  const filter = audio.createBiquadFilter();
  filter.type = "lowpass";
  filter.frequency.value = 600;
  const lfo = audio.createOscillator();
  lfo.frequency.value = 0.2;
  const lfoAmt = audio.createGain();
  lfoAmt.gain.value = 150;
  lfo.connect(lfoAmt);
  lfoAmt.connect(filter.frequency);
  const mix = audio.createGain();
  mix.gain.value = 0.35;
  const voices = [
    [NOTE.D2, -3],
    [NOTE.D2, 3],
    [NOTE.A2, -3],
    [NOTE.A2, 3],
  ].map(([freq, cents]) => {
    const osc = audio.createOscillator();
    osc.type = "sawtooth";
    osc.frequency.value = freq;
    osc.detune.value = cents;
    osc.connect(mix);
    osc.start(t0);
    osc.stop(tEnd + 0.05);
    return osc;
  });
  mix.connect(filter);
  filter.connect(amp);
  amp.connect(compressor);
  const send = audio.createGain();
  send.gain.value = opts.wet ?? 0.15;
  amp.connect(send);
  send.connect(verb);
  lfo.start(t0);
  lfo.stop(tEnd + 0.05);
  return [...voices, lfo];
}

function echoBus(live, t0, openAt) {
  const { audio, compressor } = live;
  const delay = audio.createDelay(1.5);
  delay.delayTime.value = 0.6;
  const fb = audio.createGain();
  fb.gain.value = 0.35;
  delay.connect(fb);
  fb.connect(delay);
  const out = audio.createGain();
  out.gain.setValueAtTime(0.0001, t0);
  out.gain.setValueAtTime(0.0001, openAt);
  out.gain.exponentialRampToValueAtTime(db(-12), openAt + 0.04);
  delay.connect(out);
  out.connect(compressor);
  return delay;
}

function at(bar, beat = 1) {
  return ((bar - 1) * 4 + (beat - 1)) * BEAT;
}

export function scheduleTitleTheme(live, t0, keep) {
  const echo = echoBus(live, t0, t0 + at(2, 3));
  const opts = { keep, echo };
  horn(live, t0 + at(1, 1), NOTE.A3, BEAT, opts);
  horn(live, t0 + at(1, 2), NOTE.D4, BEAT * 2, opts);
  horn(live, t0 + at(2, 1), NOTE.D4, BEAT * 0.5, opts);
  horn(live, t0 + at(2, 1.5), NOTE.A3, BEAT * 0.5, opts);
  horn(live, t0 + at(2, 2), NOTE.D4, BEAT, opts);
  horn(live, t0 + at(2, 3), NOTE.A4, BEAT * 2, opts);

  const leadLine = [
    [3, 1, NOTE.D4, 1],
    [3, 2, NOTE.E4, 1],
    [3, 3, NOTE.F4, 1],
    [3, 4, NOTE.G4, 1],
    [4, 1, NOTE.A4, 2],
    [4, 3, NOTE.G4, 1],
    [4, 4, NOTE.F4, 1],
    [5, 1, NOTE.E4, 1],
    [5, 2, NOTE.C4, 1],
    [5, 3, NOTE.D4, 2],
    [6, 1, NOTE.F4, 1],
    [6, 2, NOTE.E4, 1],
    [6, 3, NOTE.C4, 1],
    [6, 4, NOTE.A3, 1],
  ];
  for (const [bar, beat, freq, beats] of leadLine) {
    lead(live, t0 + at(bar, beat), freq, beats * BEAT, { keep });
  }
  horn(live, t0 + at(7, 1), NOTE.A3, BEAT, { keep });
  lead(live, t0 + at(7, 1), NOTE.A4, BEAT, { keep });
  horn(live, t0 + at(7, 2), NOTE.D4, BEAT, { keep });
  lead(live, t0 + at(7, 2), NOTE.D5, BEAT, { keep });
  horn(live, t0 + at(7, 3), NOTE.A4, BEAT * 2, { keep });
  lead(live, t0 + at(7, 3), NOTE.A5, BEAT * 2, { keep });
  horn(live, t0 + at(8, 1), NOTE.D4, BAR, { keep });
  lead(live, t0 + at(8, 1), NOTE.D4, BAR, { keep });

  for (let bar = 3; bar <= 8; bar++) {
    drum(live, t0 + at(bar, 1), bar === 7, -14).forEach((n) => keep && keep.push(n));
    drum(live, t0 + at(bar, 3), false, -14).forEach((n) => keep && keep.push(n));
  }

  const end = t0 + BAR * 8;
  drone(live, t0, t0 + at(8, 1), end, end + 3, { fadeIn: 2 }).forEach((n) => keep && keep.push(n));
  return end + 3;
}

export function startTitleTheme() {
  if (themeState !== "idle" || muted()) return;
  const live = armAudio();
  if (!live) return;
  themeState = "playing";
  const t0 = live.audio.currentTime + 0.05;
  const end = scheduleTitleTheme(live, t0, themeNodes);
  const ms = Math.max(0, (end - live.audio.currentTime) * 1000 + 200);
  window.setTimeout(() => {
    if (themeState === "playing") themeState = "done";
  }, ms);
}

export function stopTitleTheme() {
  if (!ctx || themeState === "idle") {
    themeState = themeState === "playing" ? "done" : themeState;
    return;
  }
  stopList(themeNodes, ctx.currentTime + 0.03);
  themeState = "done";
}

export function allowTitleTheme() {
  if (themeState !== "playing") themeState = "idle";
}

function cue(play) {
  const live = ensure();
  if (!live || muted() || (ctx && ctx.state === "suspended")) return;
  play(live, live.audio.currentTime + 0.02);
}

export function playTurnSting() {
  cue((live, t) => {
    horn(live, t, NOTE.A3, BEAT);
    horn(live, t + BEAT, NOTE.D4, BEAT * 2);
  });
}

export function playBreakCue() {
  const live = ensure();
  if (!live || muted() || ctx.state === "suspended") return;
  const t = live.audio.currentTime + 0.02;
  if (t < breakBusyUntil) return;
  breakBusyUntil = t + BEAT * 4;
  const line = [NOTE.F4, NOTE.E4, NOTE.C4, NOTE.A3];
  line.forEach((freq, i) => lead(live, t + i * BEAT, freq, BEAT));
  drone(live, t, t, t + BEAT * 3.2, t + BEAT * 4.4, { fadeIn: 0.35, gainDb: -20, wet: 0.15 });
}

export function playMarchTick() {
  cue((live, t) => drum(live, t, false, -22));
}

export function playCombat(strength) {
  const scale = Math.max(0.35, Math.min(1, (strength || 40) / 220));
  cue((live, t) => {
    const { audio, compressor } = live;
    const hit = audio.createBufferSource();
    hit.buffer = noiseBuffer(audio, 0.12);
    const bp = audio.createBiquadFilter();
    bp.type = "bandpass";
    bp.frequency.value = 1400 + 800 * scale;
    bp.Q.value = 0.7;
    const hg = audio.createGain();
    hg.gain.setValueAtTime(db(-8) * scale, t);
    hg.gain.exponentialRampToValueAtTime(0.0001, t + 0.09 + 0.05 * scale);
    hit.connect(bp);
    bp.connect(hg);
    hg.connect(compressor);
    hit.start(t);
    hit.stop(t + 0.14);
    const ring = audio.createOscillator();
    ring.type = "square";
    ring.frequency.setValueAtTime(180 + 40 * scale, t);
    ring.frequency.exponentialRampToValueAtTime(90, t + 0.12);
    const rg = audio.createGain();
    rg.gain.setValueAtTime(db(-14) * scale, t);
    rg.gain.exponentialRampToValueAtTime(0.0001, t + 0.16);
    ring.connect(rg);
    rg.connect(compressor);
    ring.start(t);
    ring.stop(t + 0.18);
    const shouts = scale > 0.72 ? 2 : 1;
    for (let i = 0; i < shouts; i++) {
      const src = audio.createBufferSource();
      src.buffer = noiseBuffer(audio, 0.22);
      const form = audio.createBiquadFilter();
      form.type = "bandpass";
      form.frequency.value = 520 + i * 280;
      form.Q.value = 2.2;
      const sg = audio.createGain();
      const st = t + 0.03 + i * 0.05;
      sg.gain.setValueAtTime(0.0001, st);
      sg.gain.exponentialRampToValueAtTime(db(-10) * scale, st + 0.03);
      sg.gain.exponentialRampToValueAtTime(0.0001, st + 0.2);
      src.connect(form);
      form.connect(sg);
      sg.connect(compressor);
      src.start(st);
      src.stop(st + 0.22);
    }
  });
}

export function playTownFanfare() {
  cue((live, t) => {
    horn(live, t, NOTE.A3, BEAT * 0.9);
    horn(live, t + BEAT, NOTE.D4, BEAT * 0.9);
    horn(live, t + BEAT * 2, NOTE.A4, BEAT * 1.3);
  });
}

function refreshGale() {
  if (!galeWanted || muted() || !ctx) {
    if (galeNodes.length && ctx) stopList(galeNodes, ctx.currentTime + 0.5);
    return;
  }
  if (galeNodes.length) return;
  const live = bus;
  if (!live) return;
  const t = live.audio.currentTime + 0.05;
  const { audio, compressor } = live;
  drone(live, t, t, t + 9999, t + 9999, { fadeIn: 1.2, gainDb: -23, wet: 0.15 }).forEach((n) =>
    galeNodes.push(n),
  );
  const src = audio.createBufferSource();
  src.buffer = noiseBuffer(audio, 2);
  src.loop = true;
  const hp = audio.createBiquadFilter();
  hp.type = "highpass";
  hp.frequency.value = 900;
  const ng = audio.createGain();
  ng.gain.value = db(-16) * 0.45;
  const lfo = audio.createOscillator();
  lfo.frequency.value = 0.1;
  const depth = audio.createGain();
  depth.gain.value = db(-16) * 0.4;
  lfo.connect(depth);
  depth.connect(ng.gain);
  src.connect(hp);
  hp.connect(ng);
  ng.connect(compressor);
  src.start(t);
  lfo.start(t);
  galeNodes.push(src, lfo);
}

export function syncGale(on) {
  galeWanted = !!on;
  if (galeWanted) armAudio();
  refreshGale();
}

export function audioMarkup() {
  const p = prefs();
  return `<div class="sound">
      <button id="mute" type="button" class="ghost">${p.muted ? "Unmute" : "Mute"}</button>
      <input id="volume" type="range" min="0" max="100" value="${Math.round(p.volume * 100)}" aria-label="Volume">
    </div>
    <p class="sound-credit">Title theme by Lyric Loop</p>`;
}

export function bindAudio(root) {
  const mute = root.querySelector("#mute");
  const slider = root.querySelector("#volume");
  if (mute) {
    mute.onclick = () => {
      armAudio();
      toggleMuted();
      mute.textContent = muted() ? "Unmute" : "Mute";
    };
  }
  if (slider) {
    slider.oninput = () => {
      armAudio();
      setVolume(Number(slider.value) / 100);
      if (mute) mute.textContent = muted() ? "Unmute" : "Mute";
    };
  }
}

export function renderOffline(kind) {
  const rate = 44100;
  const seconds = kind === "theme" ? 31 : kind === "gale" ? 4 : 4;
  const offline = new OfflineAudioContext(2, Math.floor(rate * seconds), rate);
  const live = createBus(offline);
  const t0 = 0.05;
  if (kind === "theme") scheduleTitleTheme(live, t0, []);
  else if (kind === "sting") {
    horn(live, t0, NOTE.A3, BEAT);
    horn(live, t0 + BEAT, NOTE.D4, BEAT * 2);
  } else if (kind === "break") {
    [NOTE.F4, NOTE.E4, NOTE.C4, NOTE.A3].forEach((freq, i) => lead(live, t0 + i * BEAT, freq, BEAT));
    drone(live, t0, t0, t0 + BEAT * 3.2, t0 + BEAT * 4.2, { fadeIn: 0.2, gainDb: -20 });
  } else if (kind === "drum") drum(live, t0, false, -14);
  else if (kind === "combat") {
    live.master.gain.value = 1;
    const audio = offline;
    const hit = audio.createBufferSource();
    hit.buffer = noiseBuffer(audio, 0.12);
    const bp = audio.createBiquadFilter();
    bp.type = "bandpass";
    bp.frequency.value = 1800;
    const hg = audio.createGain();
    hg.gain.setValueAtTime(0.4, t0);
    hg.gain.exponentialRampToValueAtTime(0.0001, t0 + 0.12);
    hit.connect(bp);
    bp.connect(hg);
    hg.connect(live.compressor);
    hit.start(t0);
    hit.stop(t0 + 0.14);
  } else if (kind === "gale") {
    drone(live, t0, t0 + 9, t0 + 9, t0 + 3.6, { fadeIn: 0.3, gainDb: -23 });
    const src = offline.createBufferSource();
    src.buffer = noiseBuffer(offline, 2);
    src.loop = true;
    const hp = offline.createBiquadFilter();
    hp.type = "highpass";
    hp.frequency.value = 900;
    const ng = offline.createGain();
    ng.gain.value = db(-16);
    src.connect(hp);
    hp.connect(ng);
    ng.connect(live.compressor);
    src.start(t0);
    src.stop(t0 + 3.5);
  } else if (kind === "fanfare") {
    horn(live, t0, NOTE.A3, BEAT);
    horn(live, t0 + BEAT, NOTE.D4, BEAT);
    horn(live, t0 + BEAT * 2, NOTE.A4, BEAT * 1.2);
  }
  return offline.startRendering();
}
