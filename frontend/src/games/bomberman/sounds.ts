/** Procedural Bomberman sound effects (Web Audio API) — layered, higher fidelity. */

let ctx: AudioContext | null = null
let masterGain: GainNode | null = null
let compressor: DynamicsCompressorNode | null = null

const MASTER_VOLUME = 0.42
const SFX_VOLUME = 0.22
const MUTE_STORAGE_KEY = 'bomberman-sound-muted'

let muted = readMutedPreference()
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

export type PowerupSoundKind = 'bomb' | 'range' | 'speed' | 'throw' | 'kick' | 'skull'

/** Pickup chime — slight flavor per power-up type. */
export function playPowerup(kind: PowerupSoundKind = 'bomb'): void {
  if (kind === 'skull') {
    // Low, uneasy sting for the cursed skull.
    ;[180, 140, 110].forEach((freq, idx) => {
      schedule(idx * 70, () => {
        tone(freq, 0.14 + idx * 0.03, {
          type: idx === 2 ? 'sawtooth' : 'triangle',
          volume: 0.09 - idx * 0.015,
          filterFreq: 900,
          slideTo: freq * 0.7,
        })
      })
    })
    noiseBurst(0.1, {
      volume: 0.045,
      filterFreq: 600,
      filterType: 'lowpass',
      delay: 0.05,
    })
    return
  }
  const flavors: Record<Exclude<PowerupSoundKind, 'skull'>, number[]> = {
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

/** Build a glottal-ish pulse train buffer (voiced source). */
function makeGlottalBuffer(
  audio: AudioContext,
  duration: number,
  startHz: number,
  endHz: number,
  opts: {
    aspirAmount?: number
    tremorHz?: number
    tremorDepth?: number
    sustainUntil?: number
    pitchRise?: number
  } = {},
) {
  const {
    aspirAmount = 0.28,
    tremorHz = 5.5,
    tremorDepth = 0.05,
    sustainUntil = 0.72,
    pitchRise = 0.12,
  } = opts
  const len = Math.max(1, Math.floor(audio.sampleRate * duration))
  const buffer = audio.createBuffer(1, len, audio.sampleRate)
  const data = buffer.getChannelData(0)
  const sr = audio.sampleRate
  let phase = 0
  let aspir = 0
  for (let i = 0; i < len; i++) {
    const u = i / len
    const pitchEase =
      u < pitchRise ? u / pitchRise : 1 - Math.pow((u - pitchRise) / Math.max(0.01, 1 - pitchRise), 1.35)
    const hz = endHz + (startHz - endHz) * pitchEase
    const period = sr / Math.max(40, hz)
    phase += 1
    if (phase >= period) phase -= period
    const p = phase / period
    let pulse = 0
    if (p < 0.4) {
      const o = p / 0.4
      pulse = Math.sin(Math.PI * o) * Math.sin(Math.PI * o)
    } else if (p < 0.55) {
      const c = (p - 0.4) / 0.15
      pulse = Math.cos(Math.PI * 0.5 * c)
    }
    const white = Math.random() * 2 - 1
    aspir = aspir * 0.92 + white * 0.08
    const fadeStart = sustainUntil
    const env =
      Math.sin(Math.PI * Math.min(1, u / 0.06)) *
      (u < fadeStart ? 1 : Math.pow(1 - (u - fadeStart) / Math.max(0.01, 1 - fadeStart), 0.85))
    const tremor = 1 + tremorDepth * Math.sin(2 * Math.PI * tremorHz * (i / sr))
    data[i] = (pulse * (1 - aspirAmount * 0.35) + aspir * aspirAmount) * env * tremor
  }
  return buffer
}

type Formant = [number, number, number, number] // startHz, endHz, Q, gain

type ScreamOpts = {
  volume?: number
  duration?: number
  startHz?: number
  endHz?: number
  formants?: Formant[]
  noiseAmount?: number
  noiseFreqStart?: number
  noiseFreqEnd?: number
  chestGain?: number
  presenceDb?: number
  presenceHz?: number
  aspirAmount?: number
  tremorHz?: number
  tremorDepth?: number
  sustainUntil?: number
  pitchRise?: number
}

/** Glottal source + vowel formants scream. */
function scream(opts: ScreamOpts = {}) {
  const audio = alive()
  if (!audio) return

  const {
    volume = 0.35,
    duration = 1.35,
    startHz = 520,
    endHz = 220,
    formants = [
      [780, 620, 6, 1.35],
      [1450, 1180, 7, 1.2],
      [2650, 2300, 8, 0.9],
      [3500, 3000, 6, 0.55],
    ],
    noiseAmount = 0.7,
    noiseFreqStart = 2400,
    noiseFreqEnd = 1500,
    chestGain = 0.55,
    presenceDb = 7,
    presenceHz = 2800,
    aspirAmount = 0.28,
    tremorHz = 5.5,
    tremorDepth = 0.05,
    sustainUntil = 0.72,
    pitchRise = 0.12,
  } = opts

  const t0 = audio.currentTime
  const source = audio.createBufferSource()
  source.buffer = makeGlottalBuffer(audio, duration, startHz, endHz, {
    aspirAmount,
    tremorHz,
    tremorDepth,
    sustainUntil,
    pitchRise,
  })

  const master = audio.createGain()
  master.gain.setValueAtTime(0.0001, t0)
  master.gain.linearRampToValueAtTime(volume, t0 + 0.04)
  master.gain.setValueAtTime(volume, t0 + duration * 0.65)
  master.gain.linearRampToValueAtTime(volume * 0.55, t0 + duration * 0.85)
  master.gain.exponentialRampToValueAtTime(0.0001, t0 + duration)

  for (const [fStart, fEnd, q, g] of formants) {
    const bp = audio.createBiquadFilter()
    bp.type = 'bandpass'
    bp.frequency.setValueAtTime(fStart, t0)
    bp.frequency.exponentialRampToValueAtTime(Math.max(80, fEnd), t0 + duration)
    bp.Q.setValueAtTime(q, t0)
    const gNode = audio.createGain()
    gNode.gain.setValueAtTime(g, t0)
    source.connect(bp)
    bp.connect(gNode)
    gNode.connect(master)
  }

  const low = audio.createBiquadFilter()
  low.type = 'lowpass'
  low.frequency.setValueAtTime(1000, t0)
  low.frequency.exponentialRampToValueAtTime(550, t0 + duration)
  low.Q.setValueAtTime(0.7, t0)
  const lowGain = audio.createGain()
  lowGain.gain.setValueAtTime(chestGain, t0)
  source.connect(low)
  low.connect(lowGain)
  lowGain.connect(master)

  const noiseDur = duration * 0.95
  const noiseLen = Math.max(1, Math.floor(audio.sampleRate * noiseDur))
  const noiseBuf = audio.createBuffer(1, noiseLen, audio.sampleRate)
  const nd = noiseBuf.getChannelData(0)
  let pink = 0
  for (let i = 0; i < noiseLen; i++) {
    const white = Math.random() * 2 - 1
    pink = (pink + 0.02 * white) / 1.02
    const u = i / noiseLen
    const env =
      Math.sin(Math.PI * Math.min(1, u / 0.08)) *
      (u < 0.7 ? 1 : Math.pow(1 - (u - 0.7) / 0.3, 0.8))
    nd[i] = (white * 0.45 + pink * 0.65) * env
  }
  const noise = audio.createBufferSource()
  noise.buffer = noiseBuf
  const nBp = audio.createBiquadFilter()
  nBp.type = 'bandpass'
  nBp.frequency.setValueAtTime(noiseFreqStart, t0)
  nBp.frequency.exponentialRampToValueAtTime(noiseFreqEnd, t0 + noiseDur)
  nBp.Q.setValueAtTime(1.4, t0)
  const nGain = audio.createGain()
  nGain.gain.setValueAtTime(volume * noiseAmount, t0)
  nGain.gain.setValueAtTime(volume * noiseAmount * 0.78, t0 + noiseDur * 0.6)
  nGain.gain.exponentialRampToValueAtTime(0.0001, t0 + noiseDur)
  noise.connect(nBp)
  nBp.connect(nGain)
  nGain.connect(sfxDest())

  const presence = audio.createBiquadFilter()
  presence.type = 'peaking'
  presence.frequency.setValueAtTime(presenceHz, t0)
  presence.Q.setValueAtTime(1.1, t0)
  presence.gain.setValueAtTime(presenceDb, t0)

  master.connect(presence)
  presence.connect(sfxDest())

  source.start(t0)
  source.stop(t0 + duration + 0.02)
  noise.start(t0)
  noise.stop(t0 + noiseDur + 0.02)
}

/** 10 Death Scream flavors — one is chosen at random on each death. */
const DEATH_SCREAMS: ScreamOpts[] = [
  {
    volume: 0.42,
    duration: 7.2,
    startHz: 980,
    endHz: 210,
    pitchRise: 0.08,
    sustainUntil: 0.72,
    aspirAmount: 0.28,
    noiseAmount: 0.65,
    noiseFreqStart: 4000,
    noiseFreqEnd: 1800,
    chestGain: 0.28,
    presenceHz: 3400,
    presenceDb: 8,
    tremorHz: 7.0,
    tremorDepth: 0.1,
    formants: [
      [880, 560, 4, 1.55],
      [1750, 1100, 5, 1.6],
      [3000, 1900, 6, 1.45],
      [4500, 2800, 4, 1.1],
    ],
  },
  {
    volume: 0.4,
    duration: 6.8,
    startHz: 1080,
    endHz: 240,
    pitchRise: 0.07,
    sustainUntil: 0.7,
    aspirAmount: 0.25,
    noiseAmount: 0.7,
    noiseFreqStart: 4400,
    noiseFreqEnd: 2000,
    chestGain: 0.25,
    presenceHz: 3800,
    presenceDb: 9,
    tremorHz: 8.2,
    tremorDepth: 0.11,
    formants: [
      [960, 620, 4, 1.5],
      [1900, 1200, 5, 1.55],
      [3300, 2100, 6, 1.4],
      [5000, 3200, 4, 1.15],
    ],
  },
  {
    volume: 0.44,
    duration: 7.5,
    startHz: 860,
    endHz: 170,
    pitchRise: 0.09,
    sustainUntil: 0.74,
    aspirAmount: 0.32,
    noiseAmount: 0.6,
    noiseFreqStart: 3600,
    noiseFreqEnd: 1500,
    chestGain: 0.42,
    presenceHz: 3000,
    presenceDb: 7,
    tremorHz: 6.2,
    tremorDepth: 0.09,
    formants: [
      [780, 480, 4, 1.6],
      [1550, 900, 5, 1.55],
      [2700, 1600, 6, 1.35],
      [4000, 2400, 4, 1.0],
    ],
  },
  {
    volume: 0.4,
    duration: 8.4,
    startHz: 1020,
    endHz: 150,
    pitchRise: 0.1,
    sustainUntil: 0.8,
    aspirAmount: 0.3,
    noiseAmount: 0.62,
    noiseFreqStart: 4200,
    noiseFreqEnd: 1600,
    chestGain: 0.3,
    presenceHz: 3500,
    presenceDb: 8,
    tremorHz: 6.8,
    tremorDepth: 0.1,
    formants: [
      [900, 500, 4, 1.55],
      [1800, 1000, 5, 1.55],
      [3100, 1700, 6, 1.4],
      [4600, 2500, 4, 1.05],
    ],
  },
  {
    volume: 0.45,
    duration: 5.6,
    startHz: 1120,
    endHz: 260,
    pitchRise: 0.06,
    sustainUntil: 0.55,
    aspirAmount: 0.26,
    noiseAmount: 0.75,
    noiseFreqStart: 4600,
    noiseFreqEnd: 2100,
    chestGain: 0.28,
    presenceHz: 4000,
    presenceDb: 9,
    tremorHz: 9.0,
    tremorDepth: 0.12,
    formants: [
      [1000, 650, 4, 1.55],
      [2000, 1300, 5, 1.6],
      [3500, 2200, 6, 1.45],
      [5200, 3400, 4, 1.2],
    ],
  },
  {
    volume: 0.43,
    duration: 7.0,
    startHz: 940,
    endHz: 200,
    pitchRise: 0.08,
    sustainUntil: 0.7,
    aspirAmount: 0.45,
    noiseAmount: 0.95,
    noiseFreqStart: 3800,
    noiseFreqEnd: 1400,
    chestGain: 0.35,
    presenceHz: 3200,
    presenceDb: 8,
    tremorHz: 7.8,
    tremorDepth: 0.13,
    formants: [
      [850, 520, 4, 1.5],
      [1700, 1000, 5, 1.5],
      [2900, 1700, 6, 1.35],
      [4300, 2600, 4, 1.05],
    ],
  },
  {
    volume: 0.38,
    duration: 6.9,
    startHz: 1180,
    endHz: 280,
    pitchRise: 0.07,
    sustainUntil: 0.68,
    aspirAmount: 0.22,
    noiseAmount: 0.7,
    noiseFreqStart: 5000,
    noiseFreqEnd: 2400,
    chestGain: 0.18,
    presenceHz: 4400,
    presenceDb: 10,
    tremorHz: 8.5,
    tremorDepth: 0.1,
    formants: [
      [1100, 720, 4, 1.45],
      [2200, 1450, 5, 1.6],
      [3800, 2500, 6, 1.5],
      [5600, 3800, 4, 1.2],
    ],
  },
  {
    volume: 0.44,
    duration: 7.6,
    startHz: 820,
    endHz: 160,
    pitchRise: 0.11,
    sustainUntil: 0.76,
    aspirAmount: 0.38,
    noiseAmount: 0.72,
    noiseFreqStart: 3400,
    noiseFreqEnd: 1300,
    chestGain: 0.48,
    presenceHz: 2800,
    presenceDb: 7,
    tremorHz: 5.8,
    tremorDepth: 0.11,
    formants: [
      [720, 400, 4, 1.6],
      [1400, 780, 5, 1.5],
      [2500, 1400, 6, 1.3],
      [3800, 2100, 4, 0.95],
    ],
  },
  {
    volume: 0.41,
    duration: 6.6,
    startHz: 1040,
    endHz: 220,
    pitchRise: 0.08,
    sustainUntil: 0.66,
    aspirAmount: 0.3,
    noiseAmount: 0.8,
    noiseFreqStart: 4300,
    noiseFreqEnd: 1900,
    chestGain: 0.3,
    presenceHz: 3700,
    presenceDb: 9,
    tremorHz: 10.5,
    tremorDepth: 0.14,
    formants: [
      [920, 580, 4, 1.55],
      [1850, 1150, 5, 1.55],
      [3200, 2000, 6, 1.4],
      [4800, 3000, 4, 1.1],
    ],
  },
  {
    volume: 0.4,
    duration: 8.8,
    startHz: 900,
    endHz: 120,
    pitchRise: 0.14,
    sustainUntil: 0.84,
    aspirAmount: 0.34,
    noiseAmount: 0.58,
    noiseFreqStart: 3800,
    noiseFreqEnd: 1400,
    chestGain: 0.38,
    presenceHz: 3100,
    presenceDb: 7,
    tremorHz: 5.2,
    tremorDepth: 0.08,
    formants: [
      [800, 420, 4, 1.55],
      [1600, 850, 5, 1.5],
      [2800, 1500, 6, 1.35],
      [4200, 2200, 4, 1.0],
    ],
  },
]

/** Any bomber eliminated — random Death Scream variant. */
export function playDeath(): void {
  const pick = DEATH_SCREAMS[Math.floor(Math.random() * DEATH_SCREAMS.length)]!
  scream(pick)
}

export function playEnemyDeath(): void {
  playDeath()
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
  lastStepAt = 0
}
