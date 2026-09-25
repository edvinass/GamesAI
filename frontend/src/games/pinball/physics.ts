import { buildTable, type FlipperSpec, type Segment, type TableLayout, type Vec } from './table'

/** Physics substep — small enough that a max-speed ball moves < half its radius per step. */
const SUBSTEP = 1 / 720
const MAX_FRAME_DT = 1 / 20
const GRAVITY = 1500
const MAX_SPEED = 3200
const LINEAR_DAMPING = 0.12
/** Below this approach speed contacts don't bounce (kills resting jitter). */
const REST_SPEED = 30

const FLIPPER_UP_SPEED = 30
const FLIPPER_DOWN_SPEED = 16
const FLIPPER_E = 0.35

const BUMPER_KICK = 760
const SLING_KICK = 680
const KICK_COOLDOWN = 0.08

const PLUNGER_PULL_TIME = 0.85
const PLUNGER_MIN_LAUNCH = 900
const PLUNGER_MAX_LAUNCH = 2650

const SAUCER_HOLD = 1.1
const SAUCER_CAPTURE_SPEED = 950
const BALL_SAVE_TIME = 5
const BONUS_UNIT = 1000
const BONUS_PHASE_TIME = 1.9
const MULTIPLIER_STEPS = [1, 2, 3, 5]

export type PinballEventType =
  | 'bumper'
  | 'sling'
  | 'rollover'
  | 'laneComplete'
  | 'drop'
  | 'dropBank'
  | 'standup'
  | 'standupSet'
  | 'extraBall'
  | 'saucer'
  | 'saucerEject'
  | 'inlane'
  | 'outlane'
  | 'flipperHit'
  | 'wall'
  | 'launch'
  | 'skillShot'
  | 'ballSaved'
  | 'drain'
  | 'shootAgain'
  | 'newBall'
  | 'gameOver'

export interface PinballEvent {
  type: PinballEventType
  x: number
  y: number
  points: number
  label?: string
  intensity: number
}

export interface Ball {
  x: number
  y: number
  vx: number
  vy: number
}

export interface FlipperState {
  spec: FlipperSpec
  angle: number
  omega: number
  pressed: boolean
}

export type GamePhase = 'play' | 'bonus' | 'over'

export interface DisplayMessage {
  text: string
  sub?: string
  until: number
}

export class PinballGame {
  readonly table: TableLayout
  readonly totalBalls: number

  time = 0
  phase: GamePhase = 'play'
  ball: Ball | null = null
  flippers: FlipperState[]

  score = 0
  ballNumber = 1
  extraBalls = 0
  extraBallAwarded = false
  bonus = 0
  multiplierIndex = 0

  lanesLit = [false, false, false]
  skillLane = 1
  skillShotLive = false
  dropsDown: boolean[]
  standupsLit: boolean[]

  plungerPull = 0
  plungerHeld = false
  ballInLane = true
  ballSaveUntil = 0

  saucerHolding = false
  saucerReleaseAt = 0
  saucerCooldownUntil = 0

  /** Sim-time until which each element glows (render hints). */
  litUntil = new Map<string, number>()
  display: DisplayMessage | null = null

  private events: PinballEvent[] = []
  private accumulator = 0
  private kickCooldown = new Map<string, number>()
  private sensorsInside = new Set<string>()
  private dropResetAt = 0
  private bonusEndsAt = 0
  private stillSince = 0
  private flipperContact = false

  constructor(totalBalls = 3) {
    this.table = buildTable()
    this.totalBalls = Math.max(1, Math.min(5, totalBalls))
    this.flippers = this.table.flippers.map((spec) => ({
      spec,
      angle: spec.restAngle,
      omega: 0,
      pressed: false,
    }))
    this.dropsDown = this.table.dropTargets.map(() => false)
    this.standupsLit = this.table.standups.map(() => false)
    this.newBall()
  }

  get multiplier(): number {
    return MULTIPLIER_STEPS[this.multiplierIndex]
  }

  get plungerY(): number {
    return this.table.plunger.restY + this.plungerPull * this.table.plunger.maxPull
  }

  get ballSaveActive(): boolean {
    return this.phase === 'play' && (this.ballInLane || this.time < this.ballSaveUntil)
  }

  drainEvents(): PinballEvent[] {
    const out = this.events
    this.events = []
    return out
  }

  isLit(id: string): boolean {
    return (this.litUntil.get(id) ?? 0) > this.time
  }

  // —— Input ————————————————————————————————————————————————

  setFlipper(side: 'left' | 'right', pressed: boolean): void {
    if (this.phase === 'over') return
    const flipper = this.flippers.find((f) => f.spec.side === side)
    if (!flipper || flipper.pressed === pressed) return
    flipper.pressed = pressed
    if (pressed) this.rotateLanes(side === 'left' ? -1 : 1)
  }

  setPlunger(held: boolean): void {
    if (this.phase === 'over') return
    if (held) {
      this.plungerHeld = true
      return
    }
    if (!this.plungerHeld) return
    this.plungerHeld = false
    this.releasePlunger()
  }

  /** One-shot launch for tap / click (fixed strong pull). */
  autoLaunch(): void {
    if (this.phase !== 'play' || !this.ballInLane || this.plungerHeld) return
    this.plungerPull = 0.82
    this.releasePlunger()
  }

  // —— Simulation ———————————————————————————————————————————

  update(frameDt: number): void {
    if (this.phase === 'over') return
    this.accumulator += Math.min(frameDt, MAX_FRAME_DT)
    while (this.accumulator >= SUBSTEP) {
      this.step(SUBSTEP)
      this.accumulator -= SUBSTEP
    }
  }

  private step(h: number): void {
    this.time += h

    if (this.plungerHeld) {
      this.plungerPull = Math.min(1, this.plungerPull + h / PLUNGER_PULL_TIME)
    }

    for (const f of this.flippers) this.updateFlipper(f, h)

    if (this.dropResetAt && this.time >= this.dropResetAt) {
      this.dropResetAt = 0
      this.dropsDown = this.dropsDown.map(() => false)
    }

    if (this.phase === 'bonus') {
      if (this.time >= this.bonusEndsAt) this.finishBonus()
      return
    }

    const ball = this.ball
    if (!ball) return

    if (this.saucerHolding) {
      if (this.time >= this.saucerReleaseAt) this.ejectSaucer(ball)
      return
    }

    ball.vy += GRAVITY * h
    const damp = 1 - LINEAR_DAMPING * h
    ball.vx *= damp
    ball.vy *= damp
    const speed = Math.hypot(ball.vx, ball.vy)
    if (speed > MAX_SPEED) {
      ball.vx *= MAX_SPEED / speed
      ball.vy *= MAX_SPEED / speed
    }
    ball.x += ball.vx * h
    ball.y += ball.vy * h

    this.flipperContact = false
    this.collideSegments(ball)
    this.collideCircles(ball)
    this.collideTargets(ball)
    for (const f of this.flippers) this.collideFlipper(ball, f)
    this.collidePlunger(ball)
    this.checkSensors(ball)
    this.checkSaucer(ball)
    this.checkLaneExit(ball)
    this.checkStuck(ball)

    if (ball.y > this.table.drainY) this.handleDrain()
  }

  private updateFlipper(f: FlipperState, h: number): void {
    const target = f.pressed ? f.spec.activeAngle : f.spec.restAngle
    const diff = target - f.angle
    const maxStep = (f.pressed ? FLIPPER_UP_SPEED : FLIPPER_DOWN_SPEED) * h
    const next = Math.abs(diff) <= maxStep ? target : f.angle + Math.sign(diff) * maxStep
    f.omega = (next - f.angle) / h
    f.angle = next
  }

  // —— Collision ————————————————————————————————————————————

  /** Resolve ball vs. a static segment; returns impact speed (0 if no contact). */
  private resolveSegment(ball: Ball, seg: { a: Vec; b: Vec; oneWay?: boolean }, e: number): number {
    const r = this.table.ballRadius
    const abx = seg.b.x - seg.a.x
    const aby = seg.b.y - seg.a.y
    const len2 = abx * abx + aby * aby
    let t = ((ball.x - seg.a.x) * abx + (ball.y - seg.a.y) * aby) / len2
    t = Math.max(0, Math.min(1, t))
    const qx = seg.a.x + abx * t
    const qy = seg.a.y + aby * t
    let dx = ball.x - qx
    let dy = ball.y - qy
    const d2 = dx * dx + dy * dy
    if (d2 >= r * r) return 0

    if (seg.oneWay) {
      const len = Math.sqrt(len2)
      const nx = aby / len
      const ny = -abx / len
      if ((ball.x - seg.a.x) * nx + (ball.y - seg.a.y) * ny <= 0) return 0
    }

    const d = Math.sqrt(d2)
    if (d < 1e-6) {
      const len = Math.sqrt(len2)
      dx = aby / len
      dy = -abx / len
    } else {
      dx /= d
      dy /= d
    }
    const pen = r - d
    ball.x += dx * pen
    ball.y += dy * pen
    return this.bounce(ball, dx, dy, e)
  }

  /** Reflect the normal component; returns approach speed. */
  private bounce(ball: Ball, nx: number, ny: number, e: number): number {
    const vn = ball.vx * nx + ball.vy * ny
    if (vn >= 0) return 0
    const restitution = -vn < REST_SPEED ? 0 : e
    ball.vx -= (1 + restitution) * vn * nx
    ball.vy -= (1 + restitution) * vn * ny
    return -vn
  }

  /** Guarantee at least `kick` outward speed along the normal (active kickers). */
  private applyKick(ball: Ball, nx: number, ny: number, kick: number): void {
    const vn = ball.vx * nx + ball.vy * ny
    if (vn < kick) {
      ball.vx += (kick - vn) * nx
      ball.vy += (kick - vn) * ny
    }
  }

  private kickReady(id: string): boolean {
    if ((this.kickCooldown.get(id) ?? 0) > this.time) return false
    this.kickCooldown.set(id, this.time + KICK_COOLDOWN)
    return true
  }

  private collideSegments(ball: Ball): void {
    for (const seg of this.table.segments) {
      const impact = this.resolveSegment(ball, seg, seg.restitution)
      if (!impact) continue
      if (seg.kind === 'sling' && seg.id && impact > 60 && this.kickReady(seg.id)) {
        const n = segmentNormalToward(seg, ball)
        // Real slings are never perfectly consistent; jitter breaks sling-to-sling loops.
        const jitter = (Math.random() - 0.5) * 0.4
        const kx = n.x * Math.cos(jitter) - n.y * Math.sin(jitter)
        const ky = n.x * Math.sin(jitter) + n.y * Math.cos(jitter)
        this.applyKick(ball, kx, ky, SLING_KICK * (0.85 + Math.random() * 0.25))
        this.litUntil.set(seg.id, this.time + 0.12)
        this.addScore(10)
        this.cancelSkillShot()
        this.emit('sling', ball.x, ball.y, 10, 1)
      } else if (impact > 140) {
        this.emit('wall', ball.x, ball.y, 0, Math.min(1, impact / 1400))
      }
    }
  }

  private collideCircles(ball: Ball): void {
    const r = this.table.ballRadius
    for (const c of this.table.circles) {
      const dx = ball.x - c.c.x
      const dy = ball.y - c.c.y
      const minD = c.r + r
      const d2 = dx * dx + dy * dy
      if (d2 >= minD * minD) continue
      const d = Math.sqrt(d2) || 1e-6
      const nx = dx / d
      const ny = dy / d
      ball.x = c.c.x + nx * minD
      ball.y = c.c.y + ny * minD
      const impact = this.bounce(ball, nx, ny, c.restitution)
      if (c.kind === 'bumper') {
        if (this.kickReady(c.id)) {
          this.applyKick(ball, nx, ny, BUMPER_KICK)
          this.litUntil.set(c.id, this.time + 0.15)
          this.addScore(100)
          this.cancelSkillShot()
          this.emit('bumper', c.c.x, c.c.y, 100, 1)
        }
      } else if (impact > 140) {
        this.emit('wall', ball.x, ball.y, 0, Math.min(1, impact / 1400))
      }
    }
  }

  private collideTargets(ball: Ball): void {
    this.table.dropTargets.forEach((t, i) => {
      if (this.dropsDown[i]) return
      const impact = this.resolveSegment(ball, t, 0.45)
      if (!impact || impact < 40) return
      this.dropsDown[i] = true
      this.addScore(500)
      this.bonus++
      this.cancelSkillShot()
      const mx = (t.a.x + t.b.x) / 2
      const my = (t.a.y + t.b.y) / 2
      this.emit('drop', mx, my, 500, 1)
      if (this.dropsDown.every(Boolean)) {
        this.addScore(5000)
        this.bonus += 3
        this.dropResetAt = this.time + 1.2
        this.showMessage('DROP TARGETS', '5,000')
        this.emit('dropBank', mx, my, 5000, 1, 'TARGETS 5,000')
      }
    })

    this.table.standups.forEach((t, i) => {
      const impact = this.resolveSegment(ball, t, 0.5)
      if (!impact || impact < 60 || !this.kickReady(t.id)) return
      const mx = (t.a.x + t.b.x) / 2
      const my = (t.a.y + t.b.y) / 2
      this.litUntil.set(t.id, this.time + 0.2)
      this.cancelSkillShot()
      if (this.standupsLit[i]) {
        this.addScore(200)
        this.emit('standup', mx, my, 200, 0.5)
        return
      }
      this.standupsLit[i] = true
      this.addScore(1000)
      this.bonus++
      this.emit('standup', mx, my, 1000, 1)
      if (this.standupsLit.every(Boolean)) {
        this.standupsLit = this.standupsLit.map(() => false)
        if (!this.extraBallAwarded) {
          this.extraBallAwarded = true
          this.extraBalls++
          this.showMessage('EXTRA BALL', 'SHOOT AGAIN LIT')
          this.emit('extraBall', mx, my, 0, 1, 'EXTRA BALL')
        } else {
          this.addScore(10000)
          this.showMessage('TARGETS COMPLETE', '10,000')
          this.emit('standupSet', mx, my, 10000, 1, '10,000')
        }
      }
    })
  }

  private collideFlipper(ball: Ball, f: FlipperState): void {
    const { pivot, length, r0, r1 } = f.spec
    const R = this.table.ballRadius
    const dirX = Math.cos(f.angle)
    const dirY = Math.sin(f.angle)
    const px = ball.x - pivot.x
    const py = ball.y - pivot.y
    const t = Math.max(0, Math.min(1, (px * dirX + py * dirY) / length))
    const cx = pivot.x + dirX * length * t
    const cy = pivot.y + dirY * length * t
    const rad = r0 + (r1 - r0) * t
    let dx = ball.x - cx
    let dy = ball.y - cy
    const d = Math.hypot(dx, dy)
    if (d >= rad + R) return

    if (d < 1e-6) {
      dx = 0
      dy = -1
    } else {
      dx /= d
      dy /= d
    }
    const pen = rad + R - d
    ball.x += dx * pen
    ball.y += dy * pen
    this.flipperContact = true

    // Surface velocity at the contact point from the flipper's rotation.
    const rx = cx + dx * rad - pivot.x
    const ry = cy + dy * rad - pivot.y
    const vs = -f.omega * ry * dx + f.omega * rx * dy
    const vb = ball.vx * dx + ball.vy * dy
    const vrel = vb - vs
    if (vrel >= 0) return
    const e = -vrel < REST_SPEED ? 0 : FLIPPER_E
    const newVb = vs - e * vrel
    ball.vx += (newVb - vb) * dx
    ball.vy += (newVb - vb) * dy
    if (f.omega !== 0 && -vrel > 300) {
      this.emit('flipperHit', ball.x, ball.y, 0, Math.min(1, -vrel / 2000))
    }
  }

  private collidePlunger(ball: Ball): void {
    const { x0, x1 } = this.table.plunger
    if (ball.x < x0 || ball.x > x1) return
    const y = this.plungerY
    const hit = this.resolveSegment(ball, { a: { x: x0, y }, b: { x: x1, y }, oneWay: true }, 0.25)
    if (hit) this.flipperContact = true
  }

  // —— Switches & features ——————————————————————————————————

  private checkSensors(ball: Ball): void {
    for (const s of this.table.sensors) {
      const inside = Math.hypot(ball.x - s.c.x, ball.y - s.c.y) < s.r
      const was = this.sensorsInside.has(s.id)
      if (inside === was) continue
      if (!inside) {
        this.sensorsInside.delete(s.id)
        continue
      }
      this.sensorsInside.add(s.id)
      this.litUntil.set(s.id, this.time + 0.3)
      if (s.kind === 'rollover') this.hitRollover(Number(s.id.slice(4)), s.c)
      else if (s.kind === 'inlane') {
        this.addScore(500)
        this.bonus++
        this.cancelSkillShot()
        this.emit('inlane', s.c.x, s.c.y, 500, 0.6)
      } else {
        this.addScore(2000)
        this.bonus++
        this.cancelSkillShot()
        this.emit('outlane', s.c.x, s.c.y, 2000, 0.6)
      }
    }
  }

  private hitRollover(i: number, at: Vec): void {
    if (this.skillShotLive) {
      this.skillShotLive = false
      if (i === this.skillLane) {
        this.addScore(5000)
        this.showMessage('SKILL SHOT', '5,000')
        this.emit('skillShot', at.x, at.y, 5000, 1, 'SKILL SHOT')
      }
    }
    if (this.lanesLit[i]) {
      this.addScore(100)
      this.emit('rollover', at.x, at.y, 100, 0.4)
      return
    }
    this.lanesLit[i] = true
    this.addScore(500)
    this.bonus++
    this.emit('rollover', at.x, at.y, 500, 1)
    if (this.lanesLit.every(Boolean)) {
      this.lanesLit = [false, false, false]
      if (this.multiplierIndex < MULTIPLIER_STEPS.length - 1) {
        this.multiplierIndex++
        this.showMessage(`BONUS ${this.multiplier}X`, 'LANES COMPLETE')
        this.emit('laneComplete', at.x, at.y, 0, 1, `${this.multiplier}X BONUS`)
      } else {
        this.addScore(25000)
        this.showMessage('LANES COMPLETE', '25,000')
        this.emit('laneComplete', at.x, at.y, 25000, 1, '25,000')
      }
    }
  }

  /** Classic lane change: flipper buttons shift lit top-lane lamps. */
  private rotateLanes(dir: -1 | 1): void {
    if (this.phase !== 'play') return
    if (this.ballInLane) {
      this.skillLane = (this.skillLane + dir + 3) % 3
      return
    }
    const l = this.lanesLit
    this.lanesLit = dir < 0 ? [l[1], l[2], l[0]] : [l[2], l[0], l[1]]
  }

  private checkSaucer(ball: Ball): void {
    if (this.time < this.saucerCooldownUntil) return
    const { c } = this.table.saucer
    const d = Math.hypot(ball.x - c.x, ball.y - c.y)
    if (d > 9 || Math.hypot(ball.vx, ball.vy) > SAUCER_CAPTURE_SPEED) return
    this.saucerHolding = true
    this.saucerReleaseAt = this.time + SAUCER_HOLD
    ball.x = c.x
    ball.y = c.y
    ball.vx = 0
    ball.vy = 0
    const points = 2500 * this.multiplier
    this.addScore(points)
    this.bonus += 2
    this.cancelSkillShot()
    this.litUntil.set('saucer', this.time + SAUCER_HOLD)
    this.emit('saucer', c.x, c.y, points, 1)
  }

  private ejectSaucer(ball: Ball): void {
    this.saucerHolding = false
    this.saucerCooldownUntil = this.time + 0.6
    const angle = -Math.PI / 2 + (Math.random() - 0.5) * 1.1
    const speed = 1150 + Math.random() * 250
    ball.vx = Math.cos(angle) * speed
    ball.vy = Math.sin(angle) * speed
    this.emit('saucerEject', ball.x, ball.y, 0, 1)
  }

  private checkLaneExit(ball: Ball): void {
    if (!this.ballInLane) return
    if (ball.x < this.table.playRight - this.table.ballRadius) {
      this.ballInLane = false
      this.ballSaveUntil = this.time + BALL_SAVE_TIME
    }
  }

  /** Free a ball stranded on a flat spot (never while cradled or on the plunger). */
  private checkStuck(ball: Ball): void {
    if (this.flipperContact || Math.hypot(ball.vx, ball.vy) > 12) {
      this.stillSince = this.time
      return
    }
    if (this.time - this.stillSince > 3) {
      ball.vx = (Math.random() - 0.5) * 300
      ball.vy = -400
      this.stillSince = this.time
    }
  }

  private releasePlunger(): void {
    const pull = this.plungerPull
    this.plungerPull = 0
    const ball = this.ball
    if (!ball || this.phase !== 'play') return
    const { x0, x1 } = this.table.plunger
    const onPlunger = ball.x > x0 && ball.x < x1 && ball.y + this.table.ballRadius >= this.plungerY - 4
    if (!onPlunger || pull < 0.03) return
    ball.vy = -(PLUNGER_MIN_LAUNCH + pull * (PLUNGER_MAX_LAUNCH - PLUNGER_MIN_LAUNCH))
    ball.vx = 0
    this.skillShotLive = this.ballInLane
    this.emit('launch', ball.x, ball.y, 0, pull)
  }

  // —— Ball lifecycle ———————————————————————————————————————

  private newBall(): void {
    const { plunger, ballRadius } = this.table
    this.ball = {
      x: (plunger.x0 + plunger.x1) / 2,
      y: plunger.restY - ballRadius - 0.5,
      vx: 0,
      vy: 0,
    }
    this.phase = 'play'
    this.ballInLane = true
    this.ballSaveUntil = 0
    this.skillShotLive = false
    this.skillLane = Math.floor(Math.random() * 3)
    this.saucerHolding = false
    this.sensorsInside.clear()
    this.stillSince = this.time
    this.emit('newBall', this.ball.x, this.ball.y, 0, 1)
  }

  private handleDrain(): void {
    const ball = this.ball
    if (!ball) return
    this.ball = null
    if (this.time < this.ballSaveUntil) {
      this.showMessage('BALL SAVED', 'SHOOT AGAIN')
      this.emit('ballSaved', ball.x, this.table.height - 40, 0, 1, 'BALL SAVED')
      this.newBall()
      return
    }
    const award = this.bonus * BONUS_UNIT * this.multiplier
    this.addScore(award)
    this.showMessage(
      `BONUS ${award.toLocaleString()}`,
      `${this.bonus} × 1,000 × ${this.multiplier}X`,
      BONUS_PHASE_TIME,
    )
    this.emit('drain', ball.x, this.table.height - 40, award, 1)
    this.phase = 'bonus'
    this.bonusEndsAt = this.time + BONUS_PHASE_TIME
  }

  private finishBonus(): void {
    this.bonus = 0
    this.multiplierIndex = 0
    this.lanesLit = [false, false, false]
    this.dropsDown = this.dropsDown.map(() => false)
    this.standupsLit = this.standupsLit.map(() => false)
    if (this.extraBalls > 0) {
      this.extraBalls--
      this.showMessage('SHOOT AGAIN', `BALL ${this.ballNumber}`)
      this.emit('shootAgain', 0, 0, 0, 1)
      this.newBall()
      return
    }
    if (this.ballNumber < this.totalBalls) {
      this.ballNumber++
      this.showMessage(`BALL ${this.ballNumber}`, '')
      this.newBall()
      return
    }
    this.phase = 'over'
    this.display = null
    this.emit('gameOver', 0, 0, 0, 1)
  }

  // —— Helpers ——————————————————————————————————————————————

  private addScore(points: number): void {
    this.score += points
  }

  private cancelSkillShot(): void {
    this.skillShotLive = false
  }

  private showMessage(text: string, sub = '', duration = 1.6): void {
    this.display = { text, sub, until: this.time + duration }
  }

  private emit(type: PinballEventType, x: number, y: number, points: number, intensity: number, label?: string) {
    this.events.push({ type, x, y, points, intensity, label })
  }
}

function segmentNormalToward(seg: Segment, p: Vec): Vec {
  const dx = seg.b.x - seg.a.x
  const dy = seg.b.y - seg.a.y
  const len = Math.hypot(dx, dy)
  let nx = dy / len
  let ny = -dx / len
  if ((p.x - seg.a.x) * nx + (p.y - seg.a.y) * ny < 0) {
    nx = -nx
    ny = -ny
  }
  return { x: nx, y: ny }
}
