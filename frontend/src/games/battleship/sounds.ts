/** Procedural Battleship sound effects (Web Audio API). */

let ctx: AudioContext | null = null
let masterGain: GainNode | null = null

const MASTER_VOLUME = 0.4
const SFX_VOLUME = 0.2
const MUTE_STORAGE_KEY = 'battleship-sound-muted'

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
    slideTo?: number
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
    slideTo,
  } = options

  const osc = audio.createOscillator()
  const gain = audio.createGain()
  osc.type = type
  osc.frequency.value = freq
  osc.detune.value = detune

  const t = audio.currentTime
  if (slideTo != null) {
    osc.frequency.setValueAtTime(freq, t)
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

function noiseBurst(
  duration: number,
  volume = 0.1,
  filterFreq = 1200,
  filterType: BiquadFilterType = 'bandpass',
) {
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
  filter.type = filterType
  filter.frequency.value = filterFreq
  filter.Q.value = filterType === 'bandpass' ? 0.7 : 0.5

  const gain = audio.createGain()
  const t = audio.currentTime
  gain.gain.setValueAtTime(volume, t)
  gain.gain.exponentialRampToValueAtTime(0.001, t + duration)

  source.connect(filter)
  filter.connect(gain)
  gain.connect(sfxDest())
  source.start(t)
}

/** Soft thud when a ship segment drops onto the grid. */
export function playPlaceShip(): void {
  tone(140, 0.08, { volume: 0.1, type: 'triangle', decay: 0.1 })
  noiseBurst(0.04, 0.05, 600, 'lowpass')
}

export function playRemoveShip(): void {
  tone(220, 0.06, { volume: 0.07, type: 'sine', decay: 0.07, slideTo: 140 })
}

export function playAutoPlace(): void {
  tone(180, 0.05, { volume: 0.08, type: 'triangle' })
  setTimeout(() => tone(240, 0.05, { volume: 0.08, type: 'triangle' }), 40)
  setTimeout(() => tone(300, 0.07, { volume: 0.09, type: 'triangle' }), 85)
}

export function playReady(): void {
  tone(392, 0.08, { volume: 0.12, type: 'sine', decay: 0.1 })
  setTimeout(() => tone(523, 0.12, { volume: 0.12, type: 'sine', decay: 0.14 }), 90)
}

export function playBattleStart(): void {
  tone(196, 0.12, { volume: 0.12, type: 'triangle', decay: 0.14 })
  setTimeout(() => tone(247, 0.12, { volume: 0.12, type: 'triangle', decay: 0.14 }), 100)
  setTimeout(() => tone(330, 0.18, { volume: 0.14, type: 'sine', decay: 0.22 }), 200)
  setTimeout(() => noiseBurst(0.08, 0.06, 400, 'lowpass'), 280)
}

/** Cannon / launch whoosh when a shot is fired. */
export function playFire(): void {
  noiseBurst(0.1, 0.12, 900, 'bandpass')
  tone(120, 0.14, { volume: 0.14, type: 'sawtooth', decay: 0.16, slideTo: 55 })
  setTimeout(() => tone(80, 0.1, { volume: 0.08, type: 'sine', decay: 0.12 }), 40)
}

/** Water splash for a miss. */
export function playMiss(): void {
  noiseBurst(0.18, 0.14, 1400, 'bandpass')
  noiseBurst(0.22, 0.08, 500, 'lowpass')
  tone(280, 0.1, { volume: 0.06, type: 'sine', decay: 0.14, slideTo: 90 })
}

/** Explosive hit on a ship. */
export function playHit(): void {
  noiseBurst(0.16, 0.18, 700, 'lowpass')
  noiseBurst(0.1, 0.1, 2200, 'bandpass')
  tone(90, 0.2, { volume: 0.16, type: 'sawtooth', decay: 0.22, slideTo: 40 })
  setTimeout(() => tone(160, 0.08, { volume: 0.08, type: 'square', decay: 0.1 }), 50)
}

/** Bigger boom + descending tones when a ship sinks. */
export function playSink(): void {
  playHit()
  setTimeout(() => {
    noiseBurst(0.28, 0.16, 400, 'lowpass')
    tone(180, 0.25, { volume: 0.12, type: 'sawtooth', decay: 0.3, slideTo: 60 })
  }, 120)
  setTimeout(() => tone(110, 0.35, { volume: 0.1, type: 'triangle', decay: 0.4, slideTo: 40 }), 220)
  setTimeout(() => {
    tone(330, 0.1, { volume: 0.1, type: 'sine', decay: 0.12 })
    setTimeout(() => tone(247, 0.12, { volume: 0.09, type: 'sine', decay: 0.14 }), 90)
    setTimeout(() => tone(196, 0.18, { volume: 0.08, type: 'sine', decay: 0.22 }), 180)
  }, 280)
}

export function playYourTurn(): void {
  tone(440, 0.07, { volume: 0.09, type: 'sine', decay: 0.08 })
  setTimeout(() => tone(554, 0.1, { volume: 0.09, type: 'sine', decay: 0.12 }), 80)
}

export function playWin(): void {
  tone(392, 0.1, { volume: 0.12, type: 'triangle', decay: 0.12 })
  setTimeout(() => tone(494, 0.1, { volume: 0.12, type: 'triangle', decay: 0.12 }), 100)
  setTimeout(() => tone(587, 0.12, { volume: 0.13, type: 'sine', decay: 0.14 }), 200)
  setTimeout(() => tone(784, 0.22, { volume: 0.14, type: 'sine', decay: 0.28 }), 320)
}

export function playLose(): void {
  tone(220, 0.2, { volume: 0.12, type: 'triangle', decay: 0.25, slideTo: 140 })
  setTimeout(() => tone(165, 0.28, { volume: 0.1, type: 'sine', decay: 0.35, slideTo: 90 }), 160)
  setTimeout(() => noiseBurst(0.2, 0.07, 350, 'lowpass'), 240)
}

export function disposeSounds(): void {
  if (ctx && ctx.state !== 'closed') {
    void ctx.close()
  }
  ctx = null
  masterGain = null
}
