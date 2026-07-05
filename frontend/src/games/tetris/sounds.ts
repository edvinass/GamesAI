/** Procedural retro sound effects and background music for Tetris (Web Audio API). */

let ctx: AudioContext | null = null
let masterGain: GainNode | null = null
let musicGain: GainNode | null = null
let musicTimer: ReturnType<typeof setInterval> | null = null
let musicStep = 0

const MASTER_VOLUME = 0.35
const MUSIC_VOLUME = 0.08
const SFX_VOLUME = 0.22
const MUTE_STORAGE_KEY = 'tetris-sound-muted'

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
    /* ignore storage errors */
  }
  getCtx()
  applyMasterVolume()
  if (value) stopBackgroundMusic()
}

function getCtx(): AudioContext {
  if (!ctx) {
    ctx = new AudioContext()
    masterGain = ctx.createGain()
    masterGain.connect(ctx.destination)
    applyMasterVolume()

    musicGain = ctx.createGain()
    musicGain.gain.value = MUSIC_VOLUME
    musicGain.connect(masterGain!)
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
    attack = 0.005,
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

function noiseBurst(duration: number, volume = 0.12, filterFreq = 800) {
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
  filter.type = 'lowpass'
  filter.frequency.value = filterFreq

  const gain = audio.createGain()
  const t = audio.currentTime
  gain.gain.setValueAtTime(volume, t)
  gain.gain.exponentialRampToValueAtTime(0.001, t + duration)

  source.connect(filter)
  filter.connect(gain)
  gain.connect(sfxDest())
  source.start(t)
}

function arpeggio(notes: number[], noteLen = 0.07, volume = SFX_VOLUME) {
  notes.forEach((freq, i) => {
    setTimeout(() => {
      tone(freq, noteLen * 0.9, { volume, attack: 0.003, decay: noteLen, type: 'triangle' })
    }, i * noteLen * 1000)
  })
}

export function playMove(): void {
  tone(180, 0.04, { volume: 0.1, type: 'square' })
}

export function playRotate(): void {
  tone(320, 0.05, { volume: 0.12, type: 'square' })
  setTimeout(() => tone(420, 0.04, { volume: 0.08, type: 'square' }), 25)
}

export function playSoftDrop(): void {
  tone(140, 0.03, { volume: 0.06, type: 'square' })
}

export function playHardDrop(): void {
  noiseBurst(0.08, 0.1, 1200)
  tone(90, 0.12, { volume: 0.18, type: 'sine' })
}

export function playLock(): void {
  tone(110, 0.1, { volume: 0.14, type: 'triangle' })
  tone(55, 0.15, { volume: 0.1, type: 'sine' })
}

export function playLineClear(lines: number): void {
  const base = 330
  const intervals = [0, 4, 7, 12, 16]
  const count = Math.min(lines, 4)
  const notes = intervals.slice(0, count + 1).map((semi) => base * 2 ** (semi / 12))

  if (lines >= 4) {
    arpeggio([262, 330, 392, 523, 659, 784], 0.09, 0.2)
    setTimeout(() => tone(1047, 0.25, { volume: 0.22, type: 'square', decay: 0.3 }), 450)
  } else {
    arpeggio(notes, 0.08, 0.16 + lines * 0.02)
  }
}

export function playLevelUp(): void {
  arpeggio([392, 494, 587, 784, 988], 0.1, 0.18)
}

export function playDeath(): void {
  tone(220, 0.2, { volume: 0.15, type: 'sawtooth', decay: 0.35 })
  setTimeout(() => tone(165, 0.25, { volume: 0.12, type: 'sawtooth', decay: 0.4 }), 120)
  setTimeout(() => tone(98, 0.4, { volume: 0.1, type: 'sawtooth', decay: 0.5 }), 280)
}

export function playCountdownTick(): void {
  tone(880, 0.06, { volume: 0.14, type: 'square' })
}

export function playCountdownGo(): void {
  arpeggio([523, 659, 784], 0.08, 0.2)
}

export function playGameOver(): void {
  arpeggio([392, 330, 262, 196], 0.15, 0.14)
}

// Korobeiniki-inspired melody (public domain folk tune), one octave up for chiptune feel
const MELODY = [
  659, 494, 523, 587, 523, 494, 440, 440, 523, 659, 587, 523, 494, 523, 587, 523, 494,
  659, 494, 523, 587, 523, 494, 440, 440, 523, 659, 587, 523, 587, 659, 587, 523, 494,
]
const MELODY_TEMPO_MS = 180

function playMusicNote(freq: number) {
  if (muted) return
  const audio = getCtx()
  if (audio.state !== 'running' || !musicGain) return

  const osc = audio.createOscillator()
  const gain = audio.createGain()
  osc.type = 'square'
  osc.frequency.value = freq

  const t = audio.currentTime
  const dur = MELODY_TEMPO_MS / 1000 * 0.85
  gain.gain.setValueAtTime(0.001, t)
  gain.gain.linearRampToValueAtTime(1, t + 0.01)
  gain.gain.setValueAtTime(0.7, t + dur * 0.6)
  gain.gain.exponentialRampToValueAtTime(0.001, t + dur)

  osc.connect(gain)
  gain.connect(musicGain)
  osc.start(t)
  osc.stop(t + dur + 0.02)
}

export function startBackgroundMusic(): void {
  if (muted) return
  stopBackgroundMusic()
  musicStep = 0
  playMusicNote(MELODY[0]!)
  musicStep = 1

  musicTimer = setInterval(() => {
    playMusicNote(MELODY[musicStep % MELODY.length]!)
    musicStep++
  }, MELODY_TEMPO_MS)
}

export function stopBackgroundMusic(): void {
  if (musicTimer) {
    clearInterval(musicTimer)
    musicTimer = null
  }
}

export function disposeSounds(): void {
  stopBackgroundMusic()
  if (ctx && ctx.state !== 'closed') {
    void ctx.close()
  }
  ctx = null
  masterGain = null
  musicGain = null
}
