export const TILE_PATH = 0
export const TILE_WALL = 1

/** Classic arcade palette */
export const CLASSIC = {
  wall: '#2121de',
  wallHi: '#3b5bff',
  wallGlow: 'rgba(60, 90, 255, 0.4)',
  floor: '#000000',
  pellet: '#ffb897',
  power: '#ffb897',
  gate: '#ffb8ff',
  pacYellow: '#ffff00',
}

export interface EntitySnapshot {
  x: number
  y: number
  alive: boolean
  color: string
  direction: string
  powered?: boolean
  frightened?: boolean
  frightenedTicks?: number
  eaten?: boolean
  visible?: boolean
  invuln?: boolean
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
  gate?: number[] | null
}

const DIR_DELTA: Record<string, [number, number]> = {
  up: [0, -1],
  down: [0, 1],
  left: [-1, 0],
  right: [1, 0],
}

function cellSize(displayW: number, displayH: number, gridW: number, gridH: number) {
  return Math.floor(Math.min(displayW / gridW, displayH / gridH))
}

export function snapshotEntities(
  pacmen: Record<
    string,
    {
      x: number
      y: number
      alive: boolean
      color: string
      direction: string
      powered_ticks?: number
      respawn_ticks?: number
      invuln_ticks?: number
    }
  >,
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
      invuln: (p.invuln_ticks ?? 0) > 0,
    }
  }
  const gOut = ghosts.map((g) => ({
    x: g.x,
    y: g.y,
    alive: true,
    color: g.color,
    direction: g.direction,
    frightened: (g.frightened_ticks ?? 0) > 0 || g.mode === 'frightened',
    frightenedTicks: g.frightened_ticks ?? 0,
    eaten: Boolean(g.eaten),
    visible: true,
  }))
  return { pacmen: pOut, ghosts: gOut }
}

/** Linear interpolate with tunnel-aware snap (no cross-map lerp). */
export function lerpEntity(
  prev: EntitySnapshot | undefined,
  target: EntitySnapshot,
  t: number,
  gridW: number,
): SmoothEntity {
  if (!prev || !target.alive || !prev.alive || target.visible === false) {
    return { ...target, speed: 0 }
  }
  let dx = target.x - prev.x
  let dy = target.y - prev.y
  // Tunnel wrap: jump instead of sliding across the maze.
  if (Math.abs(dx) > gridW * 0.5 || Math.abs(dx) > 2.2 || Math.abs(dy) > 2.2) {
    return { ...target, speed: 0 }
  }
  // Slight overshoot before next tick for continuous arcade glide.
  const u = t <= 1 ? t : 1 + Math.min(0.35, t - 1) * 0.45
  const x = prev.x + dx * Math.min(u, 1.15)
  const y = prev.y + dy * Math.min(u, 1.15)
  // If past the tick, nudge along facing so motion doesn't freeze.
  if (t > 1) {
    const [ddx, ddy] = DIR_DELTA[target.direction] ?? [0, 0]
    const extra = Math.min(0.35, t - 1) * 0.5
    return {
      ...target,
      x: target.x + ddx * extra,
      y: target.y + ddy * extra,
      speed: Math.hypot(dx, dy),
    }
  }
  return { ...target, x, y, speed: Math.hypot(dx, dy) }
}

export function lerpEntities(
  prev: Record<string, EntitySnapshot>,
  target: Record<string, EntitySnapshot>,
  t: number,
  gridW: number,
): Record<string, SmoothEntity> {
  const out: Record<string, SmoothEntity> = {}
  for (const [id, cur] of Object.entries(target)) {
    out[id] = lerpEntity(prev[id], cur, t, gridW)
  }
  return out
}

export function lerpGhostList(
  prev: EntitySnapshot[],
  target: EntitySnapshot[],
  t: number,
  gridW: number,
): SmoothEntity[] {
  return target.map((g, i) => lerpEntity(prev[i], g, t, gridW))
}

// Keep legacy exports used elsewhere (no-op wrappers).
export function smoothEntities(
  display: Record<string, SmoothEntity>,
  target: Record<string, EntitySnapshot>,
  dt: number,
  followHz = 28,
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
    if (Math.abs(dx) > 2.2 || Math.abs(dy) > 2.2) {
      out[id] = { ...cur, speed: 0 }
      continue
    }
    out[id] = {
      ...cur,
      x: prev.x + dx * alpha,
      y: prev.y + dy * alpha,
      speed: Math.hypot(dx, dy) / Math.max(dt, 1e-4),
    }
  }
  return out
}

export function smoothGhostList(
  display: SmoothEntity[],
  target: EntitySnapshot[],
  dt: number,
  followHz = 28,
): SmoothEntity[] {
  const byIndex = Object.fromEntries(display.map((g, i) => [String(i), g]))
  const targetMap = Object.fromEntries(target.map((g, i) => [String(i), g]))
  const smoothed = smoothEntities(byIndex, targetMap, dt, followHz)
  return target.map((_, i) => smoothed[String(i)] ?? { ...target[i]!, speed: 0 })
}

export function spawnChompParticles(x: number, y: number, color = CLASSIC.pellet): Particle[] {
  const out: Particle[] = []
  for (let i = 0; i < 5; i++) {
    const a = (Math.PI * 2 * i) / 5 + Math.random() * 0.2
    out.push({
      x: x + 0.5,
      y: y + 0.5,
      vx: Math.cos(a) * (1.2 + Math.random()),
      vy: Math.sin(a) * (1.2 + Math.random()),
      life: 0.28,
      maxLife: 0.28,
      color,
      size: 0.1,
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
      vx: p.vx * 0.9,
      vy: p.vy * 0.9,
      life,
    })
  }
  return out
}

function isWallCell(grid: number[][], x: number, y: number, gridW: number, gridH: number): boolean {
  if (x < 0 || y < 0 || x >= gridW || y >= gridH) return false
  return grid[y]![x] === TILE_WALL
}

function strokeMazeOutlines(
  ctx: CanvasRenderingContext2D,
  grid: number[][],
  ox: number,
  oy: number,
  cs: number,
  gridW: number,
  gridH: number,
  inset: number,
  radius: number,
) {
  const r = Math.min(radius, Math.max(0.5, cs * 0.5 - inset - 0.5))

  for (let y = 0; y < gridH; y++) {
    for (let x = 0; x < gridW; x++) {
      if (isWallCell(grid, x, y, gridW, gridH)) continue

      const n = isWallCell(grid, x, y - 1, gridW, gridH)
      const s = isWallCell(grid, x, y + 1, gridW, gridH)
      const w = isWallCell(grid, x - 1, y, gridW, gridH)
      const e = isWallCell(grid, x + 1, y, gridW, gridH)
      const nw = isWallCell(grid, x - 1, y - 1, gridW, gridH)
      const ne = isWallCell(grid, x + 1, y - 1, gridW, gridH)
      const sw = isWallCell(grid, x - 1, y + 1, gridW, gridH)
      const se = isWallCell(grid, x + 1, y + 1, gridW, gridH)

      const left = ox + x * cs + inset
      const right = ox + (x + 1) * cs - inset
      const top = oy + y * cs + inset
      const bottom = oy + (y + 1) * cs - inset

      if (n) {
        const x0 = w ? left + r : left
        const x1 = e ? right - r : right
        if (x1 > x0) {
          ctx.beginPath()
          ctx.moveTo(x0, top)
          ctx.lineTo(x1, top)
          ctx.stroke()
        }
      }
      if (s) {
        const x0 = w ? left + r : left
        const x1 = e ? right - r : right
        if (x1 > x0) {
          ctx.beginPath()
          ctx.moveTo(x0, bottom)
          ctx.lineTo(x1, bottom)
          ctx.stroke()
        }
      }
      if (w) {
        const y0 = n ? top + r : top
        const y1 = s ? bottom - r : bottom
        if (y1 > y0) {
          ctx.beginPath()
          ctx.moveTo(left, y0)
          ctx.lineTo(left, y1)
          ctx.stroke()
        }
      }
      if (e) {
        const y0 = n ? top + r : top
        const y1 = s ? bottom - r : bottom
        if (y1 > y0) {
          ctx.beginPath()
          ctx.moveTo(right, y0)
          ctx.lineTo(right, y1)
          ctx.stroke()
        }
      }

      if (n && w) {
        ctx.beginPath()
        ctx.arc(left + r, top + r, r, Math.PI, Math.PI * 1.5)
        ctx.stroke()
      }
      if (n && e) {
        ctx.beginPath()
        ctx.arc(right - r, top + r, r, Math.PI * 1.5, 0)
        ctx.stroke()
      }
      if (s && w) {
        ctx.beginPath()
        ctx.arc(left + r, bottom - r, r, Math.PI * 0.5, Math.PI)
        ctx.stroke()
      }
      if (s && e) {
        ctx.beginPath()
        ctx.arc(right - r, bottom - r, r, 0, Math.PI * 0.5)
        ctx.stroke()
      }

      if (!n && !w && nw) {
        ctx.beginPath()
        ctx.arc(left, top, r, 0, Math.PI * 0.5)
        ctx.stroke()
      }
      if (!n && !e && ne) {
        ctx.beginPath()
        ctx.arc(right, top, r, Math.PI * 0.5, Math.PI)
        ctx.stroke()
      }
      if (!s && !w && sw) {
        ctx.beginPath()
        ctx.arc(left, bottom, r, Math.PI * 1.5, 0)
        ctx.stroke()
      }
      if (!s && !e && se) {
        ctx.beginPath()
        ctx.arc(right, bottom, r, Math.PI, Math.PI * 1.5)
        ctx.stroke()
      }
    }
  }
}

function drawClassicMazeWalls(
  ctx: CanvasRenderingContext2D,
  grid: number[][],
  ox: number,
  oy: number,
  cs: number,
  gridW: number,
  gridH: number,
) {
  const inset = cs * 0.2
  const radius = Math.min(cs * 0.34, inset + cs * 0.1)
  const lineW = Math.max(2.2, cs * 0.17)

  ctx.fillStyle = CLASSIC.floor
  for (let y = 0; y < gridH; y++) {
    for (let x = 0; x < gridW; x++) {
      if (grid[y]![x] === TILE_WALL) continue
      ctx.fillRect(ox + x * cs, oy + y * cs, cs + 0.6, cs + 0.6)
    }
  }

  ctx.lineCap = 'round'
  ctx.lineJoin = 'round'

  ctx.strokeStyle = CLASSIC.wallGlow
  ctx.lineWidth = lineW + 2.5
  strokeMazeOutlines(ctx, grid, ox, oy, cs, gridW, gridH, inset, radius)

  ctx.strokeStyle = CLASSIC.wall
  ctx.lineWidth = lineW
  strokeMazeOutlines(ctx, grid, ox, oy, cs, gridW, gridH, inset, radius)

  const innerInset = inset + lineW * 0.5
  const innerRadius = Math.max(1, radius - lineW * 0.4)
  if (innerInset + 1 < cs * 0.45) {
    ctx.strokeStyle = CLASSIC.wallHi
    ctx.lineWidth = Math.max(1, lineW * 0.32)
    strokeMazeOutlines(ctx, grid, ox, oy, cs, gridW, gridH, innerInset, innerRadius)
  }
}

function drawGhostGate(
  ctx: CanvasRenderingContext2D,
  ox: number,
  oy: number,
  cs: number,
  gate: number[] | null | undefined,
) {
  if (!gate || gate.length < 2) return
  const [gx, gy] = gate
  const x = ox + gx! * cs
  const y = oy + gy! * cs + cs * 0.42
  ctx.strokeStyle = CLASSIC.gate
  ctx.lineWidth = Math.max(2, cs * 0.14)
  ctx.lineCap = 'butt'
  ctx.beginPath()
  ctx.moveTo(x + cs * 0.12, y)
  ctx.lineTo(x + cs * 0.88, y)
  ctx.stroke()
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
  invuln: boolean,
  speed: number,
) {
  // Chomp rate follows movement — classic wakka mouth.
  const chompHz = 10 + Math.min(8, speed * 2)
  const mouth = 0.08 + 0.38 * Math.abs(Math.sin((time / 1000) * chompHz * Math.PI))
  const angles: Record<string, number> = {
    right: 0,
    down: Math.PI / 2,
    left: Math.PI,
    up: -Math.PI / 2,
  }
  const rot = angles[direction] ?? 0
  if (invuln && Math.floor(time / 80) % 2 === 0) return

  ctx.save()
  ctx.translate(cx, cy)
  ctx.rotate(rot)
  ctx.beginPath()
  ctx.moveTo(0, 0)
  ctx.arc(0, 0, r, mouth, Math.PI * 2 - mouth)
  ctx.closePath()
  ctx.fillStyle = powered ? '#ffffaa' : color || CLASSIC.pacYellow
  ctx.fill()
  if (powered) {
    ctx.strokeStyle = 'rgba(255,255,255,0.85)'
    ctx.lineWidth = Math.max(1.5, r * 0.12)
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
  direction: string,
  frightened: boolean,
  frightenedTicks: number,
  eaten: boolean,
  time: number,
) {
  const [dx] = DIR_DELTA[direction] ?? [0, 0]
  const eyeLookX = dx * r * 0.12

  if (eaten) {
    ctx.fillStyle = '#ffffff'
    ctx.beginPath()
    ctx.ellipse(cx - r * 0.28, cy - r * 0.05, r * 0.22, r * 0.26, 0, 0, Math.PI * 2)
    ctx.ellipse(cx + r * 0.28, cy - r * 0.05, r * 0.22, r * 0.26, 0, 0, Math.PI * 2)
    ctx.fill()
    ctx.fillStyle = '#2121de'
    ctx.beginPath()
    ctx.arc(cx - r * 0.28 + eyeLookX, cy - r * 0.05, r * 0.1, 0, Math.PI * 2)
    ctx.arc(cx + r * 0.28 + eyeLookX, cy - r * 0.05, r * 0.1, 0, Math.PI * 2)
    ctx.fill()
    return
  }

  // Flash white when fright is about to end (classic).
  const flashing = frightened && frightenedTicks > 0 && frightenedTicks < 14
  const flashOn = flashing && Math.floor(time / 100) % 2 === 0
  const body = frightened
    ? flashOn
      ? '#ffffff'
      : '#2121de'
    : color

  const bob = Math.sin(time / 90) * r * 0.04
  const gy = cy + bob

  ctx.fillStyle = body
  ctx.beginPath()
  ctx.arc(cx, gy - r * 0.12, r * 0.88, Math.PI, 0)
  ctx.lineTo(cx + r * 0.88, gy + r * 0.78)
  const waves = 4
  const phase = Math.floor(time / 140) % 2
  for (let i = waves; i >= 0; i--) {
    const wx = cx - r * 0.88 + (r * 1.76 * i) / waves
    const wy = gy + r * 0.78 + ((i + phase) % 2 === 0 ? r * 0.18 : -r * 0.06)
    ctx.lineTo(wx, wy)
  }
  ctx.closePath()
  ctx.fill()

  if (frightened) {
    ctx.fillStyle = flashOn ? '#2121de' : '#ffb8ff'
    ctx.beginPath()
    ctx.arc(cx - r * 0.28, gy - r * 0.15, r * 0.12, 0, Math.PI * 2)
    ctx.arc(cx + r * 0.28, gy - r * 0.15, r * 0.12, 0, Math.PI * 2)
    ctx.fill()
    // Squiggle mouth
    ctx.strokeStyle = flashOn ? '#2121de' : '#ffb8ff'
    ctx.lineWidth = Math.max(1.5, r * 0.1)
    ctx.beginPath()
    ctx.moveTo(cx - r * 0.45, gy + r * 0.25)
    for (let i = 0; i < 4; i++) {
      ctx.lineTo(cx - r * 0.45 + r * 0.3 * (i + 0.5), gy + r * 0.25 + (i % 2 === 0 ? r * 0.12 : -r * 0.08))
    }
    ctx.stroke()
    return
  }

  ctx.fillStyle = '#ffffff'
  ctx.beginPath()
  ctx.ellipse(cx - r * 0.28, gy - r * 0.2, r * 0.2, r * 0.24, 0, 0, Math.PI * 2)
  ctx.ellipse(cx + r * 0.28, gy - r * 0.2, r * 0.2, r * 0.24, 0, 0, Math.PI * 2)
  ctx.fill()
  ctx.fillStyle = '#2121de'
  ctx.beginPath()
  ctx.arc(cx - r * 0.22 + eyeLookX, gy - r * 0.18, r * 0.1, 0, Math.PI * 2)
  ctx.arc(cx + r * 0.34 + eyeLookX, gy - r * 0.18, r * 0.1, 0, Math.PI * 2)
  ctx.fill()
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
    pellets,
    powerPellets,
    pacmen,
    ghosts,
    playerId,
    time,
    particles,
    gate,
  } = input
  const cs = cellSize(displayW, displayH, gridW, gridH)
  const ox = Math.floor((displayW - cs * gridW) / 2)
  const oy = Math.floor((displayH - cs * gridH) / 2)

  ctx.clearRect(0, 0, displayW, displayH)
  ctx.fillStyle = '#000000'
  ctx.fillRect(0, 0, displayW, displayH)
  if (cs > 0) {
    ctx.fillStyle = CLASSIC.floor
    ctx.fillRect(ox, oy, cs * gridW, cs * gridH)
  }

  drawClassicMazeWalls(ctx, grid, ox, oy, cs, gridW, gridH)
  drawGhostGate(ctx, ox, oy, cs, gate)

  // Pellets — classic pinkish dots
  for (let y = 0; y < gridH; y++) {
    for (let x = 0; x < gridW; x++) {
      const px = ox + x * cs + cs / 2
      const py = oy + y * cs + cs / 2
      if (powerPellets[y]?.[x]) {
        const pulse = 0.65 + 0.35 * Math.abs(Math.sin(time / 180))
        ctx.fillStyle = CLASSIC.power
        ctx.beginPath()
        ctx.arc(px, py, cs * 0.3 * pulse, 0, Math.PI * 2)
        ctx.fill()
      } else if (pellets[y]?.[x]) {
        ctx.fillStyle = CLASSIC.pellet
        ctx.beginPath()
        ctx.arc(px, py, Math.max(1.6, cs * 0.09), 0, Math.PI * 2)
        ctx.fill()
      }
    }
  }

  for (const g of ghosts) {
    if (g.visible === false) continue
    drawGhost(
      ctx,
      ox + (g.x + 0.5) * cs,
      oy + (g.y + 0.5) * cs,
      cs * 0.44,
      g.color,
      g.direction,
      Boolean(g.frightened),
      g.frightenedTicks ?? 0,
      Boolean(g.eaten),
      time,
    )
  }

  for (const [pid, p] of Object.entries(pacmen)) {
    if (!p.alive || p.visible === false) continue
    const isMe = pid === playerId
    if (isMe) {
      ctx.strokeStyle = 'rgba(255,255,255,0.22)'
      ctx.lineWidth = 1.5
      ctx.beginPath()
      ctx.arc(ox + (p.x + 0.5) * cs, oy + (p.y + 0.5) * cs, cs * 0.5, 0, Math.PI * 2)
      ctx.stroke()
    }
    drawPac(
      ctx,
      ox + (p.x + 0.5) * cs,
      oy + (p.y + 0.5) * cs,
      cs * 0.42,
      p.direction,
      p.color || CLASSIC.pacYellow,
      time,
      Boolean(p.powered),
      Boolean(p.invuln),
      p.speed ?? 1,
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
