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
}

export interface SmoothBomber extends BomberSnapshot {
  /** Cells per second, for walk-cycle animation. */
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
    { x: number; y: number; alive: boolean; color: string; direction: string; speed?: number }
  >
  bombs: BombermanBomb[]
  explosions: BombermanExplosion[]
  powerups: BombermanPowerup[]
  playerId: string
  time: number
  particles?: Particle[]
  shake?: number
}

function cellSize(displayW: number, displayH: number, gridW: number, gridH: number) {
  return Math.floor(Math.min(displayW / gridW, displayH / gridH))
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

export function interpolateBombers(
  prev: Record<string, BomberSnapshot>,
  target: Record<string, BomberSnapshot>,
  t: number,
): Record<string, { x: number; y: number; alive: boolean; color: string; direction: string }> {
  const out: Record<string, { x: number; y: number; alive: boolean; color: string; direction: string }> = {}
  for (const [pid, cur] of Object.entries(target)) {
    const p = prev[pid]
    if (!p || !cur.alive) {
      out[pid] = { ...cur }
      continue
    }
    const dx = cur.x - p.x
    const dy = cur.y - p.y
    // Snap on teleports / respawns
    if (Math.abs(dx) > 1.5 || Math.abs(dy) > 1.5) {
      out[pid] = { ...cur }
      continue
    }
    out[pid] = {
      x: p.x + dx * t,
      y: p.y + dy * t,
      alive: cur.alive,
      color: cur.color,
      direction: cur.direction,
    }
  }
  return out
}

/**
 * Continuously ease display positions toward server grid coords.
 * Feels smoother than per-tick lerp when ticks jitter or speed moves 2+ cells.
 */
export function smoothBombers(
  display: Record<string, SmoothBomber>,
  target: Record<string, BomberSnapshot>,
  dt: number,
  followHz = 18,
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
    // Hard snap on large jumps (death warp / desync).
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
      // Keep last facing briefly while settling onto a cell.
      direction = prev.direction
    }

    out[pid] = {
      x,
      y,
      alive: cur.alive,
      color: cur.color,
      direction,
      speed,
    }
  }

  return out
}

/** Smooth kicked / thrown bombs the same way. */
export function smoothBombs(
  display: Record<string, { x: number; y: number }>,
  bombs: BombermanBomb[],
  dt: number,
  followHz = 20,
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
  // Mutate display map in place for caller convenience
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

export function spawnDebrisParticles(cx: number, cy: number, count = 8): Particle[] {
  const particles: Particle[] = []
  const colors = ['#c47a3a', '#a05a28', '#d4924e', '#6b3a18']
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

function drawHardBlock(ctx: CanvasRenderingContext2D, x: number, y: number, s: number) {
  const pad = s * 0.05
  const bx = x + pad
  const by = y + pad
  const bw = s - pad * 2
  const bh = s - pad * 2

  // Depth shadow
  ctx.fillStyle = 'rgba(0,0,0,0.35)'
  drawRoundRect(ctx, bx + s * 0.04, by + s * 0.05, bw, bh, s * 0.1)
  ctx.fill()

  const grad = ctx.createLinearGradient(bx, by, bx, by + bh)
  grad.addColorStop(0, '#5a6578')
  grad.addColorStop(0.45, '#3d4656')
  grad.addColorStop(1, '#2a3140')
  drawRoundRect(ctx, bx, by, bw, bh, s * 0.1)
  ctx.fillStyle = grad
  ctx.fill()

  ctx.strokeStyle = 'rgba(0,0,0,0.45)'
  ctx.lineWidth = Math.max(1, s * 0.04)
  ctx.stroke()

  // Rivets
  ctx.fillStyle = 'rgba(255,255,255,0.14)'
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

  // Top sheen
  ctx.fillStyle = 'rgba(255,255,255,0.1)'
  drawRoundRect(ctx, bx + bw * 0.12, by + bh * 0.1, bw * 0.5, bh * 0.16, 2)
  ctx.fill()
}

function drawSoftBlock(
  ctx: CanvasRenderingContext2D,
  x: number,
  y: number,
  s: number,
  time: number,
) {
  const pad = s * 0.07
  const bx = x + pad
  const by = y + pad
  const bw = s - pad * 2
  const bh = s - pad * 2
  const wobble = Math.sin(time / 900 + x * 0.07 + y * 0.11) * s * 0.008

  ctx.fillStyle = 'rgba(0,0,0,0.28)'
  drawRoundRect(ctx, bx + s * 0.03, by + s * 0.04, bw, bh, s * 0.08)
  ctx.fill()

  const grad = ctx.createLinearGradient(bx, by, bx + bw, by + bh)
  grad.addColorStop(0, '#e09a55')
  grad.addColorStop(0.5, '#c47432')
  grad.addColorStop(1, '#8f4a1c')
  drawRoundRect(ctx, bx, by + wobble, bw, bh, s * 0.08)
  ctx.fillStyle = grad
  ctx.fill()

  ctx.strokeStyle = 'rgba(60, 28, 8, 0.5)'
  ctx.lineWidth = Math.max(1, s * 0.035)
  ctx.stroke()

  // Brick mortar lines
  ctx.strokeStyle = 'rgba(0,0,0,0.22)'
  ctx.lineWidth = Math.max(1, s * 0.03)
  ctx.beginPath()
  ctx.moveTo(bx + bw * 0.5, by + wobble)
  ctx.lineTo(bx + bw * 0.5, by + bh + wobble)
  ctx.moveTo(bx, by + bh * 0.33 + wobble)
  ctx.lineTo(bx + bw * 0.5, by + bh * 0.33 + wobble)
  ctx.moveTo(bx + bw * 0.5, by + bh * 0.66 + wobble)
  ctx.lineTo(bx + bw, by + bh * 0.66 + wobble)
  ctx.stroke()

  ctx.fillStyle = 'rgba(255,220,160,0.12)'
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
  sliding = false,
  slideDir: string | null = null,
  flight: string | null = null,
) {
  const dirOff: Record<string, [number, number]> = {
    up: [0, -0.12],
    down: [0, 0.12],
    left: [-0.12, 0],
    right: [0.12, 0],
  }
  const airborne = flight === 'throw' || (sliding && flight !== 'kick')
  const kicking = flight === 'kick'
  const [ox, oy] = sliding && slideDir ? (dirOff[slideDir] ?? [0, 0]) : [0, 0]
  const lift = airborne ? s * 0.14 : kicking ? s * 0.04 : 0
  const cx = x + s / 2 + ox * s
  const cy = y + s / 2 + oy * s - lift
  const urgent = fuse <= 5
  const pulse = 1 + Math.sin(time / (urgent ? 45 : 90) + fuse) * (urgent ? 0.1 : 0.045)
  const r = s * 0.3 * pulse

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
    r * (airborne ? 0.5 : kicking ? 0.65 : 0.75),
    r * 0.28,
    0,
    0,
    Math.PI * 2,
  )
  ctx.fillStyle = airborne || kicking ? 'rgba(0,0,0,0.22)' : 'rgba(0,0,0,0.35)'
  ctx.fill()

  const body = ctx.createRadialGradient(cx - r * 0.3, cy - r * 0.25, r * 0.1, cx, cy, r)
  body.addColorStop(0, '#3a3a42')
  body.addColorStop(0.55, '#16161c')
  body.addColorStop(1, '#050508')
  ctx.beginPath()
  ctx.arc(cx, cy + s * 0.02, r, 0, Math.PI * 2)
  ctx.fillStyle = body
  ctx.fill()
  ctx.strokeStyle = airborne
    ? 'rgba(251, 191, 36, 0.5)'
    : kicking
      ? 'rgba(244, 114, 182, 0.55)'
      : 'rgba(255,255,255,0.12)'
  ctx.lineWidth = sliding ? Math.max(1.5, s * 0.045) : 1
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

  // Outer glow
  const glow = ctx.createRadialGradient(cx, cy, s * 0.05, cx, cy, s * 0.62)
  glow.addColorStop(0, `rgba(255, 240, 160, ${0.55 * intensity * flicker})`)
  glow.addColorStop(0.35, `rgba(255, 120, 30, ${0.4 * intensity})`)
  glow.addColorStop(1, 'rgba(255, 40, 0, 0)')
  ctx.fillStyle = glow
  ctx.beginPath()
  ctx.arc(cx, cy, s * 0.62, 0, Math.PI * 2)
  ctx.fill()

  const pad = s * (0.12 + (1 - intensity) * 0.12)
  const coreGrad = ctx.createLinearGradient(x, y, x + s, y + s)
  coreGrad.addColorStop(0, `rgba(255, 210, 90, ${0.85 * intensity * flicker})`)
  coreGrad.addColorStop(0.5, `rgba(255, 110, 30, ${0.75 * intensity})`)
  coreGrad.addColorStop(1, `rgba(220, 40, 10, ${0.55 * intensity})`)
  drawRoundRect(ctx, x + pad, y + pad, s - pad * 2, s - pad * 2, s * 0.18)
  ctx.fillStyle = coreGrad
  ctx.fill()

  // Hot core
  ctx.beginPath()
  ctx.arc(cx, cy, s * 0.16 * intensity, 0, Math.PI * 2)
  ctx.fillStyle = `rgba(255, 255, 230, ${0.7 * intensity * flicker})`
  ctx.fill()
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
  }
  const labels: Record<string, string> = {
    bomb: '💣',
    range: '🔥',
    speed: '⚡',
    throw: '🧤',
    kick: '🦵',
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
) {
  const moving = speed > 0.4 || direction !== 'stop'
  const walk = Math.min(1, speed / 8)
  const bounce = moving
    ? Math.abs(Math.sin(time / (75 - walk * 18))) * s * (0.035 + walk * 0.035)
    : Math.sin(time / 420) * s * 0.01
  const squash = moving ? 1 + Math.sin(time / (75 - walk * 18)) * 0.04 * walk : 1
  const cx = x + s / 2
  const cy = y + s / 2 - bounce
  const bodyR = s * 0.3

  // Shadow
  ctx.beginPath()
  ctx.ellipse(
    cx,
    y + s * 0.72 + bounce * 0.35,
    bodyR * (0.85 + walk * 0.08) * squash,
    bodyR * (0.26 / squash),
    0,
    0,
    Math.PI * 2,
  )
  ctx.fillStyle = 'rgba(0,0,0,0.32)'
  ctx.fill()

  // You indicator ring
  if (isMe) {
    ctx.beginPath()
    ctx.arc(cx, cy, bodyR * 1.35, 0, Math.PI * 2)
    ctx.strokeStyle = rgba(color, 0.35 + Math.sin(time / 200) * 0.1)
    ctx.lineWidth = Math.max(1.5, s * 0.045)
    ctx.stroke()
  }

  // Body with slight walk squash
  ctx.save()
  ctx.translate(cx, cy)
  ctx.scale(squash, 1 / squash)
  const bodyGrad = ctx.createRadialGradient(
    -bodyR * 0.3,
    -bodyR * 0.35,
    bodyR * 0.15,
    0,
    0,
    bodyR,
  )
  bodyGrad.addColorStop(0, shade(color, 0.35))
  bodyGrad.addColorStop(0.55, color)
  bodyGrad.addColorStop(1, shade(color, -0.25))
  ctx.beginPath()
  ctx.arc(0, 0, bodyR, 0, Math.PI * 2)
  ctx.fillStyle = bodyGrad
  ctx.fill()
  ctx.strokeStyle = isMe ? 'rgba(255,255,255,0.85)' : 'rgba(0,0,0,0.35)'
  ctx.lineWidth = isMe ? Math.max(2, s * 0.06) : 1.2
  ctx.stroke()

  // Helmet band
  ctx.beginPath()
  ctx.arc(0, -bodyR * 0.15, bodyR * 0.92, Math.PI * 1.15, Math.PI * 1.85)
  ctx.strokeStyle = 'rgba(255,255,255,0.22)'
  ctx.lineWidth = Math.max(2, s * 0.07)
  ctx.stroke()
  ctx.restore()

  // Eyes face direction
  const face: Record<string, [number, number]> = {
    up: [0, -0.14],
    down: [0, 0.16],
    left: [-0.16, 0.04],
    right: [0.16, 0.04],
    stop: [0, 0.06],
  }
  const [fx, fy] = face[direction] ?? face.stop!
  const eyeY = cy + fy * s
  const eyeSpread = s * 0.11
  for (const side of [-1, 1] as const) {
    const ex = cx + fx * s + side * eyeSpread
    ctx.beginPath()
    ctx.arc(ex, eyeY, s * 0.07, 0, Math.PI * 2)
    ctx.fillStyle = '#fff'
    ctx.fill()
    ctx.beginPath()
    ctx.arc(ex + fx * s * 0.15, eyeY + fy * s * 0.1, s * 0.038, 0, Math.PI * 2)
    ctx.fillStyle = '#111'
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

function drawFloor(
  ctx: CanvasRenderingContext2D,
  ox: number,
  oy: number,
  boardW: number,
  boardH: number,
  gridW: number,
  gridH: number,
  s: number,
) {
  const floor = ctx.createLinearGradient(ox, oy, ox, oy + boardH)
  floor.addColorStop(0, '#1c2838')
  floor.addColorStop(1, '#121a24')
  ctx.fillStyle = floor
  ctx.fillRect(ox, oy, boardW, boardH)

  for (let y = 0; y < gridH; y++) {
    for (let x = 0; x < gridW; x++) {
      const px = ox + x * s
      const py = oy + y * s
      if ((x + y) % 2 === 0) {
        ctx.fillStyle = 'rgba(255,255,255,0.025)'
        ctx.fillRect(px, py, s, s)
      }
      // Subtle tile inset
      ctx.strokeStyle = 'rgba(0,0,0,0.12)'
      ctx.lineWidth = 1
      ctx.strokeRect(px + 0.5, py + 0.5, s - 1, s - 1)
    }
  }

  // Arena vignette inside board
  const vig = ctx.createRadialGradient(
    ox + boardW / 2,
    oy + boardH / 2,
    boardH * 0.2,
    ox + boardW / 2,
    oy + boardH / 2,
    boardW * 0.72,
  )
  vig.addColorStop(0, 'rgba(0,0,0,0)')
  vig.addColorStop(1, 'rgba(0,0,0,0.28)')
  ctx.fillStyle = vig
  ctx.fillRect(ox, oy, boardW, boardH)
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
  } = input
  const s = cellSize(displayW, displayH, gridW, gridH)
  const boardW = s * gridW
  const boardH = s * gridH
  let ox = Math.floor((displayW - boardW) / 2)
  let oy = Math.floor((displayH - boardH) / 2)

  if (shake > 0.01) {
    ox += Math.sin(time * 0.08) * shake * 4
    oy += Math.cos(time * 0.11) * shake * 3
  }

  ctx.clearRect(0, 0, displayW, displayH)
  drawFloor(ctx, ox, oy, boardW, boardH, gridW, gridH, s)

  // Soft then hard for depth ordering feel
  for (let y = 0; y < gridH; y++) {
    const row = grid[y] ?? []
    for (let x = 0; x < gridW; x++) {
      if ((row[x] ?? TILE_EMPTY) === TILE_SOFT) {
        drawSoftBlock(ctx, ox + x * s, oy + y * s, s, time)
      }
    }
  }
  for (let y = 0; y < gridH; y++) {
    const row = grid[y] ?? []
    for (let x = 0; x < gridW; x++) {
      if ((row[x] ?? TILE_EMPTY) === TILE_HARD) {
        drawHardBlock(ctx, ox + x * s, oy + y * s, s)
      }
    }
  }

  for (const p of powerups) {
    drawPowerup(ctx, ox + p.x * s, oy + p.y * s, s, p.type, time)
  }

  for (const b of bombs) {
    drawBomb(
      ctx,
      ox + b.x * s,
      oy + b.y * s,
      s,
      b.fuse,
      time,
      Boolean(b.sliding || b.flight),
      b.slide_dir ?? null,
      b.flight ?? null,
    )
  }

  for (const e of explosions) {
    drawExplosion(ctx, ox + e.x * s, oy + e.y * s, s, e.ttl, time)
  }

  drawParticles(ctx, particles, ox, oy, s)

  // Draw alive bombers last; sort so local player is on top
  const entries = Object.entries(bombers).filter(([, b]) => b.alive)
  entries.sort(([a], [b]) => (a === playerId ? 1 : b === playerId ? -1 : 0))
  for (const [pid, b] of entries) {
    drawBomber(
      ctx,
      ox + b.x * s,
      oy + b.y * s,
      s,
      b.color,
      pid === playerId,
      b.direction,
      time,
      b.speed ?? 0,
    )
  }

  // Soft outer frame
  ctx.strokeStyle = 'rgba(249, 115, 22, 0.22)'
  ctx.lineWidth = 2
  ctx.strokeRect(ox - 1, oy - 1, boardW + 2, boardH + 2)
}
