/** Procedural Side Duel sound effects (Web Audio API). */

let ctx: AudioContext | null = null
let masterGain: GainNode | null = null

const MASTER_VOLUME = 0.36
const SFX_VOLUME = 0.22
const MUTE_STORAGE_KEY = 'duel-sound-muted'

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
    detune?: number
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
    detune = 0,
  } = options

  const osc = audio.createOscillator()
  const gain = audio.createGain()
  osc.type = type
  osc.frequency.setValueAtTime(freq, audio.currentTime)
  osc.detune.setValueAtTime(detune, audio.currentTime)
  osc.connect(gain)
  gain.connect(sfxDest())

  const t = audio.currentTime
  gain.gain.setValueAtTime(0, t)
  gain.gain.linearRampToValueAtTime(volume, t + attack)
  gain.gain.exponentialRampToValueAtTime(0.001, t + decay)
  osc.start(t)
  osc.stop(t + decay + 0.02)
}

function noiseBurst(duration: number, volume = 0.08) {
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
  const gain = audio.createGain()
  source.buffer = buffer
  source.connect(gain)
  gain.connect(sfxDest())
  gain.gain.setValueAtTime(volume, audio.currentTime)
  gain.gain.exponentialRampToValueAtTime(0.001, audio.currentTime + duration)
  source.start()
}

export function playShootSound(charged = false): void {
  tone(charged ? 220 : 320, 0.08, { type: 'square', volume: 0.14 })
  tone(charged ? 440 : 520, 0.06, { type: 'triangle', volume: 0.1, detune: charged ? 80 : 0 })
}

export function playHitSound(crit = false): void {
  tone(crit ? 180 : 140, 0.12, { type: 'sawtooth', volume: crit ? 0.2 : 0.16 })
  noiseBurst(crit ? 0.08 : 0.05, crit ? 0.1 : 0.07)
}

export function playShieldBlockSound(): void {
  tone(880, 0.1, { type: 'sine', volume: 0.12 })
  tone(660, 0.14, { type: 'triangle', volume: 0.08 })
}

export function playPowerupCollectSound(): void {
  tone(520, 0.06, { type: 'sine', volume: 0.12 })
  tone(780, 0.08, { type: 'sine', volume: 0.1 })
  tone(1040, 0.1, { type: 'triangle', volume: 0.08 })
}

export function playPowerupActivateSound(tier: 'common' | 'rare' | 'epic' = 'common'): void {
  const scale = tier === 'epic' ? 1.35 : tier === 'rare' ? 1.1 : 1
  tone(330 * scale, 0.08, { type: 'sawtooth', volume: 0.1 })
  tone(660 * scale, tier === 'epic' ? 0.18 : 0.12, { type: 'square', volume: 0.12 })
  if (tier === 'epic') {
    tone(990, 0.22, { type: 'triangle', volume: 0.1 })
    tone(1320, 0.16, { type: 'sine', volume: 0.08 })
  } else if (tier === 'rare') {
    tone(990, 0.16, { type: 'triangle', volume: 0.08 })
  }
}

export function playArenaShrinkSound(): void {
  tone(90, 0.2, { type: 'sawtooth', volume: 0.14 })
  tone(60, 0.28, { type: 'square', volume: 0.1 })
}

export function playRoundWinSound(): void {
  tone(523, 0.1, { type: 'square', volume: 0.12 })
  tone(659, 0.1, { type: 'square', volume: 0.12 })
  tone(784, 0.16, { type: 'triangle', volume: 0.14 })
}

export function playHazardTickSound(): void {
  tone(120, 0.06, { type: 'sawtooth', volume: 0.08 })
}
