import type {
  BombermanBomb,
  BombermanBomber,
  BombermanExplosion,
  BombermanPowerup,
} from '@/types'

export const TILE_EMPTY = 0
export const TILE_HARD = 1
export const TILE_SOFT = 2

export interface BomberSnapshot {
  x: number
  y: number
  alive: boolean
  color: string
  direction: string
  disease?: string | null
  respawn_ticks?: number
}

export interface SmoothBomber extends BomberSnapshot {
  /** Cells advanced this tick (for walk-cycle animation). */
  speed: number
}

export interface Particle {
  x: number
  y: number
  vx: number
  vy: number
  life: number
  maxLife: number
  color: string
  size: number
  gravity?: number
  kind?: 'ember' | 'debris' | 'spark' | 'smoke'
}

export interface RenderFrameInput {
  gridW: number
  gridH: number
  grid: number[][]
  bombers: Record<
    string,
    {
      x: number
      y: number
      alive: boolean
      color: string
      direction: string
      speed?: number
      disease?: string | null
      respawn_ticks?: number
    }
  >
  bombs: BombermanBomb[]
  explosions: BombermanExplosion[]
  powerups: BombermanPowerup[]
  playerId: string
  time: number
  particles?: Particle[]
  shake?: number
  mapId?: string
  /** 0–1 strength of the local-player ground marker (countdown / early play). */
  selfMarker?: number
  /** Optional camera focus in cell coords (spectate pan). Defaults to local bomber. */
  focusX?: number
  focusY?: number
}

export type SoftBlockStyle = 'brick' | 'crate' | 'ice' | 'hedge' | 'wood' | 'stone'
export type HardBlockStyle = 'steel' | 'stone' | 'crystal' | 'rust' | 'sandstone'

export interface MapTheme {
  id: string
  floorTop: string
  floorBottom: string
  checker: string
  tileInset: string
  vignette: string
  hard: [string, string, string]
  soft: [string, string, string]
  softStroke: string
  softSheen: string
  hardStyle: HardBlockStyle
  softStyle: SoftBlockStyle
  debris: string[]
  accent: string
  accentRgb: string
  glow: string
  wrapTop: string
  wrapBottom: string
}

const CLASSIC_THEME: MapTheme = {
  id: 'classic',
  floorTop: '#1c2838',
  floorBottom: '#121a24',
  checker: 'rgba(255,255,255,0.025)',
  tileInset: 'rgba(0,0,0,0.12)',
  vignette: 'rgba(0,0,0,0.28)',
  hard: ['#5a6578', '#3d4656', '#2a3140'],
  soft: ['#e09a55', '#c47432', '#8f4a1c'],
  softStroke: 'rgba(60, 28, 8, 0.5)',
  softSheen: 'rgba(255,220,160,0.12)',
  hardStyle: 'steel',
  softStyle: 'brick',
  debris: ['#c47a3a', '#a05a28', '#d4924e', '#6b3a18'],
  accent: '#f97316',
  accentRgb: '249, 115, 22',
  glow: 'rgba(255, 120, 40, 0.16)',
  wrapTop: '#101820',
  wrapBottom: '#0a0e14',
}

export const MAP_THEMES: Record<string, MapTheme> = {
  classic: CLASSIC_THEME,
  open_field: {
    id: 'open_field',
    floorTop: '#2a2418',
    floorBottom: '#1a1610',
    checker: 'rgba(255,210,140,0.04)',
    tileInset: 'rgba(0,0,0,0.14)',
    vignette: 'rgba(40,28,10,0.32)',
    hard: ['#9a8b6e', '#6f6350', '#4a4236'],
    soft: ['#d4a574', '#b8844a', '#8a5c2e'],
    softStroke: 'rgba(70, 40, 16, 0.55)',
    softSheen: 'rgba(255,230,180,0.14)',
    hardStyle: 'sandstone',
    softStyle: 'crate',
    debris: ['#c4965a', '#a07438', '#e0b878', '#6e4820'],
    accent: '#d4a017',
    accentRgb: '212, 160, 23',
    glow: 'rgba(212, 160, 23, 0.14)',
    wrapTop: '#1c1810',
    wrapBottom: '#0e0c08',
  },
  crossroads: {
    id: 'crossroads',
    floorTop: '#1a1e24',
    floorBottom: '#0e1218',
    checker: 'rgba(180,200,220,0.035)',
    tileInset: 'rgba(0,0,0,0.16)',
    vignette: 'rgba(0,0,0,0.34)',
    hard: ['#6a7380', '#4a5360', '#2e3540'],
    soft: ['#8a919c', '#6a717c', '#4a515c'],
    softStroke: 'rgba(20, 24, 30, 0.55)',
    softSheen: 'rgba(220,230,240,0.1)',
    hardStyle: 'stone',
    softStyle: 'stone',
    debris: ['#7a818c', '#5a616c', '#9aa1ac', '#3a414c'],
    accent: '#94a3b8',
    accentRgb: '148, 163, 184',
    glow: 'rgba(148, 163, 184, 0.12)',
    wrapTop: '#12161c',
    wrapBottom: '#080a0e',
  },
  fortress: {
    id: 'fortress',
    floorTop: '#1a1c18',
    floorBottom: '#0e100e',
    checker: 'rgba(120,160,100,0.03)',
    tileInset: 'rgba(0,0,0,0.18)',
    vignette: 'rgba(0,0,0,0.38)',
    hard: ['#4a5248', '#323a32', '#1e241e'],
    soft: ['#6b5a3e', '#4e422c', '#342c1c'],
    softStroke: 'rgba(20, 30, 16, 0.55)',
    softSheen: 'rgba(160,200,120,0.08)',
    hardStyle: 'stone',
    softStyle: 'crate',
    debris: ['#5a4a30', '#3e3420', '#7a6a48', '#2a2418'],
    accent: '#84cc16',
    accentRgb: '132, 204, 22',
    glow: 'rgba(100, 140, 60, 0.14)',
    wrapTop: '#121410',
    wrapBottom: '#080a08',
  },
  labyrinth: {
    id: 'labyrinth',
    floorTop: '#1c1624',
    floorBottom: '#100e18',
    checker: 'rgba(180,140,220,0.035)',
    tileInset: 'rgba(0,0,0,0.16)',
    vignette: 'rgba(20,10,30,0.4)',
    hard: ['#5a4a68', '#3e3450', '#2a2438'],
    soft: ['#6b5a3e', '#4a3e2a', '#2e2618'],
    softStroke: 'rgba(40, 24, 50, 0.55)',
    softSheen: 'rgba(200,160,255,0.08)',
    hardStyle: 'stone',
    softStyle: 'hedge',
    debris: ['#5a4a30', '#3e3420', '#7a5a90', '#2a2038'],
    accent: '#a855f7',
    accentRgb: '168, 85, 247',
    glow: 'rgba(168, 85, 247, 0.14)',
    wrapTop: '#141018',
    wrapBottom: '#0a0810',
  },
  islands: {
    id: 'islands',
    floorTop: '#143038',
    floorBottom: '#0a1c24',
    checker: 'rgba(80,200,200,0.04)',
    tileInset: 'rgba(0,20,30,0.18)',
    vignette: 'rgba(0,20,30,0.36)',
    hard: ['#5a7068', '#3e5248', '#2a3a34'],
    soft: ['#c4a06a', '#a07840', '#6e5028'],
    softStroke: 'rgba(40, 28, 12, 0.5)',
    softSheen: 'rgba(255,230,180,0.12)',
    hardStyle: 'stone',
    softStyle: 'wood',
    debris: ['#b89050', '#8a6830', '#d4b078', '#5a4020'],
    accent: '#14b8a6',
    accentRgb: '20, 184, 166',
    glow: 'rgba(20, 184, 166, 0.14)',
    wrapTop: '#0e2028',
    wrapBottom: '#061018',
  },
  diamond: {
    id: 'diamond',
    floorTop: '#142028',
    floorBottom: '#0a141c',
    checker: 'rgba(120,220,255,0.04)',
    tileInset: 'rgba(0,40,60,0.14)',
    vignette: 'rgba(0,30,50,0.34)',
    hard: ['#6ec8e8', '#3a9abc', '#206880'],
    soft: ['#b8e0f0', '#7ab8d0', '#4a88a0'],
    softStroke: 'rgba(20, 60, 80, 0.5)',
    softSheen: 'rgba(220,250,255,0.22)',
    hardStyle: 'crystal',
    softStyle: 'ice',
    debris: ['#8ad0e8', '#5aa8c0', '#c0e8f4', '#3a7890'],
    accent: '#22d3ee',
    accentRgb: '34, 211, 238',
    glow: 'rgba(34, 211, 238, 0.14)',
    wrapTop: '#0e1a22',
    wrapBottom: '#060e14',
  },
  narrows: {
    id: 'narrows',
    floorTop: '#241818',
    floorBottom: '#140c0c',
    checker: 'rgba(255,100,60,0.03)',
    tileInset: 'rgba(0,0,0,0.2)',
    vignette: 'rgba(40,10,0,0.42)',
    hard: ['#8a5040', '#5e3428', '#3a2018'],
    soft: ['#a06040', '#7a4030', '#4e2818'],
    softStroke: 'rgba(50, 18, 10, 0.6)',
    softSheen: 'rgba(255,160,100,0.1)',
    hardStyle: 'rust',
    softStyle: 'crate',
    debris: ['#a05030', '#7a3820', '#c07048', '#4a2010'],
    accent: '#ef4444',
    accentRgb: '239, 68, 68',
    glow: 'rgba(239, 68, 68, 0.14)',
    wrapTop: '#1a1010',
    wrapBottom: '#0c0606',
  },
  arena: {
    id: 'arena',
    floorTop: '#2a2218',
    floorBottom: '#18140e',
    checker: 'rgba(255,200,120,0.04)',
    tileInset: 'rgba(0,0,0,0.14)',
    vignette: 'rgba(30,20,8,0.3)',
    hard: ['#b09a78', '#80705a', '#54483a'],
    soft: ['#d4b080', '#b08850', '#7a5830'],
    softStroke: 'rgba(60, 40, 16, 0.5)',
    softSheen: 'rgba(255,230,180,0.14)',
    hardStyle: 'sandstone',
    softStyle: 'brick',
    debris: ['#c4a060', '#9a7840', '#e0c088', '#6a5028'],
    accent: '#f59e0b',
    accentRgb: '245, 158, 11',
    glow: 'rgba(245, 158, 11, 0.14)',
    wrapTop: '#1c1610',
    wrapBottom: '#0e0a08',
  },
}

export function getMapTheme(mapId?: string | null): MapTheme {
  if (mapId && MAP_THEMES[mapId]) return MAP_THEMES[mapId]!
  return CLASSIC_THEME
}

/** Preferred on-screen window in cells — slight zoom-out from classic 15×13. */
const VIEW_COLS = 21
const VIEW_ROWS = 17

function cellSize(displayW: number, displayH: number, gridW: number, gridH: number) {
  // Cover a slightly wider window so a few more tiles stay visible while filling the canvas.
  // If the whole map fits in that window, contain-fit instead so edges aren't cropped.
  const cols = Math.min(gridW, VIEW_COLS)
  const rows = Math.min(gridH, VIEW_ROWS)
  if (gridW <= VIEW_COLS && gridH <= VIEW_ROWS) {
    return Math.max(1, Math.floor(Math.min(displayW / gridW, displayH / gridH)))
  }
  return Math.max(1, Math.ceil(Math.max(displayW / cols, displayH / rows)))
}

function cameraOffset(
  displayW: number,
  displayH: number,
  gridW: number,
  gridH: number,
  s: number,
  focusX: number,
  focusY: number,
): { ox: number; oy: number } {
  const boardW = s * gridW
  const boardH = s * gridH

  let ox: number
  if (boardW <= displayW) {
    ox = Math.floor((displayW - boardW) / 2)
  } else {
    // Keep focus cell centered; clamp so the camera never leaves the map.
    ox = Math.floor(displayW / 2 - (focusX + 0.5) * s)
    ox = Math.max(displayW - boardW, Math.min(0, ox))
  }

  let oy: number
  if (boardH <= displayH) {
    oy = Math.floor((displayH - boardH) / 2)
  } else {
    oy = Math.floor(displayH / 2 - (focusY + 0.5) * s)
    oy = Math.max(displayH - boardH, Math.min(0, oy))
  }

  return { ox, oy }
}

function visibleTileRange(
  displayW: number,
  displayH: number,
  gridW: number,
  gridH: number,
  s: number,
  ox: number,
  oy: number,
): { x0: number; x1: number; y0: number; y1: number } {
  const pad = 1
  const x0 = Math.max(0, Math.floor(-ox / s) - pad)
  const y0 = Math.max(0, Math.floor(-oy / s) - pad)
  const x1 = Math.min(gridW, Math.ceil((displayW - ox) / s) + pad)
  const y1 = Math.min(gridH, Math.ceil((displayH - oy) / s) + pad)
  return { x0, x1, y0, y1 }
}

function drawRoundRect(
  ctx: CanvasRenderingContext2D,
  x: number,
  y: number,
  w: number,
  h: number,
  r: number,
) {
  const radius = Math.min(r, w / 2, h / 2)
  ctx.beginPath()
  ctx.moveTo(x + radius, y)
  ctx.arcTo(x + w, y, x + w, y + h, radius)
  ctx.arcTo(x + w, y + h, x, y + h, radius)
  ctx.arcTo(x, y + h, x, y, radius)
  ctx.arcTo(x, y, x + w, y, radius)
  ctx.closePath()
}

function hexToRgb(hex: string): [number, number, number] {
  const h = hex.replace('#', '')
  const full = h.length === 3 ? h.split('').map((c) => c + c).join('') : h
  const n = parseInt(full.slice(0, 6), 16)
  return [(n >> 16) & 255, (n >> 8) & 255, n & 255]
}

function rgba(hex: string, a: number): string {
  const [r, g, b] = hexToRgb(hex)
  return `rgba(${r},${g},${b},${a})`
}

function shade(hex: string, amount: number): string {
  const [r, g, b] = hexToRgb(hex)
  const t = amount < 0 ? 0 : 255
  const p = Math.abs(amount)
  return `rgb(${Math.round(r + (t - r) * p)},${Math.round(g + (t - g) * p)},${Math.round(b + (t - b) * p)})`
}

const DIR_DELTA: Record<string, [number, number]> = {
  up: [0, -1],
  down: [0, 1],
  left: [-1, 0],
  right: [1, 0],
}

/**
 * Tick-timed lerp: complete each cell step over one tick, then glide slightly
 * along facing so late ticks don't freeze motion (same approach as Pac-Man).
 */
export function lerpBomber(
  prev: BomberSnapshot | undefined,
  target: BomberSnapshot,
  t: number,
): SmoothBomber {
  if (!prev || !target.alive || !prev.alive) {
    return { ...target, speed: 0 }
  }
  const dx = target.x - prev.x
  const dy = target.y - prev.y
  // Snap on teleports / multi-cell warps.
  if (Math.abs(dx) > 2.75 || Math.abs(dy) > 2.75) {
    return { ...target, speed: 0 }
  }

  let direction = target.direction
  if (Math.hypot(dx, dy) > 0.01) {
    direction =
      Math.abs(dx) >= Math.abs(dy)
        ? dx >= 0
          ? 'right'
          : 'left'
        : dy >= 0
          ? 'down'
          : 'up'
  } else if (target.direction === 'stop' && prev.direction !== 'stop') {
    direction = prev.direction
  }

  if (t > 1) {
    const moved = Math.hypot(dx, dy) > 0.01
    // Only micro-glide along the step we just took — never redirect using a
    // mid-tick facing change (that caused sideways/back pops while overshooting).
    if (moved) {
      const [ddx, ddy] = DIR_DELTA[direction] ?? [0, 0]
      const extra = Math.min(0.22, t - 1) * 0.35
      return {
        ...target,
        x: target.x + ddx * extra,
        y: target.y + ddy * extra,
        direction,
        speed: Math.max(Math.hypot(dx, dy), 0.85),
      }
    }
    return { ...target, direction, speed: 0 }
  }

  const u = Math.min(1, Math.max(0, t))
  return {
    ...target,
    x: prev.x + dx * u,
    y: prev.y + dy * u,
    direction,
    speed: Math.hypot(dx, dy),
  }
}

export function interpolateBombers(
  prev: Record<string, BomberSnapshot>,
  target: Record<string, BomberSnapshot>,
  t: number,
): Record<string, SmoothBomber> {
  const out: Record<string, SmoothBomber> = {}
  for (const [pid, cur] of Object.entries(target)) {
    out[pid] = lerpBomber(prev[pid], cur, t)
  }
  return out
}

/** Exponential chase toward server coords (legacy; prefer interpolateBombers). */
export function smoothBombers(
  display: Record<string, SmoothBomber>,
  target: Record<string, BomberSnapshot>,
  dt: number,
  followHz = 28,
): Record<string, SmoothBomber> {
  const alpha = 1 - Math.exp(-followHz * Math.max(0, dt))
  const out: Record<string, SmoothBomber> = {}
  for (const [pid, cur] of Object.entries(target)) {
    const prev = display[pid]
    if (!prev || !cur.alive || !prev.alive) {
      out[pid] = { ...cur, speed: 0 }
      continue
    }
    const dx = cur.x - prev.x
    const dy = cur.y - prev.y
    if (Math.abs(dx) > 2.75 || Math.abs(dy) > 2.75) {
      out[pid] = { ...cur, speed: 0 }
      continue
    }
    let x = prev.x + dx * alpha
    let y = prev.y + dy * alpha
    if (Math.abs(cur.x - x) < 0.012) x = cur.x
    if (Math.abs(cur.y - y) < 0.012) y = cur.y
    const moveX = x - prev.x
    const moveY = y - prev.y
    const speed = Math.hypot(moveX, moveY) / Math.max(dt, 1e-4)
    let direction = cur.direction
    if (speed > 0.35) {
      direction =
        Math.abs(moveX) >= Math.abs(moveY)
          ? moveX >= 0
            ? 'right'
            : 'left'
          : moveY >= 0
            ? 'down'
            : 'up'
    } else if (cur.direction === 'stop' && prev.direction !== 'stop') {
      direction = prev.direction
    }
    out[pid] = { x, y, alive: cur.alive, color: cur.color, direction, speed }
  }
  return out
}

/** Tick-timed positions for kicked / thrown bombs. */
export function interpolateBombs(
  prev: Record<string, { x: number; y: number }>,
  bombs: BombermanBomb[],
  t: number,
): BombermanBomb[] {
  const u = Math.min(1, Math.max(0, t))
  return bombs.map((bomb) => {
    const p = prev[bomb.id]
    const moving = bomb.flight === 'throw' || bomb.flight === 'kick' || Boolean(bomb.sliding)
    if (!p || !moving) return bomb
    const dx = bomb.x - p.x
    const dy = bomb.y - p.y
    if (Math.abs(dx) > 2.75 || Math.abs(dy) > 2.75) return bomb
    if (t > 1 && Math.hypot(dx, dy) > 0.01) {
      const [ddx, ddy] = DIR_DELTA[bomb.slide_dir ?? ''] ?? [0, 0]
      const extra = Math.min(0.28, t - 1) * 0.45
      return { ...bomb, x: bomb.x + ddx * extra, y: bomb.y + ddy * extra }
    }
    return { ...bomb, x: p.x + dx * u, y: p.y + dy * u }
  })
}

/** @deprecated Prefer interpolateBombs. */
export function smoothBombs(
  display: Record<string, { x: number; y: number }>,
  bombs: BombermanBomb[],
  dt: number,
  followHz = 28,
): BombermanBomb[] {
  const alpha = 1 - Math.exp(-followHz * Math.max(0, dt))
  const nextDisplay: Record<string, { x: number; y: number }> = {}
  const out = bombs.map((bomb) => {
    const prev = display[bomb.id]
    const moving = Boolean(bomb.flight || bomb.sliding)
    if (!prev || !moving) {
      nextDisplay[bomb.id] = { x: bomb.x, y: bomb.y }
      return bomb
    }
    const dx = bomb.x - prev.x
    const dy = bomb.y - prev.y
    if (Math.abs(dx) > 2.75 || Math.abs(dy) > 2.75) {
      nextDisplay[bomb.id] = { x: bomb.x, y: bomb.y }
      return bomb
    }
    let x = prev.x + dx * alpha
    let y = prev.y + dy * alpha
    if (Math.abs(bomb.x - x) < 0.02) x = bomb.x
    if (Math.abs(bomb.y - y) < 0.02) y = bomb.y
    nextDisplay[bomb.id] = { x, y }
    return { ...bomb, x, y }
  })
  for (const key of Object.keys(display)) {
    if (!(key in nextDisplay)) delete display[key]
  }
  Object.assign(display, nextDisplay)
  return out
}

export function snapshotBombers(
  bombers: Record<string, BombermanBomber>,
): Record<string, BomberSnapshot> {
  const out: Record<string, BomberSnapshot> = {}
  for (const [pid, b] of Object.entries(bombers)) {
    out[pid] = {
      x: b.x,
      y: b.y,
      alive: b.alive,
      color: b.color,
      direction: b.direction,
      disease: b.disease ?? null,
      respawn_ticks: b.respawn_ticks ?? 0,
    }
  }
  return out
}

export function spawnExplosionParticles(cx: number, cy: number, count = 14): Particle[] {
  const particles: Particle[] = []
  const colors = ['#ff6b2c', '#ffb020', '#ffe08a', '#ff3d00', '#ff8a4c']
  for (let i = 0; i < count; i++) {
    const angle = (Math.PI * 2 * i) / count + Math.random() * 0.4
    const speed = 1.2 + Math.random() * 3.2
    particles.push({
      x: cx + 0.5,
      y: cy + 0.5,
      vx: Math.cos(angle) * speed,
      vy: Math.sin(angle) * speed,
      life: 0.35 + Math.random() * 0.35,
      maxLife: 0.55 + Math.random() * 0.25,
      color: colors[i % colors.length]!,
      size: 0.12 + Math.random() * 0.18,
      gravity: 1.8,
      kind: i % 3 === 0 ? 'smoke' : 'ember',
    })
  }
  return particles
}

export function spawnDebrisParticles(
  cx: number,
  cy: number,
  count = 8,
  debrisColors?: string[],
): Particle[] {
  const particles: Particle[] = []
  const colors = debrisColors?.length ? debrisColors : CLASSIC_THEME.debris
  for (let i = 0; i < count; i++) {
    const angle = -Math.PI / 2 + (Math.random() - 0.5) * Math.PI
    const speed = 0.8 + Math.random() * 2.2
    particles.push({
      x: cx + 0.5,
      y: cy + 0.5,
      vx: Math.cos(angle) * speed,
      vy: Math.sin(angle) * speed - 0.6,
      life: 0.4 + Math.random() * 0.35,
      maxLife: 0.5 + Math.random() * 0.3,
      color: colors[i % colors.length]!,
      size: 0.1 + Math.random() * 0.14,
      gravity: 4.5,
      kind: 'debris',
    })
  }
  return particles
}

export function spawnPowerupParticles(cx: number, cy: number, color: string): Particle[] {
  const particles: Particle[] = []
  for (let i = 0; i < 10; i++) {
    const angle = (Math.PI * 2 * i) / 10
    particles.push({
      x: cx + 0.5,
      y: cy + 0.5,
      vx: Math.cos(angle) * (1.2 + Math.random()),
      vy: Math.sin(angle) * (1.2 + Math.random()) - 0.5,
      life: 0.4,
      maxLife: 0.45,
      color,
      size: 0.08 + Math.random() * 0.08,
      gravity: -0.6,
      kind: 'spark',
    })
  }
  return particles
}

export function spawnDeathParticles(cx: number, cy: number, color: string): Particle[] {
  return [
    ...spawnExplosionParticles(cx, cy, 10).map((p) => ({ ...p, color })),
    ...spawnExplosionParticles(cx, cy, 6),
  ]
}

export function updateParticles(particles: Particle[], dt: number): Particle[] {
  const next: Particle[] = []
  for (const p of particles) {
    const life = p.life - dt
    if (life <= 0) continue
    next.push({
      ...p,
      x: p.x + p.vx * dt,
      y: p.y + p.vy * dt,
      vx: p.vx * (p.kind === 'smoke' ? 0.92 : 0.98),
      vy: p.vy + (p.gravity ?? 0) * dt,
      life,
      size: p.kind === 'smoke' ? p.size * (1 + dt * 0.8) : p.size,
    })
  }
  return next
}

function drawHardBlock(
  ctx: CanvasRenderingContext2D,
  x: number,
  y: number,
  s: number,
  theme: MapTheme,
) {
  const pad = s * 0.05
  const bx = x + pad
  const by = y + pad
  const bw = s - pad * 2
  const bh = s - pad * 2
  const radius =
    theme.hardStyle === 'crystal' ? s * 0.06 : theme.hardStyle === 'sandstone' ? s * 0.14 : s * 0.1

  ctx.fillStyle = 'rgba(0,0,0,0.35)'
  drawRoundRect(ctx, bx + s * 0.04, by + s * 0.05, bw, bh, radius)
  ctx.fill()

  const grad = ctx.createLinearGradient(bx, by, bx, by + bh)
  grad.addColorStop(0, theme.hard[0])
  grad.addColorStop(0.45, theme.hard[1])
  grad.addColorStop(1, theme.hard[2])
  drawRoundRect(ctx, bx, by, bw, bh, radius)
  ctx.fillStyle = grad
  ctx.fill()

  ctx.strokeStyle = 'rgba(0,0,0,0.45)'
  ctx.lineWidth = Math.max(1, s * 0.04)
  ctx.stroke()

  if (theme.hardStyle === 'steel' || theme.hardStyle === 'rust') {
    ctx.fillStyle =
      theme.hardStyle === 'rust' ? 'rgba(255,160,100,0.12)' : 'rgba(255,255,255,0.14)'
    for (const [rx, ry] of [
      [0.18, 0.18],
      [0.82, 0.18],
      [0.18, 0.82],
      [0.82, 0.82],
    ] as const) {
      ctx.beginPath()
      ctx.arc(bx + bw * rx, by + bh * ry, s * 0.045, 0, Math.PI * 2)
      ctx.fill()
    }
  } else if (theme.hardStyle === 'crystal') {
    ctx.strokeStyle = 'rgba(255,255,255,0.28)'
    ctx.lineWidth = Math.max(1, s * 0.025)
    ctx.beginPath()
    ctx.moveTo(bx + bw * 0.5, by + bh * 0.12)
    ctx.lineTo(bx + bw * 0.18, by + bh * 0.72)
    ctx.lineTo(bx + bw * 0.82, by + bh * 0.72)
    ctx.closePath()
    ctx.stroke()
    ctx.fillStyle = 'rgba(255,255,255,0.16)'
    ctx.fill()
  } else if (theme.hardStyle === 'stone' || theme.hardStyle === 'sandstone') {
    ctx.strokeStyle = 'rgba(0,0,0,0.18)'
    ctx.lineWidth = Math.max(1, s * 0.025)
    ctx.beginPath()
    ctx.moveTo(bx + bw * 0.2, by + bh * 0.35)
    ctx.lineTo(bx + bw * 0.75, by + bh * 0.28)
    ctx.moveTo(bx + bw * 0.3, by + bh * 0.7)
    ctx.lineTo(bx + bw * 0.85, by + bh * 0.62)
    ctx.stroke()
  }

  ctx.fillStyle =
    theme.hardStyle === 'crystal' ? 'rgba(220,250,255,0.22)' : 'rgba(255,255,255,0.1)'
  drawRoundRect(ctx, bx + bw * 0.12, by + bh * 0.1, bw * 0.5, bh * 0.16, 2)
  ctx.fill()
}

function drawSoftDetail(
  ctx: CanvasRenderingContext2D,
  bx: number,
  by: number,
  bw: number,
  bh: number,
  wobble: number,
  style: SoftBlockStyle,
) {
  ctx.strokeStyle = 'rgba(0,0,0,0.22)'
  ctx.lineWidth = Math.max(1, bw * 0.04)
  ctx.beginPath()
  if (style === 'brick' || style === 'stone') {
    ctx.moveTo(bx + bw * 0.5, by + wobble)
    ctx.lineTo(bx + bw * 0.5, by + bh + wobble)
    ctx.moveTo(bx, by + bh * 0.33 + wobble)
    ctx.lineTo(bx + bw * 0.5, by + bh * 0.33 + wobble)
    ctx.moveTo(bx + bw * 0.5, by + bh * 0.66 + wobble)
    ctx.lineTo(bx + bw, by + bh * 0.66 + wobble)
  } else if (style === 'crate' || style === 'wood') {
    ctx.moveTo(bx + bw * 0.15, by + bh * 0.15 + wobble)
    ctx.lineTo(bx + bw * 0.85, by + bh * 0.85 + wobble)
    ctx.moveTo(bx + bw * 0.85, by + bh * 0.15 + wobble)
    ctx.lineTo(bx + bw * 0.15, by + bh * 0.85 + wobble)
    ctx.stroke()
    ctx.strokeRect(bx + bw * 0.12, by + bh * 0.12 + wobble, bw * 0.76, bh * 0.76)
    return
  } else if (style === 'ice') {
    ctx.moveTo(bx + bw * 0.2, by + bh * 0.25 + wobble)
    ctx.lineTo(bx + bw * 0.55, by + bh * 0.7 + wobble)
    ctx.moveTo(bx + bw * 0.55, by + bh * 0.2 + wobble)
    ctx.lineTo(bx + bw * 0.8, by + bh * 0.55 + wobble)
  } else if (style === 'hedge') {
    for (let i = 0; i < 3; i++) {
      const yy = by + bh * (0.25 + i * 0.25) + wobble
      ctx.moveTo(bx + bw * 0.15, yy)
      ctx.quadraticCurveTo(bx + bw * 0.5, yy - bh * 0.08, bx + bw * 0.85, yy)
    }
  }
  ctx.stroke()
}

function drawSoftBlock(
  ctx: CanvasRenderingContext2D,
  x: number,
  y: number,
  s: number,
  time: number,
  theme: MapTheme,
) {
  const pad = s * 0.07
  const bx = x + pad
  const by = y + pad
  const bw = s - pad * 2
  const bh = s - pad * 2
  const wobble = Math.sin(time / 900 + x * 0.07 + y * 0.11) * s * 0.008
  const radius = theme.softStyle === 'ice' ? s * 0.14 : s * 0.08

  ctx.fillStyle = 'rgba(0,0,0,0.28)'
  drawRoundRect(ctx, bx + s * 0.03, by + s * 0.04, bw, bh, radius)
  ctx.fill()

  const grad = ctx.createLinearGradient(bx, by, bx + bw, by + bh)
  grad.addColorStop(0, theme.soft[0])
  grad.addColorStop(0.5, theme.soft[1])
  grad.addColorStop(1, theme.soft[2])
  drawRoundRect(ctx, bx, by + wobble, bw, bh, radius)
  ctx.fillStyle = grad
  ctx.fill()

  ctx.strokeStyle = theme.softStroke
  ctx.lineWidth = Math.max(1, s * 0.035)
  ctx.stroke()

  drawSoftDetail(ctx, bx, by, bw, bh, wobble, theme.softStyle)

  ctx.fillStyle = theme.softSheen
  drawRoundRect(ctx, bx + bw * 0.1, by + bh * 0.08 + wobble, bw * 0.4, bh * 0.14, 2)
  ctx.fill()
}

function drawBomb(
  ctx: CanvasRenderingContext2D,
  x: number,
  y: number,
  s: number,
  fuse: number,
  time: number,
  slideDir: string | null = null,
  flight: string | null = null,
) {
  const dirOff: Record<string, [number, number]> = {
    up: [0, -0.12],
    down: [0, 0.12],
    left: [-0.12, 0],
    right: [0.12, 0],
  }
  const airborne = flight === 'throw'
  const carried = flight === 'carried'
  const kicking = flight === 'kick'
  const [ox, oy] = (airborne || kicking) && slideDir ? (dirOff[slideDir] ?? [0, 0]) : [0, 0]
  const lift = carried ? s * 0.34 : airborne ? s * 0.16 : kicking ? s * 0.04 : 0
  const cx = x + s / 2 + ox * s
  const cy = y + s / 2 + oy * s - lift
  const urgent = fuse <= 5
  const pulse = 1 + Math.sin(time / (urgent ? 45 : 90) + fuse) * (urgent ? 0.1 : 0.045)
  const r = s * (carried ? 0.24 : 0.3) * pulse

  // Warning ring when fuse is low
  if (urgent) {
    const ring = 0.55 + Math.sin(time / 50) * 0.15
    ctx.beginPath()
    ctx.arc(cx, cy + s * 0.02, r * 1.55, 0, Math.PI * 2)
    ctx.strokeStyle = `rgba(255, 80, 40, ${0.25 + ring * 0.25})`
    ctx.lineWidth = Math.max(1.5, s * 0.05)
    ctx.stroke()
  }

  // Shadow
  ctx.beginPath()
  ctx.ellipse(
    cx,
    cy + r * 0.95 + lift,
    r * (airborne || carried ? 0.45 : kicking ? 0.65 : 0.75),
    r * 0.28,
    0,
    0,
    Math.PI * 2,
  )
  ctx.fillStyle = airborne || kicking || carried ? 'rgba(0,0,0,0.2)' : 'rgba(0,0,0,0.35)'
  ctx.fill()

  const body = ctx.createRadialGradient(cx - r * 0.3, cy - r * 0.25, r * 0.1, cx, cy, r)
  body.addColorStop(0, '#3a3a42')
  body.addColorStop(0.55, '#16161c')
  body.addColorStop(1, '#050508')
  ctx.beginPath()
  ctx.arc(cx, cy + s * 0.02, r, 0, Math.PI * 2)
  ctx.fillStyle = body
  ctx.fill()
  ctx.strokeStyle = carried
    ? 'rgba(251, 191, 36, 0.65)'
    : airborne
      ? 'rgba(251, 191, 36, 0.5)'
      : kicking
        ? 'rgba(244, 114, 182, 0.55)'
        : 'rgba(255,255,255,0.12)'
  ctx.lineWidth = airborne || kicking || carried ? Math.max(1.5, s * 0.045) : 1
  ctx.stroke()

  // Highlight
  ctx.beginPath()
  ctx.ellipse(cx - r * 0.28, cy - r * 0.2, r * 0.28, r * 0.18, -0.5, 0, Math.PI * 2)
  ctx.fillStyle = 'rgba(255,255,255,0.16)'
  ctx.fill()

  // Fuse wire
  const tipX = cx + s * 0.1
  const tipY = cy - r * 1.35
  ctx.beginPath()
  ctx.moveTo(cx, cy - r * 0.55)
  ctx.quadraticCurveTo(cx + s * 0.14, cy - r * 1.05, tipX, tipY)
  ctx.strokeStyle = '#d4a017'
  ctx.lineWidth = Math.max(1.5, s * 0.055)
  ctx.lineCap = 'round'
  ctx.stroke()

  // Spark
  const sparkPulse = urgent ? 1.15 + Math.sin(time / 35) * 0.35 : 0.85 + Math.sin(time / 60) * 0.15
  const sparkR = s * 0.07 * sparkPulse
  const sparkGrad = ctx.createRadialGradient(tipX, tipY, 0, tipX, tipY, sparkR * 2.2)
  sparkGrad.addColorStop(0, '#fff7c2')
  sparkGrad.addColorStop(0.4, urgent ? '#ff4d2a' : '#ff9a1a')
  sparkGrad.addColorStop(1, 'rgba(255,80,0,0)')
  ctx.beginPath()
  ctx.arc(tipX, tipY, sparkR * 2.2, 0, Math.PI * 2)
  ctx.fillStyle = sparkGrad
  ctx.fill()
}

const BLAST_DIRS: Array<[number, number]> = [
  [0, -1],
  [0, 1],
  [-1, 0],
  [1, 0],
]
/** Delay before a blast cell appears, per cell of distance from the bomb. */
const BLAST_CELL_DELAY_MS = 40

type BlastWave = {
  startedAt: number
  centers: Array<{ x: number; y: number }>
  cells: Set<string>
}

const blastWaves: BlastWave[] = []
const blastPrevTtl = new Map<string, number>()

function blastKey(x: number, y: number): string {
  return `${x},${y}`
}

function parseBlastKey(key: string): { x: number; y: number } {
  const [xs, ys] = key.split(',')
  return { x: Number(xs), y: Number(ys) }
}

/** Bomb epicenters = strict local maxima of cardinal reach (tips must not count). */
function findBlastCenters(cellSet: Set<string>): Array<{ x: number; y: number }> {
  const cells: Array<{ x: number; y: number }> = []
  for (const key of cellSet) cells.push(parseBlastKey(key))
  if (cells.length === 0) return []

  const scoreOf = (x: number, y: number) => {
    let score = 0
    for (const [dx, dy] of BLAST_DIRS) {
      let step = 1
      while (cellSet.has(blastKey(x + dx * step, y + dy * step))) {
        score++
        step++
      }
    }
    return score
  }

  const scores = new Map<string, number>()
  let maxScore = 0
  for (const c of cells) {
    const sc = scoreOf(c.x, c.y)
    scores.set(blastKey(c.x, c.y), sc)
    if (sc > maxScore) maxScore = sc
  }

  const centers: Array<{ x: number; y: number }> = []
  for (const c of cells) {
    const key = blastKey(c.x, c.y)
    const sc = scores.get(key) ?? 0
    let strictMax = true
    for (const [dx, dy] of BLAST_DIRS) {
      const n = scores.get(blastKey(c.x + dx, c.y + dy))
      if (n != null && n >= sc) {
        strictMax = false
        break
      }
    }
    if (strictMax) centers.push(c)
  }
  if (centers.length) return centers

  // Fallback: every cell with the best reach score (overlapping bombs).
  return cells.filter((c) => (scores.get(blastKey(c.x, c.y)) ?? 0) === maxScore)
}

function distToNearestCenter(
  x: number,
  y: number,
  centers: Array<{ x: number; y: number }>,
): number {
  let best = Infinity
  for (const c of centers) {
    const d = Math.abs(x - c.x) + Math.abs(y - c.y)
    if (d < best) best = d
  }
  return Number.isFinite(best) ? best : 0
}

function syncBlastWaves(explosions: BombermanExplosion[], now: number) {
  const live = new Set(explosions.map((e) => blastKey(e.x, e.y)))
  for (const key of [...blastPrevTtl.keys()]) {
    if (!live.has(key)) blastPrevTtl.delete(key)
  }

  // Drop waves whose cells are all gone.
  for (let i = blastWaves.length - 1; i >= 0; i--) {
    const wave = blastWaves[i]!
    let anyLive = false
    for (const key of wave.cells) {
      if (live.has(key)) {
        anyLive = true
        break
      }
    }
    if (!anyLive) blastWaves.splice(i, 1)
  }

  const ignited: BombermanExplosion[] = []
  for (const e of explosions) {
    const key = blastKey(e.x, e.y)
    const prev = blastPrevTtl.get(key)
    if (prev == null || e.ttl > prev) ignited.push(e)
    blastPrevTtl.set(key, e.ttl)
  }
  if (ignited.length === 0) return

  // One wave per batch of newly ignited cells (a bomb or chain pop).
  const ignitedSet = new Set(ignited.map((e) => blastKey(e.x, e.y)))
  blastWaves.push({
    startedAt: now,
    centers: findBlastCenters(ignitedSet),
    cells: ignitedSet,
  })
}

/** Newest wave that owns this cell (chain reactions stack as new waves). */
function waveForCell(key: string): BlastWave | null {
  for (let i = blastWaves.length - 1; i >= 0; i--) {
    const wave = blastWaves[i]!
    if (wave.cells.has(key)) return wave
  }
  return null
}

/** Original per-cell flame cross (unchanged look). */
function drawExplosion(
  ctx: CanvasRenderingContext2D,
  x: number,
  y: number,
  s: number,
  ttl: number,
  time: number,
) {
  const intensity = Math.min(1, ttl / 4)
  const flicker = 0.82 + Math.sin(time / 28 + x * 0.3 + y * 0.5) * 0.18
  const cx = x + s / 2
  const cy = y + s / 2
  const arm = s * (0.18 + 0.2 * intensity)
  const len = s * (0.42 + 0.08 * intensity)

  for (const [dx, dy] of BLAST_DIRS) {
    const tipX = cx + dx * len
    const tipY = cy + dy * len
    const grad = ctx.createLinearGradient(cx, cy, tipX, tipY)
    grad.addColorStop(0, `rgba(255, 250, 200, ${0.9 * intensity * flicker})`)
    grad.addColorStop(0.45, `rgba(255, 140, 40, ${0.8 * intensity})`)
    grad.addColorStop(1, `rgba(220, 40, 0, ${0.15 * intensity})`)
    ctx.fillStyle = grad
    ctx.beginPath()
    if (dx === 0) {
      ctx.moveTo(cx - arm, cy)
      ctx.lineTo(cx + arm, cy)
      ctx.lineTo(tipX + arm * 0.35, tipY)
      ctx.lineTo(tipX - arm * 0.35, tipY)
    } else {
      ctx.moveTo(cx, cy - arm)
      ctx.lineTo(cx, cy + arm)
      ctx.lineTo(tipX, tipY + arm * 0.35)
      ctx.lineTo(tipX, tipY - arm * 0.35)
    }
    ctx.closePath()
    ctx.fill()
  }

  ctx.beginPath()
  ctx.arc(cx, cy, s * 0.22 * intensity, 0, Math.PI * 2)
  ctx.fillStyle = `rgba(255, 255, 220, ${0.85 * intensity * flicker})`
  ctx.fill()
  ctx.beginPath()
  ctx.arc(cx, cy, s * 0.1 * intensity, 0, Math.PI * 2)
  ctx.fillStyle = `rgba(255, 180, 60, ${0.7 * intensity})`
  ctx.fill()
}

/**
 * Same per-cell blast art; only timing changes — farther cells appear later.
 */
function drawExplosions(
  ctx: CanvasRenderingContext2D,
  explosions: BombermanExplosion[],
  ox: number,
  oy: number,
  s: number,
  time: number,
) {
  if (explosions.length === 0) {
    blastWaves.length = 0
    blastPrevTtl.clear()
    return
  }

  syncBlastWaves(explosions, time)

  for (const e of explosions) {
    const key = blastKey(e.x, e.y)
    const wave = waveForCell(key)
    if (!wave) {
      drawExplosion(ctx, ox + e.x * s, oy + e.y * s, s, e.ttl, time)
      continue
    }
    const dist = distToNearestCenter(e.x, e.y, wave.centers)
    if (time < wave.startedAt + dist * BLAST_CELL_DELAY_MS) continue
    drawExplosion(ctx, ox + e.x * s, oy + e.y * s, s, e.ttl, time)
  }
}

function drawPowerup(
  ctx: CanvasRenderingContext2D,
  x: number,
  y: number,
  s: number,
  type: string,
  time: number,
) {
  const bob = Math.sin(time / 220) * s * 0.06
  const spin = time / 600
  const cx = x + s / 2
  const cy = y + s / 2 + bob
  const r = s * 0.3
  const colors: Record<string, string> = {
    bomb: '#f97316',
    range: '#38bdf8',
    speed: '#a3e635',
    throw: '#fbbf24',
    kick: '#f472b6',
    skull: '#64748b',
  }
  const labels: Record<string, string> = {
    bomb: '💣',
    range: '🔥',
    speed: '⚡',
    throw: '🧤',
    kick: '🦵',
    skull: '💀',
  }
  const color = colors[type] ?? '#fff'

  // Soft ground glow
  ctx.beginPath()
  ctx.ellipse(cx, y + s * 0.78, r * 0.9, r * 0.28, 0, 0, Math.PI * 2)
  ctx.fillStyle = rgba(color, 0.2)
  ctx.fill()

  // Orbiting ring
  ctx.save()
  ctx.translate(cx, cy)
  ctx.rotate(spin)
  ctx.strokeStyle = rgba(color, 0.45)
  ctx.lineWidth = Math.max(1.5, s * 0.04)
  ctx.beginPath()
  ctx.ellipse(0, 0, r * 1.25, r * 0.7, 0, 0, Math.PI * 2)
  ctx.stroke()
  ctx.restore()

  const grad = ctx.createRadialGradient(cx - r * 0.25, cy - r * 0.3, r * 0.1, cx, cy, r)
  grad.addColorStop(0, shade(color, 0.45))
  grad.addColorStop(1, shade(color, -0.15))
  ctx.beginPath()
  ctx.arc(cx, cy, r, 0, Math.PI * 2)
  ctx.fillStyle = grad
  ctx.fill()
  ctx.strokeStyle = 'rgba(255,255,255,0.35)'
  ctx.lineWidth = Math.max(1.5, s * 0.045)
  ctx.stroke()

  ctx.font = `${Math.floor(s * 0.42)}px "Apple Color Emoji", "Segoe UI Emoji", "Noto Color Emoji", sans-serif`
  ctx.textAlign = 'center'
  ctx.textBaseline = 'middle'
  ctx.fillText(labels[type] ?? '❓', cx, cy + 1)
}

function drawSelfMarker(
  ctx: CanvasRenderingContext2D,
  cx: number,
  footY: number,
  s: number,
  color: string,
  time: number,
  strength: number,
) {
  if (strength <= 0.01) return
  const pulse = 0.55 + 0.45 * Math.sin(time / 180)
  const rx = s * (0.38 + pulse * 0.06)
  const ry = s * (0.14 + pulse * 0.03)
  const alpha = strength * (0.35 + pulse * 0.35)

  ctx.beginPath()
  ctx.ellipse(cx, footY, rx * 1.15, ry * 1.35, 0, 0, Math.PI * 2)
  ctx.fillStyle = rgba(color, alpha * 0.35)
  ctx.fill()

  ctx.beginPath()
  ctx.ellipse(cx, footY, rx, ry, 0, 0, Math.PI * 2)
  ctx.strokeStyle = rgba('#ffffff', alpha * 0.85)
  ctx.lineWidth = Math.max(2, s * 0.055)
  ctx.stroke()

  ctx.beginPath()
  ctx.ellipse(cx, footY, rx * 0.92, ry * 0.92, 0, 0, Math.PI * 2)
  ctx.strokeStyle = rgba(color, alpha)
  ctx.lineWidth = Math.max(1.5, s * 0.04)
  ctx.stroke()
}

interface BomberBodyOpts {
  s: number
  color: string
  isMe: boolean
  stride: number
  /** Facing unit: -1/0/1 on each axis. */
  fdx: number
  fdy: number
  /** 'up' | 'down' | 'left' | 'right' | 'stop' */
  facing: string
  backView: boolean
  sideView: boolean
  skin: string
  skinShade: string
  boot: string
  glove: string
  suitDark: string
  suitLite: string
}

function drawDomeBody(ctx: CanvasRenderingContext2D, o: BomberBodyOpts): number {
  const { s, color, isMe, stride, fdx, fdy, facing, backView, sideView, boot, glove, suitDark, suitLite } =
    o
  const leanX = fdx * s * 0.055
  const leanY = fdy * s * 0.012
  // Side profile: tuck body depth; front/back keep full width.
  const torsoW = sideView ? s * 0.2 : s * 0.34
  const torsoH = s * 0.24
  const legSpread = sideView ? s * 0.03 : s * 0.09
  const armLen = s * 0.13

  // Legs — stride along facing so the silhouette walks in that direction.
  for (const side of [-1, 1] as const) {
    const swing = side * stride * s * (sideView ? 0.12 : 0.09)
    const hipX = leanX + side * legSpread
    const hipY = s * 0.1 + leanY
    // Boots point along facing (side view: forward/back of stride; front: outward + lean).
    const footX = sideView
      ? leanX + swing + fdx * s * 0.04
      : hipX + swing * 0.35 + fdx * s * 0.05
    const footY = hipY + s * 0.2 + Math.abs(swing) * 0.1 + (backView ? -s * 0.01 : 0)

    ctx.strokeStyle = suitDark
    ctx.lineWidth = Math.max(3, s * (sideView ? 0.09 : 0.08))
    ctx.lineCap = 'round'
    ctx.beginPath()
    ctx.moveTo(hipX, hipY)
    ctx.lineTo(footX, footY)
    ctx.stroke()

    // Boot sole oriented toward facing.
    const bootW = sideView ? s * 0.16 : s * 0.13
    const bootH = s * 0.055
    const bootOx = sideView ? fdx * bootW * 0.25 : fdx * s * 0.02
    drawRoundRect(ctx, footX - bootW / 2 + bootOx, footY, bootW, bootH, 2)
    ctx.fillStyle = boot
    ctx.fill()
    if (sideView || Math.abs(fdx) > 0.5) {
      // Toe tip — reinforces left/right.
      ctx.beginPath()
      ctx.ellipse(footX + fdx * bootW * 0.45, footY + bootH * 0.45, s * 0.035, bootH * 0.45, 0, 0, Math.PI * 2)
      ctx.fillStyle = shade(boot, 0.15)
      ctx.fill()
    }
  }

  const torsoX = leanX - torsoW / 2
  const torsoY = -torsoH * 0.25 + leanY
  const torsoGrad = ctx.createLinearGradient(
    torsoX + (sideView ? 0 : torsoW * 0.2),
    torsoY,
    torsoX + torsoW * (sideView ? 1 : 0.8),
    torsoY + torsoH,
  )
  if (sideView) {
    // Lit edge toward facing; dark trailing edge.
    torsoGrad.addColorStop(0, fdx < 0 ? suitDark : suitLite)
    torsoGrad.addColorStop(0.45, color)
    torsoGrad.addColorStop(1, fdx < 0 ? suitLite : suitDark)
  } else if (backView) {
    torsoGrad.addColorStop(0, suitDark)
    torsoGrad.addColorStop(0.55, color)
    torsoGrad.addColorStop(1, shade(color, -0.35))
  } else {
    torsoGrad.addColorStop(0, suitLite)
    torsoGrad.addColorStop(0.55, color)
    torsoGrad.addColorStop(1, suitDark)
  }
  drawRoundRect(ctx, torsoX, torsoY, torsoW, torsoH, s * 0.1)
  ctx.fillStyle = torsoGrad
  ctx.fill()
  ctx.strokeStyle = isMe ? 'rgba(255,255,255,0.5)' : 'rgba(0,0,0,0.3)'
  ctx.lineWidth = isMe ? Math.max(1.5, s * 0.035) : 1.2
  ctx.stroke()

  // Chest badge only on front; backpack plate on back; side stripe on profile.
  if (backView) {
    drawRoundRect(
      ctx,
      leanX - torsoW * 0.28,
      torsoY + torsoH * 0.18,
      torsoW * 0.56,
      torsoH * 0.55,
      s * 0.06,
    )
    ctx.fillStyle = shade(color, -0.35)
    ctx.fill()
    ctx.strokeStyle = 'rgba(0,0,0,0.25)'
    ctx.lineWidth = 1
    ctx.stroke()
  } else if (sideView) {
    ctx.beginPath()
    ctx.moveTo(leanX + fdx * torsoW * 0.15, torsoY + torsoH * 0.15)
    ctx.lineTo(leanX + fdx * torsoW * 0.15, torsoY + torsoH * 0.85)
    ctx.strokeStyle = rgba('#ffffff', 0.18)
    ctx.lineWidth = Math.max(1.5, s * 0.035)
    ctx.stroke()
  } else {
    ctx.beginPath()
    ctx.ellipse(leanX, torsoY + torsoH * 0.45, torsoW * 0.28, torsoH * 0.22, 0, 0, Math.PI * 2)
    ctx.fillStyle = rgba('#ffffff', 0.14)
    ctx.fill()
  }

  // Arms — lead arm reaches toward facing; trail arm hangs back.
  const armOrder: (-1 | 1)[] = sideView ? (fdx >= 0 ? [-1, 1] : [1, -1]) : [-1, 1]
  for (const side of armOrder) {
    const isLead = sideView ? side === Math.sign(fdx || 1) : side === (fdx !== 0 ? Math.sign(fdx) : side)
    const swing = -side * stride * s * 0.08
    const shoulderX = leanX + (sideView ? fdx * torsoW * 0.15 : side * torsoW * 0.5)
    const shoulderY = torsoY + torsoH * 0.2
    let handX: number
    let handY: number
    if (sideView) {
      // Profile: lead arm forward along facing, trail arm back.
      const reach = isLead ? 1 : -0.55
      handX = shoulderX + fdx * s * (0.14 + (isLead ? 0.04 : 0)) * reach + swing * 0.4
      handY = shoulderY + armLen * (isLead ? 0.55 : 0.95) + Math.abs(swing) * 0.12
    } else if (backView) {
      handX = shoulderX + side * s * 0.02 + swing * 0.2
      handY = shoulderY + armLen + Math.abs(swing) * 0.12
    } else {
      // Front: both arms, slightly biased toward look direction.
      handX = shoulderX + side * s * 0.02 + swing * 0.25 + fdx * s * 0.06
      handY = shoulderY + armLen * (facing === 'down' ? 0.85 : 1) + Math.abs(swing) * 0.15 + fdy * s * 0.02
    }

    ctx.strokeStyle = isLead && sideView ? suitLite : color
    ctx.lineWidth = Math.max(2.4, s * (sideView && !isLead ? 0.055 : 0.07))
    ctx.lineCap = 'round'
    ctx.beginPath()
    ctx.moveTo(shoulderX, shoulderY)
    ctx.lineTo(handX, handY)
    ctx.stroke()

    ctx.beginPath()
    ctx.arc(handX, handY, s * (sideView && !isLead ? 0.04 : 0.052), 0, Math.PI * 2)
    ctx.fillStyle = glove
    ctx.fill()
  }

  return torsoH
}

function drawDomeFace(
  ctx: CanvasRenderingContext2D,
  o: BomberBodyOpts,
  domeR: number,
  domeY: number,
  faceScale = 1,
  headX = 0,
) {
  const { s, fdx, fdy, backView, sideView, skin, skinShade } = o
  if (backView) {
    // Helmet seam on the back of the head.
    ctx.beginPath()
    ctx.arc(headX, domeY + domeR * 0.1, domeR * 0.45, 0.2 * Math.PI, 0.8 * Math.PI)
    ctx.strokeStyle = 'rgba(0,0,0,0.18)'
    ctx.lineWidth = Math.max(1.5, s * 0.035)
    ctx.stroke()
    return
  }

  if (sideView) {
    // Profile face plate + single eye looking along facing.
    const faceCX = headX + fdx * domeR * 0.28
    const faceCY = domeY + domeR * 0.06
    const faceW = domeR * 0.55 * faceScale
    const faceH = domeR * 0.72 * faceScale
    drawRoundRect(ctx, faceCX - faceW / 2, faceCY - faceH / 2, faceW, faceH, s * 0.05)
    const faceGrad = ctx.createLinearGradient(faceCX, faceCY - faceH / 2, faceCX, faceCY + faceH / 2)
    faceGrad.addColorStop(0, '#ffe0c4')
    faceGrad.addColorStop(0.6, skin)
    faceGrad.addColorStop(1, skinShade)
    ctx.fillStyle = faceGrad
    ctx.fill()
    ctx.strokeStyle = 'rgba(0,0,0,0.2)'
    ctx.lineWidth = 1
    ctx.stroke()

    const ex = faceCX + fdx * s * 0.01
    const ey = faceCY - faceH * 0.05
    ctx.beginPath()
    ctx.ellipse(ex, ey, s * 0.045 * faceScale, s * 0.055 * faceScale, 0, 0, Math.PI * 2)
    ctx.fillStyle = '#fff'
    ctx.fill()
    ctx.beginPath()
    ctx.arc(ex + fdx * s * 0.012, ey + fdy * s * 0.004, s * 0.022 * faceScale, 0, Math.PI * 2)
    ctx.fillStyle = '#1a1520'
    ctx.fill()

    ctx.beginPath()
    ctx.arc(faceCX + fdx * s * 0.01, faceCY + faceH * 0.22, s * 0.03 * faceScale, 0.25 * Math.PI, 0.75 * Math.PI)
    ctx.strokeStyle = '#c45c3a'
    ctx.lineWidth = Math.max(1.2, s * 0.025)
    ctx.lineCap = 'round'
    ctx.stroke()
    return
  }

  const faceW = domeR * 0.95 * faceScale
  const faceH = domeR * 0.7 * faceScale
  const faceY = domeY + domeR * 0.08
  drawRoundRect(ctx, headX - faceW / 2, faceY - faceH / 2, faceW, faceH, s * 0.06)
  const faceGrad = ctx.createLinearGradient(0, faceY - faceH / 2, 0, faceY + faceH / 2)
  faceGrad.addColorStop(0, '#ffe0c4')
  faceGrad.addColorStop(0.6, skin)
  faceGrad.addColorStop(1, skinShade)
  ctx.fillStyle = faceGrad
  ctx.fill()
  ctx.strokeStyle = 'rgba(0,0,0,0.2)'
  ctx.lineWidth = 1
  ctx.stroke()

  const lookX = fdx * s * 0.03
  const eyeY = faceY - faceH * 0.05 + fdy * s * 0.02
  for (const side of [-1, 1] as const) {
    const ex = headX + side * s * 0.065 * faceScale + lookX
    ctx.beginPath()
    ctx.ellipse(ex, eyeY, s * 0.048 * faceScale, s * 0.052 * faceScale, 0, 0, Math.PI * 2)
    ctx.fillStyle = '#fff'
    ctx.fill()
    ctx.beginPath()
    ctx.arc(ex + lookX * 0.45, eyeY + fdy * s * 0.01, s * 0.024 * faceScale, 0, Math.PI * 2)
    ctx.fillStyle = '#1a1520'
    ctx.fill()
  }

  ctx.beginPath()
  ctx.arc(headX + lookX * 0.3, faceY + faceH * 0.22, s * 0.04 * faceScale, 0.2 * Math.PI, 0.8 * Math.PI)
  ctx.strokeStyle = '#c45c3a'
  ctx.lineWidth = Math.max(1.2, s * 0.025)
  ctx.lineCap = 'round'
  ctx.stroke()
}

function drawDomeAntenna(
  ctx: CanvasRenderingContext2D,
  o: BomberBodyOpts,
  domeR: number,
  domeY: number,
  headX: number,
  tipColor?: string,
) {
  const { s, color, fdx, fdy, backView } = o
  // Antenna tips toward facing so the whole head reads direction.
  const tipX = headX + fdx * s * 0.08
  const tipY = domeY - domeR * (backView ? 1.45 : 1.35) + fdy * s * 0.02
  const baseX = headX + fdx * s * 0.02
  const baseY = domeY - domeR * 0.85
  ctx.strokeStyle = shade(color, -0.2)
  ctx.lineWidth = Math.max(1.8, s * 0.04)
  ctx.lineCap = 'round'
  ctx.beginPath()
  ctx.moveTo(baseX, baseY)
  ctx.lineTo(tipX, tipY)
  ctx.stroke()
  ctx.beginPath()
  ctx.arc(tipX, tipY - s * 0.01, s * 0.035, 0, Math.PI * 2)
  ctx.fillStyle = tipColor ?? color
  ctx.fill()
  ctx.strokeStyle = '#fff'
  ctx.lineWidth = 1
  ctx.stroke()
}

/** Dome Shell bomber — body lean + profile/back poses make facing obvious. */
function drawBomberSprite(ctx: CanvasRenderingContext2D, o: BomberBodyOpts) {
  const torsoH = drawDomeBody(ctx, o)
  const { s, color, suitDark, suitLite, fdx, fdy, backView, sideView } = o
  const leanX = fdx * s * 0.055
  const domeR = sideView ? s * 0.21 : s * 0.23
  const domeY = -torsoH * 0.55 + fdy * s * 0.01
  // Head sits ahead of the torso along facing (classic Bomberman read).
  const headX = leanX + fdx * s * (sideView ? 0.06 : 0.02)

  // Colored outer shell — highlight from the facing side.
  const shellGrad = ctx.createRadialGradient(
    headX - domeR * 0.3 + fdx * domeR * 0.25,
    domeY - domeR * 0.4,
    domeR * 0.1,
    headX,
    domeY,
    domeR,
  )
  shellGrad.addColorStop(0, suitLite)
  shellGrad.addColorStop(0.45, color)
  shellGrad.addColorStop(1, suitDark)
  ctx.beginPath()
  if (sideView) {
    ctx.ellipse(headX, domeY, domeR * 0.85, domeR, 0, 0, Math.PI * 2)
  } else {
    ctx.arc(headX, domeY, domeR, 0, Math.PI * 2)
  }
  ctx.fillStyle = shellGrad
  ctx.fill()
  ctx.strokeStyle = 'rgba(0,0,0,0.3)'
  ctx.lineWidth = Math.max(1.5, s * 0.04)
  ctx.stroke()

  if (backView) {
    // Solid colored back of helmet — no white face plate.
    ctx.beginPath()
    ctx.arc(headX, domeY + domeR * 0.08, domeR * 0.55, 0, Math.PI * 2)
    ctx.fillStyle = shade(color, -0.2)
    ctx.fill()
    // Vertical seam
    ctx.beginPath()
    ctx.moveTo(headX, domeY - domeR * 0.35)
    ctx.lineTo(headX, domeY + domeR * 0.55)
    ctx.strokeStyle = 'rgba(0,0,0,0.2)'
    ctx.lineWidth = Math.max(1.2, s * 0.03)
    ctx.stroke()
  } else if (sideView) {
    // Partial white plate on the facing side of the helmet.
    const plateX = headX + fdx * domeR * 0.22
    const plateR = domeR * 0.55
    const innerGrad = ctx.createRadialGradient(
      plateX - fdx * plateR * 0.2,
      domeY - plateR * 0.2,
      plateR * 0.08,
      plateX,
      domeY + domeR * 0.05,
      plateR,
    )
    innerGrad.addColorStop(0, '#ffffff')
    innerGrad.addColorStop(0.7, '#f2f2f6')
    innerGrad.addColorStop(1, '#d4d4dc')
    ctx.beginPath()
    ctx.ellipse(plateX, domeY + domeR * 0.06, plateR * 0.7, plateR, 0, 0, Math.PI * 2)
    ctx.fillStyle = innerGrad
    ctx.fill()
    ctx.strokeStyle = rgba(suitDark, 0.45)
    ctx.lineWidth = 1.2
    ctx.stroke()
  } else {
    // Full white inner plate (front).
    const innerR = domeR * 0.72
    const innerGrad = ctx.createRadialGradient(
      headX - innerR * 0.25,
      domeY - innerR * 0.2,
      innerR * 0.08,
      headX,
      domeY + domeR * 0.05,
      innerR,
    )
    innerGrad.addColorStop(0, '#ffffff')
    innerGrad.addColorStop(0.7, '#f2f2f6')
    innerGrad.addColorStop(1, '#d4d4dc')
    ctx.beginPath()
    ctx.arc(headX, domeY + domeR * 0.06, innerR, 0, Math.PI * 2)
    ctx.fillStyle = innerGrad
    ctx.fill()
    ctx.strokeStyle = rgba(suitDark, 0.45)
    ctx.lineWidth = 1.2
    ctx.stroke()
  }

  // Chin / collar rim
  ctx.beginPath()
  ctx.ellipse(
    headX + fdx * s * 0.01,
    domeY + domeR * 0.62,
    domeR * (sideView ? 0.55 : 0.7),
    domeR * 0.2,
    0,
    0,
    Math.PI * 2,
  )
  ctx.fillStyle = shade(color, -0.15)
  ctx.fill()

  drawDomeAntenna(ctx, o, domeR, domeY, headX, '#fff')
  drawDomeFace(ctx, o, domeR * 0.9, domeY + domeR * 0.04, 0.95, headX)
}

function drawBomber(
  ctx: CanvasRenderingContext2D,
  x: number,
  y: number,
  s: number,
  color: string,
  isMe: boolean,
  direction: string,
  time: number,
  speed = 0,
  diseased = false,
  selfMarker = 0,
) {
  // `speed` is cells advanced this tick (≈1 at base, up to ~2 with speed power-ups).
  const moving = speed > 0.12
  const walk = moving ? Math.min(1, 0.55 + speed * 0.4) : 0
  const phase = time / (70 - walk * 16)
  const stride = moving ? Math.sin(phase) * walk : 0
  const bounce = moving
    ? Math.abs(Math.sin(phase)) * s * (0.028 + walk * 0.028)
    : Math.sin(time / 420) * s * 0.008

  // Classic skull cue: blink while cursed (disease type stays unnamed).
  const blinkOut = diseased && Math.floor(time / 120) % 2 === 0
  const prevAlpha = ctx.globalAlpha
  if (blinkOut) {
    ctx.globalAlpha = prevAlpha * 0.28
  }

  const cx = x + s / 2
  const cy = y + s / 2 - bounce
  const skin = '#f6c7a0'
  const skinShade = '#e39b72'
  const boot = shade(color, -0.45)
  const glove = shade(color, 0.35)
  const suitDark = shade(color, -0.22)
  const suitLite = shade(color, 0.28)

  const face: Record<string, [number, number]> = {
    up: [0, -1],
    down: [0, 1],
    left: [-1, 0.15],
    right: [1, 0.15],
    stop: [0, 0.6],
  }
  const facing = direction === 'stop' ? 'down' : direction
  const [fdx, fdy] = face[facing] ?? face.down!
  const backView = facing === 'up'
  const sideView = facing === 'left' || facing === 'right'

  if (isMe) {
    drawSelfMarker(ctx, cx, y + s * 0.78, s, color, time, selfMarker)
  }

  // Shadow stretches slightly along facing so even the ground cue reads direction.
  const shadowCX = cx + fdx * s * 0.04
  ctx.beginPath()
  ctx.ellipse(
    shadowCX,
    y + s * 0.78 + bounce * 0.3,
    s * (sideView ? 0.32 : 0.28),
    s * 0.09,
    0,
    0,
    Math.PI * 2,
  )
  ctx.fillStyle = 'rgba(0,0,0,0.3)'
  ctx.fill()

  ctx.save()
  ctx.translate(cx, cy)

  const body: BomberBodyOpts = {
    s,
    color,
    isMe,
    stride,
    fdx,
    fdy,
    facing,
    backView,
    sideView,
    skin,
    skinShade,
    boot,
    glove,
    suitDark,
    suitLite,
  }

  drawBomberSprite(ctx, body)

  ctx.restore()
  if (blinkOut) {
    ctx.globalAlpha = prevAlpha
  }

  if (diseased) {
    const pulse = 0.25 + 0.2 * Math.sin(time / 140)
    ctx.beginPath()
    ctx.ellipse(cx, y + s * 0.72, s * 0.34, s * 0.12, 0, 0, Math.PI * 2)
    ctx.fillStyle = `rgba(148, 80, 200, ${pulse})`
    ctx.fill()
  }
}

function drawParticles(
  ctx: CanvasRenderingContext2D,
  particles: Particle[],
  ox: number,
  oy: number,
  s: number,
) {
  for (const p of particles) {
    const alpha = Math.max(0, p.life / p.maxLife)
    const px = ox + p.x * s
    const py = oy + p.y * s
    const size = Math.max(1, p.size * s)
    if (p.kind === 'smoke') {
      ctx.beginPath()
      ctx.arc(px, py, size * 1.6, 0, Math.PI * 2)
      ctx.fillStyle = `rgba(80, 70, 60, ${0.2 * alpha})`
      ctx.fill()
    } else {
      ctx.beginPath()
      ctx.arc(px, py, size, 0, Math.PI * 2)
      ctx.fillStyle = rgba(p.color, 0.25 + 0.75 * alpha)
      ctx.fill()
    }
  }
}

/** Cached floor layer + hard/soft tile sprites (rebuild on theme or cell size change). */
type TileLayerCache = {
  key: string
  floor: HTMLCanvasElement
  hard: HTMLCanvasElement
  soft: HTMLCanvasElement
  cell: number
  gridW: number
  gridH: number
}

let tileLayerCache: TileLayerCache | null = null

function makeCanvas(w: number, h: number): HTMLCanvasElement {
  const c = document.createElement('canvas')
  c.width = Math.max(1, w)
  c.height = Math.max(1, h)
  return c
}

function ensureTileLayerCache(
  theme: MapTheme,
  gridW: number,
  gridH: number,
  s: number,
): TileLayerCache {
  const key = `${theme.id}:${gridW}x${gridH}:${s}`
  if (tileLayerCache && tileLayerCache.key === key) return tileLayerCache

  const floor = makeCanvas(gridW * s, gridH * s)
  const fctx = floor.getContext('2d')!
  const boardW = gridW * s
  const boardH = gridH * s
  const grad = fctx.createLinearGradient(0, 0, 0, boardH)
  grad.addColorStop(0, theme.floorTop)
  grad.addColorStop(1, theme.floorBottom)
  fctx.fillStyle = grad
  fctx.fillRect(0, 0, boardW, boardH)
  for (let y = 0; y < gridH; y++) {
    for (let x = 0; x < gridW; x++) {
      const px = x * s
      const py = y * s
      if ((x + y) % 2 === 0) {
        fctx.fillStyle = theme.checker
        fctx.fillRect(px, py, s, s)
      }
      fctx.strokeStyle = theme.tileInset
      fctx.lineWidth = 1
      fctx.strokeRect(px + 0.5, py + 0.5, s - 1, s - 1)
    }
  }

  const hard = makeCanvas(s, s)
  drawHardBlock(hard.getContext('2d')!, 0, 0, s, theme)

  const soft = makeCanvas(s, s)
  // Static soft sprite (no per-frame wobble) — gradients baked once.
  drawSoftBlock(soft.getContext('2d')!, 0, 0, s, 0, theme)

  tileLayerCache = { key, floor, hard, soft, cell: s, gridW, gridH }
  return tileLayerCache
}

function drawScreenVignette(
  ctx: CanvasRenderingContext2D,
  displayW: number,
  displayH: number,
  theme: MapTheme,
) {
  const vig = ctx.createRadialGradient(
    displayW / 2,
    displayH / 2,
    Math.min(displayW, displayH) * 0.2,
    displayW / 2,
    displayH / 2,
    Math.max(displayW, displayH) * 0.72,
  )
  vig.addColorStop(0, 'rgba(0,0,0,0)')
  vig.addColorStop(1, theme.vignette)
  ctx.fillStyle = vig
  ctx.fillRect(0, 0, displayW, displayH)
}

export function renderFrame(
  ctx: CanvasRenderingContext2D,
  displayW: number,
  displayH: number,
  input: RenderFrameInput,
) {
  const {
    gridW,
    gridH,
    grid,
    bombers,
    bombs,
    explosions,
    powerups,
    playerId,
    time,
    particles = [],
    shake = 0,
    mapId,
    selfMarker = 0,
    focusX: focusXOverride,
    focusY: focusYOverride,
  } = input
  const theme = getMapTheme(mapId)
  const s = cellSize(displayW, displayH, gridW, gridH)
  const boardW = s * gridW
  const boardH = s * gridH

  const me = bombers[playerId]
  const focusX =
    focusXOverride ?? (me ? me.x : (gridW - 1) / 2)
  const focusY =
    focusYOverride ?? (me ? me.y : (gridH - 1) / 2)
  let { ox, oy } = cameraOffset(displayW, displayH, gridW, gridH, s, focusX, focusY)

  if (shake > 0.01) {
    ox += Math.sin(time * 0.08) * shake * 4
    oy += Math.cos(time * 0.11) * shake * 3
  }

  const range = visibleTileRange(displayW, displayH, gridW, gridH, s, ox, oy)
  const inView = (x: number, y: number) =>
    x >= range.x0 - 1 && x < range.x1 + 1 && y >= range.y0 - 1 && y < range.y1 + 1

  ctx.clearRect(0, 0, displayW, displayH)
  // Off-map backdrop when the camera is clamped at a map edge.
  ctx.fillStyle = theme.wrapBottom
  ctx.fillRect(0, 0, displayW, displayH)

  const layers = ensureTileLayerCache(theme, gridW, gridH, s)
  // Blit only the visible floor region from the cached full-board layer.
  const srcX = range.x0 * s
  const srcY = range.y0 * s
  const srcW = (range.x1 - range.x0) * s
  const srcH = (range.y1 - range.y0) * s
  if (srcW > 0 && srcH > 0) {
    ctx.drawImage(
      layers.floor,
      srcX,
      srcY,
      srcW,
      srcH,
      ox + srcX,
      oy + srcY,
      srcW,
      srcH,
    )
  }
  drawScreenVignette(ctx, displayW, displayH, theme)

  for (let y = range.y0; y < range.y1; y++) {
    const row = grid[y] ?? []
    for (let x = range.x0; x < range.x1; x++) {
      if ((row[x] ?? TILE_EMPTY) === TILE_SOFT) {
        ctx.drawImage(layers.soft, ox + x * s, oy + y * s)
      }
    }
  }
  for (let y = range.y0; y < range.y1; y++) {
    const row = grid[y] ?? []
    for (let x = range.x0; x < range.x1; x++) {
      if ((row[x] ?? TILE_EMPTY) === TILE_HARD) {
        ctx.drawImage(layers.hard, ox + x * s, oy + y * s)
      }
    }
  }

  for (const p of powerups) {
    if (!inView(p.x, p.y)) continue
    drawPowerup(ctx, ox + p.x * s, oy + p.y * s, s, p.type, time)
  }

  for (const b of bombs) {
    if (b.flight === 'carried') continue
    if (!inView(b.x, b.y)) continue
    drawBomb(
      ctx,
      ox + b.x * s,
      oy + b.y * s,
      s,
      b.fuse,
      time,
      b.slide_dir ?? null,
      b.flight ?? null,
    )
  }

  drawExplosions(ctx, explosions, ox, oy, s, time)

  drawParticles(ctx, particles, ox, oy, s)

  const entries = Object.entries(bombers).filter(
    ([, b]) => b.alive && !(Number(b.respawn_ticks ?? 0) > 0),
  )
  entries.sort(([a], [b]) => (a === playerId ? 1 : b === playerId ? -1 : 0))
  for (const [pid, b] of entries) {
    if (!inView(b.x, b.y)) continue
    const isMe = pid === playerId
    drawBomber(
      ctx,
      ox + b.x * s,
      oy + b.y * s,
      s,
      b.color,
      isMe,
      b.direction,
      time,
      b.speed ?? 0,
      Boolean(b.disease),
      isMe ? selfMarker : 0,
    )
  }

  for (const b of bombs) {
    if (b.flight !== 'carried') continue
    if (!inView(b.x, b.y)) continue
    drawBomb(
      ctx,
      ox + b.x * s,
      oy + b.y * s,
      s,
      b.fuse,
      time,
      null,
      'carried',
    )
  }

  ctx.strokeStyle = `rgba(${theme.accentRgb}, 0.22)`
  ctx.lineWidth = 2
  ctx.strokeRect(ox - 1, oy - 1, boardW + 2, boardH + 2)
}
