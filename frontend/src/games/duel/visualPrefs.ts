const SHAKE_KEY = 'duel-shake-intensity'
const COLORBLIND_KEY = 'duel-colorblind'
const HITSTOP_KEY = 'duel-hit-stop'
const AUTO_RELEASE_KEY = 'duel-auto-release-powerup'
const DANGER_LEGEND_KEY = 'duel-danger-legend-seen'

export function loadShakeIntensity(): number {
  try {
    const raw = localStorage.getItem(SHAKE_KEY)
    if (raw == null) return 1
    const val = Number(raw)
    return Number.isFinite(val) ? Math.max(0, Math.min(1, val)) : 1
  } catch {
    return 1
  }
}

export function saveShakeIntensity(value: number): void {
  try {
    localStorage.setItem(SHAKE_KEY, String(Math.max(0, Math.min(1, value))))
  } catch {
    /* ignore */
  }
}

export function isColorblindMode(): boolean {
  try {
    return localStorage.getItem(COLORBLIND_KEY) === '1'
  } catch {
    return false
  }
}

export function setColorblindMode(value: boolean): void {
  try {
    localStorage.setItem(COLORBLIND_KEY, value ? '1' : '0')
  } catch {
    /* ignore */
  }
}

export function isHitStopEnabled(): boolean {
  try {
    return localStorage.getItem(HITSTOP_KEY) !== '0'
  } catch {
    return true
  }
}

export function setHitStopEnabled(value: boolean): void {
  try {
    localStorage.setItem(HITSTOP_KEY, value ? '1' : '0')
  } catch {
    /* ignore */
  }
}

export function isAutoReleasePowerupEnabled(): boolean {
  try {
    return localStorage.getItem(AUTO_RELEASE_KEY) !== '0'
  } catch {
    return true
  }
}

export function setAutoReleasePowerupEnabled(value: boolean): void {
  try {
    localStorage.setItem(AUTO_RELEASE_KEY, value ? '1' : '0')
  } catch {
    /* ignore */
  }
}

export function hasSeenDangerLegend(): boolean {
  try {
    return localStorage.getItem(DANGER_LEGEND_KEY) === '1'
  } catch {
    return false
  }
}

export function markDangerLegendSeen(): void {
  try {
    localStorage.setItem(DANGER_LEGEND_KEY, '1')
  } catch {
    /* ignore */
  }
}
