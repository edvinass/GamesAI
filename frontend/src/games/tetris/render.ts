import type { TetrisBoardState } from '@/types'
import { pieceCells } from './pieces'

export interface BoardMetrics {
  offsetX: number
  offsetY: number
  cell: number
  inset: number
  boardW: number
  boardH: number
}

export interface BoardEffect {
  type: 'line_clear' | 'lock' | 'level_up' | 'death'
  startedAt: number
  lines?: number
}

const EFFECT_DURATIONS: Record<BoardEffect['type'], number> = {
  line_clear: 520,
  lock: 180,
  level_up: 900,
  death: 700,
}

export function effectDuration(type: BoardEffect['type']): number {
  return EFFECT_DURATIONS[type]
}

export function computeBoardMetrics(
  displayW: number,
  displayH: number,
  width: number,
  height: number,
): BoardMetrics {
  const cell = Math.min(displayW / width, displayH / height)
  const boardW = cell * width
  const boardH = cell * height
  return {
    offsetX: (displayW - boardW) / 2,
    offsetY: (displayH - boardH) / 2,
    cell,
    inset: Math.max(1, cell * 0.08),
    boardW,
    boardH,
  }
}

function canPlace(
  grid: (string | null)[][],
  width: number,
  height: number,
  cells: [number, number][],
): boolean {
  for (const [x, y] of cells) {
    if (x < 0 || x >= width || y >= height) return false
    if (y >= 0 && grid[y]?.[x]) return false
  }
  return true
}

export function computeGhostCells(
  board: TetrisBoardState,
  boardWidth: number,
  boardHeight: number,
): [number, number][] | null {
  if (!board.active || !board.alive) return null
  const { type, rotation, x } = board.active
  let ghostY = board.active.y
  while (true) {
    const next = pieceCells(type, rotation, x, ghostY + 1)
    if (!canPlace(board.grid, boardWidth, boardHeight, next)) break
    ghostY += 1
  }
  if (ghostY === board.active.y) return null
  return pieceCells(type, rotation, x, ghostY)
}

function lightenColor(hex: string, amount: number): string {
  const raw = hex.replace('#', '')
  if (raw.length !== 6) return hex
  const r = Math.min(255, parseInt(raw.slice(0, 2), 16) + amount)
  const g = Math.min(255, parseInt(raw.slice(2, 4), 16) + amount)
  const b = Math.min(255, parseInt(raw.slice(4, 6), 16) + amount)
  return `rgb(${r}, ${g}, ${b})`
}

function darkenColor(hex: string, amount: number): string {
  const raw = hex.replace('#', '')
  if (raw.length !== 6) return hex
  const r = Math.max(0, parseInt(raw.slice(0, 2), 16) - amount)
  const g = Math.max(0, parseInt(raw.slice(2, 4), 16) - amount)
  const b = Math.max(0, parseInt(raw.slice(4, 6), 16) - amount)
  return `rgb(${r}, ${g}, ${b})`
}

export function drawBlock(
  ctx: CanvasRenderingContext2D,
  metrics: BoardMetrics,
  x: number,
  y: number,
  color: string,
  options: {
    alpha?: number
    ghost?: boolean
    glow?: boolean
    pulse?: number
  } = {},
) {
  const { offsetX, offsetY, cell, inset } = metrics
  const alpha = options.alpha ?? 1
  const size = cell - inset * 2
  const px = offsetX + x * cell + inset
  const py = offsetY + y * cell + inset
  const radius = Math.max(2, size * 0.18)

  ctx.save()
  ctx.globalAlpha = alpha

  if (options.glow && options.pulse != null) {
    ctx.shadowColor = color
    ctx.shadowBlur = 8 + options.pulse * 10
  }

  if (options.ghost) {
    ctx.strokeStyle = color
    ctx.lineWidth = Math.max(1.5, size * 0.08)
    ctx.setLineDash([Math.max(3, size * 0.15), Math.max(2, size * 0.1)])
    roundRect(ctx, px, py, size, size, radius)
    ctx.stroke()
    ctx.setLineDash([])
    ctx.restore()
    return
  }

  const gradient = ctx.createLinearGradient(px, py, px + size, py + size)
  gradient.addColorStop(0, lightenColor(color, 42))
  gradient.addColorStop(0.45, color)
  gradient.addColorStop(1, darkenColor(color, 36))
  ctx.fillStyle = gradient
  roundRect(ctx, px, py, size, size, radius)
  ctx.fill()

  ctx.fillStyle = 'rgba(255, 255, 255, 0.22)'
  roundRect(ctx, px + size * 0.08, py + size * 0.08, size * 0.55, size * 0.22, radius * 0.6)
  ctx.fill()

  ctx.strokeStyle = 'rgba(0, 0, 0, 0.25)'
  ctx.lineWidth = Math.max(1, size * 0.04)
  roundRect(ctx, px, py, size, size, radius)
  ctx.stroke()

  ctx.restore()
}

function roundRect(
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
  ctx.lineTo(x + w - radius, y)
  ctx.quadraticCurveTo(x + w, y, x + w, y + radius)
  ctx.lineTo(x + w, y + h - radius)
  ctx.quadraticCurveTo(x + w, y + h, x + w - radius, y + h)
  ctx.lineTo(x + radius, y + h)
  ctx.quadraticCurveTo(x, y + h, x, y + h - radius)
  ctx.lineTo(x, y + radius)
  ctx.quadraticCurveTo(x, y, x + radius, y)
  ctx.closePath()
}

interface Particle {
  x: number
  y: number
  vx: number
  vy: number
  life: number
  color: string
  size: number
}

function spawnLineClearParticles(
  particles: Particle[],
  metrics: BoardMetrics,
  color: string,
  lines: number,
) {
  const count = 12 + lines * 8
  const centerX = metrics.offsetX + metrics.boardW / 2
  const bandY = metrics.offsetY + metrics.boardH - metrics.cell * Math.min(lines, 4) * 0.5
  for (let i = 0; i < count; i++) {
    particles.push({
      x: centerX + (Math.random() - 0.5) * metrics.boardW * 0.9,
      y: bandY + (Math.random() - 0.5) * metrics.cell * lines,
      vx: (Math.random() - 0.5) * 4,
      vy: -2 - Math.random() * 5,
      life: 1,
      color,
      size: Math.max(2, metrics.cell * (0.08 + Math.random() * 0.12)),
    })
  }
}

export function drawBoardEffects(
  ctx: CanvasRenderingContext2D,
  metrics: BoardMetrics,
  effects: BoardEffect[],
  now: number,
  particles: Particle[],
  boardColor: string,
) {
  for (const effect of effects) {
    const elapsed = now - effect.startedAt
    const duration = effectDuration(effect.type)
    const t = Math.min(1, elapsed / duration)
    if (t >= 1) continue

    if (effect.type === 'line_clear') {
      const lines = effect.lines ?? 1
      const sweepY = metrics.offsetY + metrics.boardH * (1 - t)
      ctx.save()
      ctx.fillStyle = `rgba(255, 255, 255, ${0.55 * (1 - t)})`
      ctx.fillRect(metrics.offsetX, sweepY - metrics.cell * 0.4, metrics.boardW, metrics.cell * lines * 0.9)
      ctx.fillStyle = `rgba(91, 156, 255, ${0.25 * (1 - t)})`
      ctx.fillRect(metrics.offsetX, metrics.offsetY, metrics.boardW, metrics.boardH)
      ctx.restore()

      if (elapsed < 40 && particles.length < 80) {
        spawnLineClearParticles(particles, metrics, boardColor, lines)
      }
    }

    if (effect.type === 'lock') {
      ctx.save()
      ctx.strokeStyle = `rgba(255, 255, 255, ${0.35 * (1 - t)})`
      ctx.lineWidth = Math.max(2, metrics.cell * 0.1)
      const pad = (1 - t) * metrics.cell * 0.3
      ctx.strokeRect(
        metrics.offsetX + pad,
        metrics.offsetY + pad,
        metrics.boardW - pad * 2,
        metrics.boardH - pad * 2,
      )
      ctx.restore()
    }

    if (effect.type === 'level_up') {
      ctx.save()
      ctx.fillStyle = `rgba(245, 158, 11, ${0.18 * (1 - t)})`
      ctx.fillRect(metrics.offsetX, metrics.offsetY, metrics.boardW, metrics.boardH)
      ctx.restore()
    }

    if (effect.type === 'death') {
      ctx.save()
      ctx.fillStyle = `rgba(239, 68, 68, ${0.35 * (1 - t)})`
      ctx.fillRect(metrics.offsetX, metrics.offsetY, metrics.boardW, metrics.boardH)
      ctx.restore()
    }
  }

  for (let i = particles.length - 1; i >= 0; i--) {
    const p = particles[i]
    p.x += p.vx
    p.y += p.vy
    p.vy += 0.15
    p.life -= 0.025
    if (p.life <= 0) {
      particles.splice(i, 1)
      continue
    }
    ctx.save()
    ctx.globalAlpha = p.life
    ctx.fillStyle = p.color
    ctx.beginPath()
    ctx.arc(p.x, p.y, p.size, 0, Math.PI * 2)
    ctx.fill()
    ctx.restore()
  }
}

export type { Particle }
