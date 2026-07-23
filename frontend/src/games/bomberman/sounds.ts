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

export type ScreamVariant = {
  id: number
  name: string
  description: string
}

const SCREAM_PREF_KEY = 'bomberman-scream-variant'

export const SCREAM_VARIANTS: ScreamVariant[] = [
  { id: 1, name: 'Classic Yell', description: 'Balanced loud scream' },
  { id: 2, name: 'High Panic', description: 'Higher pitch, fast tremor, urgent' },
  { id: 3, name: 'Deep Roar', description: 'Low chesty bellow' },
  { id: 4, name: 'Long Wail', description: 'Extended sustained cry' },
  { id: 5, name: 'Sharp Yelp', description: 'Quick attack then falling cry' },
  { id: 6, name: 'Rough Rasp', description: 'Heavy breath and grit' },
  { id: 7, name: 'Twin Tone', description: 'Single scream with dual formant color' },
  { id: 8, name: 'Shrill', description: 'Piercing high formants' },
  { id: 9, name: 'Strained Cry', description: 'Tense single cry with grit' },
  { id: 10, name: 'Horror', description: 'Slow descending nightmare wail' },
  { id: 11, name: 'Soprano Cry', description: 'High bright voice, clear tone' },
  { id: 12, name: 'Mouse Squeal', description: 'Very high, tight and thin' },
  { id: 13, name: 'Glass Shriek', description: 'Ultra-high piercing shriek' },
  { id: 14, name: 'Child Panic', description: 'High youthful panic yell' },
  { id: 15, name: 'Falsetto Wail', description: 'Airy high falsetto cry' },
  { id: 16, name: 'Siren Peak', description: 'High rising then falling siren' },
  { id: 17, name: 'Opera Death', description: 'Huge dramatic falling aria cry' },
  { id: 18, name: 'Agony Peak', description: 'Explosive high peak into collapse' },
  { id: 19, name: 'Tragic Wail', description: 'Slow mournful high-to-low tragedy' },
  { id: 20, name: 'Bloodcurdle', description: 'Intense raw terror scream' },
  { id: 21, name: 'Final Breath', description: 'Long fading last cry' },
  { id: 22, name: 'Thunder Howl', description: 'Powerful roaring dramatic howl' },
  { id: 23, name: 'Yelp Snap', description: 'Ultra-short sharp yelp bite' },
  { id: 24, name: 'Yelp Sting', description: 'High sting yelp with fast fall' },
  { id: 25, name: 'Yelp Bark', description: 'Punchy mid sharp yelp' },
  { id: 26, name: 'Yelp Pierce', description: 'Needle-thin sharp high yelp' },
  { id: 27, name: 'Yelp Crack', description: 'Cracking sharp yelp with grit' },
  { id: 28, name: 'Yelp Slash', description: 'Longer sharp yelp slash fall' },
  { id: 29, name: 'Dying Cry', description: 'Classic fading death cry' },
  { id: 30, name: 'Last Gasp', description: 'Short dying gasp into silence' },
  { id: 31, name: 'Fading Moan', description: 'Weak moaning death fade' },
  { id: 32, name: 'Death Whimper', description: 'High soft dying whimper' },
  { id: 33, name: 'Broken Cry', description: 'Cracking broken dying cry' },
  { id: 34, name: 'Soul Leave', description: 'Long ethereal departing cry' },
  { id: 35, name: 'Death Scream', description: 'Full-power high dying scream' },
  { id: 36, name: 'Terror Scream', description: 'Piercing high terror scream' },
  { id: 37, name: 'Rage Scream', description: 'Fierce high-power scream' },
  { id: 38, name: 'Panic Scream', description: 'Urgent full-throat high scream' },
  { id: 39, name: 'Blast Scream', description: 'Explosive high scream peak' },
  { id: 40, name: 'Knife Scream', description: 'Sharp cutting high scream' },
]

function clampVariantId(id: number): number {
  const max = SCREAM_VARIANTS.length
  if (!Number.isFinite(id) || id < 1 || id > max) return 1
  return Math.floor(id)
}

export function getSelectedScreamVariant(): number {
  try {
    const raw = localStorage.getItem(SCREAM_PREF_KEY)
    if (raw == null) return 1
    return clampVariantId(Number(raw))
  } catch {
    return 1
  }
}

export function setSelectedScreamVariant(id: number): void {
  const next = clampVariantId(id)
  try {
    localStorage.setItem(SCREAM_PREF_KEY, String(next))
  } catch {
    /* ignore */
  }
}

/** Play one of the scream recipes (also used for death). */
export function playScreamVariant(id: number): void {
  void unlockAudio()
  const v = clampVariantId(id)
  switch (v) {
    case 1: // Classic Yell
      scream({
        volume: 0.58,
        duration: 3.1,
        startHz: 580,
        endHz: 190,
        sustainUntil: 0.78,
      })
      break
    case 2: // High Panic
      scream({
        volume: 0.6,
        duration: 2.8,
        startHz: 780,
        endHz: 280,
        tremorHz: 8.5,
        tremorDepth: 0.09,
        presenceHz: 3200,
        presenceDb: 9,
        sustainUntil: 0.75,
        formants: [
          [900, 780, 5, 1.4],
          [1700, 1400, 6, 1.3],
          [2900, 2500, 7, 1.1],
          [4200, 3600, 5, 0.7],
        ],
      })
      break
    case 3: // Deep Roar
      scream({
        volume: 0.62,
        duration: 3.4,
        startHz: 280,
        endHz: 95,
        chestGain: 1.1,
        noiseAmount: 0.45,
        presenceHz: 1600,
        presenceDb: 5,
        tremorHz: 4.2,
        sustainUntil: 0.8,
        formants: [
          [520, 380, 5, 1.5],
          [980, 720, 6, 1.2],
          [1800, 1400, 5, 0.7],
          [2400, 1900, 4, 0.35],
        ],
      })
      break
    case 4: // Long Wail
      scream({
        volume: 0.55,
        duration: 5,
        startHz: 560,
        endHz: 160,
        sustainUntil: 0.85,
        pitchRise: 0.08,
        tremorHz: 5.2,
        tremorDepth: 0.06,
      })
      break
    case 5: // Sharp Yelp
      scream({
        volume: 0.64,
        duration: 2.3,
        startHz: 880,
        endHz: 180,
        pitchRise: 0.05,
        sustainUntil: 0.4,
        noiseAmount: 0.55,
        presenceDb: 8,
      })
      break
    case 6: // Rough Rasp
      scream({
        volume: 0.58,
        duration: 3.2,
        startHz: 500,
        endHz: 170,
        aspirAmount: 0.55,
        noiseAmount: 1.15,
        noiseFreqStart: 2800,
        noiseFreqEnd: 1100,
        tremorDepth: 0.08,
        presenceDb: 6,
        sustainUntil: 0.78,
      })
      break
    case 7: // Twin Tone
      scream({
        volume: 0.56,
        duration: 3,
        startHz: 620,
        endHz: 210,
        sustainUntil: 0.78,
        formants: [
          [720, 560, 5, 1.35],
          [980, 780, 5, 1.15],
          [1600, 1280, 6, 1.1],
          [2800, 2300, 7, 0.85],
          [3800, 3100, 5, 0.45],
        ],
      })
      break
    case 8: // Shrill
      scream({
        volume: 0.52,
        duration: 2.8,
        startHz: 980,
        endHz: 360,
        presenceHz: 3800,
        presenceDb: 10,
        chestGain: 0.25,
        noiseAmount: 0.85,
        noiseFreqStart: 4200,
        noiseFreqEnd: 2600,
        sustainUntil: 0.75,
        formants: [
          [1100, 900, 5, 1.2],
          [2200, 1800, 6, 1.4],
          [3600, 3000, 7, 1.3],
          [5200, 4200, 5, 0.9],
        ],
      })
      break
    case 9: // Strained Cry
      scream({
        volume: 0.6,
        duration: 2.7,
        startHz: 680,
        endHz: 160,
        aspirAmount: 0.42,
        noiseAmount: 0.95,
        tremorHz: 7.2,
        tremorDepth: 0.1,
        sustainUntil: 0.7,
        pitchRise: 0.1,
      })
      break
    case 10: // Horror
      scream({
        volume: 0.56,
        duration: 4.4,
        startHz: 420,
        endHz: 70,
        pitchRise: 0.18,
        sustainUntil: 0.82,
        tremorHz: 3.8,
        tremorDepth: 0.07,
        chestGain: 0.85,
        presenceHz: 2000,
        presenceDb: 6,
        formants: [
          [600, 320, 5, 1.4],
          [1200, 700, 6, 1.15],
          [2200, 1400, 6, 0.8],
          [3100, 2000, 5, 0.45],
        ],
      })
      break
    case 11: // Soprano Cry
      scream({
        volume: 0.58,
        duration: 3.1,
        startHz: 1050,
        endHz: 420,
        chestGain: 0.2,
        aspirAmount: 0.22,
        noiseAmount: 0.55,
        presenceHz: 3600,
        presenceDb: 9,
        tremorHz: 6.5,
        tremorDepth: 0.055,
        sustainUntil: 0.78,
        formants: [
          [950, 820, 5, 1.25],
          [1900, 1650, 6, 1.35],
          [3200, 2800, 7, 1.2],
          [4800, 4100, 5, 0.75],
        ],
      })
      break
    case 12: // Mouse Squeal
      scream({
        volume: 0.5,
        duration: 2.4,
        startHz: 1350,
        endHz: 620,
        chestGain: 0.12,
        aspirAmount: 0.18,
        noiseAmount: 0.7,
        noiseFreqStart: 5000,
        noiseFreqEnd: 3200,
        presenceHz: 4200,
        presenceDb: 11,
        tremorHz: 9.5,
        tremorDepth: 0.07,
        sustainUntil: 0.72,
        pitchRise: 0.07,
        formants: [
          [1200, 1000, 5, 1.1],
          [2400, 2000, 6, 1.4],
          [4000, 3400, 7, 1.35],
          [5800, 4800, 5, 0.95],
        ],
      })
      break
    case 13: // Glass Shriek
      scream({
        volume: 0.48,
        duration: 2.7,
        startHz: 1500,
        endHz: 700,
        chestGain: 0.08,
        aspirAmount: 0.15,
        noiseAmount: 0.95,
        noiseFreqStart: 6200,
        noiseFreqEnd: 3800,
        presenceHz: 4800,
        presenceDb: 12,
        tremorHz: 10.5,
        tremorDepth: 0.08,
        sustainUntil: 0.7,
        formants: [
          [1400, 1200, 4, 1.0],
          [2800, 2400, 5, 1.35],
          [4500, 3800, 6, 1.45],
          [6500, 5200, 4, 1.1],
        ],
      })
      break
    case 14: // Child Panic
      scream({
        volume: 0.6,
        duration: 2.9,
        startHz: 1180,
        endHz: 380,
        chestGain: 0.18,
        aspirAmount: 0.28,
        noiseAmount: 0.65,
        presenceHz: 3800,
        presenceDb: 10,
        tremorHz: 8.2,
        tremorDepth: 0.1,
        sustainUntil: 0.74,
        pitchRise: 0.1,
        formants: [
          [1000, 850, 5, 1.3],
          [2100, 1700, 6, 1.35],
          [3400, 2900, 7, 1.15],
          [5000, 4200, 5, 0.8],
        ],
      })
      break
    case 15: // Falsetto Wail
      scream({
        volume: 0.52,
        duration: 3.7,
        startHz: 1120,
        endHz: 480,
        chestGain: 0.15,
        aspirAmount: 0.38,
        noiseAmount: 0.8,
        noiseFreqStart: 4600,
        noiseFreqEnd: 2800,
        presenceHz: 4000,
        presenceDb: 8,
        tremorHz: 5.8,
        tremorDepth: 0.06,
        sustainUntil: 0.82,
        pitchRise: 0.14,
        formants: [
          [880, 760, 4, 1.1],
          [1800, 1550, 5, 1.25],
          [3000, 2600, 6, 1.15],
          [4600, 3900, 5, 0.7],
        ],
      })
      break
    case 16: // Siren Peak
      scream({
        volume: 0.56,
        duration: 3.4,
        startHz: 1280,
        endHz: 700,
        chestGain: 0.22,
        aspirAmount: 0.2,
        noiseAmount: 0.6,
        presenceHz: 3600,
        presenceDb: 9,
        tremorHz: 7.0,
        tremorDepth: 0.05,
        sustainUntil: 0.8,
        pitchRise: 0.45,
        formants: [
          [980, 900, 5, 1.25],
          [2100, 1900, 6, 1.3],
          [3400, 3000, 7, 1.2],
          [5000, 4400, 5, 0.85],
        ],
      })
      break
    case 17: // Opera Death
      scream({
        volume: 0.66,
        duration: 4.6,
        startHz: 980,
        endHz: 140,
        chestGain: 0.45,
        aspirAmount: 0.25,
        noiseAmount: 0.55,
        presenceHz: 3000,
        presenceDb: 10,
        tremorHz: 5.5,
        tremorDepth: 0.08,
        sustainUntil: 0.86,
        pitchRise: 0.16,
        formants: [
          [820, 480, 5, 1.45],
          [1600, 900, 6, 1.35],
          [2800, 1600, 7, 1.15],
          [4200, 2400, 5, 0.7],
        ],
      })
      break
    case 18: // Agony Peak
      scream({
        volume: 0.7,
        duration: 3.6,
        startHz: 1400,
        endHz: 160,
        chestGain: 0.3,
        aspirAmount: 0.35,
        noiseAmount: 0.95,
        noiseFreqStart: 4800,
        noiseFreqEnd: 1600,
        presenceHz: 4000,
        presenceDb: 12,
        tremorHz: 9.5,
        tremorDepth: 0.12,
        sustainUntil: 0.55,
        pitchRise: 0.22,
        formants: [
          [1100, 500, 5, 1.4],
          [2200, 1000, 6, 1.45],
          [3600, 1800, 7, 1.3],
          [5400, 2800, 5, 0.95],
        ],
      })
      break
    case 19: // Tragic Wail
      scream({
        volume: 0.6,
        duration: 5.2,
        startHz: 860,
        endHz: 110,
        chestGain: 0.5,
        aspirAmount: 0.3,
        noiseAmount: 0.5,
        presenceHz: 2600,
        presenceDb: 8,
        tremorHz: 4.2,
        tremorDepth: 0.07,
        sustainUntil: 0.88,
        pitchRise: 0.1,
        formants: [
          [760, 420, 5, 1.4],
          [1450, 780, 6, 1.25],
          [2500, 1400, 6, 1.0],
          [3800, 2100, 5, 0.55],
        ],
      })
      break
    case 20: // Bloodcurdle
      scream({
        volume: 0.72,
        duration: 3.8,
        startHz: 1200,
        endHz: 200,
        chestGain: 0.35,
        aspirAmount: 0.5,
        noiseAmount: 1.25,
        noiseFreqStart: 5200,
        noiseFreqEnd: 1400,
        presenceHz: 3800,
        presenceDb: 13,
        tremorHz: 11,
        tremorDepth: 0.14,
        sustainUntil: 0.7,
        pitchRise: 0.12,
        formants: [
          [1000, 560, 4, 1.5],
          [2000, 1100, 5, 1.5],
          [3400, 1900, 6, 1.35],
          [5000, 2800, 5, 1.05],
        ],
      })
      break
    case 21: // Final Breath
      scream({
        volume: 0.58,
        duration: 5.5,
        startHz: 720,
        endHz: 85,
        chestGain: 0.55,
        aspirAmount: 0.45,
        noiseAmount: 0.75,
        noiseFreqStart: 3000,
        noiseFreqEnd: 900,
        presenceHz: 2200,
        presenceDb: 7,
        tremorHz: 3.5,
        tremorDepth: 0.06,
        sustainUntil: 0.9,
        pitchRise: 0.08,
        formants: [
          [680, 300, 5, 1.4],
          [1300, 620, 6, 1.2],
          [2300, 1100, 6, 0.9],
          [3400, 1600, 5, 0.45],
        ],
      })
      break
    case 22: // Thunder Howl
      scream({
        volume: 0.74,
        duration: 4.2,
        startHz: 640,
        endHz: 90,
        chestGain: 1.25,
        aspirAmount: 0.4,
        noiseAmount: 0.85,
        noiseFreqStart: 2400,
        noiseFreqEnd: 700,
        presenceHz: 1800,
        presenceDb: 8,
        tremorHz: 4.8,
        tremorDepth: 0.09,
        sustainUntil: 0.84,
        pitchRise: 0.14,
        formants: [
          [480, 220, 4, 1.6],
          [900, 420, 5, 1.4],
          [1600, 800, 5, 1.1],
          [2600, 1300, 4, 0.65],
        ],
      })
      break
    case 23: // Yelp Snap
      scream({
        volume: 0.68,
        duration: 1.6,
        startHz: 920,
        endHz: 220,
        pitchRise: 0.03,
        sustainUntil: 0.28,
        noiseAmount: 0.5,
        presenceDb: 9,
        presenceHz: 3200,
        chestGain: 0.25,
        tremorHz: 8,
        tremorDepth: 0.04,
      })
      break
    case 24: // Yelp Sting
      scream({
        volume: 0.66,
        duration: 2.1,
        startHz: 1100,
        endHz: 200,
        pitchRise: 0.04,
        sustainUntil: 0.32,
        noiseAmount: 0.6,
        presenceDb: 10,
        presenceHz: 3800,
        chestGain: 0.18,
        aspirAmount: 0.2,
        formants: [
          [980, 620, 5, 1.3],
          [1900, 1100, 6, 1.35],
          [3200, 1800, 7, 1.15],
          [4800, 2800, 5, 0.8],
        ],
      })
      break
    case 25: // Yelp Bark
      scream({
        volume: 0.7,
        duration: 2.0,
        startHz: 720,
        endHz: 160,
        pitchRise: 0.04,
        sustainUntil: 0.35,
        noiseAmount: 0.65,
        presenceDb: 8,
        presenceHz: 2600,
        chestGain: 0.55,
        aspirAmount: 0.3,
        tremorHz: 6.5,
        formants: [
          [700, 420, 5, 1.4],
          [1400, 820, 6, 1.25],
          [2400, 1400, 6, 0.95],
          [3600, 2000, 5, 0.55],
        ],
      })
      break
    case 26: // Yelp Pierce
      scream({
        volume: 0.58,
        duration: 2.2,
        startHz: 1320,
        endHz: 340,
        pitchRise: 0.035,
        sustainUntil: 0.3,
        noiseAmount: 0.75,
        noiseFreqStart: 5000,
        noiseFreqEnd: 2400,
        presenceDb: 12,
        presenceHz: 4400,
        chestGain: 0.1,
        aspirAmount: 0.15,
        formants: [
          [1200, 800, 4, 1.2],
          [2400, 1500, 5, 1.4],
          [4000, 2600, 6, 1.35],
          [5800, 3800, 4, 1.0],
        ],
      })
      break
    case 27: // Yelp Crack
      scream({
        volume: 0.67,
        duration: 2.4,
        startHz: 960,
        endHz: 170,
        pitchRise: 0.05,
        sustainUntil: 0.38,
        aspirAmount: 0.48,
        noiseAmount: 1.05,
        noiseFreqStart: 3600,
        noiseFreqEnd: 1200,
        presenceDb: 9,
        presenceHz: 3000,
        chestGain: 0.3,
        tremorHz: 9,
        tremorDepth: 0.1,
      })
      break
    case 28: // Yelp Slash
      scream({
        volume: 0.65,
        duration: 3.0,
        startHz: 1000,
        endHz: 140,
        pitchRise: 0.045,
        sustainUntil: 0.42,
        noiseAmount: 0.7,
        presenceDb: 10,
        presenceHz: 3400,
        chestGain: 0.28,
        aspirAmount: 0.28,
        tremorHz: 7.5,
        tremorDepth: 0.07,
        formants: [
          [900, 480, 5, 1.35],
          [1800, 900, 6, 1.3],
          [3000, 1500, 7, 1.1],
          [4600, 2400, 5, 0.75],
        ],
      })
      break
    case 29: // Dying Cry
      scream({
        volume: 0.62,
        duration: 3.8,
        startHz: 640,
        endHz: 95,
        pitchRise: 0.08,
        sustainUntil: 0.55,
        aspirAmount: 0.4,
        noiseAmount: 0.7,
        noiseFreqStart: 2800,
        noiseFreqEnd: 800,
        chestGain: 0.6,
        presenceHz: 2200,
        presenceDb: 7,
        tremorHz: 4.5,
        tremorDepth: 0.08,
        formants: [
          [620, 280, 5, 1.4],
          [1200, 560, 6, 1.2],
          [2200, 1000, 6, 0.85],
          [3400, 1600, 5, 0.4],
        ],
      })
      break
    case 30: // Last Gasp
      scream({
        volume: 0.58,
        duration: 2.0,
        startHz: 520,
        endHz: 110,
        pitchRise: 0.06,
        sustainUntil: 0.3,
        aspirAmount: 0.55,
        noiseAmount: 0.95,
        noiseFreqStart: 2200,
        noiseFreqEnd: 600,
        chestGain: 0.7,
        presenceHz: 1800,
        presenceDb: 6,
        tremorHz: 3.8,
        tremorDepth: 0.05,
      })
      break
    case 31: // Fading Moan
      scream({
        volume: 0.48,
        duration: 4.4,
        startHz: 380,
        endHz: 70,
        pitchRise: 0.05,
        sustainUntil: 0.7,
        aspirAmount: 0.5,
        noiseAmount: 0.55,
        chestGain: 0.9,
        presenceHz: 1400,
        presenceDb: 5,
        tremorHz: 3.2,
        tremorDepth: 0.06,
        formants: [
          [420, 200, 4, 1.5],
          [780, 360, 5, 1.2],
          [1400, 700, 5, 0.7],
          [2200, 1100, 4, 0.3],
        ],
      })
      break
    case 32: // Death Whimper
      scream({
        volume: 0.5,
        duration: 3.2,
        startHz: 880,
        endHz: 220,
        pitchRise: 0.07,
        sustainUntil: 0.45,
        aspirAmount: 0.35,
        noiseAmount: 0.6,
        chestGain: 0.2,
        presenceHz: 3200,
        presenceDb: 8,
        tremorHz: 6.5,
        tremorDepth: 0.09,
        formants: [
          [900, 500, 5, 1.25],
          [1800, 1000, 6, 1.2],
          [3000, 1700, 6, 0.95],
          [4400, 2500, 5, 0.55],
        ],
      })
      break
    case 33: // Broken Cry
      scream({
        volume: 0.6,
        duration: 3.5,
        startHz: 700,
        endHz: 120,
        pitchRise: 0.1,
        sustainUntil: 0.5,
        aspirAmount: 0.55,
        noiseAmount: 1.1,
        noiseFreqStart: 3400,
        noiseFreqEnd: 900,
        chestGain: 0.45,
        presenceHz: 2600,
        presenceDb: 8,
        tremorHz: 8.5,
        tremorDepth: 0.13,
        formants: [
          [680, 320, 4, 1.35],
          [1300, 620, 5, 1.25],
          [2400, 1100, 6, 1.0],
          [3800, 1800, 5, 0.6],
        ],
      })
      break
    case 34: // Soul Leave
      scream({
        volume: 0.52,
        duration: 5.0,
        startHz: 760,
        endHz: 80,
        pitchRise: 0.12,
        sustainUntil: 0.82,
        aspirAmount: 0.42,
        noiseAmount: 0.65,
        noiseFreqStart: 3600,
        noiseFreqEnd: 1000,
        chestGain: 0.35,
        presenceHz: 2800,
        presenceDb: 7,
        tremorHz: 4.0,
        tremorDepth: 0.07,
        formants: [
          [720, 280, 5, 1.3],
          [1500, 600, 6, 1.15],
          [2700, 1100, 6, 0.9],
          [4200, 1800, 5, 0.5],
        ],
      })
      break
    case 35: // Death Scream — strong high dying scream
      scream({
        volume: 0.78,
        duration: 7.2,
        startHz: 980,
        endHz: 210,
        pitchRise: 0.08,
        sustainUntil: 0.72,
        aspirAmount: 0.28,
        noiseAmount: 0.9,
        noiseFreqStart: 4000,
        noiseFreqEnd: 1800,
        chestGain: 0.32,
        presenceHz: 3400,
        presenceDb: 13,
        tremorHz: 7.0,
        tremorDepth: 0.1,
        formants: [
          [880, 560, 4, 1.55],
          [1750, 1100, 5, 1.6],
          [3000, 1900, 6, 1.45],
          [4500, 2800, 4, 1.1],
        ],
      })
      break
    case 36: // Terror Scream
      scream({
        volume: 0.8,
        duration: 6.8,
        startHz: 1400,
        endHz: 320,
        pitchRise: 0.07,
        sustainUntil: 0.7,
        aspirAmount: 0.32,
        noiseAmount: 1.05,
        noiseFreqStart: 5600,
        noiseFreqEnd: 2600,
        chestGain: 0.18,
        presenceHz: 4500,
        presenceDb: 15,
        tremorHz: 9.5,
        tremorDepth: 0.12,
        formants: [
          [1200, 800, 4, 1.5],
          [2400, 1600, 5, 1.65],
          [4000, 2800, 6, 1.55],
          [6000, 4200, 4, 1.25],
        ],
      })
      break
    case 37: // Rage Scream
      scream({
        volume: 0.82,
        duration: 7.6,
        startHz: 1100,
        endHz: 240,
        pitchRise: 0.1,
        sustainUntil: 0.75,
        aspirAmount: 0.4,
        noiseAmount: 1.15,
        noiseFreqStart: 4200,
        noiseFreqEnd: 1600,
        chestGain: 0.4,
        presenceHz: 3600,
        presenceDb: 13,
        tremorHz: 8.0,
        tremorDepth: 0.11,
        formants: [
          [950, 550, 4, 1.6],
          [1900, 1100, 5, 1.55],
          [3200, 1900, 6, 1.4],
          [4800, 2800, 5, 1.1],
        ],
      })
      break
    case 38: // Panic Scream
      scream({
        volume: 0.8,
        duration: 6.4,
        startHz: 1320,
        endHz: 300,
        pitchRise: 0.06,
        sustainUntil: 0.68,
        aspirAmount: 0.3,
        noiseAmount: 0.95,
        noiseFreqStart: 5000,
        noiseFreqEnd: 2400,
        chestGain: 0.22,
        presenceHz: 4200,
        presenceDb: 14,
        tremorHz: 10.5,
        tremorDepth: 0.13,
        formants: [
          [1100, 750, 4, 1.55],
          [2200, 1500, 5, 1.6],
          [3800, 2600, 6, 1.5],
          [5600, 3800, 4, 1.2],
        ],
      })
      break
    case 39: // Blast Scream
      scream({
        volume: 0.85,
        duration: 6.0,
        startHz: 1500,
        endHz: 260,
        pitchRise: 0.12,
        sustainUntil: 0.55,
        aspirAmount: 0.35,
        noiseAmount: 1.2,
        noiseFreqStart: 5800,
        noiseFreqEnd: 2000,
        chestGain: 0.28,
        presenceHz: 4600,
        presenceDb: 16,
        tremorHz: 11,
        tremorDepth: 0.14,
        formants: [
          [1250, 700, 3.5, 1.65],
          [2500, 1400, 4.5, 1.7],
          [4200, 2400, 5.5, 1.55],
          [6200, 3600, 4, 1.3],
        ],
      })
      break
    case 40: // Knife Scream
      scream({
        volume: 0.78,
        duration: 7.0,
        startHz: 1450,
        endHz: 350,
        pitchRise: 0.05,
        sustainUntil: 0.65,
        aspirAmount: 0.22,
        noiseAmount: 0.85,
        noiseFreqStart: 5400,
        noiseFreqEnd: 2800,
        chestGain: 0.12,
        presenceHz: 4800,
        presenceDb: 15,
        tremorHz: 8.5,
        tremorDepth: 0.09,
        formants: [
          [1300, 900, 4, 1.45],
          [2600, 1800, 5, 1.65],
          [4400, 3000, 6, 1.55],
          [6500, 4500, 4, 1.25],
        ],
      })
      break
  }
}

/** Any bomber eliminated — uses the selected scream variant. */
export function playDeath(): void {
  playScreamVariant(getSelectedScreamVariant())
}

/** @deprecated Use playDeath — same scream for every bomber. */
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
  lastFuseBeepAt = 0
  lastStepAt = 0
}
