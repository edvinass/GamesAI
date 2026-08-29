/** Procedural Monopoly sound effects (Web Audio API). */

let ctx: AudioContext | null = null
let masterGain: GainNode | null = null

const MASTER_VOLUME = 0.4
const SFX_VOLUME = 0.2
const MUTE_STORAGE_KEY = 'monopoly-sound-muted'

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

function alive(): AudioContext | null {
  if (muted) return null
  const audio = getCtx()
  if (audio.state !== 'running') return null
  return audio
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
  const audio = alive()
  if (!audio) return

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
    osc.frequency.exponentialRampToValueAtTime(Math.max(40, slideTo), t + decay)
  }

  gain.gain.setValueAtTime(0.001, t)
  gain.gain.linearRampToValueAtTime(volume, t + attack)
  gain.gain.exponentialRampToValueAtTime(0.001, t + Math.max(attack + 0.01, decay))

  osc.connect(gain)
  gain.connect(sfxDest())
  osc.start(t)
  osc.stop(t + decay + 0.03)
}

function noiseBurst(duration: number, volume = 0.08, filterFreq = 1200) {
  const audio = alive()
  if (!audio) return

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
  filter.Q.value = 0.85

  const gain = audio.createGain()
  const t = audio.currentTime
  gain.gain.setValueAtTime(volume, t)
  gain.gain.exponentialRampToValueAtTime(0.001, t + duration)

  source.connect(filter)
  filter.connect(gain)
  gain.connect(sfxDest())
  source.start(t)
}

/** Soft plastic dice tumble tick (call repeatedly while rolling). */
export function playDiceTick(): void {
  noiseBurst(0.03, 0.05, 2400)
  tone(180 + Math.random() * 80, 0.035, { volume: 0.05, type: 'triangle', decay: 0.03 })
}

/** Dice settle on the final faces. */
export function playDiceSettle(doubles = false): void {
  noiseBurst(0.05, 0.07, 1600)
  tone(280, 0.07, { volume: 0.09, type: 'triangle', decay: 0.08 })
  setTimeout(() => tone(360, 0.08, { volume: 0.07, type: 'sine', decay: 0.09 }), 40)
  if (doubles) {
    setTimeout(() => {
      tone(520, 0.08, { volume: 0.08, type: 'sine', decay: 0.09 })
      setTimeout(() => tone(660, 0.1, { volume: 0.07, type: 'sine', decay: 0.12 }), 70)
    }, 120)
  }
}

/** Token hop onto the next space. */
export function playTokenHop(): void {
  tone(420 + Math.random() * 40, 0.045, { volume: 0.07, type: 'triangle', decay: 0.05 })
  noiseBurst(0.02, 0.035, 1800)
}

/** Soft thump when landing on the final space. */
export function playLand(): void {
  tone(160, 0.09, { volume: 0.1, type: 'sine', decay: 0.11, slideTo: 110 })
  noiseBurst(0.04, 0.05, 900)
}

/** Cash register / coin for buying property. */
export function playBuy(): void {
  tone(880, 0.05, { volume: 0.1, type: 'sine', decay: 0.06 })
  setTimeout(() => tone(1175, 0.07, { volume: 0.09, type: 'sine', decay: 0.09 }), 45)
  setTimeout(() => tone(1568, 0.1, { volume: 0.07, type: 'triangle', decay: 0.12 }), 95)
}

/** Money gained. */
export function playCashGain(): void {
  tone(523, 0.06, { volume: 0.08, type: 'sine', decay: 0.07 })
  setTimeout(() => tone(784, 0.09, { volume: 0.08, type: 'sine', decay: 0.11 }), 55)
}

/** Money lost / rent paid. */
export function playCashLoss(): void {
  tone(320, 0.08, { volume: 0.08, type: 'triangle', decay: 0.1, slideTo: 180 })
  noiseBurst(0.05, 0.04, 600)
}

/** Card drawn from the deck (face-down slide). */
export function playCardDraw(chance = false): void {
  noiseBurst(0.06, 0.06, chance ? 2000 : 1100)
  const base = chance ? 494 : 349
  tone(base, 0.08, { volume: 0.09, type: 'triangle', decay: 0.1 })
  setTimeout(() => tone(base * 1.33, 0.12, { volume: 0.08, type: 'sine', decay: 0.14 }), 80)
}

/** Card flips face-up. */
export function playCardFlip(): void {
  noiseBurst(0.08, 0.07, 1400)
  tone(260, 0.05, { volume: 0.05, type: 'triangle', decay: 0.06, slideTo: 380 })
  setTimeout(() => tone(520, 0.07, { volume: 0.06, type: 'sine', decay: 0.09 }), 90)
}

/** Auction bid tap. */
export function playAuctionBid(): void {
  tone(740, 0.05, { volume: 0.1, type: 'square', decay: 0.06 })
  setTimeout(() => tone(990, 0.06, { volume: 0.07, type: 'triangle', decay: 0.07 }), 30)
}

/** Auction opens. */
export function playAuctionStart(): void {
  tone(392, 0.08, { volume: 0.09, type: 'triangle', decay: 0.1 })
  setTimeout(() => tone(523, 0.1, { volume: 0.08, type: 'sine', decay: 0.12 }), 90)
}

/** Sent to jail. */
export function playJail(): void {
  tone(220, 0.12, { volume: 0.1, type: 'square', decay: 0.14, slideTo: 140 })
  setTimeout(() => tone(110, 0.16, { volume: 0.09, type: 'sawtooth', decay: 0.18 }), 100)
  noiseBurst(0.08, 0.06, 500)
}

/** House / hotel placed. */
export function playBuild(): void {
  tone(349, 0.05, { volume: 0.08, type: 'triangle', decay: 0.06 })
  setTimeout(() => tone(440, 0.06, { volume: 0.08, type: 'triangle', decay: 0.07 }), 40)
  setTimeout(() => tone(554, 0.08, { volume: 0.07, type: 'sine', decay: 0.1 }), 85)
  noiseBurst(0.03, 0.04, 1400)
}

/** Player bankrupt. */
export function playBankrupt(): void {
  tone(392, 0.1, { volume: 0.09, type: 'triangle', decay: 0.12, slideTo: 196 })
  setTimeout(() => tone(196, 0.18, { volume: 0.1, type: 'sine', decay: 0.22, slideTo: 98 }), 120)
}

/** Game won. */
export function playWin(): void {
  tone(523, 0.1, { volume: 0.12, type: 'triangle', decay: 0.12 })
  setTimeout(() => tone(659, 0.1, { volume: 0.11, type: 'triangle', decay: 0.12 }), 100)
  setTimeout(() => tone(784, 0.12, { volume: 0.11, type: 'sine', decay: 0.14 }), 200)
  setTimeout(() => tone(1047, 0.2, { volume: 0.12, type: 'sine', decay: 0.24 }), 320)
}

/** Soft cue that it's your turn. */
export function playYourTurn(): void {
  tone(587, 0.07, { volume: 0.08, type: 'sine', decay: 0.08 })
  setTimeout(() => tone(784, 0.1, { volume: 0.08, type: 'sine', decay: 0.12 }), 90)
}

export function disposeSounds(): void {
  if (ctx && ctx.state !== 'closed') {
    void ctx.close()
  }
  ctx = null
  masterGain = null
}
