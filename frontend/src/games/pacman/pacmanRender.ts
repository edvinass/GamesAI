export const TILE_PATH = 0
export const TILE_WALL = 1

export interface EntitySnapshot {
  x: number
  y: number
  alive: boolean
  color: string
  direction: string
  powered?: boolean
  frightened?: boolean
  eaten?: boolean
  visible?: boolean
}

export interface SmoothEntity extends EntitySnapshot {
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
}

export interface RenderFrameInput {
  gridW: number
  gridH: number
  grid: number[][]
  pellets: boolean[][]
  powerPellets: boolean[][]
  pacmen: Record<string, SmoothEntity>
  ghosts: SmoothEntity[]
  playerId: string
  time: number
  particles?: Particle[]
  mode?: string
}

function cellSize(displayW: number, displayH: number, gridW: number, gridH: number) {
  return Math.floor(Math.min(displayW / gridW, displayH / gridH))
}

export function snapshotEntities(
  pacmen: Record<string, {
    x: number
    y: number
    alive: boolean
    color: string
    direction: string
    powered_ticks?: number
    respawn_ticks?: number
  }>,
  ghosts: Array<{
    x: number
    y: number
    color: string
    direction: string
    frightened_ticks?: number
    eaten?: boolean
    mode?: string
  }>,
): { pacmen: Record<string, EntitySnapshot>; ghosts: EntitySnapshot[] } {
  const pOut: Record<string, EntitySnapshot> = {}
  for (const [pid, p] of Object.entries(pacmen)) {
    pOut[pid] = {
      x: p.x,
      y: p.y,
      alive: p.alive,
      color: p.color,
      direction: p.direction,
      powered: (p.powered_ticks ?? 0) > 0,
      visible: (p.respawn_ticks ?? 0) <= 0,
    }
  }
  const gOut = ghosts.map((g) => ({
    x: g.x,
    y: g.y,
    alive: true,
    color: g.color,
    direction: g.direction,
    frightened: (g.frightened_ticks ?? 0) > 0 || g.mode === 'frightened',
    eaten: Boolean(g.eaten),
    visible: true,
  }))
  return { pacmen: pOut, ghosts: gOut }
}

export function smoothEntities(
  display: Record<string, SmoothEntity>,
  target: Record<string, EntitySnapshot>,
  dt: number,
  followHz = 20,
): Record<string, SmoothEntity> {
  const alpha = 1 - Math.exp(-followHz * Math.max(0, dt))
  const out: Record<string, SmoothEntity> = {}
  for (const [id, cur] of Object.entries(target)) {
    const prev = display[id]
    if (!prev || !cur.alive || !prev.alive || cur.visible === false) {
      out[id] = { ...cur, speed: 0 }
      continue
    }
    const dx = cur.x - prev.x
    const dy = cur.y - prev.y
    if (Math.abs(dx) > 2.5 || Math.abs(dy) > 2.5) {
      out[id] = { ...cur, speed: 0 }
      continue
    }
    const nx = prev.x + dx * alpha
    const ny = prev.y + dy * alpha
    const speed = Math.hypot(nx - prev.x, ny - prev.y) / Math.max(dt, 1e-4)
    out[id] = { ...cur, x: nx, y: ny, speed }
  }
  return out
}

export function smoothGhostList(
  display: SmoothEntity[],
  target: EntitySnapshot[],
  dt: number,
  followHz = 20,
): SmoothEntity[] {
  const byIndex = Object.fromEntries(display.map((g, i) => [String(i), g]))
  const targetMap = Object.fromEntries(target.map((g, i) => [String(i), g]))
  const smoothed = smoothEntities(byIndex, targetMap, dt, followHz)
  return target.map((_, i) => smoothed[String(i)] ?? { ...target[i]!, speed: 0 })
}

export function spawnChompParticles(x: number, y: number, color = '#facc15'): Particle[] {
  const out: Particle[] = []
  for (let i = 0; i < 6; i++) {
    const a = (Math.PI * 2 * i) / 6
    out.push({
      x: x + 0.5,
      y: y + 0.5,
      vx: Math.cos(a) * (1.5 + Math.random()),
      vy: Math.sin(a) * (1.5 + Math.random()),
      life: 0.35,
      maxLife: 0.35,
      color,
      size: 0.12,
    })
  }
  return out
}

export function updateParticles(particles: Particle[], dt: number): Particle[] {
  const out: Particle[] = []
  for (const p of particles) {
    const life = p.life - dt
    if (life <= 0) continue
    out.push({
      ...p,
      x: p.x + p.vx * dt,
      y: p.y + p.vy * dt,
      vx: p.vx * 0.92,
      vy: p.vy * 0.92,
      life,
    })
  }
  return out
}

function drawPac(
  ctx: CanvasRenderingContext2D,
  cx: number,
  cy: number,
  r: number,
  direction: string,
  color: string,
  time: number,
  powered: boolean,
) {
  const mouth = 0.25 + 0.2 * Math.abs(Math.sin(time / 80))
  const angles: Record<string, number> = {
    right: 0,
    down: Math.PI / 2,
    left: Math.PI,
    up: -Math.PI / 2,
  }
  const rot = angles[direction] ?? 0
  ctx.save()
  ctx.translate(cx, cy)
  ctx.rotate(rot)
  ctx.beginPath()
  ctx.moveTo(0, 0)
  ctx.arc(0, 0, r, mouth, Math.PI * 2 - mouth)
  ctx.closePath()
  ctx.fillStyle = powered ? '#fff7ad' : color
  ctx.fill()
  if (powered) {
    ctx.strokeStyle = 'rgba(255,255,255,0.7)'
    ctx.lineWidth = 2
    ctx.stroke()
  }
  ctx.restore()
}

function drawGhost(
  ctx: CanvasRenderingContext2D,
  cx: number,
  cy: number,
  r: number,
  color: string,
  frightened: boolean,
  eaten: boolean,
  time: number,
) {
  if (eaten) {
    ctx.fillStyle = '#e2e8f0'
    ctx.beginPath()
    ctx.arc(cx - r * 0.3, cy - r * 0.1, r * 0.22, 0, Math.PI * 2)
    ctx.arc(cx + r * 0.3, cy - r * 0.1, r * 0.22, 0, Math.PI * 2)
    ctx.fill()
    ctx.fillStyle = '#1e293b'
    ctx.beginPath()
    ctx.arc(cx - r * 0.3, cy - r * 0.1, r * 0.1, 0, Math.PI * 2)
    ctx.arc(cx + r * 0.3, cy - r * 0.1, r * 0.1, 0, Math.PI * 2)
    ctx.fill()
    return
  }

  const body = frightened
    ? (Math.floor(time / 120) % 2 === 0 ? '#64748b' : '#94a3b8')
    : color

  ctx.fillStyle = body
  ctx.beginPath()
  ctx.arc(cx, cy - r * 0.15, r * 0.85, Math.PI, 0)
  ctx.lineTo(cx + r * 0.85, cy + r * 0.75)
  const waves = 4
  for (let i = waves; i >= 0; i--) {
    const wx = cx - r * 0.85 + (r * 1.7 * i) / waves
    const wy = cy + r * 0.75 + (i % 2 === 0 ? r * 0.2 : -r * 0.05)
    ctx.lineTo(wx, wy)
  }
  ctx.closePath()
  ctx.fill()

  ctx.fillStyle = frightened ? '#1e293b' : '#fff'
  const eyeY = cy - r * 0.25
  ctx.beginPath()
  ctx.arc(cx - r * 0.28, eyeY, r * 0.2, 0, Math.PI * 2)
  ctx.arc(cx + r * 0.28, eyeY, r * 0.2, 0, Math.PI * 2)
  ctx.fill()
  if (!frightened) {
    ctx.fillStyle = '#1e3a5f'
    ctx.beginPath()
    ctx.arc(cx - r * 0.22, eyeY, r * 0.1, 0, Math.PI * 2)
    ctx.arc(cx + r * 0.34, eyeY, r * 0.1, 0, Math.PI * 2)
    ctx.fill()
  }
}

export function renderFrame(
  ctx: CanvasRenderingContext2D,
  displayW: number,
  displayH: number,
  input: RenderFrameInput,
) {
  const { gridW, gridH, grid, pellets, powerPellets, pacmen, ghosts, playerId, time, particles } =
    input
  const cs = cellSize(displayW, displayH, gridW, gridH)
  const ox = Math.floor((displayW - cs * gridW) / 2)
  const oy = Math.floor((displayH - cs * gridH) / 2)

  ctx.clearRect(0, 0, displayW, displayH)

  // Atmosphere
  const bg = ctx.createRadialGradient(
    displayW * 0.5,
    displayH * 0.4,
    20,
    displayW * 0.5,
    displayH * 0.5,
    Math.max(displayW, displayH) * 0.7,
  )
  bg.addColorStop(0, '#0b1a3a')
  bg.addColorStop(1, '#050914')
  ctx.fillStyle = bg
  ctx.fillRect(0, 0, displayW, displayH)

  // Walls
  for (let y = 0; y < gridH; y++) {
    for (let x = 0; x < gridW; x++) {
      if (grid[y]?.[x] !== TILE_WALL) continue
      const px = ox + x * cs
      const py = oy + y * cs
      ctx.fillStyle = '#1d4ed8'
      ctx.fillRect(px + 1, py + 1, cs - 2, cs - 2)
      ctx.strokeStyle = '#60a5fa'
      ctx.lineWidth = Math.max(1, cs * 0.08)
      ctx.strokeRect(px + 2, py + 2, cs - 4, cs - 4)
    }
  }

  // Pellets
  for (let y = 0; y < gridH; y++) {
    for (let x = 0; x < gridW; x++) {
      const px = ox + x * cs + cs / 2
      const py = oy + y * cs + cs / 2
      if (powerPellets[y]?.[x]) {
        const pulse = 0.7 + 0.3 * Math.sin(time / 140)
        ctx.fillStyle = `rgba(253, 224, 71, ${0.85 * pulse})`
        ctx.beginPath()
        ctx.arc(px, py, cs * 0.28 * pulse, 0, Math.PI * 2)
        ctx.fill()
      } else if (pellets[y]?.[x]) {
        ctx.fillStyle = '#fde047'
        ctx.beginPath()
        ctx.arc(px, py, Math.max(1.5, cs * 0.1), 0, Math.PI * 2)
        ctx.fill()
      }
    }
  }

  // Ghosts under pacmen
  for (const g of ghosts) {
    if (g.visible === false) continue
    drawGhost(
      ctx,
      ox + (g.x + 0.5) * cs,
      oy + (g.y + 0.5) * cs,
      cs * 0.42,
      g.color,
      Boolean(g.frightened),
      Boolean(g.eaten),
      time,
    )
  }

  for (const [pid, p] of Object.entries(pacmen)) {
    if (!p.alive || p.visible === false) continue
    const isMe = pid === playerId
    if (isMe) {
      ctx.strokeStyle = 'rgba(255,255,255,0.35)'
      ctx.lineWidth = 2
      ctx.beginPath()
      ctx.arc(ox + (p.x + 0.5) * cs, oy + (p.y + 0.5) * cs, cs * 0.52, 0, Math.PI * 2)
      ctx.stroke()
    }
    drawPac(
      ctx,
      ox + (p.x + 0.5) * cs,
      oy + (p.y + 0.5) * cs,
      cs * 0.4,
      p.direction,
      p.color,
      time,
      Boolean(p.powered),
    )
  }

  for (const p of particles ?? []) {
    const a = p.life / p.maxLife
    ctx.fillStyle = p.color
    ctx.globalAlpha = a
    ctx.beginPath()
    ctx.arc(ox + p.x * cs, oy + p.y * cs, p.size * cs, 0, Math.PI * 2)
    ctx.fill()
    ctx.globalAlpha = 1
  }
}
