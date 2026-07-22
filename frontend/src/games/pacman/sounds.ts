/** Light Pac-Man SFX via Web Audio API. */

let ctx: AudioContext | null = null
let masterGain: GainNode | null = null

const MASTER_VOLUME = 0.36
const MUTE_STORAGE_KEY = 'pacman-sound-muted'

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

function alive(): AudioContext | null {
  if (muted) return null
  const audio = getCtx()
  if (audio.state !== 'running') return null
  return audio
}

function beep(freq: number, dur: number, type: OscillatorType = 'square', gain = 0.08) {
  const audio = alive()
  if (!audio || !masterGain) return
  const t0 = audio.currentTime
  const osc = audio.createOscillator()
  const g = audio.createGain()
  osc.type = type
  osc.frequency.setValueAtTime(freq, t0)
  g.gain.setValueAtTime(gain, t0)
  g.gain.exponentialRampToValueAtTime(0.001, t0 + dur)
  osc.connect(g)
  g.connect(masterGain)
  osc.start(t0)
  osc.stop(t0 + dur + 0.02)
}

export function playPellet() {
  beep(880, 0.04, 'square', 0.05)
}

export function playPower() {
  beep(220, 0.12, 'sawtooth', 0.07)
  beep(440, 0.18, 'square', 0.05)
}

export function playGhostEat() {
  beep(150, 0.2, 'triangle', 0.09)
  beep(300, 0.15, 'square', 0.05)
}

export function playDeath() {
  const audio = alive()
  if (!audio || !masterGain) return
  const t0 = audio.currentTime
  const osc = audio.createOscillator()
  const g = audio.createGain()
  osc.type = 'sawtooth'
  osc.frequency.setValueAtTime(480, t0)
  osc.frequency.exponentialRampToValueAtTime(80, t0 + 0.45)
  g.gain.setValueAtTime(0.1, t0)
  g.gain.exponentialRampToValueAtTime(0.001, t0 + 0.45)
  osc.connect(g)
  g.connect(masterGain)
  osc.start(t0)
  osc.stop(t0 + 0.5)
}

export function playWin() {
  beep(523, 0.1)
  setTimeout(() => beep(659, 0.1), 90)
  setTimeout(() => beep(784, 0.18), 180)
}

export function playLose() {
  beep(300, 0.15, 'triangle', 0.08)
  setTimeout(() => beep(200, 0.25, 'triangle', 0.08), 120)
}
