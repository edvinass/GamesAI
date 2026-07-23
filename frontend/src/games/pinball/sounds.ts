/** Procedural arcade pinball SFX (Web Audio API). */

let ctx: AudioContext | null = null
let masterGain: GainNode | null = null
let compressor: DynamicsCompressorNode | null = null

const MASTER_VOLUME = 0.45
const MUTE_STORAGE_KEY = 'pinball-sound-muted'

let muted = readMutedPreference()
let lastBumperAt = 0
let lastFlipperAt = 0
let lastWallAt = 0

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
    compressor.threshold.setValueAtTime(-16, ctx.currentTime)
    compressor.knee.setValueAtTime(10, ctx.currentTime)
    compressor.ratio.setValueAtTime(3, ctx.currentTime)
    compressor.attack.setValueAtTime(0.002, ctx.currentTime)
    compressor.release.setValueAtTime(0.15, ctx.currentTime)
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

function alive(): AudioContext | null {
  if (muted) return null
  const audio = getCtx()
  if (audio.state !== 'running') return null
  return audio
}

function tone(
  freq: number,
  dur: number,
  type: OscillatorType = 'square',
  gain = 0.08,
  slideTo?: number,
) {
  const audio = alive()
  if (!audio || !masterGain) return
  const t0 = audio.currentTime
  const osc = audio.createOscillator()
  const g = audio.createGain()
  osc.type = type
  osc.frequency.setValueAtTime(freq, t0)
  if (slideTo != null) {
    osc.frequency.exponentialRampToValueAtTime(Math.max(1, slideTo), t0 + dur)
  }
  g.gain.setValueAtTime(gain, t0)
  g.gain.exponentialRampToValueAtTime(0.001, t0 + dur)
  osc.connect(g)
  g.connect(masterGain)
  osc.start(t0)
  osc.stop(t0 + dur + 0.03)
}

function noiseBurst(duration: number, volume = 0.1, filterFreq = 1200) {
  const audio = alive()
  if (!audio || !masterGain) return

  const bufferSize = Math.floor(audio.sampleRate * duration)
  const buffer = audio.createBuffer(1, bufferSize, audio.sampleRate)
  const data = buffer.getChannelData(0)
  for (let i = 0; i < bufferSize; i++) {
    data[i] = (Math.random() * 2 - 1) * (1 - i / bufferSize)
  }

  const src = audio.createBufferSource()
  src.buffer = buffer
  const filter = audio.createBiquadFilter()
  filter.type = 'bandpass'
  filter.frequency.value = filterFreq
  filter.Q.value = 1.2
  const g = audio.createGain()
  const t0 = audio.currentTime
  g.gain.setValueAtTime(volume, t0)
  g.gain.exponentialRampToValueAtTime(0.001, t0 + duration)

  src.connect(filter)
  filter.connect(g)
  g.connect(masterGain)
  src.start(t0)
  src.stop(t0 + duration + 0.02)
}

/** Spring plunger / ball launch whoosh. */
export function playLaunch() {
  noiseBurst(0.12, 0.09, 900)
  tone(120, 0.18, 'sawtooth', 0.07, 480)
  setTimeout(() => tone(380, 0.1, 'triangle', 0.05, 720), 60)
  setTimeout(() => tone(900, 0.06, 'square', 0.035), 110)
}

/** Mechanical flipper bat. */
export function playFlipper() {
  const now = performance.now()
  if (now - lastFlipperAt < 40) return
  lastFlipperAt = now
  noiseBurst(0.04, 0.08, 1800)
  tone(180, 0.045, 'square', 0.07)
  tone(90, 0.06, 'triangle', 0.05)
}

/**
 * Classic bumper ding. Higher-value bumpers ring brighter.
 * @param points bumper point value (used for pitch)
 */
export function playBumper(points = 100) {
  const now = performance.now()
  if (now - lastBumperAt < 35) return
  lastBumperAt = now

  const base = 420 + Math.min(points, 200) * 1.4 + Math.random() * 40
  tone(base, 0.09, 'square', 0.09)
  tone(base * 1.5, 0.12, 'triangle', 0.05)
  noiseBurst(0.035, 0.06, 2400)
}

/** Target / drop-target chime. */
export function playTarget(points = 500) {
  const high = points >= 800
  const notes = high
    ? [660, 880, 1175, 1568]
    : [523, 659, 784, 1046]
  notes.forEach((f, i) => {
    setTimeout(() => tone(f, 0.1, i % 2 === 0 ? 'square' : 'triangle', 0.06), i * 45)
  })
  noiseBurst(0.05, 0.05, 3000)
}

/** Soft rail / wall tap. */
export function playWall() {
  const now = performance.now()
  if (now - lastWallAt < 80) return
  lastWallAt = now
  noiseBurst(0.03, 0.045, 600)
  tone(140, 0.04, 'triangle', 0.03)
}

/** Flipper contact with the ball. */
export function playFlipperHit() {
  noiseBurst(0.05, 0.07, 1400)
  tone(220, 0.06, 'square', 0.055)
  tone(440, 0.05, 'triangle', 0.03)
}

/** Combo multiplier tick. */
export function playCombo(level: number) {
  const freq = 520 + Math.min(level, 5) * 90
  tone(freq, 0.07, 'square', 0.055)
  setTimeout(() => tone(freq * 1.33, 0.08, 'triangle', 0.045), 40)
}

/** Ball drained past the flippers. */
export function playDrain() {
  tone(320, 0.2, 'sawtooth', 0.07, 80)
  setTimeout(() => tone(180, 0.22, 'triangle', 0.06, 60), 80)
  setTimeout(() => noiseBurst(0.15, 0.06, 400), 40)
}

/** All balls gone. */
export function playGameOver() {
  const notes = [392, 349, 311, 262, 196]
  notes.forEach((f, i) => {
    setTimeout(() => tone(f, 0.18, 'triangle', 0.07), i * 130)
  })
  setTimeout(() => noiseBurst(0.2, 0.05, 300), 400)
}

/** New high score sting. */
export function playHighScore() {
  ;[523, 659, 784, 1046, 1319].forEach((f, i) => {
    setTimeout(() => tone(f, 0.12, 'square', 0.065), i * 90)
  })
}

/** Soft UI click (mute toggle etc.). */
export function playUiClick() {
  tone(800, 0.04, 'square', 0.03)
}
