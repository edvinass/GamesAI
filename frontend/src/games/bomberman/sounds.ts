/** Procedural Bomberman sound effects (Web Audio API). */

let ctx: AudioContext | null = null
let masterGain: GainNode | null = null

const MASTER_VOLUME = 0.38
const SFX_VOLUME = 0.2
const MUTE_STORAGE_KEY = 'bomberman-sound-muted'

let muted = readMutedPreference()

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
    masterGain.connect(ctx.destination)
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

function tone(
  freq: number,
  duration: number,
  options: {
    type?: OscillatorType
    volume?: number
    attack?: number
    decay?: number
    slideTo?: number
  } = {},
) {
  if (muted) return
  const audio = getCtx()
  if (audio.state !== 'running') return

  const {
    type = 'square',
    volume = SFX_VOLUME,
    attack = 0.004,
    decay = duration,
    slideTo,
  } = options

  const osc = audio.createOscillator()
  const gain = audio.createGain()
  osc.type = type
  const t = audio.currentTime
  osc.frequency.setValueAtTime(freq, t)
  if (slideTo != null) {
    osc.frequency.exponentialRampToValueAtTime(Math.max(20, slideTo), t + decay)
  }

  gain.gain.setValueAtTime(0.001, t)
  gain.gain.linearRampToValueAtTime(volume, t + attack)
  gain.gain.exponentialRampToValueAtTime(0.001, t + decay)

  osc.connect(gain)
  gain.connect(sfxDest())
  osc.start(t)
  osc.stop(t + decay + 0.02)
}

function noiseBurst(duration: number, volume = 0.1, filterFreq = 900) {
  if (muted) return
  const audio = getCtx()
  if (audio.state !== 'running') return

  const bufferSize = Math.floor(audio.sampleRate * duration)
  const buffer = audio.createBuffer(1, bufferSize, audio.sampleRate)
  const data = buffer.getChannelData(0)
  for (let i = 0; i < bufferSize; i++) {
    data[i] = (Math.random() * 2 - 1) * (1 - i / bufferSize)
  }

  const source = audio.createBufferSource()
  source.buffer = buffer

  const filter = audio.createBiquadFilter()
  filter.type = 'bandpass'
  filter.frequency.value = filterFreq
  filter.Q.value = 0.8

  const gain = audio.createGain()
  const t = audio.currentTime
  gain.gain.setValueAtTime(volume, t)
  gain.gain.exponentialRampToValueAtTime(0.001, t + duration)

  source.connect(filter)
  filter.connect(gain)
  gain.connect(sfxDest())
  source.start(t)
}

export function playBombPlace(): void {
  tone(90, 0.1, { type: 'sine', volume: 0.16, slideTo: 55 })
  noiseBurst(0.06, 0.06, 400)
  setTimeout(() => tone(420, 0.04, { type: 'square', volume: 0.06 }), 40)
}

export function playBombFuse(): void {
  tone(880, 0.03, { type: 'square', volume: 0.05 })
}

export function playExplosion(): void {
  noiseBurst(0.28, 0.18, 280)
  noiseBurst(0.18, 0.12, 700)
  tone(120, 0.22, { type: 'sawtooth', volume: 0.16, slideTo: 40 })
  tone(60, 0.3, { type: 'sine', volume: 0.14, slideTo: 28 })
}

export function playSoftDestroy(): void {
  noiseBurst(0.1, 0.08, 1100)
  tone(180, 0.08, { type: 'triangle', volume: 0.08, slideTo: 90 })
}

export function playPowerup(): void {
  tone(523, 0.06, { type: 'sine', volume: 0.12 })
  setTimeout(() => tone(659, 0.07, { type: 'sine', volume: 0.11 }), 50)
  setTimeout(() => tone(784, 0.1, { type: 'triangle', volume: 0.12 }), 100)
}

export function playDeath(): void {
  tone(280, 0.15, { type: 'sawtooth', volume: 0.14, slideTo: 120 })
  setTimeout(() => tone(160, 0.22, { type: 'sawtooth', volume: 0.12, slideTo: 70 }), 90)
  setTimeout(() => noiseBurst(0.15, 0.08, 500), 140)
}

export function playCountdownTick(): void {
  tone(760, 0.07, { type: 'square', volume: 0.12 })
}

export function playCountdownGo(): void {
  tone(523, 0.08, { type: 'square', volume: 0.14 })
  setTimeout(() => tone(784, 0.14, { type: 'triangle', volume: 0.16 }), 80)
}

export function playWin(): void {
  tone(392, 0.1, { type: 'square', volume: 0.12 })
  setTimeout(() => tone(523, 0.1, { type: 'square', volume: 0.13 }), 90)
  setTimeout(() => tone(659, 0.12, { type: 'square', volume: 0.14 }), 180)
  setTimeout(() => tone(784, 0.22, { type: 'triangle', volume: 0.16 }), 280)
}

export function playLose(): void {
  tone(330, 0.14, { type: 'sawtooth', volume: 0.12, slideTo: 220 })
  setTimeout(() => tone(220, 0.18, { type: 'sawtooth', volume: 0.1, slideTo: 140 }), 120)
  setTimeout(() => tone(140, 0.28, { type: 'triangle', volume: 0.1, slideTo: 80 }), 260)
}

export function disposeSounds(): void {
  if (ctx && ctx.state !== 'closed') {
    void ctx.close()
  }
  ctx = null
  masterGain = null
}
