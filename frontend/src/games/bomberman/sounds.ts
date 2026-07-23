/** Procedural Bomberman sound effects (Web Audio API) — layered, higher fidelity. */

let ctx: AudioContext | null = null
let masterGain: GainNode | null = null
let compressor: DynamicsCompressorNode | null = null

const MASTER_VOLUME = 0.42
const SFX_VOLUME = 0.22
const MUTE_STORAGE_KEY = 'bomberman-sound-muted'

let muted = readMutedPreference()
let lastFuseBeepAt = 0
let lastStepAt = 0

function readMutedPreference(): boolean {
  try {
    return localStorage.getItem(MUTE_STORAGE_KEY) === '1'
  } catch {
    return false
  }
}

function applyMasterVolume() {
  if (!masterGain || !ctx) return
  masterGain.gain.setValueAtTime(muted ? 0 : MASTER_VOLUME, ctx.currentTime)
}

export function isSoundMuted(): boolean {
  return muted
}

export function setSoundMuted(value: boolean): void {
  if (muted === value) return
  muted = value
  try {
    localStorage.setItem(MUTE_STORAGE_KEY, value ? '1' : '0')
  } catch {
    /* ignore */
  }
  getCtx()
  applyMasterVolume()
}

function getCtx(): AudioContext {
  if (!ctx) {
    ctx = new AudioContext()
    masterGain = ctx.createGain()
    compressor = ctx.createDynamicsCompressor()
    compressor.threshold.setValueAtTime(-18, ctx.currentTime)
    compressor.knee.setValueAtTime(12, ctx.currentTime)
    compressor.ratio.setValueAtTime(3.5, ctx.currentTime)
    compressor.attack.setValueAtTime(0.003, ctx.currentTime)
    compressor.release.setValueAtTime(0.18, ctx.currentTime)
    masterGain.connect(compressor)
    compressor.connect(ctx.destination)
    applyMasterVolume()
  }
  return ctx
}

export async function unlockAudio(): Promise<void> {
  const audio = getCtx()
  if (audio.state === 'suspended') await audio.resume()
}

function sfxDest(): AudioNode {
  getCtx()
  return masterGain!
}

function alive(): AudioContext | null {
  if (muted) return null
  const audio = getCtx()
  if (audio.state !== 'running') return null
  return audio
}

function schedule(
  delayMs: number,
  fn: () => void,
): void {
  if (muted) return
  window.setTimeout(fn, delayMs)
}

type ToneOpts = {
  type?: OscillatorType
  volume?: number
  attack?: number
  decay?: number
  slideTo?: number
  detune?: number
  delay?: number
  filterFreq?: number
  filterType?: BiquadFilterType
  filterQ?: number
}

function tone(freq: number, duration: number, options: ToneOpts = {}) {
  const audio = alive()
  if (!audio) return

  const {
    type = 'square',
    volume = SFX_VOLUME,
    attack = 0.005,
    decay = duration,
    slideTo,
    detune = 0,
    delay = 0,
    filterFreq,
    filterType = 'lowpass',
    filterQ = 0.7,
  } = options

  const osc = audio.createOscillator()
  const gain = audio.createGain()
  osc.type = type
  osc.detune.setValueAtTime(detune, audio.currentTime)

  const t = audio.currentTime + delay
  osc.frequency.setValueAtTime(Math.max(20, freq), t)
  if (slideTo != null) {
    osc.frequency.exponentialRampToValueAtTime(Math.max(20, slideTo), t + Math.max(0.01, decay * 0.95))
  }

  gain.gain.setValueAtTime(0.0001, t)
  gain.gain.linearRampToValueAtTime(volume, t + attack)
  gain.gain.exponentialRampToValueAtTime(0.0001, t + decay)

  if (filterFreq != null) {
    const filter = audio.createBiquadFilter()
    filter.type = filterType
    filter.frequency.setValueAtTime(filterFreq, t)
    filter.Q.setValueAtTime(filterQ, t)
    osc.connect(filter)
    filter.connect(gain)
  } else {
    osc.connect(gain)
  }

  gain.connect(sfxDest())
  osc.start(t)
  osc.stop(t + decay + 0.03)
}

type NoiseOpts = {
  volume?: number
  filterFreq?: number
  filterType?: BiquadFilterType
  filterQ?: number
  delay?: number
  decayShape?: 'exp' | 'linear'
}

function noiseBurst(duration: number, options: NoiseOpts = {}) {
  const audio = alive()
  if (!audio) return

  const {
    volume = 0.1,
    filterFreq = 900,
    filterType = 'bandpass',
    filterQ = 0.85,
    delay = 0,
    decayShape = 'exp',
  } = options

  const bufferSize = Math.max(1, Math.floor(audio.sampleRate * duration))
  const buffer = audio.createBuffer(1, bufferSize, audio.sampleRate)
  const data = buffer.getChannelData(0)
  let last = 0
  for (let i = 0; i < bufferSize; i++) {
    // Soft pink-ish noise (leaky integrator) for less harsh grit.
    const white = Math.random() * 2 - 1
    last = (last + 0.02 * white) / 1.02
    const env = 1 - i / bufferSize
    data[i] = (white * 0.35 + last * 0.65) * env
  }

  const source = audio.createBufferSource()
  source.buffer = buffer

  const filter = audio.createBiquadFilter()
  filter.type = filterType
  filter.frequency.value = filterFreq
  filter.Q.value = filterQ

  const gain = audio.createGain()
  const t = audio.currentTime + delay
  gain.gain.setValueAtTime(volume, t)
  if (decayShape === 'linear') {
    gain.gain.linearRampToValueAtTime(0.0001, t + duration)
  } else {
    gain.gain.exponentialRampToValueAtTime(0.0001, t + duration)
  }

  source.connect(filter)
  filter.connect(gain)
  gain.connect(sfxDest())
  source.start(t)
}

function rumble(duration: number, volume = 0.12) {
  tone(48, duration, {
    type: 'sine',
    volume: volume * 0.9,
    attack: 0.01,
    decay: duration,
    slideTo: 28,
    filterFreq: 120,
  })
  tone(72, duration * 0.85, {
    type: 'triangle',
    volume: volume * 0.45,
    attack: 0.008,
    decay: duration * 0.85,
    slideTo: 36,
  })
}

/** Plant a bomb — heavy drop + short fuse spark. */
export function playBombPlace(): void {
  rumble(0.12, 0.1)
  tone(95, 0.12, { type: 'sine', volume: 0.14, slideTo: 52, attack: 0.003 })
  tone(180, 0.07, { type: 'triangle', volume: 0.07, slideTo: 90, delay: 0.02 })
  noiseBurst(0.07, { volume: 0.07, filterFreq: 320, filterType: 'lowpass', filterQ: 0.6 })
  schedule(45, () => {
    tone(640, 0.035, { type: 'square', volume: 0.05, filterFreq: 1800 })
    tone(980, 0.025, { type: 'sine', volume: 0.035 })
  })
}

/** Power Glove throw — whoosh + spinning body. */
export function playBombThrow(): void {
  noiseBurst(0.16, {
    volume: 0.1,
    filterFreq: 1400,
    filterType: 'bandpass',
    filterQ: 1.2,
  })
  noiseBurst(0.12, {
    volume: 0.06,
    filterFreq: 2400,
    filterType: 'highpass',
    filterQ: 0.7,
    delay: 0.02,
  })
  tone(220, 0.18, { type: 'sawtooth', volume: 0.08, slideTo: 520, filterFreq: 900 })
  tone(440, 0.14, { type: 'triangle', volume: 0.07, slideTo: 880, delay: 0.03 })
  schedule(40, () => tone(160, 0.08, { type: 'sine', volume: 0.06, slideTo: 90 }))
}

/** Classic kick — impact then rolling bounce. */
export function playBombKick(): void {
  noiseBurst(0.06, { volume: 0.11, filterFreq: 180, filterType: 'lowpass', filterQ: 0.5 })
  tone(110, 0.09, { type: 'sine', volume: 0.14, slideTo: 70, attack: 0.002 })
  tone(240, 0.05, { type: 'triangle', volume: 0.07, delay: 0.015 })
  schedule(55, () => {
    tone(180, 0.05, { type: 'sine', volume: 0.06, slideTo: 140 })
    noiseBurst(0.05, { volume: 0.04, filterFreq: 600, filterType: 'bandpass' })
  })
  schedule(110, () => tone(150, 0.04, { type: 'sine', volume: 0.04, slideTo: 120 }))
}

/** Soft thud when a kicked/thrown bomb settles. */
export function playBombStop(): void {
  tone(90, 0.07, { type: 'sine', volume: 0.07, slideTo: 55 })
  noiseBurst(0.05, { volume: 0.045, filterFreq: 250, filterType: 'lowpass' })
}

/** Urgent fuse hiss/beep while bombs are about to blow. */
export function playBombFuse(urgent = false): void {
  const now = performance.now()
  if (now - lastFuseBeepAt < (urgent ? 90 : 160)) return
  lastFuseBeepAt = now

  if (urgent) {
    tone(980, 0.035, { type: 'square', volume: 0.055, filterFreq: 2200 })
    noiseBurst(0.04, { volume: 0.035, filterFreq: 3200, filterType: 'highpass', filterQ: 0.5 })
  } else {
    tone(720, 0.028, { type: 'square', volume: 0.035, filterFreq: 1600 })
    noiseBurst(0.03, { volume: 0.02, filterFreq: 1800, filterType: 'bandpass' })
  }
}

/** Big layered blast with rumble and crackle. */
export function playExplosion(intensity = 1): void {
  const i = Math.max(0.55, Math.min(1.35, intensity))
  rumble(0.38 * i, 0.16 * i)
  noiseBurst(0.32 * i, {
    volume: 0.2 * i,
    filterFreq: 220,
    filterType: 'lowpass',
    filterQ: 0.45,
  })
  noiseBurst(0.22 * i, {
    volume: 0.14 * i,
    filterFreq: 650,
    filterType: 'bandpass',
    filterQ: 0.9,
    delay: 0.015,
  })
  noiseBurst(0.14 * i, {
    volume: 0.09 * i,
    filterFreq: 2200,
    filterType: 'highpass',
    filterQ: 0.6,
    delay: 0.03,
  })
  tone(140, 0.26 * i, {
    type: 'sawtooth',
    volume: 0.15 * i,
    slideTo: 36,
    filterFreq: 400,
  })
  tone(70, 0.34 * i, { type: 'sine', volume: 0.14 * i, slideTo: 26 })
  schedule(40, () =>
    noiseBurst(0.1, { volume: 0.06 * i, filterFreq: 900, filterType: 'bandpass' }),
  )
}

/** Soft wall crumble. */
export function playSoftDestroy(): void {
  noiseBurst(0.12, { volume: 0.1, filterFreq: 900, filterType: 'bandpass', filterQ: 1.1 })
  noiseBurst(0.1, {
    volume: 0.06,
    filterFreq: 1600,
    filterType: 'highpass',
    filterQ: 0.6,
    delay: 0.02,
  })
  tone(210, 0.1, { type: 'triangle', volume: 0.08, slideTo: 85 })
  tone(140, 0.08, { type: 'sine', volume: 0.05, slideTo: 70, delay: 0.03 })
}

export type PowerupSoundKind = 'bomb' | 'range' | 'speed' | 'throw' | 'kick'

/** Pickup chime — slight flavor per power-up type. */
export function playPowerup(kind: PowerupSoundKind = 'bomb'): void {
  const flavors: Record<PowerupSoundKind, number[]> = {
    bomb: [392, 523, 659],
    range: [440, 554, 740],
    speed: [523, 659, 880],
    throw: [349, 523, 698],
    kick: [294, 440, 587],
  }
  const notes = flavors[kind] ?? flavors.bomb
  notes.forEach((freq, idx) => {
    schedule(idx * 55, () => {
      tone(freq, 0.09 + idx * 0.02, {
        type: idx === 2 ? 'triangle' : 'sine',
        volume: 0.11 - idx * 0.015,
        filterFreq: 2400,
      })
      if (idx === 2) {
        tone(freq * 2, 0.08, { type: 'sine', volume: 0.04, delay: 0.01 })
      }
    })
  })
  noiseBurst(0.06, {
    volume: 0.03,
    filterFreq: 2800,
    filterType: 'highpass',
    delay: 0.08,
  })
}

/** Cartoonish scream — pitched yell + filtered noise formants. */
function scream(opts: {
  volume?: number
  duration?: number
  startHz?: number
  endHz?: number
  vibrato?: number
} = {}) {
  const audio = alive()
  if (!audio) return

  const {
    volume = 0.14,
    duration = 0.55,
    startHz = 720,
    endHz = 180,
    vibrato = 38,
  } = opts

  const t0 = audio.currentTime

  // Core yell (saw + square for grit)
  for (const [type, volMul, detune] of [
    ['sawtooth', 0.72, 0],
    ['square', 0.38, 7],
    ['triangle', 0.28, -11],
  ] as const) {
    const osc = audio.createOscillator()
    const gain = audio.createGain()
    const filter = audio.createBiquadFilter()
    const lfo = audio.createOscillator()
    const lfoGain = audio.createGain()

    osc.type = type
    osc.frequency.setValueAtTime(startHz, t0)
    osc.frequency.exponentialRampToValueAtTime(Math.max(40, endHz), t0 + duration * 0.92)
    osc.detune.setValueAtTime(detune, t0)

    // Pitch wobble = scream vibrato
    lfo.type = 'sine'
    lfo.frequency.setValueAtTime(vibrato, t0)
    lfo.frequency.linearRampToValueAtTime(vibrato * 0.55, t0 + duration)
    lfoGain.gain.setValueAtTime(startHz * 0.045, t0)
    lfoGain.gain.linearRampToValueAtTime(endHz * 0.03, t0 + duration)
    lfo.connect(lfoGain)
    lfoGain.connect(osc.frequency)

    filter.type = 'bandpass'
    filter.frequency.setValueAtTime(1400, t0)
    filter.frequency.exponentialRampToValueAtTime(700, t0 + duration)
    filter.Q.setValueAtTime(3.2, t0)

    gain.gain.setValueAtTime(0.0001, t0)
    gain.gain.linearRampToValueAtTime(volume * volMul, t0 + 0.02)
    gain.gain.setValueAtTime(volume * volMul * 0.85, t0 + duration * 0.35)
    gain.gain.exponentialRampToValueAtTime(0.0001, t0 + duration)

    osc.connect(filter)
    filter.connect(gain)
    gain.connect(sfxDest())
    osc.start(t0)
    osc.stop(t0 + duration + 0.04)
    lfo.start(t0)
    lfo.stop(t0 + duration + 0.04)
  }

  // Breath / rasp layer
  noiseBurst(duration * 0.85, {
    volume: volume * 0.55,
    filterFreq: 1800,
    filterType: 'bandpass',
    filterQ: 1.4,
  })
  noiseBurst(duration * 0.55, {
    volume: volume * 0.28,
    filterFreq: 3200,
    filterType: 'highpass',
    filterQ: 0.7,
    delay: 0.04,
  })

  // Quick attack yelp before the fall
  tone(startHz * 1.15, 0.07, {
    type: 'sawtooth',
    volume: volume * 0.55,
    slideTo: startHz * 0.95,
    filterFreq: 2200,
    attack: 0.004,
  })
}

/** Local player eliminated — full scream. */
export function playDeath(): void {
  scream({
    volume: 0.16,
    duration: 0.62,
    startHz: 780,
    endHz: 140,
    vibrato: 42,
  })
  schedule(80, () =>
    scream({
      volume: 0.07,
      duration: 0.38,
      startHz: 520,
      endHz: 110,
      vibrato: 28,
    }),
  )
  schedule(200, () => rumble(0.22, 0.07))
}

/** Another bomber goes out — shorter scream. */
export function playEnemyDeath(): void {
  scream({
    volume: 0.11,
    duration: 0.42,
    startHz: 640,
    endHz: 160,
    vibrato: 34,
  })
  schedule(90, () =>
    noiseBurst(0.12, { volume: 0.05, filterFreq: 600, filterType: 'lowpass' }),
  )
}

export function playCountdownTick(): void {
  tone(820, 0.06, { type: 'square', volume: 0.1, filterFreq: 2000 })
  tone(620, 0.05, { type: 'triangle', volume: 0.06, delay: 0.01 })
}

export function playCountdownGo(): void {
  tone(392, 0.07, { type: 'square', volume: 0.11 })
  schedule(55, () => tone(523, 0.08, { type: 'square', volume: 0.12 }))
  schedule(120, () => {
    tone(784, 0.16, { type: 'triangle', volume: 0.14 })
    tone(1175, 0.12, { type: 'sine', volume: 0.06, delay: 0.02 })
  })
}

export function playWin(): void {
  const melody = [392, 523, 659, 784, 988]
  melody.forEach((freq, idx) => {
    schedule(idx * 95, () => {
      tone(freq, 0.12 + idx * 0.02, {
        type: idx >= 3 ? 'triangle' : 'square',
        volume: 0.11 + idx * 0.01,
        filterFreq: 2600,
      })
      tone(freq * 2, 0.08, { type: 'sine', volume: 0.035, delay: 0.01 })
    })
  })
  schedule(480, () => rumble(0.2, 0.05))
}

export function playLose(): void {
  tone(349, 0.14, { type: 'sawtooth', volume: 0.11, slideTo: 260, filterFreq: 800 })
  schedule(110, () =>
    tone(262, 0.16, { type: 'sawtooth', volume: 0.1, slideTo: 180, filterFreq: 600 }),
  )
  schedule(240, () => {
    tone(175, 0.28, { type: 'triangle', volume: 0.1, slideTo: 90 })
    noiseBurst(0.22, { volume: 0.06, filterFreq: 350, filterType: 'lowpass' })
  })
}

/** Quiet step when the local bomber moves a cell. */
export function playStep(): void {
  const now = performance.now()
  if (now - lastStepAt < 70) return
  lastStepAt = now
  noiseBurst(0.035, { volume: 0.028, filterFreq: 420, filterType: 'lowpass', filterQ: 0.5 })
  tone(95, 0.03, { type: 'sine', volume: 0.03, slideTo: 70 })
}

export function disposeSounds(): void {
  if (ctx && ctx.state !== 'closed') {
    void ctx.close()
  }
  ctx = null
  masterGain = null
  compressor = null
  lastFuseBeepAt = 0
  lastStepAt = 0
}
