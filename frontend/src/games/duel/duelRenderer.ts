import type { DuelBullet, DuelFighter, DuelGameState, DuelLastHit, DuelObstacle, DuelPowerup } from '@/types'
import { resolveTheme, type ArenaTheme } from './themes'
import { isColorblindMode, isHitStopEnabled, loadShakeIntensity } from './visualPrefs'

interface Particle {
  x: number
  y: number
  vx: number
  vy: number
  life: number
  maxLife: number
  color: string
  size: number
  kind: 'spark' | 'ring' | 'smoke' | 'nova' | 'sparkle'
}

interface MuzzleFlash {
  x: number
  y: number
  color: string
  until: number
}

interface BeamFlash {
  x1: number
  y1: number
  x2: number
  y2: number
  color: string
  until: number
  width: number
}

interface ArenaPulse {
  x: number
  y: number
  color: string
  until: number
  durationMs: number
  maxRadius: number
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
  machine_gun: '#eab308',
  shield: '#38bdf8',
  wide_shot: '#a855f7',
  pierce: '#14b8a6',
  ghost: '#94a3b8',
  freeze: '#67e8f9',
  laser: '#f43f5e',
  railgun: '#dc2626',
  homing: '#22c55e',
  heal: '#4ade80',
  mirror: '#e879f9',
  overdrive: '#fb923c',
  bomb: '#f59e0b',
  cluster: '#ef4444',
  burst: '#60a5fa',
  phase_shift: '#818cf8',
  decoy: '#cbd5e1',
}

export const POWERUP_ICONS: Record<string, string> = {
  rapid_fire: '⚡',
  machine_gun: '🔫',
  shield: '◆',
  wide_shot: '▣',
  pierce: '➤',
  ghost: '◎',
  freeze: '❄',
  laser: '═',
  railgun: '▬',
  homing: '↯',
  heal: '+',
  mirror: '⟲',
  overdrive: '✦',
  bomb: '💣',
  cluster: '✸',
  burst: '⋯',
  phase_shift: '◇',
  decoy: '◌',
}

export const POWERUP_LABELS: Record<string, string> = {
  rapid_fire: 'Rapid Fire',
  machine_gun: 'Machine Gun',
  shield: 'Shield',
  wide_shot: 'Wide Shot',
  pierce: 'Pierce',
  ghost: 'Ghost',
  freeze: 'Freeze',
  laser: 'Laser',
  railgun: 'Railgun',
  homing: 'Homing',
  heal: 'Heal',
  mirror: 'Mirror',
  overdrive: 'Overdrive',
  bomb: 'Bomb',
  cluster: 'Cluster',
  burst: 'Burst',
  phase_shift: 'Phase Shift',
  decoy: 'Decoy',
}

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
  private beamFlashes: BeamFlash[] = []
  private arenaPulses: ArenaPulse[] = []
  private fighterPoses = new Map<string, FighterPose>()
  private shakeUntil = 0
  private shakeIntensity = 0
  private hitFlashUntil = 0
  private processedHitStamps = new Set<string>()
  private processedHitsTick = -1
  private lastActionStamp = ''
  private stars: Star[] = []
  private starsSeed = 0

  private lastPlayableMin = 0
  private lastPlayableMax = 999
  private hazardPulseUntil = 0
  private arenaBoundsInitialized = false
  private theme: ArenaTheme = resolveTheme('classic')
  private flipView = false
  private viewGridWidth = 0

  /** Mirror the arena horizontally so the local player always appears on the left. */
  private syncViewFlip(state: DuelGameState, viewerId: string) {
    const viewer = state.fighters[viewerId]
    this.flipView = viewer?.side === 'right'
    this.viewGridWidth = state.grid_width
  }

  private viewGridX(x: number): number {
    return this.flipView ? this.viewGridWidth - 1 - x : x
  }

  private boardX(offsetX: number, cell: number, gridX: number): number {
    return offsetX + this.viewGridX(gridX) * cell
  }

  private viewGridRectLeft(x: number, width: number): number {
    return this.flipView ? this.viewGridWidth - x - width : x
  }

  private facingRight(side: string): boolean {
    return this.flipView ? side === 'right' : side === 'left'
  }

  private screenShotDir(side: string): number {
    return this.facingRight(side) ? 1 : -1
  }

  reset() {
    this.particles = []
    this.muzzleFlashes = []
    this.beamFlashes = []
    this.arenaPulses = []
    this.fighterPoses.clear()
    this.clearCombatFx()
    this.processedHitStamps.clear()
    this.processedHitsTick = -1
    this.lastActionStamp = ''
    this.stars = []
    this.lastPlayableMin = 0
    this.lastPlayableMax = 999
    this.hazardPulseUntil = 0
    this.arenaBoundsInitialized = false
  }

  clearCombatFx() {
    this.shakeUntil = 0
    this.shakeIntensity = 0
    this.hitFlashUntil = 0
    this.particles = []
    this.muzzleFlashes = []
    this.beamFlashes = []
    this.arenaPulses = []
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
    if (state.tick !== this.processedHitsTick) {
      this.processedHitsTick = state.tick
      this.processedHitStamps.clear()
    }
    const yPart = hit.y ?? ''
    const stamp = `${state.tick}:${hit.player_id}:${hit.damage}:${hit.crit}:${Boolean(hit.blocked)}:${yPart}`
    if (this.processedHitStamps.has(stamp)) return
    this.processedHitStamps.add(stamp)

    const fighter = state.fighters[hit.player_id]
    if (!fighter) return

    const pose = this.fighterPoses.get(hit.player_id)
    const displayY = pose?.y ?? fighter.display_y ?? fighter.y
    const barCount = state.fighter_height ?? 3
    const cx = this.boardX(offsetX, cell, fighter.x) + cell / 2
    const hitRow = hit.y ?? displayY + Math.floor(barCount / 2)
    const cy = offsetY + hitRow * cell + cell / 2

    this.spawnHitBurst(cx, cy, fighter.color, hit.crit, Boolean(hit.blocked))

    if (hit.player_id === viewerId) {
      const shakeScale = loadShakeIntensity()
      if (shakeScale > 0) {
        this.shakeUntil = Date.now() + 280
        this.shakeIntensity = (hit.blocked ? 4 : 9) * shakeScale
      }
      this.hitFlashUntil = Date.now() + (hit.blocked ? 120 : 220)
      if (hit.crit && isHitStopEnabled()) {
        /* brief hit-stop handled via shake timing */
      }
    } else if (hit.damage > 0) {
      const shakeScale = loadShakeIntensity()
      if (shakeScale > 0) {
        this.shakeUntil = Date.now() + 140
        this.shakeIntensity = 5 * shakeScale
      }
    }
  }

  private handleTickHits(
    hits: DuelLastHit[] | undefined,
    viewerId: string,
    state: DuelGameState,
    cell: number,
    offsetX: number,
    offsetY: number,
  ) {
    if (!hits?.length) return
    for (const hit of hits) {
      this.handleHit(hit, viewerId, state, cell, offsetX, offsetY)
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

  private spawnPowerupBurst(x: number, y: number, color: string, large = false) {
    const count = large ? 28 : 18
    for (let i = 0; i < count; i++) {
      const angle = (Math.PI * 2 * i) / count + Math.random() * 0.5
      const speed = large ? 2.5 + Math.random() * 4 : 1.5 + Math.random() * 3
      this.particles.push({
        x,
        y,
        vx: Math.cos(angle) * speed,
        vy: Math.sin(angle) * speed,
        life: 1,
        maxLife: 1,
        color,
        size: large ? 2.5 + Math.random() * 2 : 1.5 + Math.random() * 2,
        kind: i % 3 === 0 ? 'sparkle' : 'spark',
      })
    }
    this.particles.push({ x, y, vx: 0, vy: 0, life: 1, maxLife: 1, color, size: large ? 22 : 14, kind: 'nova' })
    const durationMs = large ? 420 : 280
    this.arenaPulses.push({
      x,
      y,
      color,
      until: Date.now() + durationMs,
      durationMs,
      maxRadius: large ? 48 : 32,
    })
  }

  private spawnHealRise(x: number, y: number) {
    for (let i = 0; i < 16; i++) {
      this.particles.push({
        x: x + (Math.random() - 0.5) * 20,
        y: y + (Math.random() - 0.5) * 10,
        vx: (Math.random() - 0.5) * 0.8,
        vy: -1.2 - Math.random() * 2,
        life: 1,
        maxLife: 1,
        color: i % 2 === 0 ? '#4ade80' : '#bbf7d0',
        size: 2 + Math.random() * 2,
        kind: 'sparkle',
      })
    }
  }

  private spawnBeamFlash(
    x1: number,
    y1: number,
    x2: number,
    y2: number,
    color: string,
    width = 4,
    duration = 220,
  ) {
    this.beamFlashes.push({ x1, y1, x2, y2, color, until: Date.now() + duration, width })
    this.spawnPowerupBurst((x1 + x2) / 2, y1, color, true)
    this.shakeUntil = Date.now() + 180
    this.shakeIntensity = 6
  }

  private handleAction(state: DuelGameState, cell: number, offsetX: number, offsetY: number) {
    const action = state.last_action
    if (!action) return
    const type = action.type as string
    const powerupTypes = new Set([
      'shoot',
      'release_charge',
      'bomb_detonated',
      'powerup_collected',
      'powerup_activated',
      'powerup_spawned',
    ])
    if (!powerupTypes.has(type)) return
    const stamp = `${action.player_id}:${type}:${action.charge_ticks ?? 0}:${action.powerup_type ?? ''}:${action.x ?? ''}:${action.y ?? ''}`
    if (stamp === this.lastActionStamp) return
    this.lastActionStamp = stamp

    const playerId = action.player_id as string | undefined

    if (type === 'powerup_spawned') {
      const px = Number(action.x ?? 0)
      const py = Number(action.y ?? 0)
      const ptype = String(action.powerup_type ?? '')
      const color = POWERUP_COLORS[ptype] ?? '#fbbf24'
      const cx = this.boardX(offsetX, cell, px) + cell / 2
      const cy = offsetY + py * cell + cell / 2
      this.spawnPowerupBurst(cx, cy, color, false)
      return
    }

    const fighter = playerId ? state.fighters[playerId] : null
    if (!fighter && type !== 'bomb_detonated') return

    if (type === 'powerup_collected') {
      const ptype = String(action.powerup_type ?? '')
      const color = POWERUP_COLORS[ptype] ?? '#fbbf24'
      const pose = playerId ? this.fighterPoses.get(playerId) : null
      const displayY = pose?.y ?? fighter?.display_y ?? fighter?.y ?? 0
      const cx = this.boardX(offsetX, cell, fighter?.x ?? 0) + cell / 2
      const cy = offsetY + displayY * cell + (cell * (state.fighter_height ?? 3)) / 2
      this.spawnPowerupBurst(cx, cy, color, true)
      return
    }

    if (type === 'powerup_activated') {
      const ptype = String(action.powerup_type ?? '')
      const color = POWERUP_COLORS[ptype] ?? '#a855f7'
      const pose = playerId ? this.fighterPoses.get(playerId) : null
      const displayY = pose?.y ?? fighter?.display_y ?? fighter?.y ?? 0
      const barCount = state.fighter_height ?? 3
      const aimRow = displayY + Math.floor(barCount / 2)
      const cx = this.boardX(offsetX, cell, fighter?.x ?? 0) + cell / 2
      const cy = offsetY + aimRow * cell + cell / 2
      const boardEndX = this.facingRight(fighter!.side)
        ? offsetX + state.grid_width * cell
        : offsetX

      if (ptype === 'laser') {
        this.spawnBeamFlash(cx, cy, boardEndX, cy, color, 3, 180)
      } else if (ptype === 'railgun') {
        this.spawnBeamFlash(cx, cy, boardEndX, cy, '#dc2626', 6, 260)
      } else if (ptype === 'heal') {
        this.spawnHealRise(cx, cy)
      } else if (ptype === 'bomb' || ptype === 'cluster' || ptype === 'burst') {
        const muzzleX = this.boardX(offsetX, cell, fighter?.x ?? 0) + (this.facingRight(fighter!.side) ? cell : 0)
        this.muzzleFlashes.push({ x: muzzleX, y: cy, color, until: Date.now() + 160 })
        this.spawnPowerupBurst(muzzleX, cy, color, false)
      } else {
        this.spawnPowerupBurst(cx, cy, color, false)
      }
      return
    }

    if (type === 'bomb_detonated') {
      const bx = Number(action.x ?? 0)
      const by = Number(action.y ?? 0)
      const wallHit = Boolean(action.wall_hit)
      const cx = this.boardX(offsetX, cell, bx) + cell / 2
      const cy = offsetY + by * cell + cell / 2
      this.spawnHitBurst(cx, cy, '#f59e0b', true, false)
      if (wallHit) {
        this.spawnPowerupBurst(cx, cy, '#f59e0b', true)
      }
      const particleCount = wallHit ? 36 : 24
      for (let i = 0; i < particleCount; i++) {
        const angle = (Math.PI * 2 * i) / particleCount + Math.random() * 0.3
        const speed = wallHit ? 3 + Math.random() * 5 : 2 + Math.random() * 4
        this.particles.push({
          x: cx,
          y: cy,
          vx: Math.cos(angle) * speed,
          vy: Math.sin(angle) * speed,
          life: 1,
          maxLife: 1,
          color: i % 3 === 0 ? '#ef4444' : '#fbbf24',
          size: wallHit ? 2.5 + Math.random() * 3.5 : 2 + Math.random() * 3,
          kind: 'spark',
        })
      }
      this.shakeUntil = Date.now() + (wallHit ? 280 : 220)
      this.shakeIntensity = wallHit ? 10 : 7
      return
    }

    const pose = this.fighterPoses.get(playerId!)
    const displayY = pose?.y ?? fighter!.display_y ?? fighter!.y
    const aimRow = displayY + Math.floor((state.fighter_height ?? 3) / 2)
    const cx = this.boardX(offsetX, cell, fighter!.x) + (this.facingRight(fighter!.side) ? cell : 0)
    const cy = offsetY + aimRow * cell + cell / 2

    this.muzzleFlashes.push({ x: cx, y: cy, color: fighter!.color, until: Date.now() + 120 })

    const dir = this.screenShotDir(fighter!.side)
    for (let i = 0; i < 6; i++) {
      this.particles.push({
        x: cx,
        y: cy,
        vx: dir * (2 + Math.random() * 4),
        vy: (Math.random() - 0.5) * 3,
        life: 1,
        maxLife: 1,
        color: fighter!.color,
        size: 1.5 + Math.random() * 2,
        kind: 'spark',
      })
    }
  }

  private updateFighterPoses(state: DuelGameState, viewerId: string, now: number) {
    const elapsed = Math.max(0, now - this.stateSnapshotAt)
    const progress = Math.min(0.95, elapsed / this.tickMs)
    const barCount = state.fighter_height ?? 3
    const minY = state.playable_y_min
    const maxTop = Math.min(
      state.grid_height - barCount,
      state.playable_y_max - barCount + 1,
    )

    for (const [pid, fighter] of Object.entries(state.fighters)) {
      let targetY = fighter.display_y ?? fighter.y
      if (
        pid === viewerId &&
        fighter.alive &&
        fighter.move_direction !== 'stop' &&
        state.phase === 'playing'
      ) {
        const delta = fighter.move_direction === 'down' ? progress : -progress
        targetY = Math.max(minY, Math.min(maxTop, fighter.y + delta))
      }

      const existing = this.fighterPoses.get(pid)
      if (!existing) {
        this.fighterPoses.set(pid, { y: targetY, targetY, moveDirection: fighter.move_direction })
        continue
      }
      existing.targetY = targetY
      existing.moveDirection = fighter.move_direction
      const lerpFactor = pid === viewerId ? 0.58 : 0.34
      existing.y = lerp(existing.y, existing.targetY, lerpFactor)
      this.fighterPoses.set(pid, existing)
    }
  }

  private syncArenaShrink(state: DuelGameState, now: number) {
    const min = state.playable_y_min
    const max = state.playable_y_max
    if (this.arenaBoundsInitialized) {
      if (min > this.lastPlayableMin || max < this.lastPlayableMax) {
        this.hazardPulseUntil = now + 900
        this.shakeUntil = now + 220
        this.shakeIntensity = 4
      }
    } else {
      this.arenaBoundsInitialized = true
    }
    this.lastPlayableMin = min
    this.lastPlayableMax = max
  }

  private updateParticles() {
    this.particles = this.particles
      .map((p) => ({
        ...p,
        x: p.x + p.vx,
        y: p.y + p.vy,
        vy: p.vy + (p.kind === 'smoke' ? 0.02 : 0.004),
        life: p.life - (p.kind === 'nova' ? 0.022 : p.kind === 'sparkle' ? 0.028 : 0.035),
      }))
      .filter((p) => p.life > 0)

    const now = Date.now()
    this.muzzleFlashes = this.muzzleFlashes.filter((f) => f.until > now)
    this.beamFlashes = this.beamFlashes.filter((f) => f.until > now)
    this.arenaPulses = this.arenaPulses.filter((p) => p.until > now)
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
      x: this.viewGridX(bullet.x + bullet.vx * progress),
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
        this.processedHitStamps.clear()
        this.processedHitsTick = -1
        this.lastActionStamp = ''
      }
      this.lastPhase = state.phase
    }

    this.theme = resolveTheme(state.arena_theme)
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

    this.syncViewFlip(state, viewerId)
    this.ensureStars(displayW, displayH)
    this.syncStateSnapshot(state, now)
    this.syncArenaShrink(state, now)
    this.updateFighterPoses(state, viewerId, now)
    this.updateParticles()

    const shake = this.shakeOffset(now)
    const cell = Math.min(displayW / grid_width, displayH / grid_height)
    const boardW = cell * grid_width
    const boardH = cell * grid_height
    const offsetX = (displayW - boardW) / 2 + shake.x
    const offsetY = (displayH - boardH) / 2 + shake.y

    if (combatActive) {
      this.handleTickHits(state.tick_hits, viewerId, state, cell, offsetX, offsetY)
      if (!state.tick_hits?.length) {
        this.handleHit(state.last_hit, viewerId, state, cell, offsetX, offsetY)
      }
      this.handleAction(state, cell, offsetX, offsetY)
    }

    ctx.clearRect(0, 0, displayW, displayH)
    this.drawBackdrop(ctx, displayW, displayH, now)
    this.drawArena(ctx, offsetX, offsetY, boardW, boardH, grid_width, grid_height, cell, playable_y_min, playable_y_max, now)
    this.drawSpawnZones(ctx, offsetX, offsetY, boardW, boardH, cell, now)
    this.drawObstacles(ctx, offsetX, offsetY, cell, obstacles, now)
    this.drawDecoys(ctx, offsetX, offsetY, cell, grid_width, state.decoys ?? [], barCount, now)
    this.drawPowerup(
      ctx,
      offsetX,
      offsetY,
      cell,
      powerup,
      now,
      state.tick,
      state.powerup_lifetime_ticks ?? 120,
    )
    this.drawArenaPulses(ctx, now)
    this.drawBullets(ctx, offsetX, offsetY, cell, bullets, now)
    this.drawFighters(ctx, offsetX, offsetY, boardW, cell, barCount, fighters, viewerId, dangerRows, now, state)
    this.drawBeamFlashes(ctx, now)
    this.drawMuzzleFlashes(ctx, cell, now)
    this.drawParticles(ctx)
    if (combatActive) {
      this.drawHitFlash(ctx, offsetX, offsetY, boardW, boardH, now)
    }
    this.drawVignette(ctx, displayW, displayH)
  }

  private drawBackdrop(ctx: CanvasRenderingContext2D, width: number, height: number, now: number) {
    const grad = ctx.createRadialGradient(width * 0.5, height * 0.45, 0, width * 0.5, height * 0.5, Math.max(width, height) * 0.75)
    grad.addColorStop(0, this.theme.backdrop[0])
    grad.addColorStop(1, this.theme.backdrop[1])
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
    bg.addColorStop(0, this.theme.backdrop[0])
    bg.addColorStop(0.5, this.theme.backdrop[1])
    bg.addColorStop(1, this.theme.backdrop[0])
    ctx.fillStyle = bg
    ctx.fillRect(offsetX, offsetY, boardW, boardH)

    ctx.fillStyle = this.theme.grid
    for (let y = 0; y < gridH; y += 2) {
      ctx.fillRect(offsetX, offsetY + y * cell, boardW, cell)
    }

    const midX = offsetX + boardW / 2
    const midGrad = ctx.createLinearGradient(midX - cell * 2, offsetY, midX + cell * 2, offsetY)
    midGrad.addColorStop(0, 'rgba(91,156,255,0)')
    midGrad.addColorStop(0.5, this.theme.midline)
    midGrad.addColorStop(1, 'rgba(91,156,255,0)')
    ctx.fillStyle = midGrad
    ctx.fillRect(midX - cell * 3, offsetY, cell * 6, boardH)

    ctx.strokeStyle = this.theme.grid
    ctx.lineWidth = 1
    for (let x = 0; x <= gridW; x++) {
      const sx = this.boardX(offsetX, cell, x)
      ctx.beginPath()
      ctx.moveTo(sx, offsetY)
      ctx.lineTo(sx, offsetY + boardH)
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
      const hazardBoost = now < this.hazardPulseUntil ? 0.12 : 0
      const grad = ctx.createLinearGradient(offsetX, offsetY, offsetX, offsetY + h)
      grad.addColorStop(0, this.theme.hazard.replace(/0\.\d+\)/, `${0.35 + hazardBoost})`))
      grad.addColorStop(1, this.theme.hazard.replace(/0\.\d+\)/, '0.12)'))
      ctx.fillStyle = grad
      ctx.fillRect(offsetX, offsetY, boardW, h)
      this.drawHazardStripe(ctx, offsetX, offsetY, boardW, h, now, true)
    }
    if (playableMax < gridH - 1) {
      const top = offsetY + (playableMax + 1) * cell
      const h = (gridH - 1 - playableMax) * cell
      const hazardBoost = now < this.hazardPulseUntil ? 0.12 : 0
      const grad = ctx.createLinearGradient(offsetX, top, offsetX, top + h)
      grad.addColorStop(0, this.theme.hazard.replace(/0\.\d+\)/, '0.12)'))
      grad.addColorStop(1, this.theme.hazard.replace(/0\.\d+\)/, `${0.35 + hazardBoost})`))
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
    const blueGrad = (fromX: number, toX: number) => {
      const grad = ctx.createLinearGradient(fromX, offsetY, toX, offsetY)
      grad.addColorStop(0, `rgba(59,130,246,${0.22 * pulse})`)
      grad.addColorStop(1, 'rgba(59,130,246,0)')
      return grad
    }
    const redGrad = (fromX: number, toX: number) => {
      const grad = ctx.createLinearGradient(fromX, offsetY, toX, offsetY)
      grad.addColorStop(0, `rgba(239,68,68,${0.22 * pulse})`)
      grad.addColorStop(1, 'rgba(239,68,68,0)')
      return grad
    }

    const blueOnLeft = !this.flipView
    if (blueOnLeft) {
      ctx.fillStyle = blueGrad(offsetX, offsetX + cell * 2.5)
      ctx.fillRect(offsetX, offsetY, cell * 2.5, boardH)
      ctx.fillStyle = redGrad(offsetX + boardW, offsetX + boardW - cell * 2.5)
      ctx.fillRect(offsetX + boardW - cell * 2.5, offsetY, cell * 2.5, boardH)
    } else {
      ctx.fillStyle = redGrad(offsetX, offsetX + cell * 2.5)
      ctx.fillRect(offsetX, offsetY, cell * 2.5, boardH)
      ctx.fillStyle = blueGrad(offsetX + boardW, offsetX + boardW - cell * 2.5)
      ctx.fillRect(offsetX + boardW - cell * 2.5, offsetY, cell * 2.5, boardH)
    }
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
      const x = offsetX + this.viewGridRectLeft(obstacle.x, obstacle.w) * cell
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
    lifetimeTicks = 100,
  ) {
    if (!powerup) return
    const color = POWERUP_COLORS[powerup.type] ?? '#fbbf24'
    const cx = this.boardX(offsetX, cell, powerup.x) + cell / 2
    const cy = offsetY + powerup.y * cell + cell / 2
    let pulse = 0.82 + Math.sin(now * 0.006) * 0.18
    if (powerup.despawn_at_tick != null && tick > 0) {
      const remaining = powerup.despawn_at_tick - tick
      if (remaining <= 30) {
        pulse *= 0.65 + Math.sin(now * 0.015) * 0.35
      }
    }
    const orbit = now * 0.003
    const bob = Math.sin(now * 0.004) * cell * 0.08
    const drawY = cy + bob

    const tierRing =
      powerup.type === 'laser' || powerup.type === 'railgun' || powerup.type === 'cluster'
        ? '#fcd34d'
        : powerup.type === 'pierce' ||
            powerup.type === 'ghost' ||
            powerup.type === 'freeze' ||
            powerup.type === 'mirror' ||
            powerup.type === 'overdrive' ||
            powerup.type === 'bomb' ||
            powerup.type === 'burst'
          ? '#c084fc'
          : '#94a3b8'

    const pillar = ctx.createLinearGradient(cx, drawY - cell * 1.2, cx, drawY + cell * 1.2)
    pillar.addColorStop(0, rgba(color, 0))
    pillar.addColorStop(0.45, rgba(color, 0.22 * pulse))
    pillar.addColorStop(0.5, rgba('#ffffff', 0.35 * pulse))
    pillar.addColorStop(0.55, rgba(color, 0.22 * pulse))
    pillar.addColorStop(1, rgba(color, 0))
    ctx.fillStyle = pillar
    ctx.fillRect(cx - cell * 0.12, drawY - cell * 1.2, cell * 0.24, cell * 2.4)

    ctx.strokeStyle = rgba(tierRing, 0.35 + Math.sin(now * 0.008) * 0.15)
    ctx.lineWidth = Math.max(1.5, cell * 0.07)
    ctx.beginPath()
    ctx.arc(cx, drawY, cell * 0.52 * pulse, 0, Math.PI * 2)
    ctx.stroke()

    for (let i = 0; i < 5; i++) {
      const angle = orbit + (Math.PI * 2 * i) / 5
      const ox = cx + Math.cos(angle) * cell * 0.48 * pulse
      const oy = drawY + Math.sin(angle) * cell * 0.48 * pulse
      ctx.fillStyle = rgba(color, 0.55)
      ctx.beginPath()
      ctx.arc(ox, oy, cell * 0.07, 0, Math.PI * 2)
      ctx.fill()
      ctx.strokeStyle = rgba('#ffffff', 0.35)
      ctx.lineWidth = 1
      ctx.beginPath()
      ctx.moveTo(cx, drawY)
      ctx.lineTo(ox, oy)
      ctx.stroke()
    }

    const glow = ctx.createRadialGradient(cx, drawY, 0, cx, drawY, cell * 0.75 * pulse)
    glow.addColorStop(0, rgba(color, 0.65))
    glow.addColorStop(0.55, rgba(color, 0.25))
    glow.addColorStop(1, rgba(color, 0))
    ctx.fillStyle = glow
    ctx.beginPath()
    ctx.arc(cx, drawY, cell * 0.75 * pulse, 0, Math.PI * 2)
    ctx.fill()

    ctx.fillStyle = color
    ctx.beginPath()
    ctx.arc(cx, drawY, cell * 0.26, 0, Math.PI * 2)
    ctx.fill()

    ctx.fillStyle = '#fff'
    ctx.font = `bold ${Math.max(10, cell * 0.42)}px system-ui`
    ctx.textAlign = 'center'
    ctx.textBaseline = 'middle'
    ctx.fillText(POWERUP_ICONS[powerup.type] ?? '★', cx, drawY + 1)

    const label = POWERUP_LABELS[powerup.type] ?? powerup.type
    ctx.font = `600 ${Math.max(9, cell * 0.28)}px system-ui`
    ctx.fillStyle = rgba(color, 0.95)
    ctx.fillText(label, cx, drawY + cell * 0.78)

    if (powerup.despawn_at_tick != null && tick > 0) {
      const remaining = Math.max(0, powerup.despawn_at_tick - tick)
      const progress = Math.max(0, Math.min(1, remaining / lifetimeTicks))
      ctx.strokeStyle = rgba(tierRing, 0.75)
      ctx.lineWidth = Math.max(2, cell * 0.09)
      ctx.beginPath()
      ctx.arc(cx, drawY, cell * 0.42, -Math.PI / 2, -Math.PI / 2 + Math.PI * 2 * progress)
      ctx.stroke()
    }
  }

  private drawArenaPulses(ctx: CanvasRenderingContext2D, now: number) {
    for (const pulse of this.arenaPulses) {
      const remaining = pulse.until - now
      if (remaining <= 0) continue
      const duration = pulse.durationMs > 0 ? pulse.durationMs : 420
      const t = Math.min(1, Math.max(0, 1 - remaining / duration))
      const radius = pulse.maxRadius * t
      if (radius <= 0) continue
      ctx.strokeStyle = rgba(pulse.color, (1 - t) * 0.55)
      ctx.lineWidth = 2 + (1 - t) * 3
      ctx.beginPath()
      ctx.arc(pulse.x, pulse.y, radius, 0, Math.PI * 2)
      ctx.stroke()
    }
  }

  private drawBeamFlashes(ctx: CanvasRenderingContext2D, now: number) {
    for (const beam of this.beamFlashes) {
      const t = Math.min(1, Math.max(0, (beam.until - now) / 260))
      const grad = ctx.createLinearGradient(beam.x1, beam.y1, beam.x2, beam.y2)
      grad.addColorStop(0, rgba(beam.color, 0.15 * t))
      grad.addColorStop(0.5, rgba('#ffffff', 0.95 * t))
      grad.addColorStop(1, rgba(beam.color, 0.25 * t))
      ctx.strokeStyle = grad
      ctx.lineWidth = beam.width * (0.6 + t * 0.8)
      ctx.lineCap = 'round'
      ctx.beginPath()
      ctx.moveTo(beam.x1, beam.y1)
      ctx.lineTo(beam.x2, beam.y2)
      ctx.stroke()

      ctx.strokeStyle = rgba('#ffffff', 0.85 * t)
      ctx.lineWidth = Math.max(1, beam.width * 0.35)
      ctx.beginPath()
      ctx.moveTo(beam.x1, beam.y1)
      ctx.lineTo(beam.x2, beam.y2)
      ctx.stroke()
    }
  }

  private drawFighterEffectAura(
    ctx: CanvasRenderingContext2D,
    fx: number,
    top: number,
    fw: number,
    height: number,
    cell: number,
    fighter: DuelFighter,
    now: number,
  ) {
    const effects = fighter.effects
    if (!effects) return
    const facingRight = this.facingRight(fighter.side)

    if (effects.rapid_fire_active) {
      const flicker = 0.25 + Math.sin(now * 0.02) * 0.15
      ctx.fillStyle = rgba('#f97316', flicker)
      ctx.fillRect(fx - cell * 0.15, top + height * 0.35, cell * 0.2, height * 0.3)
    }

    if (effects.machine_gun_active) {
      ctx.fillStyle = rgba('#eab308', 0.35 + Math.sin(now * 0.035) * 0.2)
      ctx.beginPath()
      ctx.arc(fx + (facingRight ? fw : 0), top + height / 2, cell * 0.12, 0, Math.PI * 2)
      ctx.fill()
    }

    if (effects.overdrive_active) {
      const flame = 0.3 + Math.sin(now * 0.025) * 0.2
      ctx.fillStyle = rgba('#fb923c', flame)
      ctx.fillRect(fx - cell * 0.25, top + height * 0.2, cell * 0.18, height * 0.6)
    }

    if (effects.homing_active) {
      ctx.strokeStyle = rgba('#22c55e', 0.35 + Math.sin(now * 0.018) * 0.2)
      ctx.lineWidth = 1.5
      ctx.beginPath()
      ctx.arc(fx + fw / 2, top + height / 2, cell * 0.55, now * 0.004, now * 0.004 + Math.PI * 1.2)
      ctx.stroke()
    }

    if (effects.wide_shot_active) {
      for (const row of [-1, 0, 1]) {
        const ry = top + height / 2 + row * cell * 0.35
        ctx.fillStyle = rgba('#a855f7', 0.25 + Math.sin(now * 0.02 + row) * 0.15)
        ctx.beginPath()
        ctx.arc(fx + fw + (facingRight ? cell * 0.08 : -cell * 0.08), ry, cell * 0.08, 0, Math.PI * 2)
        ctx.fill()
      }
    }

    if (effects.pierce_active) {
      ctx.strokeStyle = rgba('#14b8a6', 0.45)
      ctx.lineWidth = 2
      ctx.setLineDash([3, 4])
      ctx.lineDashOffset = -now * 0.04
      ctx.beginPath()
      ctx.moveTo(fx + fw * 0.5, top)
      ctx.lineTo(fx + fw + cell * 0.35, top + height / 2)
      ctx.lineTo(fx + fw * 0.5, top + height)
      ctx.stroke()
      ctx.setLineDash([])
    }

    if (fighter.stored_powerup) {
      const storedColor = POWERUP_COLORS[fighter.stored_powerup] ?? '#fbbf24'
      const pulse = 0.35 + Math.sin(now * 0.012) * 0.2
      ctx.strokeStyle = rgba(storedColor, pulse)
      ctx.lineWidth = Math.max(2, cell * 0.1)
      ctx.beginPath()
      ctx.roundRect(fx - 3, top - 3, fw + 6, height + 6, cell * 0.18)
      ctx.stroke()
    }
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
      const cx = this.boardX(offsetX, cell, pos.x) + cell / 2
      const cy = offsetY + pos.y * cell + cell / 2
      const isBomb = bullet.kind === 'bomb'
      const charged = !isBomb && (bullet.damage ?? 1) >= 2
      const homing = bullet.homing
      const colorblind = isColorblindMode()
      const color = isBomb
        ? '#f59e0b'
        : homing
          ? colorblind
            ? '#38bdf8'
            : '#22c55e'
          : charged
            ? colorblind
              ? '#f472b6'
              : '#fb7185'
            : colorblind
              ? '#fde047'
              : '#fbbf24'
      const dir = (this.flipView ? -bullet.vx : bullet.vx) >= 0 ? 1 : -1
      const speed = Math.abs(bullet.vx) || 1

      if (isBomb) {
        const pulse = 0.85 + Math.sin(now * 0.012 + bullet.id) * 0.15
        const glow = ctx.createRadialGradient(cx, cy, 0, cx, cy, cell * 0.55 * pulse)
        glow.addColorStop(0, rgba('#fef3c7', 0.95))
        glow.addColorStop(0.45, rgba('#f59e0b', 0.75))
        glow.addColorStop(1, rgba('#ef4444', 0))
        ctx.fillStyle = glow
        ctx.beginPath()
        ctx.arc(cx, cy, cell * 0.5 * pulse, 0, Math.PI * 2)
        ctx.fill()
        ctx.fillStyle = '#451a03'
        ctx.font = `bold ${Math.max(10, cell * 0.38)}px system-ui`
        ctx.textAlign = 'center'
        ctx.textBaseline = 'middle'
        ctx.fillText('💣', cx, cy + 1)
        continue
      }

      if (homing) {
        const vy = bullet.vy ?? 0
        const travelX = dir * speed
        const travelY = vy
        const angle = Math.atan2(travelY, travelX)
        const trailLen = 7 + speed * 2

        for (let i = 1; i <= trailLen; i++) {
          const t = i / trailLen
          const alpha = (1 - t) * 0.22
          const tx = cx - Math.cos(angle) * i * cell * 0.22
          const ty = cy - Math.sin(angle) * i * cell * 0.22
          const radius = cell * (0.14 - t * 0.08)
          ctx.fillStyle = rgba(i % 2 === 0 ? '#94a3b8' : '#64748b', alpha)
          ctx.beginPath()
          ctx.arc(tx, ty, Math.max(1, radius), 0, Math.PI * 2)
          ctx.fill()
        }

        const exhaustGrad = ctx.createRadialGradient(
          cx - Math.cos(angle) * cell * 0.28,
          cy - Math.sin(angle) * cell * 0.28,
          0,
          cx - Math.cos(angle) * cell * 0.28,
          cy - Math.sin(angle) * cell * 0.28,
          cell * 0.45,
        )
        exhaustGrad.addColorStop(0, rgba('#fef08a', 0.85))
        exhaustGrad.addColorStop(0.45, rgba('#f97316', 0.45))
        exhaustGrad.addColorStop(1, rgba('#ef4444', 0))
        ctx.fillStyle = exhaustGrad
        ctx.beginPath()
        ctx.arc(
          cx - Math.cos(angle) * cell * 0.22,
          cy - Math.sin(angle) * cell * 0.22,
          cell * 0.38,
          0,
          Math.PI * 2,
        )
        ctx.fill()

        ctx.save()
        ctx.translate(cx, cy)
        ctx.rotate(angle)
        const bodyLen = cell * 0.42
        const bodyW = cell * 0.14
        ctx.fillStyle = colorblind ? '#38bdf8' : '#86efac'
        ctx.beginPath()
        ctx.moveTo(bodyLen, 0)
        ctx.lineTo(-bodyLen * 0.55, bodyW)
        ctx.lineTo(-bodyLen * 0.35, 0)
        ctx.lineTo(-bodyLen * 0.55, -bodyW)
        ctx.closePath()
        ctx.fill()
        ctx.fillStyle = colorblind ? '#0ea5e9' : '#22c55e'
        ctx.beginPath()
        ctx.moveTo(bodyLen * 0.95, 0)
        ctx.lineTo(bodyLen * 0.35, bodyW * 0.55)
        ctx.lineTo(bodyLen * 0.35, -bodyW * 0.55)
        ctx.closePath()
        ctx.fill()
        ctx.fillStyle = '#fef08a'
        ctx.beginPath()
        ctx.arc(bodyLen * 0.72, 0, cell * 0.05, 0, Math.PI * 2)
        ctx.fill()
        ctx.restore()
        continue
      }

      const trailSteps = 4 + speed * 3

      for (let i = 1; i <= trailSteps; i++) {
        const alpha = 0.05 + ((trailSteps - i) / trailSteps) * 0.12
        const tx = cx - dir * i * cell * 0.18
        const ty = cy - (bullet.vy ?? 0) * i * cell * 0.15
        ctx.strokeStyle = rgba(color, alpha)
        ctx.lineWidth = Math.max(1, cell * (charged || homing ? 0.16 : 0.08))
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

  private traceFighterHullPath(
    ctx: CanvasRenderingContext2D,
    fx: number,
    top: number,
    fw: number,
    height: number,
    cell: number,
    facingRight: boolean,
  ) {
    const nose = cell * 0.14
    const tail = cell * 0.1
    const wingY = top + height * 0.56
    const wingOut = fw * 0.24

    if (facingRight) {
      const back = fx + tail
      const front = fx + fw + nose
      ctx.moveTo(back, top + height * 0.14)
      ctx.quadraticCurveTo(fx + fw * 0.35, top + height * 0.02, front, top + height * 0.5)
      ctx.quadraticCurveTo(fx + fw * 0.35, top + height * 0.98, back, top + height * 0.86)
      ctx.lineTo(fx + fw * 0.08, wingY + cell * 0.08)
      ctx.lineTo(fx - wingOut, wingY)
      ctx.lineTo(fx + fw * 0.08, wingY - cell * 0.08)
      ctx.closePath()
    } else {
      const back = fx + fw - tail
      const front = fx - nose
      ctx.moveTo(back, top + height * 0.14)
      ctx.quadraticCurveTo(fx + fw * 0.65, top + height * 0.02, front, top + height * 0.5)
      ctx.quadraticCurveTo(fx + fw * 0.65, top + height * 0.98, back, top + height * 0.86)
      ctx.lineTo(fx + fw * 0.92, wingY + cell * 0.08)
      ctx.lineTo(fx + fw + wingOut, wingY)
      ctx.lineTo(fx + fw * 0.92, wingY - cell * 0.08)
      ctx.closePath()
    }
  }

  private drawFighterShip(
    ctx: CanvasRenderingContext2D,
    fx: number,
    shipTop: number,
    fw: number,
    shipHeight: number,
    cell: number,
    barCount: number,
    fighter: DuelFighter,
    dangerRows: Set<number>,
    displayY: number,
    isMe: boolean,
    moving: boolean,
    now: number,
    state?: DuelGameState,
    pid?: string,
  ) {
    const color = fighter.color
    const facingRight = this.facingRight(fighter.side)
    const cx = fx + fw / 2
    const cy = shipTop + shipHeight / 2

    ctx.save()
    this.traceFighterHullPath(ctx, fx, shipTop, fw, shipHeight, cell, facingRight)

    const glow = ctx.createRadialGradient(cx, cy, 0, cx, cy, cell * barCount * 0.75)
    glow.addColorStop(0, rgba(color, 0.35))
    glow.addColorStop(1, rgba(color, 0))
    ctx.fillStyle = glow
    ctx.fill()

    this.traceFighterHullPath(ctx, fx, shipTop, fw, shipHeight, cell, facingRight)
    const hullGrad = ctx.createLinearGradient(
      facingRight ? fx : fx + fw,
      shipTop,
      facingRight ? fx + fw : fx,
      shipTop + shipHeight,
    )
    hullGrad.addColorStop(0, lighten(color, 0.42))
    hullGrad.addColorStop(0.45, color)
    hullGrad.addColorStop(1, darken(color, 0.35))
    ctx.fillStyle = hullGrad
    ctx.fill()

    ctx.clip()

    for (let i = 0; i < barCount; i++) {
      const rowTop = shipTop + i * cell
      if (i > 0) {
        ctx.strokeStyle = rgba('#ffffff', 0.08)
        ctx.lineWidth = 1
        ctx.beginPath()
        ctx.moveTo(fx - cell * 0.05, rowTop)
        ctx.lineTo(fx + fw + cell * 0.05, rowTop)
        ctx.stroke()
      }
      if (isMe && dangerRows.has(displayY + i)) {
        const pulse = 0.28 + Math.sin(now * 0.025) * 0.12
        if (isColorblindMode()) {
          ctx.fillStyle = rgba('#fbbf24', pulse * 1.15)
          ctx.fillRect(fx - cell * 0.1, rowTop, fw + cell * 0.2, cell)
          ctx.strokeStyle = rgba('#0f172a', 0.55)
          ctx.lineWidth = Math.max(1, cell * 0.08)
          const stripeStep = Math.max(3, cell * 0.35)
          for (let sx = fx - cell * 0.1; sx < fx + fw + cell * 0.2; sx += stripeStep) {
            ctx.beginPath()
            ctx.moveTo(sx, rowTop)
            ctx.lineTo(sx + stripeStep * 0.55, rowTop + cell)
            ctx.stroke()
          }
        } else {
          ctx.fillStyle = rgba('#ef4444', pulse)
          ctx.fillRect(fx - cell * 0.1, rowTop, fw + cell * 0.2, cell)
        }
      }
    }

    const lostHp = Math.max(0, fighter.max_hp - fighter.hp)
    if (lostHp > 0 && fighter.alive) {
      const damageH = (shipHeight / fighter.max_hp) * lostHp
      ctx.fillStyle = rgba('#0f172a', 0.45)
      ctx.fillRect(fx - cell * 0.1, shipTop, fw + cell * 0.2, damageH)
      ctx.strokeStyle = rgba('#fca5a5', 0.35)
      ctx.lineWidth = 1
      for (let i = 0; i < lostHp; i++) {
        const sy = shipTop + (i + 0.5) * (shipHeight / fighter.max_hp)
        ctx.beginPath()
        ctx.moveTo(fx + fw * 0.15, sy - cell * 0.08)
        ctx.lineTo(fx + fw * 0.75, sy + cell * 0.06)
        ctx.stroke()
      }
    }

    ctx.restore()

    this.traceFighterHullPath(ctx, fx, shipTop, fw, shipHeight, cell, facingRight)
    ctx.strokeStyle = rgba(lighten(color, 0.55), 0.55)
    ctx.lineWidth = Math.max(1, cell * 0.07)
    ctx.stroke()

    const cockpitX = facingRight ? fx + fw * 0.58 : fx + fw * 0.42
    const cockpitY = cy
    ctx.fillStyle = rgba('#e0f2fe', 0.85)
    ctx.beginPath()
    ctx.ellipse(cockpitX, cockpitY, cell * 0.14, cell * 0.2, 0, 0, Math.PI * 2)
    ctx.fill()
    ctx.strokeStyle = rgba('#ffffff', 0.65)
    ctx.lineWidth = Math.max(1, cell * 0.05)
    ctx.stroke()

    ctx.fillStyle = rgba('#0c4a6e', 0.75)
    ctx.beginPath()
    ctx.ellipse(cockpitX + (facingRight ? cell * 0.03 : -cell * 0.03), cockpitY, cell * 0.06, cell * 0.1, 0, 0, Math.PI * 2)
    ctx.fill()

    const nozzleX = facingRight ? fx + cell * 0.06 : fx + fw - cell * 0.06
    if (moving && fighter.alive) {
      const flicker = 0.55 + Math.sin(now * 0.035) * 0.25
      const flameLen = cell * (0.35 + flicker * 0.25)
      const flameGrad = ctx.createLinearGradient(
        nozzleX,
        cy,
        facingRight ? nozzleX - flameLen : nozzleX + flameLen,
        cy,
      )
      flameGrad.addColorStop(0, rgba(color, 0.95))
      flameGrad.addColorStop(0.35, rgba('#fde68a', 0.85 * flicker))
      flameGrad.addColorStop(1, rgba('#f97316', 0))
      ctx.fillStyle = flameGrad
      ctx.beginPath()
      ctx.moveTo(nozzleX, cy - cell * 0.12)
      ctx.lineTo(facingRight ? nozzleX - flameLen : nozzleX + flameLen, cy)
      ctx.lineTo(nozzleX, cy + cell * 0.12)
      ctx.closePath()
      ctx.fill()
    } else if (fighter.alive) {
      ctx.fillStyle = rgba(lighten(color, 0.3), 0.5)
      ctx.beginPath()
      ctx.arc(nozzleX, cy, cell * 0.07, 0, Math.PI * 2)
      ctx.fill()
    }

    const fogActive =
      Boolean(state?.fog) ||
      state?.mutator === 'fog' ||
      state?.mutator_secondary === 'fog'
    const showCharge =
      fighter.charging &&
      (isMe || (!fogActive && pid !== undefined))
    if (showCharge && state) {
      const maxTicks = state.charge_max_ticks ?? 15
      const ticks = fighter.charge_ticks ?? 0
      const progress = Math.min(1, ticks / maxTicks)
      ctx.strokeStyle = rgba('#f472b6', 0.85)
      ctx.lineWidth = Math.max(2, cell * 0.08)
      ctx.beginPath()
      ctx.arc(cx, cy, cell * barCount * 0.55, -Math.PI / 2, -Math.PI / 2 + progress * Math.PI * 2)
      ctx.stroke()
    }
  }

  private drawDecoys(
    ctx: CanvasRenderingContext2D,
    offsetX: number,
    offsetY: number,
    cell: number,
    gridWidth: number,
    decoys: Array<{ player_id: string; y: number; side?: string }>,
    barCount: number,
    now: number,
  ) {
    for (const decoy of decoys) {
      const spawnX = decoy.side === 'right' ? gridWidth - 2 : 1
      const x = this.boardX(offsetX, cell, spawnX)
      const top = offsetY + decoy.y * cell
      const height = cell * barCount
      const pulse = 0.25 + Math.sin(now * 0.01) * 0.15
      ctx.globalAlpha = pulse
      ctx.strokeStyle = rgba('#cbd5e1', 0.8)
      ctx.lineWidth = Math.max(1, cell * 0.08)
      ctx.setLineDash([5, 4])
      ctx.strokeRect(x, top, cell, height)
      ctx.setLineDash([])
      ctx.globalAlpha = 1
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
    state: DuelGameState,
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

      const inset = Math.max(1, cell * 0.1)
      const fx = this.boardX(offsetX, cell, fighter.x) + inset
      const fw = cell - inset * 2
      const shipTop = offsetY + displayY * cell
      const shipHeight = cell * barCount
      const facingRight = this.facingRight(fighter.side)
      const fighterColX = this.boardX(offsetX, cell, fighter.x)

      this.drawFighterEffectAura(ctx, fx, shipTop, fw, shipHeight, cell, fighter, now)

      this.drawFighterShip(
        ctx,
        fx,
        shipTop,
        fw,
        shipHeight,
        cell,
        barCount,
        fighter,
        dangerRows,
        displayY,
        isMe,
        moving,
        now,
        state,
        pid,
      )

      if (fighter.effects?.shield_active) {
        const top = offsetY + displayY * cell
        const height = cell * barCount
        const shimmer = now * 0.004
        ctx.strokeStyle = rgba('#38bdf8', 0.35 + Math.sin(shimmer) * 0.2)
        ctx.lineWidth = Math.max(2, cell * 0.12)
        ctx.beginPath()
        ctx.roundRect(fighterColX - 2, top - 2, cell + 4, height + 4, cell * 0.2)
        ctx.stroke()

        ctx.strokeStyle = rgba('#7dd3fc', 0.5)
        ctx.lineWidth = 1
        ctx.setLineDash([4, 6])
        ctx.lineDashOffset = -now * 0.05
        ctx.stroke()
        ctx.setLineDash([])

        ctx.fillStyle = rgba('#38bdf8', 0.08 + Math.sin(shimmer * 2) * 0.05)
        ctx.fillRect(fighterColX - 1, top, cell + 2, height)
      }

      if (fighter.effects?.mirror_active) {
        const top = offsetY + displayY * cell
        const height = cell * barCount
        const pulse = 0.4 + Math.sin(now * 0.008) * 0.25
        ctx.strokeStyle = rgba('#e879f9', pulse)
        ctx.lineWidth = Math.max(2, cell * 0.1)
        ctx.beginPath()
        ctx.roundRect(fighterColX - 3, top - 3, cell + 6, height + 6, cell * 0.25)
        ctx.stroke()
      }

      if (fighter.effects?.freeze_active) {
        const top = offsetY + displayY * cell
        const height = cell * barCount
        ctx.fillStyle = rgba('#67e8f9', 0.18 + Math.sin(now * 0.006) * 0.08)
        ctx.fillRect(fighterColX - 1, top, cell + 2, height)
      }

      if (isMe && fighter.alive) {
        ctx.strokeStyle = 'rgba(255,255,255,0.85)'
        ctx.lineWidth = Math.max(1.5, cell * 0.08)
        ctx.beginPath()
        this.traceFighterHullPath(ctx, fx, shipTop, fw, shipHeight, cell, facingRight)
        ctx.stroke()

        const aimRow = displayY + Math.floor(barCount / 2)
        const ay = offsetY + aimRow * cell + cell / 2
        const sweep = (Math.sin(now * 0.008) + 1) * 0.5
        const aimEndX = facingRight ? offsetX + boardW : offsetX
        const muzzleX = facingRight ? fx + fw + cell * 0.08 : fx - cell * 0.08
        ctx.strokeStyle = `rgba(255,255,255,${0.12 + sweep * 0.12})`
        ctx.lineWidth = 1
        ctx.setLineDash([cell * 0.35, cell * 0.3])
        ctx.beginPath()
        ctx.moveTo(muzzleX, ay)
        ctx.lineTo(aimEndX, ay)
        ctx.stroke()
        ctx.setLineDash([])
      }

      if (!fighter.alive) {
        const cx = fx + fw / 2
        const cy = shipTop + shipHeight / 2
        ctx.strokeStyle = rgba(fighter.color, 0.45)
        ctx.lineWidth = Math.max(2, cell * 0.1)
        ctx.beginPath()
        ctx.moveTo(cx - cell * 0.35, cy - cell * 0.35)
        ctx.lineTo(cx + cell * 0.35, cy + cell * 0.35)
        ctx.moveTo(cx + cell * 0.35, cy - cell * 0.35)
        ctx.lineTo(cx - cell * 0.35, cy + cell * 0.35)
        ctx.stroke()
        ctx.strokeStyle = rgba(fighter.color, 0.2)
        ctx.beginPath()
        this.traceFighterHullPath(ctx, fx, shipTop, fw, shipHeight, cell, facingRight)
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
        const radius = Math.max(0, p.size * (2 - alpha))
        if (radius <= 0) continue
        ctx.strokeStyle = rgba(p.color, alpha * 0.8)
        ctx.lineWidth = 2
        ctx.beginPath()
        ctx.arc(p.x, p.y, radius, 0, Math.PI * 2)
        ctx.stroke()
        continue
      }
      if (p.kind === 'nova') {
        const radius = Math.max(0, p.size * (1.6 - alpha * 0.5))
        if (radius <= 0) continue
        const grad = ctx.createRadialGradient(p.x, p.y, 0, p.x, p.y, radius)
        grad.addColorStop(0, rgba('#ffffff', alpha * 0.9))
        grad.addColorStop(0.35, rgba(p.color, alpha * 0.65))
        grad.addColorStop(1, rgba(p.color, 0))
        ctx.fillStyle = grad
        ctx.beginPath()
        ctx.arc(p.x, p.y, radius, 0, Math.PI * 2)
        ctx.fill()
        continue
      }
      if (p.kind === 'sparkle') {
        ctx.save()
        ctx.translate(p.x, p.y)
        ctx.rotate((1 - alpha) * Math.PI * 2)
        ctx.fillStyle = rgba(p.color, alpha)
        ctx.fillRect(-p.size * alpha, -p.size * alpha * 0.35, p.size * alpha * 2, p.size * alpha * 0.7)
        ctx.fillRect(-p.size * alpha * 0.35, -p.size * alpha, p.size * alpha * 0.7, p.size * alpha * 2)
        ctx.restore()
        continue
      }
      ctx.fillStyle = rgba(p.color, alpha)
      const dotRadius = Math.max(0, p.size * alpha)
      if (dotRadius <= 0) continue
      ctx.beginPath()
      ctx.arc(p.x, p.y, dotRadius, 0, Math.PI * 2)
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
