/** Procedural solitaire card sound effects (Web Audio API). */

let ctx: AudioContext | null = null
let masterGain: GainNode | null = null

const MASTER_VOLUME = 0.4
const SFX_VOLUME = 0.18
const MUTE_STORAGE_KEY = 'solitaire-sound-muted'

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

/** Soft paper scrape when lifting a card. */
export function playPickup(): void {
  noiseBurst(0.03, 0.045, 2200)
  tone(280, 0.04, { volume: 0.04, type: 'triangle', decay: 0.035 })
}

/** Draw from stock onto the waste. */
export function playDraw(): void {
  noiseBurst(0.05, 0.07, 1900)
  tone(260, 0.055, { volume: 0.06, type: 'triangle', decay: 0.045 })
  setTimeout(() => tone(210, 0.04, { volume: 0.04, type: 'sine', decay: 0.04 }), 28)
}

/** Place a card or pile onto the tableau. */
export function playPlace(): void {
  noiseBurst(0.04, 0.06, 1400)
  tone(190, 0.06, { volume: 0.07, type: 'triangle', decay: 0.05 })
}

/** Move a card onto its foundation. */
export function playFoundation(): void {
  noiseBurst(0.035, 0.05, 1600)
  tone(392, 0.07, { volume: 0.09, type: 'triangle', decay: 0.08 })
  setTimeout(() => tone(523, 0.09, { volume: 0.07, type: 'sine', decay: 0.1 }), 55)
}

/** Recycle waste back into the stock. */
export function playRecycle(): void {
  noiseBurst(0.08, 0.06, 900)
  tone(180, 0.08, { volume: 0.06, type: 'sine', decay: 0.09 })
  setTimeout(() => {
    noiseBurst(0.05, 0.05, 1100)
    tone(220, 0.06, { volume: 0.05, type: 'triangle', decay: 0.06 })
  }, 70)
}

/** Fresh deal / new game. */
export function playDeal(): void {
  const gaps = [0, 40, 75, 105, 140]
  for (const delay of gaps) {
    setTimeout(() => {
      noiseBurst(0.035, 0.05, 1700)
      tone(240 + delay * 0.4, 0.04, { volume: 0.045, type: 'triangle', decay: 0.035 })
    }, delay)
  }
}

/** Auto-complete cascade onto foundations. */
export function playAutoComplete(): void {
  const notes = [392, 440, 494, 523, 587, 659]
  notes.forEach((freq, i) => {
    setTimeout(() => {
      tone(freq, 0.08, { volume: 0.08, type: 'triangle', decay: 0.09 })
      if (i % 2 === 0) noiseBurst(0.025, 0.035, 1500)
    }, i * 70)
  })
}

/** Win fanfare. */
export function playWin(): void {
  const notes = [523, 659, 784, 1047]
  notes.forEach((freq, i) => {
    setTimeout(() => {
      tone(freq, 0.14, { volume: 0.12 - i * 0.01, type: 'triangle', decay: 0.16 })
    }, i * 110)
  })
  setTimeout(() => {
    tone(784, 0.22, { volume: 0.1, type: 'sine', decay: 0.28 })
    tone(1047, 0.22, { volume: 0.08, type: 'sine', decay: 0.28, detune: 6 })
  }, 480)
}

export function playActionSound(type: string): void {
  switch (type) {
    case 'draw':
      playDraw()
      break
    case 'reset_stock':
      playRecycle()
      break
    case 'move_to_foundation':
      playFoundation()
      break
    case 'move_to_tableau':
      playPlace()
      break
    case 'auto_complete':
      playAutoComplete()
      break
    case 'new_game':
      playDeal()
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
