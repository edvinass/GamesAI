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

export interface RenderFrameInput {
  gridW: number
  gridH: number
  grid: number[][]
  bombers: Record<string, { x: number; y: number; alive: boolean; color: string; direction: string }>
  bombs: BombermanBomb[]
  explosions: BombermanExplosion[]
  powerups: BombermanPowerup[]
  playerId: string
  time: number
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
    out[pid] = {
      x: p.x + (cur.x - p.x) * t,
      y: p.y + (cur.y - p.y) * t,
      alive: cur.alive,
      color: cur.color,
      direction: cur.direction,
    }
  }
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

function drawHardBlock(ctx: CanvasRenderingContext2D, x: number, y: number, s: number) {
  const pad = s * 0.06
  drawRoundRect(ctx, x + pad, y + pad, s - pad * 2, s - pad * 2, s * 0.12)
  ctx.fillStyle = '#3d4555'
  ctx.fill()
  ctx.strokeStyle = 'rgba(0,0,0,0.35)'
  ctx.lineWidth = Math.max(1, s * 0.04)
  ctx.stroke()
  ctx.fillStyle = 'rgba(255,255,255,0.08)'
  drawRoundRect(ctx, x + pad + s * 0.08, y + pad + s * 0.08, s * 0.35, s * 0.18, 2)
  ctx.fill()
}

function drawSoftBlock(ctx: CanvasRenderingContext2D, x: number, y: number, s: number) {
  const pad = s * 0.08
  drawRoundRect(ctx, x + pad, y + pad, s - pad * 2, s - pad * 2, s * 0.1)
  ctx.fillStyle = '#c47a3a'
  ctx.fill()
  ctx.strokeStyle = 'rgba(80,40,10,0.4)'
  ctx.lineWidth = Math.max(1, s * 0.035)
  ctx.stroke()
  ctx.strokeStyle = 'rgba(0,0,0,0.18)'
  ctx.beginPath()
  ctx.moveTo(x + s * 0.3, y + pad)
  ctx.lineTo(x + s * 0.3, y + s - pad)
  ctx.moveTo(x + s * 0.7, y + pad)
  ctx.lineTo(x + s * 0.7, y + s - pad)
  ctx.moveTo(x + pad, y + s * 0.5)
  ctx.lineTo(x + s - pad, y + s * 0.5)
  ctx.stroke()
}

function drawBomb(
  ctx: CanvasRenderingContext2D,
  x: number,
  y: number,
  s: number,
  fuse: number,
  time: number,
) {
  const cx = x + s / 2
  const cy = y + s / 2
  const pulse = 1 + Math.sin(time / 80 + fuse) * 0.04
  const r = s * 0.28 * pulse
  ctx.beginPath()
  ctx.arc(cx, cy + s * 0.04, r, 0, Math.PI * 2)
  ctx.fillStyle = '#1a1a1a'
  ctx.fill()
  ctx.strokeStyle = '#444'
  ctx.lineWidth = 1
  ctx.stroke()
  // Fuse spark
  const spark = fuse < 6 ? 0.9 + Math.sin(time / 40) * 0.1 : 0.7
  ctx.beginPath()
  ctx.moveTo(cx, cy - r * 0.6)
  ctx.quadraticCurveTo(cx + s * 0.12, cy - r * 1.1, cx + s * 0.08, cy - r * 1.4)
  ctx.strokeStyle = '#fbbf24'
  ctx.lineWidth = Math.max(1.5, s * 0.05)
  ctx.stroke()
  ctx.beginPath()
  ctx.arc(cx + s * 0.08, cy - r * 1.4, s * 0.06 * spark, 0, Math.PI * 2)
  ctx.fillStyle = fuse < 5 ? '#ef4444' : '#f97316'
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
  const flicker = 0.85 + Math.sin(time / 30 + x + y) * 0.15
  const pad = s * (0.08 + (1 - intensity) * 0.15)
  drawRoundRect(ctx, x + pad, y + pad, s - pad * 2, s - pad * 2, s * 0.15)
  ctx.fillStyle = `rgba(255, ${120 + intensity * 80}, 40, ${0.55 * intensity * flicker})`
  ctx.fill()
  ctx.fillStyle = `rgba(255, 240, 180, ${0.45 * intensity})`
  const inner = s * 0.22
  drawRoundRect(
    ctx,
    x + s / 2 - inner,
    y + s / 2 - inner,
    inner * 2,
    inner * 2,
    inner * 0.4,
  )
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
  const bob = Math.sin(time / 200) * s * 0.04
  const cx = x + s / 2
  const cy = y + s / 2 + bob
  const r = s * 0.28
  const colors: Record<string, string> = {
    bomb: '#f97316',
    range: '#38bdf8',
    speed: '#a3e635',
  }
  const labels: Record<string, string> = {
    bomb: 'B',
    range: 'R',
    speed: 'S',
  }
  ctx.beginPath()
  ctx.arc(cx, cy, r, 0, Math.PI * 2)
  ctx.fillStyle = colors[type] ?? '#fff'
  ctx.fill()
  ctx.strokeStyle = 'rgba(0,0,0,0.35)'
  ctx.lineWidth = 1.5
  ctx.stroke()
  ctx.fillStyle = '#111'
  ctx.font = `bold ${Math.floor(s * 0.28)}px Outfit, system-ui, sans-serif`
  ctx.textAlign = 'center'
  ctx.textBaseline = 'middle'
  ctx.fillText(labels[type] ?? '?', cx, cy + 1)
}

function drawBomber(
  ctx: CanvasRenderingContext2D,
  x: number,
  y: number,
  s: number,
  color: string,
  isMe: boolean,
  direction: string,
) {
  const cx = x + s / 2
  const cy = y + s / 2
  const bodyR = s * 0.32
  // Shadow
  ctx.beginPath()
  ctx.ellipse(cx, cy + bodyR * 0.85, bodyR * 0.7, bodyR * 0.22, 0, 0, Math.PI * 2)
  ctx.fillStyle = 'rgba(0,0,0,0.25)'
  ctx.fill()
  // Body
  ctx.beginPath()
  ctx.arc(cx, cy, bodyR, 0, Math.PI * 2)
  ctx.fillStyle = color
  ctx.fill()
  if (isMe) {
    ctx.strokeStyle = '#fff'
    ctx.lineWidth = Math.max(2, s * 0.06)
    ctx.stroke()
  } else {
    ctx.strokeStyle = 'rgba(0,0,0,0.3)'
    ctx.lineWidth = 1
    ctx.stroke()
  }
  // Eyes face direction
  const face: Record<string, [number, number]> = {
    up: [0, -0.12],
    down: [0, 0.14],
    left: [-0.14, 0.04],
    right: [0.14, 0.04],
    stop: [0, 0.06],
  }
  const [fx, fy] = face[direction] ?? face.stop
  const eyeY = cy + fy * s
  const eyeSpread = s * 0.1
  for (const side of [-1, 1]) {
    ctx.beginPath()
    ctx.arc(cx + fx * s + side * eyeSpread, eyeY, s * 0.055, 0, Math.PI * 2)
    ctx.fillStyle = '#111'
    ctx.fill()
  }
}

export function renderFrame(
  ctx: CanvasRenderingContext2D,
  displayW: number,
  displayH: number,
  input: RenderFrameInput,
) {
  const { gridW, gridH, grid, bombers, bombs, explosions, powerups, playerId, time } = input
  const s = cellSize(displayW, displayH, gridW, gridH)
  const boardW = s * gridW
  const boardH = s * gridH
  const ox = Math.floor((displayW - boardW) / 2)
  const oy = Math.floor((displayH - boardH) / 2)

  ctx.clearRect(0, 0, displayW, displayH)

  // Floor
  ctx.fillStyle = '#1a2330'
  ctx.fillRect(ox, oy, boardW, boardH)
  for (let y = 0; y < gridH; y++) {
    for (let x = 0; x < gridW; x++) {
      if ((x + y) % 2 === 0) {
        ctx.fillStyle = 'rgba(255,255,255,0.02)'
        ctx.fillRect(ox + x * s, oy + y * s, s, s)
      }
    }
  }

  // Walls
  for (let y = 0; y < gridH; y++) {
    const row = grid[y] ?? []
    for (let x = 0; x < gridW; x++) {
      const tile = row[x] ?? TILE_EMPTY
      const px = ox + x * s
      const py = oy + y * s
      if (tile === TILE_HARD) drawHardBlock(ctx, px, py, s)
      else if (tile === TILE_SOFT) drawSoftBlock(ctx, px, py, s)
    }
  }

  // Powerups
  for (const p of powerups) {
    drawPowerup(ctx, ox + p.x * s, oy + p.y * s, s, p.type, time)
  }

  // Bombs
  for (const b of bombs) {
    drawBomb(ctx, ox + b.x * s, oy + b.y * s, s, b.fuse, time)
  }

  // Explosions
  for (const e of explosions) {
    drawExplosion(ctx, ox + e.x * s, oy + e.y * s, s, e.ttl, time)
  }

  // Bombers
  for (const [pid, b] of Object.entries(bombers)) {
    if (!b.alive) continue
    drawBomber(ctx, ox + b.x * s, oy + b.y * s, s, b.color, pid === playerId, b.direction)
  }
}
