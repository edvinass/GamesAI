export type Point = { x: number; y: number }

export type SnakeSnapshot = {
  body: number[][]
  direction: string
  alive: boolean
  color: string
  score: number
}

export type Particle = {
  x: number
  y: number
  vx: number
  vy: number
  life: number
  maxLife: number
  color: string
  size: number
}

const DIR_VEC: Record<string, Point> = {
  up: { x: 0, y: -1 },
  down: { x: 0, y: 1 },
  left: { x: -1, y: 0 },
  right: { x: 1, y: 0 },
}

function clamp(n: number, lo: number, hi: number) {
  return Math.max(lo, Math.min(hi, n))
}

function hexToRgb(hex: string): [number, number, number] {
  const h = hex.replace('#', '')
  const full = h.length === 3 ? h.split('').map((c) => c + c).join('') : h
  const n = parseInt(full.slice(0, 6), 16)
  return [(n >> 16) & 255, (n >> 8) & 255, n & 255]
}

function shade(hex: string, amount: number): string {
  const [r, g, b] = hexToRgb(hex)
  const t = amount < 0 ? 0 : 255
  const p = Math.abs(amount)
  const nr = Math.round(r + (t - r) * p)
  const ng = Math.round(g + (t - g) * p)
  const nb = Math.round(b + (t - b) * p)
  return `rgb(${nr},${ng},${nb})`
}

function rgba(hex: string, a: number): string {
  const [r, g, b] = hexToRgb(hex)
  return `rgba(${r},${g},${b},${a})`
}

/** Shortest wrapped delta on a torus axis. */
export function wrapDelta(from: number, to: number, size: number): number {
  let d = to - from
  if (d > size / 2) d -= size
  if (d < -size / 2) d += size
  return d
}

export function lerpSeg(
  from: number[],
  to: number[],
  t: number,
  gridW: number,
  gridH: number,
): Point {
  const dx = wrapDelta(from[0], to[0], gridW)
  const dy = wrapDelta(from[1], to[1], gridH)
  // Large jumps (respawn / length change) snap instead of wrapping oddly
  if (Math.abs(dx) > 1.5 || Math.abs(dy) > 1.5) {
    return { x: to[0], y: to[1] }
  }
  return { x: from[0] + dx * t, y: from[1] + dy * t }
}

export function interpolateBody(
  prev: number[][] | undefined,
  curr: number[][],
  t: number,
  gridW: number,
  gridH: number,
): Point[] {
  if (!prev || prev.length === 0) {
    return curr.map(([x, y]) => ({ x, y }))
  }
  const len = Math.max(prev.length, curr.length)
  const out: Point[] = []
  for (let i = 0; i < len; i++) {
    const a = prev[Math.min(i, prev.length - 1)]
    const b = curr[Math.min(i, curr.length - 1)]
    out.push(lerpSeg(a, b, t, gridW, gridH))
  }
  // Prefer current length once grown
  if (curr.length >= prev.length) {
    return out.slice(0, curr.length)
  }
  return out.slice(0, Math.max(curr.length, Math.ceil(prev.length * (1 - t) + curr.length * t)))
}

/** Split a path that crosses the wrap boundary into contiguous chunks. */
export function splitWrappedPath(points: Point[], gridW: number, gridH: number): Point[][] {
  if (points.length === 0) return []
  const chunks: Point[][] = []
  let cur: Point[] = [points[0]]
  for (let i = 1; i < points.length; i++) {
    const a = points[i - 1]
    const b = points[i]
    if (Math.abs(b.x - a.x) > gridW / 2 || Math.abs(b.y - a.y) > gridH / 2) {
      chunks.push(cur)
      cur = [b]
    } else {
      cur.push(b)
    }
  }
  chunks.push(cur)
  return chunks
}

export function spawnEatParticles(food: [number, number], color: string, count = 14): Particle[] {
  const particles: Particle[] = []
  for (let i = 0; i < count; i++) {
    const angle = (Math.PI * 2 * i) / count + Math.random() * 0.4
    const speed = 2.5 + Math.random() * 4
    particles.push({
      x: food[0] + 0.5,
      y: food[1] + 0.5,
      vx: Math.cos(angle) * speed,
      vy: Math.sin(angle) * speed,
      life: 1,
      maxLife: 0.45 + Math.random() * 0.35,
      color,
      size: 0.12 + Math.random() * 0.18,
    })
  }
  return particles
}

export function updateParticles(particles: Particle[], dt: number): Particle[] {
  const next: Particle[] = []
  for (const p of particles) {
    p.life -= dt / p.maxLife
    if (p.life <= 0) continue
    p.x += p.vx * dt
    p.y += p.vy * dt
    p.vx *= 0.92
    p.vy *= 0.92
    p.vy += 2.2 * dt
    next.push(p)
  }
  return next
}

function cellCenter(p: Point, offsetX: number, offsetY: number, cell: number): Point {
  return {
    x: offsetX + (p.x + 0.5) * cell,
    y: offsetY + (p.y + 0.5) * cell,
  }
}

function drawBoardBackground(
  ctx: CanvasRenderingContext2D,
  offsetX: number,
  offsetY: number,
  boardW: number,
  boardH: number,
  gridW: number,
  gridH: number,
  cell: number,
  time: number,
) {
  // Meadow base
  const grass = ctx.createLinearGradient(offsetX, offsetY, offsetX, offsetY + boardH)
  grass.addColorStop(0, '#1a3d28')
  grass.addColorStop(0.5, '#163524')
  grass.addColorStop(1, '#0f281c')
  ctx.fillStyle = grass
  ctx.fillRect(offsetX, offsetY, boardW, boardH)

  // Soft checker texture
  for (let y = 0; y < gridH; y++) {
    for (let x = 0; x < gridW; x++) {
      if ((x + y) % 2 !== 0) continue
      ctx.fillStyle = 'rgba(255,255,255,0.018)'
      ctx.fillRect(offsetX + x * cell, offsetY + y * cell, cell, cell)
    }
  }

  // Sparse shimmer dots
  ctx.fillStyle = 'rgba(120, 200, 140, 0.06)'
  for (let i = 0; i < 40; i++) {
    const gx = (i * 7 + 3) % gridW
    const gy = (i * 11 + 5) % gridH
    const pulse = 0.5 + 0.5 * Math.sin(time * 0.0015 + i)
    ctx.globalAlpha = 0.04 + pulse * 0.06
    ctx.beginPath()
    ctx.arc(
      offsetX + (gx + 0.5) * cell,
      offsetY + (gy + 0.5) * cell,
      cell * 0.12,
      0,
      Math.PI * 2,
    )
    ctx.fill()
  }
  ctx.globalAlpha = 1

  // Soft grid
  ctx.strokeStyle = 'rgba(255,255,255,0.04)'
  ctx.lineWidth = 1
  for (let x = 0; x <= gridW; x++) {
    ctx.beginPath()
    ctx.moveTo(offsetX + x * cell, offsetY)
    ctx.lineTo(offsetX + x * cell, offsetY + boardH)
    ctx.stroke()
  }
  for (let y = 0; y <= gridH; y++) {
    ctx.beginPath()
    ctx.moveTo(offsetX, offsetY + y * cell)
    ctx.lineTo(offsetX + boardW, offsetY + y * cell)
    ctx.stroke()
  }

  // Border
  ctx.strokeStyle = 'rgba(90, 200, 130, 0.35)'
  ctx.lineWidth = Math.max(2, cell * 0.12)
  ctx.strokeRect(offsetX + 1, offsetY + 1, boardW - 2, boardH - 2)

  // Vignette
  const vig = ctx.createRadialGradient(
    offsetX + boardW / 2,
    offsetY + boardH / 2,
    Math.min(boardW, boardH) * 0.25,
    offsetX + boardW / 2,
    offsetY + boardH / 2,
    Math.max(boardW, boardH) * 0.72,
  )
  vig.addColorStop(0, 'rgba(0,0,0,0)')
  vig.addColorStop(1, 'rgba(0,0,0,0.35)')
  ctx.fillStyle = vig
  ctx.fillRect(offsetX, offsetY, boardW, boardH)
}

function drawFood(
  ctx: CanvasRenderingContext2D,
  food: [number, number],
  offsetX: number,
  offsetY: number,
  cell: number,
  time: number,
) {
  const cx = offsetX + (food[0] + 0.5) * cell
  const cy = offsetY + (food[1] + 0.5) * cell + Math.sin(time * 0.006) * cell * 0.08
  const pulse = 0.85 + 0.15 * Math.sin(time * 0.008)
  const r = cell * 0.32 * pulse

  // Glow
  const glow = ctx.createRadialGradient(cx, cy, r * 0.2, cx, cy, r * 2.4)
  glow.addColorStop(0, 'rgba(255, 80, 90, 0.55)')
  glow.addColorStop(0.45, 'rgba(255, 60, 80, 0.18)')
  glow.addColorStop(1, 'rgba(255, 40, 60, 0)')
  ctx.fillStyle = glow
  ctx.beginPath()
  ctx.arc(cx, cy, r * 2.4, 0, Math.PI * 2)
  ctx.fill()

  // Apple body
  const body = ctx.createRadialGradient(cx - r * 0.3, cy - r * 0.35, r * 0.1, cx, cy, r)
  body.addColorStop(0, '#ff8a8a')
  body.addColorStop(0.45, '#ef4444')
  body.addColorStop(1, '#b91c1c')
  ctx.fillStyle = body
  ctx.beginPath()
  ctx.ellipse(cx, cy + r * 0.05, r * 0.95, r, 0, 0, Math.PI * 2)
  ctx.fill()

  // Highlight
  ctx.fillStyle = 'rgba(255,255,255,0.35)'
  ctx.beginPath()
  ctx.ellipse(cx - r * 0.28, cy - r * 0.28, r * 0.28, r * 0.18, -0.5, 0, Math.PI * 2)
  ctx.fill()

  // Stem
  ctx.strokeStyle = '#5b3a1a'
  ctx.lineWidth = Math.max(1.5, cell * 0.08)
  ctx.lineCap = 'round'
  ctx.beginPath()
  ctx.moveTo(cx, cy - r * 0.75)
  ctx.quadraticCurveTo(cx + r * 0.15, cy - r * 1.15, cx + r * 0.05, cy - r * 1.25)
  ctx.stroke()

  // Leaf
  ctx.fillStyle = '#4ade80'
  ctx.beginPath()
  ctx.ellipse(cx + r * 0.35, cy - r * 1.05, r * 0.35, r * 0.18, -0.6, 0, Math.PI * 2)
  ctx.fill()
}

function strokeSnakeChunk(
  ctx: CanvasRenderingContext2D,
  pts: Point[],
  offsetX: number,
  offsetY: number,
  cell: number,
  color: string,
  alpha: number,
  headBoost: boolean,
) {
  if (pts.length === 0) return
  const screen = pts.map((p) => cellCenter(p, offsetX, offsetY, cell))
  const bodyW = cell * 0.72
  const headW = cell * 0.88

  ctx.save()
  ctx.globalAlpha = alpha
  ctx.lineCap = 'round'
  ctx.lineJoin = 'round'

  // Shadow
  ctx.strokeStyle = 'rgba(0,0,0,0.35)'
  ctx.lineWidth = bodyW + cell * 0.12
  ctx.beginPath()
  ctx.moveTo(screen[0].x + 1.5, screen[0].y + 2)
  for (let i = 1; i < screen.length; i++) {
    ctx.lineTo(screen[i].x + 1.5, screen[i].y + 2)
  }
  if (screen.length === 1) {
    ctx.lineTo(screen[0].x + 1.5, screen[0].y + 2.01)
  }
  ctx.stroke()

  // Outer body
  const grad = ctx.createLinearGradient(
    screen[0].x,
    screen[0].y,
    screen[screen.length - 1].x,
    screen[screen.length - 1].y,
  )
  grad.addColorStop(0, shade(color, 0.25))
  grad.addColorStop(0.35, color)
  grad.addColorStop(1, shade(color, -0.25))
  ctx.strokeStyle = grad
  ctx.lineWidth = headBoost ? headW : bodyW
  ctx.beginPath()
  ctx.moveTo(screen[0].x, screen[0].y)
  for (let i = 1; i < screen.length; i++) {
    ctx.lineTo(screen[i].x, screen[i].y)
  }
  if (screen.length === 1) {
    ctx.lineTo(screen[0].x + 0.01, screen[0].y)
  }
  ctx.stroke()

  // Belly highlight stripe
  ctx.strokeStyle = rgba(shade(color, 0.45), 0.45)
  ctx.lineWidth = bodyW * 0.35
  ctx.beginPath()
  ctx.moveTo(screen[0].x, screen[0].y)
  for (let i = 1; i < screen.length; i++) {
    ctx.lineTo(screen[i].x, screen[i].y)
  }
  if (screen.length === 1) {
    ctx.lineTo(screen[0].x + 0.01, screen[0].y)
  }
  ctx.stroke()

  // Scale chevrons along body (skip head)
  const scaleStart = headBoost ? 1 : 0
  for (let i = scaleStart; i < screen.length - 1; i++) {
    const a = screen[i]
    const b = screen[i + 1]
    const mx = (a.x + b.x) / 2
    const my = (a.y + b.y) / 2
    const ang = Math.atan2(b.y - a.y, b.x - a.x)
    const s = bodyW * 0.28
    ctx.save()
    ctx.translate(mx, my)
    ctx.rotate(ang)
    ctx.fillStyle = rgba(shade(color, -0.35), 0.35)
    ctx.beginPath()
    ctx.moveTo(-s * 0.2, 0)
    ctx.lineTo(s, -s * 0.7)
    ctx.lineTo(s * 0.35, 0)
    ctx.lineTo(s, s * 0.7)
    ctx.closePath()
    ctx.fill()
    ctx.restore()
  }

  ctx.restore()
}

function drawSnakeHead(
  ctx: CanvasRenderingContext2D,
  head: Point,
  direction: string,
  offsetX: number,
  offsetY: number,
  cell: number,
  color: string,
  alpha: number,
  isMe: boolean,
  time: number,
  alive: boolean,
) {
  const c = cellCenter(head, offsetX, offsetY, cell)
  const dir = DIR_VEC[direction] ?? DIR_VEC.right
  const ang = Math.atan2(dir.y, dir.x)
  const r = cell * 0.48

  ctx.save()
  ctx.globalAlpha = alpha
  ctx.translate(c.x, c.y)
  ctx.rotate(ang)

  // Head glow for local player
  if (isMe && alive) {
    const glow = ctx.createRadialGradient(0, 0, r * 0.2, 0, 0, r * 1.8)
    glow.addColorStop(0, rgba(color, 0.35))
    glow.addColorStop(1, rgba(color, 0))
    ctx.fillStyle = glow
    ctx.beginPath()
    ctx.arc(0, 0, r * 1.8, 0, Math.PI * 2)
    ctx.fill()
  }

  // Head shape (slightly elongated)
  const headGrad = ctx.createRadialGradient(-r * 0.2, -r * 0.15, r * 0.1, 0, 0, r)
  headGrad.addColorStop(0, shade(color, 0.35))
  headGrad.addColorStop(0.55, color)
  headGrad.addColorStop(1, shade(color, -0.2))
  ctx.fillStyle = headGrad
  ctx.beginPath()
  ctx.ellipse(r * 0.08, 0, r * 1.05, r * 0.9, 0, 0, Math.PI * 2)
  ctx.fill()

  // Snout highlight
  ctx.fillStyle = rgba(shade(color, 0.5), 0.35)
  ctx.beginPath()
  ctx.ellipse(r * 0.35, 0, r * 0.35, r * 0.45, 0, 0, Math.PI * 2)
  ctx.fill()

  // Eyes
  const eyeX = r * 0.25
  const eyeY = r * 0.38
  const eyeR = r * 0.28
  for (const side of [-1, 1]) {
    ctx.fillStyle = '#fff'
    ctx.beginPath()
    ctx.ellipse(eyeX, side * eyeY, eyeR, eyeR * 0.9, 0, 0, Math.PI * 2)
    ctx.fill()

    ctx.fillStyle = '#0f172a'
    const look = alive ? 0.12 : 0
    ctx.beginPath()
    ctx.arc(eyeX + r * look, side * eyeY, eyeR * 0.48, 0, Math.PI * 2)
    ctx.fill()

    ctx.fillStyle = 'rgba(255,255,255,0.7)'
    ctx.beginPath()
    ctx.arc(eyeX + r * (look - 0.05), side * eyeY - eyeR * 0.2, eyeR * 0.15, 0, Math.PI * 2)
    ctx.fill()
  }

  // Nostrils
  ctx.fillStyle = rgba('#000', 0.35)
  ctx.beginPath()
  ctx.ellipse(r * 0.85, -r * 0.12, r * 0.06, r * 0.08, 0, 0, Math.PI * 2)
  ctx.ellipse(r * 0.85, r * 0.12, r * 0.06, r * 0.08, 0, 0, Math.PI * 2)
  ctx.fill()

  // Flickering tongue
  if (alive) {
    const flick = Math.sin(time * 0.012) > 0.35
    if (flick) {
      const tongueLen = r * (0.7 + 0.25 * Math.sin(time * 0.04))
      ctx.strokeStyle = '#ef4444'
      ctx.lineWidth = Math.max(1.5, cell * 0.07)
      ctx.lineCap = 'round'
      ctx.beginPath()
      ctx.moveTo(r * 0.95, 0)
      ctx.lineTo(r * 0.95 + tongueLen, 0)
      ctx.stroke()
      // Fork
      ctx.beginPath()
      ctx.moveTo(r * 0.95 + tongueLen, 0)
      ctx.lineTo(r * 0.95 + tongueLen + r * 0.25, -r * 0.2)
      ctx.moveTo(r * 0.95 + tongueLen, 0)
      ctx.lineTo(r * 0.95 + tongueLen + r * 0.25, r * 0.2)
      ctx.stroke()
    }
  }

  ctx.restore()
}

function drawTailTip(
  ctx: CanvasRenderingContext2D,
  tip: Point,
  prev: Point | undefined,
  offsetX: number,
  offsetY: number,
  cell: number,
  color: string,
  alpha: number,
) {
  const c = cellCenter(tip, offsetX, offsetY, cell)
  let ang = 0
  if (prev) {
    const p = cellCenter(prev, offsetX, offsetY, cell)
    ang = Math.atan2(c.y - p.y, c.x - p.x)
  }
  ctx.save()
  ctx.globalAlpha = alpha
  ctx.translate(c.x, c.y)
  ctx.rotate(ang)
  ctx.fillStyle = shade(color, -0.15)
  ctx.beginPath()
  ctx.moveTo(-cell * 0.15, 0)
  ctx.lineTo(cell * 0.35, -cell * 0.22)
  ctx.lineTo(cell * 0.55, 0)
  ctx.lineTo(cell * 0.35, cell * 0.22)
  ctx.closePath()
  ctx.fill()
  ctx.restore()
}

export function drawSnake(
  ctx: CanvasRenderingContext2D,
  body: Point[],
  direction: string,
  color: string,
  alive: boolean,
  isMe: boolean,
  offsetX: number,
  offsetY: number,
  cell: number,
  gridW: number,
  gridH: number,
  time: number,
) {
  if (body.length === 0) return
  const alpha = alive ? 1 : 0.32
  const chunks = splitWrappedPath(body, gridW, gridH)

  chunks.forEach((chunk, idx) => {
    const isHeadChunk = idx === 0
    strokeSnakeChunk(ctx, chunk, offsetX, offsetY, cell, color, alpha, isHeadChunk)
  })

  const head = body[0]
  drawSnakeHead(ctx, head, direction, offsetX, offsetY, cell, color, alpha, isMe, time, alive)

  if (body.length > 1) {
    const tip = body[body.length - 1]
    const before = body[body.length - 2]
    // Only draw tip if not wrapping away from previous
    if (Math.abs(tip.x - before.x) <= 1.5 && Math.abs(tip.y - before.y) <= 1.5) {
      drawTailTip(ctx, tip, before, offsetX, offsetY, cell, color, alpha)
    }
  }
}

function drawParticles(
  ctx: CanvasRenderingContext2D,
  particles: Particle[],
  offsetX: number,
  offsetY: number,
  cell: number,
) {
  for (const p of particles) {
    const px = offsetX + p.x * cell
    const py = offsetY + p.y * cell
    ctx.globalAlpha = clamp(p.life, 0, 1)
    ctx.fillStyle = p.color
    ctx.beginPath()
    ctx.arc(px, py, p.size * cell, 0, Math.PI * 2)
    ctx.fill()
  }
  ctx.globalAlpha = 1
}

export type RenderFrame = {
  gridW: number
  gridH: number
  food: [number, number] | null
  snakes: Record<
    string,
    {
      body: Point[]
      direction: string
      color: string
      alive: boolean
    }
  >
  playerId: string
  particles: Particle[]
  time: number
}

export function renderFrame(
  ctx: CanvasRenderingContext2D,
  displayW: number,
  displayH: number,
  frame: RenderFrame,
) {
  const { gridW, gridH, food, snakes, playerId, particles, time } = frame

  ctx.clearRect(0, 0, displayW, displayH)
  ctx.fillStyle = '#0a1210'
  ctx.fillRect(0, 0, displayW, displayH)

  const cell = Math.min(displayW / gridW, displayH / gridH)
  const boardW = cell * gridW
  const boardH = cell * gridH
  const offsetX = (displayW - boardW) / 2
  const offsetY = (displayH - boardH) / 2

  drawBoardBackground(ctx, offsetX, offsetY, boardW, boardH, gridW, gridH, cell, time)

  if (food) {
    drawFood(ctx, food, offsetX, offsetY, cell, time)
  }

  // Draw dead snakes first, then alive, with local player last
  const entries = Object.entries(snakes).sort(([aId, a], [bId, b]) => {
    if (a.alive !== b.alive) return a.alive ? 1 : -1
    if (aId === playerId) return 1
    if (bId === playerId) return -1
    return 0
  })

  for (const [pid, snake] of entries) {
    drawSnake(
      ctx,
      snake.body,
      snake.direction,
      snake.color,
      snake.alive,
      pid === playerId,
      offsetX,
      offsetY,
      cell,
      gridW,
      gridH,
      time,
    )
  }

  drawParticles(ctx, particles, offsetX, offsetY, cell)

  return { cell, offsetX, offsetY, boardW, boardH }
}
