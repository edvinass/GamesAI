import type { DuelBullet, DuelFighter, DuelGameState, DuelLastHit, DuelObstacle, DuelPowerup } from '@/types'

interface Particle {
  x: number
  y: number
  vx: number
  vy: number
  life: number
  maxLife: number
  color: string
  size: number
  kind: 'spark' | 'ring' | 'smoke'
}

interface MuzzleFlash {
  x: number
  y: number
  color: string
  until: number
}

interface FighterPose {
  y: number
  targetY: number
  moveDirection: string
}

interface Star {
  x: number
  y: number
  size: number
  twinkle: number
}

export const POWERUP_COLORS: Record<string, string> = {
  rapid_fire: '#f97316',
  shield: '#38bdf8',
  wide_shot: '#a855f7',
  ghost: '#94a3b8',
  freeze: '#67e8f9',
  laser: '#f43f5e',
  homing: '#22c55e',
  heal: '#4ade80',
  mirror: '#e879f9',
  overdrive: '#fb923c',
}

export const POWERUP_ICONS: Record<string, string> = {
  rapid_fire: '⚡',
  shield: '◆',
  wide_shot: '▣',
  ghost: '◎',
  freeze: '❄',
  laser: '═',
  homing: '↯',
  heal: '+',
  mirror: '⟲',
  overdrive: '✦',
}

export const POWERUP_LABELS: Record<string, string> = {
  rapid_fire: 'Rapid Fire',
  shield: 'Shield',
  wide_shot: 'Wide Shot',
  ghost: 'Ghost',
  freeze: 'Freeze',
  laser: 'Laser',
  homing: 'Homing',
  heal: 'Heal',
  mirror: 'Mirror',
  overdrive: 'Overdrive',
}

export const POWERUP_ACTIVATION_TICKS = 12

function hexToRgb(hex: string): [number, number, number] {
  const raw = hex.replace('#', '')
  const value = parseInt(raw.length === 3 ? raw.split('').map((c) => c + c).join('') : raw, 16)
  return [(value >> 16) & 255, (value >> 8) & 255, value & 255]
}

function rgba(hex: string, alpha: number): string {
  const [r, g, b] = hexToRgb(hex)
  return `rgba(${r}, ${g}, ${b}, ${alpha})`
}

function lerp(a: number, b: number, t: number): number {
  return a + (b - a) * t
}

function lighten(hex: string, amount: number): string {
  const [r, g, b] = hexToRgb(hex)
  return `rgb(${Math.min(255, r + 255 * amount)}, ${Math.min(255, g + 255 * amount)}, ${Math.min(255, b + 255 * amount)})`
}

function darken(hex: string, amount: number): string {
  const [r, g, b] = hexToRgb(hex)
  return `rgb(${Math.max(0, r * (1 - amount))}, ${Math.max(0, g * (1 - amount))}, ${Math.max(0, b * (1 - amount))})`
}

export class DuelRenderer {
  private particles: Particle[] = []
  private muzzleFlashes: MuzzleFlash[] = []
  private fighterPoses = new Map<string, FighterPose>()
  private shakeUntil = 0
  private shakeIntensity = 0
  private hitFlashUntil = 0
  private lastHitStamp = ''
  private lastActionStamp = ''
  private stars: Star[] = []
  private starsSeed = 0

  reset() {
    this.particles = []
    this.muzzleFlashes = []
    this.fighterPoses.clear()
    this.clearCombatFx()
    this.lastHitStamp = ''
    this.lastActionStamp = ''
    this.stars = []
  }

  clearCombatFx() {
    this.shakeUntil = 0
    this.shakeIntensity = 0
    this.hitFlashUntil = 0
    this.particles = []
    this.muzzleFlashes = []
  }

  private ensureStars(width: number, height: number) {
    if (this.stars.length > 0 && this.starsSeed === width * height) return
    this.starsSeed = width * height
    this.stars = Array.from({ length: 52 }, () => ({
      x: Math.random() * width,
      y: Math.random() * height,
      size: 0.6 + Math.random() * 1.5,
      twinkle: Math.random() * Math.PI * 2,
    }))
  }

  handleHit(hit: DuelLastHit | null, viewerId: string, state: DuelGameState, cell: number, offsetX: number, offsetY: number) {
    if (!hit) return
    const stamp = `${hit.player_id}:${hit.damage}:${hit.crit}:${Boolean(hit.blocked)}`
    if (stamp === this.lastHitStamp) return
    this.lastHitStamp = stamp

    const fighter = state.fighters[hit.player_id]
    if (!fighter) return

    const pose = this.fighterPoses.get(hit.player_id)
    const displayY = pose?.y ?? fighter.display_y ?? fighter.y
    const barCount = state.fighter_height ?? 3
    const cx = offsetX + fighter.x * cell + cell / 2
    const cy = offsetY + displayY * cell + (cell * barCount) / 2

    this.spawnHitBurst(cx, cy, fighter.color, hit.crit, Boolean(hit.blocked))

    if (hit.player_id === viewerId) {
      this.shakeUntil = Date.now() + 280
      this.shakeIntensity = hit.blocked ? 4 : 9
      this.hitFlashUntil = Date.now() + (hit.blocked ? 120 : 220)
    } else if (hit.damage > 0) {
      this.shakeUntil = Date.now() + 140
      this.shakeIntensity = 5
    }
  }

  private spawnHitBurst(x: number, y: number, color: string, crit = false, blocked = false) {
    const count = blocked ? 8 : crit ? 18 : 12
    for (let i = 0; i < count; i++) {
      const angle = (Math.PI * 2 * i) / count + Math.random() * 0.4
      const speed = blocked ? 1.2 : crit ? 3.5 : 2.4
      this.particles.push({
        x,
        y,
        vx: Math.cos(angle) * speed,
        vy: Math.sin(angle) * speed,
        life: 1,
        maxLife: 1,
        color: blocked ? '#38bdf8' : crit ? '#fb7185' : color,
        size: blocked ? 2 : crit ? 3.5 : 2.5,
        kind: 'spark',
      })
    }
    if (crit) {
      this.particles.push({ x, y, vx: 0, vy: 0, life: 1, maxLife: 1, color: '#fb7185', size: 14, kind: 'ring' })
    }
  }

  private handleAction(state: DuelGameState, cell: number, offsetX: number, offsetY: number) {
    const action = state.last_action
    if (!action) return
    const type = action.type as string
    if (type !== 'shoot' && type !== 'release_charge') return
    const stamp = `${action.player_id}:${type}:${action.charge_ticks ?? 0}`
    if (stamp === this.lastActionStamp) return
    this.lastActionStamp = stamp

    const playerId = action.player_id as string
    const fighter = state.fighters[playerId]
    if (!fighter) return

    const pose = this.fighterPoses.get(playerId)
    const displayY = pose?.y ?? fighter.display_y ?? fighter.y
    const aimRow = displayY + Math.floor((state.fighter_height ?? 3) / 2)
    const cx = offsetX + fighter.x * cell + (fighter.side === 'left' ? cell : 0)
    const cy = offsetY + aimRow * cell + cell / 2

    this.muzzleFlashes.push({ x: cx, y: cy, color: fighter.color, until: Date.now() + 120 })

    const dir = fighter.side === 'left' ? 1 : -1
    for (let i = 0; i < 6; i++) {
      this.particles.push({
        x: cx,
        y: cy,
        vx: dir * (2 + Math.random() * 4),
        vy: (Math.random() - 0.5) * 3,
        life: 1,
        maxLife: 1,
        color: fighter.color,
        size: 1.5 + Math.random() * 2,
        kind: 'spark',
      })
    }
  }

  private updateFighterPoses(state: DuelGameState) {
    for (const [pid, fighter] of Object.entries(state.fighters)) {
      const targetY = fighter.display_y ?? fighter.y
      const existing = this.fighterPoses.get(pid)
      if (!existing) {
        this.fighterPoses.set(pid, { y: targetY, targetY, moveDirection: fighter.move_direction })
        continue
      }
      existing.targetY = targetY
      existing.moveDirection = fighter.move_direction
      existing.y = lerp(existing.y, existing.targetY, 0.34)
      this.fighterPoses.set(pid, existing)
    }
  }

  private updateParticles() {
    this.particles = this.particles
      .map((p) => ({
        ...p,
        x: p.x + p.vx,
        y: p.y + p.vy,
        vy: p.vy + (p.kind === 'smoke' ? 0.02 : 0.004),
        life: p.life - 0.035,
      }))
      .filter((p) => p.life > 0)

    const now = Date.now()
    this.muzzleFlashes = this.muzzleFlashes.filter((f) => f.until > now)
  }

  private shakeOffset(now: number): { x: number; y: number } {
    if (now >= this.shakeUntil) return { x: 0, y: 0 }
    const t = Math.min(1, Math.max(0, (this.shakeUntil - now) / 280))
    const amp = this.shakeIntensity * t
    return { x: Math.sin(now * 0.05) * amp, y: Math.cos(now * 0.06) * amp * 0.7 }
  }

  private lastPhase = ''
  private stateSnapshotTick = -1
  private stateSnapshotAt = 0
  private tickMs = 75

  private syncStateSnapshot(state: DuelGameState, now: number) {
    if (state.tick !== this.stateSnapshotTick) {
      this.stateSnapshotTick = state.tick
      this.stateSnapshotAt = now
    }
    this.tickMs = state.tick_ms || 75
  }

  private bulletDisplayPos(bullet: DuelBullet, now: number): { x: number; y: number } {
    const elapsed = Math.max(0, now - this.stateSnapshotAt)
    const progress = Math.min(0.95, elapsed / this.tickMs)
    return {
      x: bullet.x + bullet.vx * progress,
      y: bullet.y + (bullet.vy ?? 0) * progress,
    }
  }

  draw(
    ctx: CanvasRenderingContext2D,
    state: DuelGameState,
    viewerId: string,
    displayW: number,
    displayH: number,
    now: number,
    dangerRows: Set<number>,
  ) {
    const combatActive = state.phase === 'playing'
    if (state.phase !== this.lastPhase) {
      if (!combatActive) {
        this.clearCombatFx()
        this.lastHitStamp = ''
        this.lastActionStamp = ''
      }
      this.lastPhase = state.phase
    }

    const {
      grid_width,
      grid_height,
      fighter_height,
      fighters,
      bullets,
      obstacles,
      powerup,
      playable_y_min,
      playable_y_max,
    } = state
    const barCount = fighter_height ?? 3

    this.ensureStars(displayW, displayH)
    this.syncStateSnapshot(state, now)
    this.updateFighterPoses(state)
    this.updateParticles()

    const shake = this.shakeOffset(now)
    const cell = Math.min(displayW / grid_width, displayH / grid_height)
    const boardW = cell * grid_width
    const boardH = cell * grid_height
    const offsetX = (displayW - boardW) / 2 + shake.x
    const offsetY = (displayH - boardH) / 2 + shake.y

    if (!state.last_hit) {
      this.lastHitStamp = ''
    }

    if (combatActive) {
      this.handleHit(state.last_hit, viewerId, state, cell, offsetX, offsetY)
      this.handleAction(state, cell, offsetX, offsetY)
    }

    ctx.clearRect(0, 0, displayW, displayH)
    this.drawBackdrop(ctx, displayW, displayH, now)
    this.drawArena(ctx, offsetX, offsetY, boardW, boardH, grid_width, grid_height, cell, playable_y_min, playable_y_max, now)
    this.drawSpawnZones(ctx, offsetX, offsetY, boardW, boardH, cell, now)
    this.drawObstacles(ctx, offsetX, offsetY, cell, obstacles, now)
    this.drawPowerup(ctx, offsetX, offsetY, cell, powerup, now, state.tick)
    this.drawBullets(ctx, offsetX, offsetY, cell, bullets, now)
    this.drawFighters(ctx, offsetX, offsetY, boardW, cell, barCount, fighters, viewerId, dangerRows, now)
    this.drawMuzzleFlashes(ctx, cell, now)
    this.drawParticles(ctx)
    if (combatActive) {
      this.drawHitFlash(ctx, offsetX, offsetY, boardW, boardH, now)
    }
    this.drawVignette(ctx, displayW, displayH)
  }

  private drawBackdrop(ctx: CanvasRenderingContext2D, width: number, height: number, now: number) {
    const grad = ctx.createRadialGradient(width * 0.5, height * 0.45, 0, width * 0.5, height * 0.5, Math.max(width, height) * 0.75)
    grad.addColorStop(0, '#121a2b')
    grad.addColorStop(1, '#070b12')
    ctx.fillStyle = grad
    ctx.fillRect(0, 0, width, height)

    for (const star of this.stars) {
      const alpha = 0.15 + Math.sin(now * 0.002 + star.twinkle) * 0.12
      ctx.fillStyle = `rgba(180, 210, 255, ${alpha})`
      ctx.beginPath()
      ctx.arc(star.x, star.y, star.size, 0, Math.PI * 2)
      ctx.fill()
    }
  }

  private drawArena(
    ctx: CanvasRenderingContext2D,
    offsetX: number,
    offsetY: number,
    boardW: number,
    boardH: number,
    gridW: number,
    gridH: number,
    cell: number,
    playableMin: number,
    playableMax: number,
    now: number,
  ) {
    const bg = ctx.createLinearGradient(offsetX, offsetY, offsetX + boardW, offsetY + boardH)
    bg.addColorStop(0, '#0c121c')
    bg.addColorStop(0.5, '#101827')
    bg.addColorStop(1, '#0c121c')
    ctx.fillStyle = bg
    ctx.fillRect(offsetX, offsetY, boardW, boardH)

    ctx.fillStyle = 'rgba(255,255,255,0.015)'
    for (let y = 0; y < gridH; y += 2) {
      ctx.fillRect(offsetX, offsetY + y * cell, boardW, cell)
    }

    const midX = offsetX + boardW / 2
    const pulse = 0.35 + Math.sin(now * 0.003) * 0.15
    const midGrad = ctx.createLinearGradient(midX - cell * 2, offsetY, midX + cell * 2, offsetY)
    midGrad.addColorStop(0, 'rgba(91,156,255,0)')
    midGrad.addColorStop(0.5, `rgba(91,156,255,${0.12 * pulse})`)
    midGrad.addColorStop(1, 'rgba(91,156,255,0)')
    ctx.fillStyle = midGrad
    ctx.fillRect(midX - cell * 3, offsetY, cell * 6, boardH)

    ctx.strokeStyle = 'rgba(30, 41, 59, 0.55)'
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

    if (playableMin > 0) {
      const h = playableMin * cell
      const grad = ctx.createLinearGradient(offsetX, offsetY, offsetX, offsetY + h)
      grad.addColorStop(0, 'rgba(239,68,68,0.45)')
      grad.addColorStop(1, 'rgba(239,68,68,0.12)')
      ctx.fillStyle = grad
      ctx.fillRect(offsetX, offsetY, boardW, h)
      this.drawHazardStripe(ctx, offsetX, offsetY, boardW, h, now, true)
    }
    if (playableMax < gridH - 1) {
      const top = offsetY + (playableMax + 1) * cell
      const h = (gridH - 1 - playableMax) * cell
      const grad = ctx.createLinearGradient(offsetX, top, offsetX, top + h)
      grad.addColorStop(0, 'rgba(239,68,68,0.12)')
      grad.addColorStop(1, 'rgba(239,68,68,0.45)')
      ctx.fillStyle = grad
      ctx.fillRect(offsetX, top, boardW, h)
      this.drawHazardStripe(ctx, offsetX, top, boardW, h, now, false)
    }

    ctx.strokeStyle = 'rgba(91,156,255,0.35)'
    ctx.lineWidth = 2
    ctx.strokeRect(offsetX + 0.5, offsetY + 0.5, boardW - 1, boardH - 1)
  }

  private drawHazardStripe(
    ctx: CanvasRenderingContext2D,
    x: number,
    y: number,
    w: number,
    h: number,
    now: number,
    top: boolean,
  ) {
    ctx.save()
    ctx.beginPath()
    ctx.rect(x, y, w, h)
    ctx.clip()
    ctx.strokeStyle = 'rgba(248,113,113,0.35)'
    ctx.lineWidth = 2
    const shift = (now * 0.04) % 16
    for (let i = -16; i < w + 16; i += 16) {
      ctx.beginPath()
      if (top) {
        ctx.moveTo(x + i + shift, y + h)
        ctx.lineTo(x + i + shift + 10, y)
      } else {
        ctx.moveTo(x + i - shift, y)
        ctx.lineTo(x + i - shift + 10, y + h)
      }
      ctx.stroke()
    }
    ctx.restore()
  }

  private drawSpawnZones(
    ctx: CanvasRenderingContext2D,
    offsetX: number,
    offsetY: number,
    boardW: number,
    boardH: number,
    cell: number,
    now: number,
  ) {
    const pulse = 0.5 + Math.sin(now * 0.004) * 0.2
    const leftGrad = ctx.createLinearGradient(offsetX, offsetY, offsetX + cell * 2.5, offsetY)
    leftGrad.addColorStop(0, `rgba(59,130,246,${0.22 * pulse})`)
    leftGrad.addColorStop(1, 'rgba(59,130,246,0)')
    ctx.fillStyle = leftGrad
    ctx.fillRect(offsetX, offsetY, cell * 2.5, boardH)

    const rightGrad = ctx.createLinearGradient(offsetX + boardW, offsetY, offsetX + boardW - cell * 2.5, offsetY)
    rightGrad.addColorStop(0, `rgba(239,68,68,${0.22 * pulse})`)
    rightGrad.addColorStop(1, 'rgba(239,68,68,0)')
    ctx.fillStyle = rightGrad
    ctx.fillRect(offsetX + boardW - cell * 2.5, offsetY, cell * 2.5, boardH)
  }

  private drawObstacles(
    ctx: CanvasRenderingContext2D,
    offsetX: number,
    offsetY: number,
    cell: number,
    obstacles: DuelObstacle[],
    now: number,
  ) {
    for (const obstacle of obstacles) {
      const x = offsetX + obstacle.x * cell
      const y = offsetY + obstacle.y * cell
      const w = obstacle.w * cell
      const h = obstacle.h * cell
      const pulse = 0.9 + Math.sin(now * 0.002 + obstacle.x) * 0.05

      const grad = ctx.createLinearGradient(x, y, x + w, y + h)
      grad.addColorStop(0, '#3f4f68')
      grad.addColorStop(0.5, '#2a3548')
      grad.addColorStop(1, '#1f2937')
      ctx.fillStyle = grad
      ctx.fillRect(x + 1, y + 1, w - 2, h - 2)

      ctx.strokeStyle = 'rgba(148,163,184,0.55)'
      ctx.lineWidth = Math.max(1, cell * 0.07)
      ctx.strokeRect(x + 1, y + 1, w - 2, h - 2)

      ctx.fillStyle = `rgba(148,163,184,${0.08 * pulse})`
      ctx.fillRect(x + cell * 0.15, y + cell * 0.15, w - cell * 0.3, cell * 0.35)
    }
  }

  private drawPowerup(
    ctx: CanvasRenderingContext2D,
    offsetX: number,
    offsetY: number,
    cell: number,
    powerup: DuelPowerup | null,
    now: number,
    tick = 0,
  ) {
    if (!powerup) return
    const color = POWERUP_COLORS[powerup.type] ?? '#fbbf24'
    const cx = offsetX + powerup.x * cell + cell / 2
    const cy = offsetY + powerup.y * cell + cell / 2
    let pulse = 0.8 + Math.sin(now * 0.006) * 0.2
    if (powerup.despawn_at_tick != null && tick > 0) {
      const remaining = powerup.despawn_at_tick - tick
      if (remaining <= 30) {
        pulse *= 0.65 + Math.sin(now * 0.015) * 0.35
      }
    }
    const orbit = now * 0.003

    for (let i = 0; i < 3; i++) {
      const angle = orbit + (Math.PI * 2 * i) / 3
      const ox = cx + Math.cos(angle) * cell * 0.42 * pulse
      const oy = cy + Math.sin(angle) * cell * 0.42 * pulse
      ctx.fillStyle = rgba(color, 0.45)
      ctx.beginPath()
      ctx.arc(ox, oy, cell * 0.08, 0, Math.PI * 2)
      ctx.fill()
    }

    const glow = ctx.createRadialGradient(cx, cy, 0, cx, cy, cell * 0.65 * pulse)
    glow.addColorStop(0, rgba(color, 0.55))
    glow.addColorStop(1, rgba(color, 0))
    ctx.fillStyle = glow
    ctx.beginPath()
    ctx.arc(cx, cy, cell * 0.65 * pulse, 0, Math.PI * 2)
    ctx.fill()

    ctx.fillStyle = color
    ctx.beginPath()
    ctx.arc(cx, cy, cell * 0.24, 0, Math.PI * 2)
    ctx.fill()

    ctx.fillStyle = '#fff'
    ctx.font = `bold ${Math.max(10, cell * 0.42)}px system-ui`
    ctx.textAlign = 'center'
    ctx.textBaseline = 'middle'
    ctx.fillText(POWERUP_ICONS[powerup.type] ?? '★', cx, cy + 1)
  }

  private drawBullets(
    ctx: CanvasRenderingContext2D,
    offsetX: number,
    offsetY: number,
    cell: number,
    bullets: DuelBullet[],
    now: number,
  ) {
    for (const bullet of bullets) {
      const pos = this.bulletDisplayPos(bullet, now)
      const cx = offsetX + pos.x * cell + cell / 2
      const cy = offsetY + pos.y * cell + cell / 2
      const charged = (bullet.damage ?? 1) >= 2
      const homing = bullet.homing
      const color = homing ? '#22c55e' : charged ? '#fb7185' : '#fbbf24'
      const dir = bullet.vx >= 0 ? 1 : -1
      const speed = Math.abs(bullet.vx) || 1
      const trailSteps = 4 + speed * 3

      for (let i = 1; i <= trailSteps; i++) {
        const alpha = 0.05 + ((trailSteps - i) / trailSteps) * 0.12
        const tx = cx - dir * i * cell * 0.18
        const ty = cy - (bullet.vy ?? 0) * i * cell * 0.15
        ctx.strokeStyle = rgba(color, alpha)
        ctx.lineWidth = Math.max(1, cell * (charged ? 0.12 : 0.08))
        ctx.beginPath()
        ctx.moveTo(tx - dir * cell * 0.22, ty)
        ctx.lineTo(tx + dir * cell * 0.22, ty)
        ctx.stroke()
      }

      const beamLen = cell * (0.35 + speed * 0.12)
      const beamGrad = ctx.createLinearGradient(cx - dir * beamLen, cy, cx + dir * beamLen, cy)
      beamGrad.addColorStop(0, rgba(color, 0))
      beamGrad.addColorStop(0.45, 'rgba(255,255,255,0.95)')
      beamGrad.addColorStop(1, rgba(color, 0))
      ctx.strokeStyle = beamGrad
      ctx.lineWidth = Math.max(2, cell * (charged ? 0.2 : 0.14 + speed * 0.02))
      ctx.lineCap = 'round'
      ctx.beginPath()
      ctx.moveTo(cx - dir * beamLen, cy)
      ctx.lineTo(cx + dir * beamLen, cy)
      ctx.stroke()

      ctx.fillStyle = rgba(color, 0.4 + Math.sin(now * 0.02 + bullet.id) * 0.1)
      ctx.beginPath()
      ctx.arc(cx, cy, cell * (charged ? 0.26 : 0.18 + speed * 0.03), 0, Math.PI * 2)
      ctx.fill()
    }
  }

  private drawFighterSegment(
    ctx: CanvasRenderingContext2D,
    x: number,
    y: number,
    w: number,
    h: number,
    color: string,
    danger: boolean,
    moving: boolean,
    now: number,
  ) {
    const r = Math.min(w, h) * 0.28
    const drawColor = danger ? '#fca5a5' : color

    ctx.fillStyle = rgba(drawColor, 0.25)
    ctx.beginPath()
    ctx.roundRect(x - 1, y - 1, w + 2, h + 2, r + 1)
    ctx.fill()

    const grad = ctx.createLinearGradient(x, y, x + w, y + h)
    grad.addColorStop(0, lighten(drawColor, 0.35))
    grad.addColorStop(0.55, drawColor)
    grad.addColorStop(1, darken(drawColor, 0.25))
    ctx.fillStyle = grad
    ctx.beginPath()
    ctx.roundRect(x, y, w, h, r)
    ctx.fill()

    if (moving) {
      const flicker = 0.35 + Math.sin(now * 0.03) * 0.2
      ctx.fillStyle = rgba(drawColor, flicker)
      ctx.fillRect(x - w * 0.35, y + h * 0.25, w * 0.25, h * 0.5)
    }
  }

  private drawFighters(
    ctx: CanvasRenderingContext2D,
    offsetX: number,
    offsetY: number,
    boardW: number,
    cell: number,
    barCount: number,
    fighters: Record<string, DuelFighter>,
    viewerId: string,
    dangerRows: Set<number>,
    now: number,
  ) {
    for (const [pid, fighter] of Object.entries(fighters)) {
      const isMe = pid === viewerId
      const pose = this.fighterPoses.get(pid)
      const displayY = pose?.y ?? fighter.display_y ?? fighter.y
      const ghosted = fighter.effects?.ghost_active && !isMe
      let alpha = fighter.alive ? (ghosted ? 0.42 : 1) : 0.28
      const moving = fighter.move_direction !== 'stop'

      if (ghosted) {
        alpha *= 0.55 + Math.sin(now * 0.02 + pid.length) * 0.25
      }
      ctx.globalAlpha = alpha

      const inset = Math.max(1, cell * 0.12)
      const barGap = Math.max(1, cell * 0.07)
      const barH = (cell * barCount - barGap * (barCount - 1)) / barCount
      const fx = offsetX + fighter.x * cell + inset
      const fw = cell - inset * 2

      for (let i = 0; i < barCount; i++) {
        const barY = displayY + i
        const fy = offsetY + barY * cell + (cell - barH) / 2
        this.drawFighterSegment(ctx, fx, fy, fw, barH, fighter.color, dangerRows.has(barY) && isMe, moving, now)
      }

      if (fighter.effects?.shield) {
        const top = offsetY + displayY * cell
        const height = cell * barCount
        const shimmer = now * 0.004
        ctx.strokeStyle = rgba('#38bdf8', 0.35 + Math.sin(shimmer) * 0.2)
        ctx.lineWidth = Math.max(2, cell * 0.12)
        ctx.beginPath()
        ctx.roundRect(offsetX + fighter.x * cell - 2, top - 2, cell + 4, height + 4, cell * 0.2)
        ctx.stroke()

        ctx.strokeStyle = rgba('#7dd3fc', 0.5)
        ctx.lineWidth = 1
        ctx.setLineDash([4, 6])
        ctx.lineDashOffset = -now * 0.05
        ctx.stroke()
        ctx.setLineDash([])
      }

      if (fighter.effects?.mirror_active) {
        const top = offsetY + displayY * cell
        const height = cell * barCount
        const pulse = 0.4 + Math.sin(now * 0.008) * 0.25
        ctx.strokeStyle = rgba('#e879f9', pulse)
        ctx.lineWidth = Math.max(2, cell * 0.1)
        ctx.beginPath()
        ctx.roundRect(offsetX + fighter.x * cell - 3, top - 3, cell + 6, height + 6, cell * 0.25)
        ctx.stroke()
      }

      if (fighter.effects?.freeze_active) {
        const top = offsetY + displayY * cell
        const height = cell * barCount
        ctx.fillStyle = rgba('#67e8f9', 0.18 + Math.sin(now * 0.006) * 0.08)
        ctx.fillRect(offsetX + fighter.x * cell - 1, top, cell + 2, height)
      }

      if (isMe && fighter.alive) {
        ctx.strokeStyle = 'rgba(255,255,255,0.85)'
        ctx.lineWidth = Math.max(1.5, cell * 0.08)
        ctx.beginPath()
        ctx.roundRect(fx - 1, offsetY + displayY * cell, fw + 2, cell * barCount, cell * 0.15)
        ctx.stroke()

        const aimRow = displayY + Math.floor(barCount / 2)
        const ay = offsetY + aimRow * cell + cell / 2
        const sweep = (Math.sin(now * 0.008) + 1) * 0.5
        const aimEndX = fighter.side === 'left' ? offsetX + boardW : offsetX
        ctx.strokeStyle = `rgba(255,255,255,${0.12 + sweep * 0.12})`
        ctx.lineWidth = 1
        ctx.setLineDash([cell * 0.35, cell * 0.3])
        ctx.beginPath()
        ctx.moveTo(offsetX + fighter.x * cell + cell, ay)
        ctx.lineTo(aimEndX, ay)
        ctx.stroke()
        ctx.setLineDash([])
      }

      if (!fighter.alive) {
        const cx = offsetX + fighter.x * cell + cell / 2
        const cy = offsetY + displayY * cell + (cell * barCount) / 2
        ctx.strokeStyle = rgba(fighter.color, 0.35)
        ctx.lineWidth = 2
        ctx.beginPath()
        ctx.arc(cx, cy, cell * 0.55, 0, Math.PI * 2)
        ctx.stroke()
      }

      ctx.globalAlpha = 1
    }
  }

  private drawMuzzleFlashes(ctx: CanvasRenderingContext2D, cell: number, now: number) {
    for (const flash of this.muzzleFlashes) {
      const t = Math.min(1, Math.max(0, (flash.until - now) / 120))
      const size = cell * 0.55 * t
      const grad = ctx.createRadialGradient(flash.x, flash.y, 0, flash.x, flash.y, size)
      grad.addColorStop(0, rgba('#ffffff', 0.95 * t))
      grad.addColorStop(0.35, rgba(flash.color, 0.65 * t))
      grad.addColorStop(1, rgba(flash.color, 0))
      ctx.fillStyle = grad
      ctx.beginPath()
      ctx.arc(flash.x, flash.y, size, 0, Math.PI * 2)
      ctx.fill()
    }
  }

  private drawParticles(ctx: CanvasRenderingContext2D) {
    for (const p of this.particles) {
      const alpha = p.life / p.maxLife
      if (p.kind === 'ring') {
        ctx.strokeStyle = rgba(p.color, alpha * 0.8)
        ctx.lineWidth = 2
        ctx.beginPath()
        ctx.arc(p.x, p.y, p.size * (2 - alpha), 0, Math.PI * 2)
        ctx.stroke()
        continue
      }
      ctx.fillStyle = rgba(p.color, alpha)
      ctx.beginPath()
      ctx.arc(p.x, p.y, p.size * alpha, 0, Math.PI * 2)
      ctx.fill()
    }
  }

  private drawHitFlash(
    ctx: CanvasRenderingContext2D,
    offsetX: number,
    offsetY: number,
    boardW: number,
    boardH: number,
    now: number,
  ) {
    if (now >= this.hitFlashUntil) return
    const t = Math.min(1, Math.max(0, (this.hitFlashUntil - now) / 220))
    ctx.save()
    ctx.strokeStyle = `rgba(239, 68, 68, ${0.55 * t})`
    ctx.lineWidth = 3
    ctx.strokeRect(offsetX + 1, offsetY + 1, boardW - 2, boardH - 2)
    ctx.fillStyle = `rgba(239, 68, 68, ${0.08 * t})`
    ctx.fillRect(offsetX, offsetY, boardW, boardH)
    ctx.restore()
  }

  private drawVignette(ctx: CanvasRenderingContext2D, width: number, height: number) {
    const grad = ctx.createRadialGradient(width / 2, height / 2, height * 0.3, width / 2, height / 2, height * 0.9)
    grad.addColorStop(0, 'rgba(0,0,0,0)')
    grad.addColorStop(1, 'rgba(0,0,0,0.28)')
    ctx.fillStyle = grad
    ctx.fillRect(0, 0, width, height)
  }
}
