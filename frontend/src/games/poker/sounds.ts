/** Procedural poker sound effects (Web Audio API). */

let ctx: AudioContext | null = null
let masterGain: GainNode | null = null

const MASTER_VOLUME = 0.38
const SFX_VOLUME = 0.2
const MUTE_STORAGE_KEY = 'poker-sound-muted'

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
    type = 'sine',
    volume = SFX_VOLUME,
    attack = 0.004,
    decay = duration,
    detune = 0,
  } = options

  const osc = audio.createOscillator()
  const gain = audio.createGain()
  osc.type = type
  osc.frequency.value = freq
  osc.detune.value = detune

  const t = audio.currentTime
  gain.gain.setValueAtTime(0.001, t)
  gain.gain.linearRampToValueAtTime(volume, t + attack)
  gain.gain.exponentialRampToValueAtTime(0.001, t + decay)

  osc.connect(gain)
  gain.connect(sfxDest())
  osc.start(t)
  osc.stop(t + decay + 0.02)
}

function noiseBurst(duration: number, volume = 0.08, filterFreq = 1200) {
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

/** Card leaves the deck / lands on the felt. */
export function playDealCard(): void {
  noiseBurst(0.045, 0.07, 1800)
  tone(240, 0.05, { volume: 0.06, type: 'triangle', decay: 0.04 })
}

/** Burn card before a street. */
export function playBurnCard(): void {
  noiseBurst(0.06, 0.05, 900)
  tone(160, 0.07, { volume: 0.05, type: 'sine', decay: 0.06 })
}

/** Chips sliding into the pot. */
export function playChipBet(strong = false): void {
  const vol = strong ? 0.16 : 0.11
  tone(880, 0.04, { volume: vol, type: 'sine', decay: 0.05 })
  setTimeout(() => tone(1180, 0.035, { volume: vol * 0.75, type: 'sine', decay: 0.04 }), 18)
  if (strong) {
    setTimeout(() => tone(660, 0.05, { volume: vol * 0.6, type: 'triangle', decay: 0.06 }), 40)
  }
}

export function playCheck(): void {
  tone(320, 0.03, { volume: 0.08, type: 'triangle', decay: 0.035 })
}

export function playFold(): void {
  noiseBurst(0.07, 0.06, 700)
  tone(180, 0.1, { volume: 0.07, type: 'sine', decay: 0.12 })
}

export function playStreetReveal(street: 'flop' | 'turn' | 'river'): void {
  const base = street === 'flop' ? 392 : street === 'turn' ? 440 : 494
  tone(base, 0.08, { volume: 0.1, type: 'triangle', decay: 0.1 })
  setTimeout(() => tone(base * 1.25, 0.1, { volume: 0.08, type: 'sine', decay: 0.12 }), 70)
}

export function playShowdownFlip(): void {
  noiseBurst(0.035, 0.05, 2000)
  tone(300, 0.05, { volume: 0.07, type: 'triangle', decay: 0.05 })
}

export function playYourTurn(): void {
  tone(523, 0.07, { volume: 0.09, type: 'sine', decay: 0.08 })
  setTimeout(() => tone(659, 0.09, { volume: 0.08, type: 'sine', decay: 0.1 }), 80)
}

export function playWin(): void {
  tone(523, 0.1, { volume: 0.14, type: 'triangle', decay: 0.12 })
  setTimeout(() => tone(659, 0.1, { volume: 0.13, type: 'triangle', decay: 0.12 }), 90)
  setTimeout(() => tone(784, 0.16, { volume: 0.12, type: 'sine', decay: 0.2 }), 180)
  setTimeout(() => playChipBet(true), 260)
}

export function playActionSound(type: string): void {
  switch (type) {
    case 'fold':
      playFold()
      break
    case 'check':
      playCheck()
      break
    case 'call':
      playChipBet(false)
      break
    case 'raise':
      playChipBet(true)
      break
    case 'all_in':
      playChipBet(true)
      break
    default:
      break
  }
}

export function disposeSounds(): void {
  if (ctx && ctx.state !== 'closed') {
    void ctx.close()
  }
  ctx = null
  masterGain = null
}
