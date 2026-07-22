/** Classic-style Pac-Man SFX (procedural Web Audio). */

let ctx: AudioContext | null = null
let masterGain: GainNode | null = null

const MASTER_VOLUME = 0.4
const MUTE_STORAGE_KEY = 'pacman-sound-muted'

let muted = readMutedPreference()
let wakkaHigh = true
let lastWakkaAt = 0

let sirenNodes: { osc: OscillatorNode; gain: GainNode; lfo: OscillatorNode; stop: () => void } | null =
  null
let sirenMode: 'off' | 'normal' | 'fright' = 'off'

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
  if (muted) stopSiren()
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

function tone(
  freq: number,
  dur: number,
  type: OscillatorType = 'square',
  gain = 0.07,
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

/** Classic alternating wakka-wakka chomp. */
export function playPellet() {
  const now = performance.now()
  if (now - lastWakkaAt < 55) return
  lastWakkaAt = now
  const freq = wakkaHigh ? 740 : 520
  wakkaHigh = !wakkaHigh
  tone(freq, 0.055, 'square', 0.055)
}

export function playPower() {
  // Short rising whoop into fright energy.
  tone(180, 0.08, 'square', 0.08, 360)
  setTimeout(() => tone(360, 0.1, 'square', 0.06, 520), 70)
  setTimeout(() => tone(200, 0.16, 'triangle', 0.05), 140)
}

export function playGhostEat() {
  // Ascending eat-ghost blips.
  const steps = [300, 400, 520, 680]
  steps.forEach((f, i) => {
    setTimeout(() => tone(f, 0.09, 'square', 0.07), i * 55)
  })
}

export function playPacEat() {
  tone(220, 0.08, 'square', 0.07)
  setTimeout(() => tone(160, 0.12, 'sawtooth', 0.05), 70)
}

export function playDeath() {
  const audio = alive()
  if (!audio || !masterGain) return
  stopSiren()
  const t0 = audio.currentTime
  // Descending cascade like the arcade death jingle.
  const notes = [740, 700, 660, 620, 580, 520, 460, 400, 340, 280, 220, 160]
  notes.forEach((f, i) => {
    const osc = audio.createOscillator()
    const g = audio.createGain()
    const start = t0 + i * 0.055
    osc.type = 'square'
    osc.frequency.setValueAtTime(f, start)
    g.gain.setValueAtTime(0.08, start)
    g.gain.exponentialRampToValueAtTime(0.001, start + 0.08)
    osc.connect(g)
    g.connect(masterGain!)
    osc.start(start)
    osc.stop(start + 0.1)
  })
}

export function playStartJingle() {
  const melody = [
    [523, 0],
    [659, 90],
    [784, 180],
    [1046, 280],
    [784, 420],
    [1046, 520],
  ] as const
  for (const [f, delay] of melody) {
    setTimeout(() => tone(f, 0.1, 'square', 0.06), delay)
  }
}

export function playWin() {
  stopSiren()
  ;[523, 659, 784, 1046].forEach((f, i) => {
    setTimeout(() => tone(f, 0.12, 'square', 0.07), i * 100)
  })
}

export function playLose() {
  stopSiren()
  ;[392, 330, 262].forEach((f, i) => {
    setTimeout(() => tone(f, 0.16, 'triangle', 0.07), i * 140)
  })
}

export function playCountdownTick() {
  tone(660, 0.06, 'square', 0.045)
}

export function playCountdownGo() {
  tone(880, 0.12, 'square', 0.06)
  setTimeout(() => playStartJingle(), 80)
}

function stopSiren() {
  if (sirenNodes) {
    try {
      sirenNodes.stop()
    } catch {
      /* ignore */
    }
    sirenNodes = null
  }
  sirenMode = 'off'
}

/** Looping chase / frightened siren. */
export function setSirenMode(mode: 'off' | 'normal' | 'fright') {
  if (muted || mode === 'off') {
    stopSiren()
    return
  }
  if (sirenMode === mode && sirenNodes) return
  stopSiren()

  const audio = alive()
  if (!audio || !masterGain) return

  const osc = audio.createOscillator()
  const lfo = audio.createOscillator()
  const lfoGain = audio.createGain()
  const g = audio.createGain()

  osc.type = 'triangle'
  lfo.type = 'sine'

  if (mode === 'fright') {
    osc.frequency.setValueAtTime(180, audio.currentTime)
    lfo.frequency.setValueAtTime(8, audio.currentTime)
    lfoGain.gain.setValueAtTime(40, audio.currentTime)
    g.gain.setValueAtTime(0.028, audio.currentTime)
  } else {
    osc.frequency.setValueAtTime(110, audio.currentTime)
    lfo.frequency.setValueAtTime(2.2, audio.currentTime)
    lfoGain.gain.setValueAtTime(18, audio.currentTime)
    g.gain.setValueAtTime(0.022, audio.currentTime)
  }

  lfo.connect(lfoGain)
  lfoGain.connect(osc.frequency)
  osc.connect(g)
  g.connect(masterGain)
  osc.start()
  lfo.start()

  sirenNodes = {
    osc,
    gain: g,
    lfo,
    stop: () => {
      try {
        osc.stop()
        lfo.stop()
      } catch {
        /* ignore */
      }
      osc.disconnect()
      lfo.disconnect()
      g.disconnect()
      lfoGain.disconnect()
    },
  }
  sirenMode = mode
}
