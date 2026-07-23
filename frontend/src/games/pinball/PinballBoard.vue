<script setup lang="ts">
import { ref, shallowRef, onMounted, onUnmounted, computed, watch, markRaw } from 'vue'
import type { Room, PinballGameState } from '@/types'
import {
  createPinballWorld,
  getBallPosition,
  getFlipperTransforms,
  type PinballWorld,
  type CollisionEvent,
} from './physics'
import {
  unlockAudio,
  isSoundMuted,
  setSoundMuted,
  playLaunch,
  playFlipper,
  playBumper,
  playTarget,
  playWall,
  playFlipperHit,
  playCombo,
  playDrain,
  playGameOver,
  playHighScore,
  playUiClick,
} from './sounds'

defineProps<{
  gameState: PinballGameState
  room: Room
  playerId: string
}>()

defineEmits<{
  action: [data: Record<string, unknown>]
}>()

interface ScorePopup {
  id: number
  x: number
  y: number
  text: string
  color: string
  createdAt: number
}

interface Particle {
  x: number
  y: number
  vx: number
  vy: number
  life: number
  maxLife: number
  color: string
  size: number
}

interface BumperFlash {
  x: number
  y: number
  radius: number
  color: string
  until: number
}

interface TrailPoint {
  x: number
  y: number
  until: number
}

const canvasRef = ref<HTMLCanvasElement | null>(null)
const containerRef = ref<HTMLDivElement | null>(null)
const physicsWorld = shallowRef<PinballWorld | null>(null)
const animationFrame = ref<number | null>(null)
const displayScale = ref(1)

const score = ref(0)
const ballsRemaining = ref(3)
const gameOver = ref(false)
const showLaunchHint = ref(true)
const combo = ref(0)
const lastHitTime = ref(0)
const effects = ref<ScorePopup[]>([])
const scorePulse = ref(false)
const tableFlash = ref(0)
const soundMuted = ref(isSoundMuted())
let effectId = 0
let prevCombo = 0

const particles: Particle[] = []
const bumperFlashes: BumperFlash[] = []
const ballTrail: TrailPoint[] = []
let lastBallPos: { x: number; y: number } | null = null
let animTime = 0

const highScore = computed(() => {
  const stored = localStorage.getItem('pinball_highscore')
  return stored ? parseInt(stored, 10) : 0
})

function formatScore(n: number): string {
  return n.toLocaleString()
}

function toggleSoundMute() {
  const next = !soundMuted.value
  setSoundMuted(next)
  soundMuted.value = next
  if (!next) {
    void unlockAudio()
    playUiClick()
  }
}

function spawnParticles(x: number, y: number, color: string, count: number, speed = 4) {
  for (let i = 0; i < count; i++) {
    const angle = (Math.PI * 2 * i) / count + Math.random() * 0.4
    const mag = speed * (0.4 + Math.random() * 0.8)
    particles.push({
      x,
      y,
      vx: Math.cos(angle) * mag,
      vy: Math.sin(angle) * mag,
      life: 1,
      maxLife: 0.4 + Math.random() * 0.5,
      color,
      size: 1.5 + Math.random() * 3,
    })
  }
}

function handleCollision(event: CollisionEvent) {
  const now = Date.now()

  if (event.type === 'wall') {
    playWall()
    return
  }

  if (event.points > 0 || event.type === 'flipper') {
    if (now - lastHitTime.value < 2000) {
      combo.value++
    } else {
      combo.value = 1
    }
    lastHitTime.value = now
    if (combo.value > prevCombo && combo.value > 1) {
      playCombo(combo.value)
    }
    prevCombo = combo.value
  }

  const multiplier = Math.min(combo.value, 5)
  const points = event.points * multiplier

  if (event.type === 'bumper') {
    playBumper(event.points)
    bumperFlashes.push({
      x: event.x,
      y: event.y,
      radius: 36,
      color: event.points >= 150 ? '#ffa502' : event.points >= 100 ? '#ff4757' : '#2ed573',
      until: now + 180,
    })
    spawnParticles(event.x, event.y, '#fff', 10, 5)
    spawnParticles(event.x, event.y, event.points >= 150 ? '#ffa502' : '#ff6b81', 8, 3)
    tableFlash.value = Math.min(1, tableFlash.value + 0.35)
  } else if (event.type === 'target') {
    playTarget(event.points)
    spawnParticles(event.x, event.y, '#00f5d4', 16, 6)
    spawnParticles(event.x, event.y, '#fee440', 10, 4)
    tableFlash.value = Math.min(1, tableFlash.value + 0.55)
  } else if (event.type === 'flipper') {
    playFlipperHit()
    spawnParticles(event.x, event.y, '#fff', 4, 2)
  }

  if (points > 0) {
    score.value += points
    scorePulse.value = true
    setTimeout(() => {
      scorePulse.value = false
    }, 200)

    const id = ++effectId
    effects.value.push({
      id,
      x: event.x * displayScale.value,
      y: event.y * displayScale.value,
      text: multiplier > 1 ? `+${formatScore(points)} ×${multiplier}` : `+${formatScore(points)}`,
      color: event.type === 'bumper' ? '#ff6b81' : event.type === 'target' ? '#00f5d4' : '#fff',
      createdAt: now,
    })

    setTimeout(() => {
      effects.value = effects.value.filter((e) => e.id !== id)
    }, 1000)
  }
}

function handleBallLost() {
  combo.value = 0
  prevCombo = 0
  ballTrail.length = 0
  lastBallPos = null
  playDrain()
  if (physicsWorld.value && physicsWorld.value.ballsRemaining <= 0) {
    gameOver.value = true
    const isNewHigh = score.value > highScore.value && score.value > 0
    if (isNewHigh) {
      localStorage.setItem('pinball_highscore', score.value.toString())
      setTimeout(() => playHighScore(), 350)
    } else {
      setTimeout(() => playGameOver(), 280)
    }
  } else {
    showLaunchHint.value = true
  }
  ballsRemaining.value = physicsWorld.value?.ballsRemaining ?? 0
}

function launchBall() {
  if (physicsWorld.value && !gameOver.value && !physicsWorld.value.ballInPlay) {
    void unlockAudio()
    physicsWorld.value.launchBall()
    showLaunchHint.value = false
    ballsRemaining.value = physicsWorld.value.ballsRemaining
    tableFlash.value = 0.4
    playLaunch()
    const level = physicsWorld.value.level
    spawnParticles(level.launchX, level.launchY - 40, '#fee440', 12, 5)
  }
}

function restartGame() {
  if (physicsWorld.value) {
    physicsWorld.value.cleanup()
  }
  void unlockAudio()
  physicsWorld.value = markRaw(createPinballWorld(handleCollision, handleBallLost))
  score.value = 0
  ballsRemaining.value = 3
  gameOver.value = false
  showLaunchHint.value = true
  combo.value = 0
  prevCombo = 0
  effects.value = []
  particles.length = 0
  bumperFlashes.length = 0
  ballTrail.length = 0
  lastBallPos = null
  tableFlash.value = 0
}

function handleKeyDown(e: KeyboardEvent) {
  if (!physicsWorld.value || gameOver.value) return
  if (e.repeat) return

  if (e.code === 'Space' || e.code === 'Enter') {
    e.preventDefault()
    if (!physicsWorld.value.ballInPlay) {
      launchBall()
    }
    return
  }

  if (e.code === 'KeyA' || e.code === 'ArrowLeft' || e.code === 'KeyZ') {
    e.preventDefault()
    void unlockAudio()
    physicsWorld.value.activateLeftFlipper(true)
    playFlipper()
  }
  if (e.code === 'KeyD' || e.code === 'ArrowRight' || e.code === 'Slash' || e.code === 'KeyM') {
    e.preventDefault()
    void unlockAudio()
    physicsWorld.value.activateRightFlipper(true)
    playFlipper()
  }
}

function handleKeyUp(e: KeyboardEvent) {
  if (!physicsWorld.value) return

  if (e.code === 'KeyA' || e.code === 'ArrowLeft' || e.code === 'KeyZ') {
    physicsWorld.value.activateLeftFlipper(false)
  }
  if (e.code === 'KeyD' || e.code === 'ArrowRight' || e.code === 'Slash' || e.code === 'KeyM') {
    physicsWorld.value.activateRightFlipper(false)
  }
}

function handleTouchStart(side: 'left' | 'right') {
  if (!physicsWorld.value || gameOver.value) return
  void unlockAudio()

  if (!physicsWorld.value.ballInPlay) {
    launchBall()
    return
  }

  if (side === 'left') {
    physicsWorld.value.activateLeftFlipper(true)
  } else {
    physicsWorld.value.activateRightFlipper(true)
  }
  playFlipper()
}

function handleCanvasClick() {
  if (!physicsWorld.value || gameOver.value) return
  if (!physicsWorld.value.ballInPlay) {
    launchBall()
  }
}

function handleTouchEnd(side: 'left' | 'right') {
  if (!physicsWorld.value) return

  if (side === 'left') {
    physicsWorld.value.activateLeftFlipper(false)
  } else {
    physicsWorld.value.activateRightFlipper(false)
  }
}

function updateDisplayScale() {
  if (!containerRef.value || !physicsWorld.value) return
  const container = containerRef.value
  const level = physicsWorld.value.level
  const scaleX = container.clientWidth / level.worldWidth
  const scaleY = (container.clientHeight - 120) / level.worldHeight
  displayScale.value = Math.min(scaleX, scaleY, 1.2)
}

function drawChromeRail(
  ctx: CanvasRenderingContext2D,
  x1: number,
  y1: number,
  x2: number,
  y2: number,
  width: number
) {
  ctx.save()
  ctx.lineCap = 'round'
  ctx.lineWidth = width + 4
  ctx.strokeStyle = 'rgba(0,0,0,0.45)'
  ctx.beginPath()
  ctx.moveTo(x1, y1)
  ctx.lineTo(x2, y2)
  ctx.stroke()

  const grad = ctx.createLinearGradient(x1, y1, x2, y2)
  grad.addColorStop(0, '#f8fafc')
  grad.addColorStop(0.35, '#94a3b8')
  grad.addColorStop(0.55, '#e2e8f0')
  grad.addColorStop(1, '#64748b')
  ctx.lineWidth = width
  ctx.strokeStyle = grad
  ctx.beginPath()
  ctx.moveTo(x1, y1)
  ctx.lineTo(x2, y2)
  ctx.stroke()

  ctx.lineWidth = Math.max(1, width * 0.25)
  ctx.strokeStyle = 'rgba(255,255,255,0.7)'
  ctx.beginPath()
  ctx.moveTo(x1, y1 - width * 0.15)
  ctx.lineTo(x2, y2 - width * 0.15)
  ctx.stroke()
  ctx.restore()
}

function drawNeonArc(
  ctx: CanvasRenderingContext2D,
  cx: number,
  cy: number,
  r: number,
  start: number,
  end: number,
  color: string,
  width: number
) {
  ctx.save()
  ctx.beginPath()
  ctx.arc(cx, cy, r, start, end)
  ctx.strokeStyle = color
  ctx.lineWidth = width
  ctx.shadowColor = color
  ctx.shadowBlur = 18
  ctx.lineCap = 'round'
  ctx.stroke()
  ctx.shadowBlur = 0
  ctx.lineWidth = width * 0.35
  ctx.strokeStyle = '#fff'
  ctx.globalAlpha = 0.55
  ctx.stroke()
  ctx.restore()
}

function drawBall(
  ctx: CanvasRenderingContext2D,
  x: number,
  y: number,
  r: number,
  glow = true
) {
  if (glow) {
    ctx.save()
    ctx.beginPath()
    ctx.arc(x, y, r * 2.2, 0, Math.PI * 2)
    const aura = ctx.createRadialGradient(x, y, r * 0.2, x, y, r * 2.2)
    aura.addColorStop(0, 'rgba(255, 250, 220, 0.45)')
    aura.addColorStop(0.5, 'rgba(255, 200, 80, 0.12)')
    aura.addColorStop(1, 'rgba(255, 200, 80, 0)')
    ctx.fillStyle = aura
    ctx.fill()
    ctx.restore()
  }

  const ballGrad = ctx.createRadialGradient(x - r * 0.35, y - r * 0.4, r * 0.05, x, y, r)
  ballGrad.addColorStop(0, '#ffffff')
  ballGrad.addColorStop(0.25, '#f1f5f9')
  ballGrad.addColorStop(0.7, '#94a3b8')
  ballGrad.addColorStop(1, '#475569')

  ctx.beginPath()
  ctx.arc(x, y, r, 0, Math.PI * 2)
  ctx.fillStyle = ballGrad
  ctx.shadowColor = 'rgba(255, 255, 255, 0.8)'
  ctx.shadowBlur = 12
  ctx.fill()
  ctx.shadowBlur = 0

  ctx.beginPath()
  ctx.arc(x - r * 0.3, y - r * 0.35, r * 0.22, 0, Math.PI * 2)
  ctx.fillStyle = 'rgba(255,255,255,0.85)'
  ctx.fill()
}

function updateParticles(dt: number) {
  for (let i = particles.length - 1; i >= 0; i--) {
    const p = particles[i]
    p.x += p.vx
    p.y += p.vy
    p.vy += 0.12
    p.vx *= 0.98
    p.life -= dt / p.maxLife
    if (p.life <= 0) particles.splice(i, 1)
  }
}

function render() {
  const canvas = canvasRef.value
  const world = physicsWorld.value
  if (!canvas || !world) return

  const ctx = canvas.getContext('2d')
  if (!ctx) return

  const level = world.level
  const scale = displayScale.value
  const now = Date.now()
  animTime += 1 / 60
  const dt = 1 / 60

  tableFlash.value = Math.max(0, tableFlash.value - dt * 2.2)
  updateParticles(dt)

  canvas.width = level.worldWidth * scale
  canvas.height = level.worldHeight * scale

  ctx.save()
  ctx.scale(scale, scale)

  // Felt / playfield base
  const felt = ctx.createLinearGradient(0, 0, 0, level.worldHeight)
  felt.addColorStop(0, '#1a0a14')
  felt.addColorStop(0.35, '#120818')
  felt.addColorStop(0.7, '#0c0612')
  felt.addColorStop(1, '#08040c')
  ctx.fillStyle = felt
  ctx.fillRect(0, 0, level.worldWidth, level.worldHeight)

  // Soft vignette
  const vignette = ctx.createRadialGradient(
    level.worldWidth * 0.45,
    level.worldHeight * 0.35,
    40,
    level.worldWidth * 0.5,
    level.worldHeight * 0.5,
    level.worldHeight * 0.75
  )
  vignette.addColorStop(0, 'rgba(255, 40, 80, 0.08)')
  vignette.addColorStop(0.55, 'rgba(0, 200, 255, 0.03)')
  vignette.addColorStop(1, 'rgba(0, 0, 0, 0.55)')
  ctx.fillStyle = vignette
  ctx.fillRect(0, 0, level.worldWidth, level.worldHeight)

  // Decorative neon circuit lines
  ctx.save()
  ctx.globalAlpha = 0.18 + Math.sin(animTime * 2) * 0.04
  ctx.strokeStyle = '#00f5d4'
  ctx.lineWidth = 1.5
  ctx.setLineDash([6, 10])
  ctx.beginPath()
  ctx.moveTo(30, 80)
  ctx.quadraticCurveTo(200, 40, 320, 90)
  ctx.stroke()
  ctx.strokeStyle = '#ff006e'
  ctx.beginPath()
  ctx.moveTo(40, 260)
  ctx.quadraticCurveTo(180, 220, 300, 280)
  ctx.stroke()
  ctx.setLineDash([])
  ctx.restore()

  // Top arch neon
  drawNeonArc(ctx, 200, 40, 160, Math.PI * 0.12, Math.PI * 0.88, '#ff006e', 3)
  drawNeonArc(ctx, 200, 40, 145, Math.PI * 0.18, Math.PI * 0.82, '#00f5d4', 2)

  // Pulsing light bulbs along top
  for (let i = 0; i < 7; i++) {
    const lx = 55 + i * 48
    const ly = 28
    const pulse = 0.45 + 0.55 * Math.sin(animTime * 4 + i * 0.7)
    const color = i % 2 === 0 ? '#fee440' : '#00f5d4'
    ctx.beginPath()
    ctx.arc(lx, ly, 4.5, 0, Math.PI * 2)
    ctx.fillStyle = color
    ctx.shadowColor = color
    ctx.shadowBlur = 8 + pulse * 14
    ctx.globalAlpha = 0.55 + pulse * 0.45
    ctx.fill()
    ctx.globalAlpha = 1
    ctx.shadowBlur = 0
  }

  // Side neon rails
  drawNeonArc(ctx, 15, 320, 40, -Math.PI * 0.4, Math.PI * 0.5, '#8338ec', 2.5)
  drawNeonArc(ctx, 385, 200, 35, Math.PI * 0.5, Math.PI * 1.4, '#ffbe0b', 2.5)

  // Chrome outer rail
  drawChromeRail(ctx, 12, 20, 12, 660, 5)
  drawChromeRail(ctx, 388, 20, 388, 520, 5)
  drawChromeRail(ctx, 12, 20, 388, 20, 5)

  // Outlane wedges with neon edge
  const drawWedge = (pts: [number, number][], fill: string, edge: string) => {
    ctx.beginPath()
    ctx.moveTo(pts[0][0], pts[0][1])
    for (let i = 1; i < pts.length; i++) ctx.lineTo(pts[i][0], pts[i][1])
    ctx.closePath()
    ctx.fillStyle = fill
    ctx.fill()
    ctx.strokeStyle = edge
    ctx.lineWidth = 2
    ctx.shadowColor = edge
    ctx.shadowBlur = 10
    ctx.stroke()
    ctx.shadowBlur = 0
  }
  drawWedge(
    [
      [12, 520],
      [125, 595],
      [12, 645],
    ],
    'rgba(40, 10, 30, 0.95)',
    '#ff006e'
  )
  drawWedge(
    [
      [340, 520],
      [255, 595],
      [340, 635],
    ],
    'rgba(10, 30, 40, 0.95)',
    '#00f5d4'
  )

  // Shooter lane
  const laneGrad = ctx.createLinearGradient(350, 280, 400, 700)
  laneGrad.addColorStop(0, 'rgba(255, 190, 11, 0.15)')
  laneGrad.addColorStop(1, 'rgba(255, 0, 110, 0.08)')
  ctx.fillStyle = laneGrad
  ctx.fillRect(353, 280, 35, 400)

  ctx.fillStyle = '#1e293b'
  ctx.fillRect(347, 320, 6, 380)
  ctx.shadowColor = '#fee440'
  ctx.shadowBlur = 8
  ctx.fillStyle = '#fee440'
  ctx.globalAlpha = 0.7 + Math.sin(animTime * 5) * 0.3
  ctx.fillRect(348, 320, 4, 380)
  ctx.globalAlpha = 1
  ctx.shadowBlur = 0

  // Lane roof
  ctx.fillStyle = '#334155'
  ctx.fillRect(353, 266, 44, 8)
  ctx.fillStyle = '#00f5d4'
  ctx.shadowColor = '#00f5d4'
  ctx.shadowBlur = 10
  ctx.fillRect(353, 268, 44, 3)
  ctx.shadowBlur = 0

  // Lane chevrons
  ctx.fillStyle = 'rgba(254, 228, 64, 0.35)'
  for (let y = 360; y < 620; y += 36) {
    ctx.beginPath()
    ctx.moveTo(365, y)
    ctx.lineTo(372, y + 10)
    ctx.lineTo(379, y)
    ctx.closePath()
    ctx.fill()
  }

  // Idle ball in lane
  if (!world.ballInPlay && !gameOver.value && world.ballsRemaining > 0) {
    drawBall(ctx, level.launchX, level.launchY, level.ballRadius)
  }

  // Bumper flashes (expanding rings)
  for (let i = bumperFlashes.length - 1; i >= 0; i--) {
    const flash = bumperFlashes[i]
    if (now > flash.until) {
      bumperFlashes.splice(i, 1)
      continue
    }
    const t = 1 - (flash.until - now) / 180
    ctx.beginPath()
    ctx.arc(flash.x, flash.y, flash.radius * (0.8 + t * 0.8), 0, Math.PI * 2)
    ctx.strokeStyle = flash.color
    ctx.globalAlpha = (1 - t) * 0.9
    ctx.lineWidth = 4
    ctx.shadowColor = flash.color
    ctx.shadowBlur = 20
    ctx.stroke()
    ctx.globalAlpha = 1
    ctx.shadowBlur = 0
  }

  // Bumpers
  for (const [body, spec] of world.bumperBodies) {
    const pos = body.getPosition()
    const flash = bumperFlashes.find(
      (f) => Math.hypot(f.x - pos.x, f.y - pos.y) < 8
    )
    const pulse = flash ? 1.15 : 1 + Math.sin(animTime * 3 + pos.x) * 0.03
    const r = spec.radius * pulse

    // Outer glow ring
    ctx.beginPath()
    ctx.arc(pos.x, pos.y, r + 8, 0, Math.PI * 2)
    const glow = ctx.createRadialGradient(pos.x, pos.y, r * 0.4, pos.x, pos.y, r + 10)
    glow.addColorStop(0, flash ? `${spec.color}aa` : `${spec.color}33`)
    glow.addColorStop(1, 'transparent')
    ctx.fillStyle = glow
    ctx.fill()

    const bumperGrad = ctx.createRadialGradient(
      pos.x - r * 0.25,
      pos.y - r * 0.3,
      r * 0.1,
      pos.x,
      pos.y,
      r
    )
    bumperGrad.addColorStop(0, '#fff')
    bumperGrad.addColorStop(0.2, spec.color)
    bumperGrad.addColorStop(0.75, spec.color)
    bumperGrad.addColorStop(1, '#1a1a1a')

    ctx.beginPath()
    ctx.arc(pos.x, pos.y, r, 0, Math.PI * 2)
    ctx.fillStyle = bumperGrad
    ctx.shadowColor = spec.color
    ctx.shadowBlur = flash ? 28 : 14
    ctx.fill()
    ctx.shadowBlur = 0

    ctx.beginPath()
    ctx.arc(pos.x, pos.y, r, 0, Math.PI * 2)
    ctx.strokeStyle = '#fff'
    ctx.lineWidth = 2.5
    ctx.stroke()

    // Cap
    ctx.beginPath()
    ctx.arc(pos.x, pos.y, r * 0.35, 0, Math.PI * 2)
    ctx.fillStyle = flash ? '#fff' : 'rgba(255,255,255,0.25)'
    ctx.fill()
  }

  // Targets
  for (const [body, spec] of world.targetBodies) {
    if (world.hitTargets.has(spec.id)) continue

    const pos = body.getPosition()
    const blink = 0.65 + 0.35 * Math.sin(animTime * 6 + pos.x * 0.05)
    ctx.save()
    ctx.translate(pos.x, pos.y)

    ctx.shadowColor = spec.color
    ctx.shadowBlur = 16 * blink
    ctx.fillStyle = spec.color
    ctx.globalAlpha = 0.85 + blink * 0.15
    ctx.fillRect(-spec.width / 2, -spec.height / 2, spec.width, spec.height)

    ctx.strokeStyle = '#fff'
    ctx.lineWidth = 2
    ctx.globalAlpha = 1
    ctx.strokeRect(-spec.width / 2, -spec.height / 2, spec.width, spec.height)

    // Inner highlight stripe
    ctx.fillStyle = 'rgba(255,255,255,0.35)'
    ctx.fillRect(-spec.width / 2 + 2, -spec.height / 2 + 2, spec.width - 4, Math.max(2, spec.height * 0.3))
    ctx.restore()
  }

  // Hit targets — dim ghost marks
  for (const [body, spec] of world.targetBodies) {
    if (!world.hitTargets.has(spec.id)) continue
    const pos = body.getPosition()
    ctx.save()
    ctx.translate(pos.x, pos.y)
    ctx.globalAlpha = 0.2
    ctx.fillStyle = '#64748b'
    ctx.fillRect(-spec.width / 2, -spec.height / 2, spec.width, spec.height)
    ctx.restore()
  }

  // Flippers
  const flippers = getFlipperTransforms(world)

  const drawFlipper = (
    x: number,
    y: number,
    angle: number,
    colorA: string,
    colorB: string,
    mirrored: boolean
  ) => {
    ctx.save()
    ctx.translate(x, y)
    ctx.rotate(angle)

    ctx.shadowColor = colorA
    ctx.shadowBlur = 16

    const grad = ctx.createLinearGradient(
      -level.flipperLength / 2,
      0,
      level.flipperLength / 2,
      0
    )
    grad.addColorStop(0, colorA)
    grad.addColorStop(0.5, '#fff')
    grad.addColorStop(1, colorB)
    ctx.fillStyle = grad

    ctx.beginPath()
    if (!mirrored) {
      ctx.moveTo(-level.flipperLength / 2, -level.flipperWidth / 2)
      ctx.lineTo(level.flipperLength / 2, -level.flipperWidth / 3)
      ctx.lineTo(level.flipperLength / 2, level.flipperWidth / 3)
      ctx.lineTo(-level.flipperLength / 2, level.flipperWidth / 2)
    } else {
      ctx.moveTo(level.flipperLength / 2, -level.flipperWidth / 2)
      ctx.lineTo(-level.flipperLength / 2, -level.flipperWidth / 3)
      ctx.lineTo(-level.flipperLength / 2, level.flipperWidth / 3)
      ctx.lineTo(level.flipperLength / 2, level.flipperWidth / 2)
    }
    ctx.closePath()
    ctx.fill()

    ctx.shadowBlur = 0
    ctx.strokeStyle = '#fff'
    ctx.lineWidth = 2
    ctx.stroke()

    // Pivot cap
    ctx.beginPath()
    ctx.arc(mirrored ? level.flipperLength / 2 - 8 : -level.flipperLength / 2 + 8, 0, 6, 0, Math.PI * 2)
    ctx.fillStyle = '#e2e8f0'
    ctx.fill()
    ctx.strokeStyle = '#94a3b8'
    ctx.lineWidth = 1.5
    ctx.stroke()

    ctx.restore()
  }

  drawFlipper(flippers.left.x, flippers.left.y, flippers.left.angle, '#ff006e', '#ff6b6b', false)
  drawFlipper(flippers.right.x, flippers.right.y, flippers.right.angle, '#00f5d4', '#4ecdc4', true)

  // Particles
  for (const p of particles) {
    ctx.beginPath()
    ctx.arc(p.x, p.y, p.size * p.life, 0, Math.PI * 2)
    ctx.fillStyle = p.color
    ctx.globalAlpha = Math.max(0, p.life)
    ctx.shadowColor = p.color
    ctx.shadowBlur = 8
    ctx.fill()
  }
  ctx.globalAlpha = 1
  ctx.shadowBlur = 0

  // Ball trail + ball
  const ballPos = getBallPosition(world)
  if (ballPos) {
    if (
      lastBallPos &&
      Math.hypot(ballPos.x - lastBallPos.x, ballPos.y - lastBallPos.y) > 2
    ) {
      ballTrail.push({ x: ballPos.x, y: ballPos.y, until: now + 140 })
    }
    lastBallPos = { ...ballPos }

    for (let i = ballTrail.length - 1; i >= 0; i--) {
      const t = ballTrail[i]
      if (now > t.until) {
        ballTrail.splice(i, 1)
        continue
      }
      const life = (t.until - now) / 140
      ctx.beginPath()
      ctx.arc(t.x, t.y, level.ballRadius * (0.35 + life * 0.4), 0, Math.PI * 2)
      ctx.fillStyle = `rgba(254, 228, 64, ${life * 0.45})`
      ctx.fill()
    }

    drawBall(ctx, ballPos.x, ballPos.y, level.ballRadius)
  } else {
    lastBallPos = null
    ballTrail.length = 0
  }

  // Hit flash overlay
  if (tableFlash.value > 0) {
    ctx.fillStyle = `rgba(255, 220, 120, ${tableFlash.value * 0.18})`
    ctx.fillRect(0, 0, level.worldWidth, level.worldHeight)
  }

  // Inner bezel
  ctx.strokeStyle = 'rgba(255,255,255,0.12)'
  ctx.lineWidth = 2
  ctx.strokeRect(8, 8, level.worldWidth - 16, level.worldHeight - 16)

  ctx.restore()
}

function gameLoop() {
  if (physicsWorld.value && !gameOver.value) {
    physicsWorld.value.step()
  }
  render()
  animationFrame.value = requestAnimationFrame(gameLoop)
}

onMounted(() => {
  physicsWorld.value = markRaw(createPinballWorld(handleCollision, handleBallLost))
  updateDisplayScale()

  window.addEventListener('keydown', handleKeyDown)
  window.addEventListener('keyup', handleKeyUp)
  window.addEventListener('resize', updateDisplayScale)
  window.addEventListener('pointerdown', unlockAudio, { once: true })

  gameLoop()
})

onUnmounted(() => {
  if (animationFrame.value) {
    cancelAnimationFrame(animationFrame.value)
  }
  if (physicsWorld.value) {
    physicsWorld.value.cleanup()
  }
  window.removeEventListener('keydown', handleKeyDown)
  window.removeEventListener('keyup', handleKeyUp)
  window.removeEventListener('resize', updateDisplayScale)
})

watch(displayScale, () => {
  render()
})
</script>

<template>
  <div ref="containerRef" class="pinball-container">
    <div class="cabinet-glow" aria-hidden="true" />

    <div class="pinball-hud">
      <div class="hud-section">
        <span class="hud-label">Score</span>
        <span class="hud-value score" :class="{ pulse: scorePulse }">{{ formatScore(score) }}</span>
      </div>
      <div class="hud-brand">
        <span class="brand-mark">NEON</span>
        <span class="brand-name">PINBALL</span>
      </div>
      <div class="hud-section">
        <span class="hud-label">High</span>
        <span class="hud-value high">{{ formatScore(highScore) }}</span>
      </div>
      <div class="hud-section balls">
        <span class="hud-label">Balls</span>
        <div class="ball-indicators">
          <span
            v-for="i in 3"
            :key="i"
            class="ball-indicator"
            :class="{ active: i <= ballsRemaining }"
          />
        </div>
      </div>
      <button
        type="button"
        class="mute-btn"
        :aria-label="soundMuted ? 'Unmute sound' : 'Mute sound'"
        :title="soundMuted ? 'Unmute' : 'Mute'"
        @click="toggleSoundMute"
      >
        {{ soundMuted ? '🔇' : '🔊' }}
      </button>
      <Transition name="combo">
        <div v-if="combo > 1" class="combo-display">
          <span class="combo-mult">{{ combo }}×</span>
          <span class="combo-label">COMBO</span>
        </div>
      </Transition>
    </div>

    <div class="game-area" @click="handleCanvasClick">
      <div class="canvas-frame">
        <canvas ref="canvasRef" class="pinball-canvas" />
        <div class="frame-shine" aria-hidden="true" />
      </div>

      <TransitionGroup name="effect">
        <div
          v-for="effect in effects"
          :key="effect.id"
          class="score-effect"
          :style="{
            left: `${effect.x}px`,
            top: `${effect.y}px`,
            color: effect.color,
          }"
        >
          {{ effect.text }}
        </div>
      </TransitionGroup>

      <div
        v-if="showLaunchHint && !gameOver && ballsRemaining > 0"
        class="launch-hint"
      >
        <span class="hint-text">Press SPACE to launch</span>
        <span class="hint-subtext">or tap / click the table</span>
      </div>

      <div v-if="gameOver" class="game-over-overlay">
        <div class="game-over-content">
          <p class="over-eyebrow">Cabinet locked</p>
          <h2>GAME OVER</h2>
          <p class="final-score">{{ formatScore(score) }}</p>
          <p v-if="score >= highScore && score > 0" class="new-highscore">NEW HIGH SCORE</p>
          <button class="restart-btn" @click="restartGame">Play Again</button>
        </div>
      </div>
    </div>

    <div class="touch-controls">
      <button
        class="touch-flipper left"
        @touchstart.prevent="handleTouchStart('left')"
        @touchend.prevent="handleTouchEnd('left')"
        @mousedown.prevent="handleTouchStart('left')"
        @mouseup.prevent="handleTouchEnd('left')"
        @mouseleave="handleTouchEnd('left')"
      >
        <span class="flipper-label">LEFT</span>
        <span class="flipper-key">A / ←</span>
      </button>
      <button
        class="touch-flipper right"
        @touchstart.prevent="handleTouchStart('right')"
        @touchend.prevent="handleTouchEnd('right')"
        @mousedown.prevent="handleTouchStart('right')"
        @mouseup.prevent="handleTouchEnd('right')"
        @mouseleave="handleTouchEnd('right')"
      >
        <span class="flipper-label">RIGHT</span>
        <span class="flipper-key">D / →</span>
      </button>
    </div>
  </div>
</template>

<style scoped>
.pinball-container {
  --neon-pink: #ff006e;
  --neon-cyan: #00f5d4;
  --neon-gold: #fee440;
  --cabinet: #0a0610;

  position: relative;
  display: flex;
  flex-direction: column;
  align-items: center;
  height: 100%;
  width: 100%;
  background:
    radial-gradient(ellipse 80% 50% at 50% 0%, rgba(255, 0, 110, 0.18), transparent 55%),
    radial-gradient(ellipse 60% 40% at 80% 100%, rgba(0, 245, 212, 0.1), transparent 50%),
    linear-gradient(180deg, #140810 0%, var(--cabinet) 40%, #050308 100%);
  overflow: hidden;
  user-select: none;
  font-family: 'Outfit', 'DM Sans', system-ui, sans-serif;
}

.cabinet-glow {
  pointer-events: none;
  position: absolute;
  inset: 0;
  background:
    repeating-linear-gradient(
      0deg,
      transparent,
      transparent 2px,
      rgba(255, 255, 255, 0.015) 2px,
      rgba(255, 255, 255, 0.015) 4px
    );
  opacity: 0.5;
}

.pinball-hud {
  position: relative;
  z-index: 2;
  display: flex;
  justify-content: center;
  align-items: center;
  gap: 1.75rem;
  padding: 0.85rem 1.5rem 0.6rem;
  width: 100%;
  flex-shrink: 0;
}

.hud-section {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 0.15rem;
  min-width: 4.5rem;
}

.hud-label {
  font-size: 0.62rem;
  font-weight: 700;
  letter-spacing: 0.18em;
  color: rgba(255, 255, 255, 0.45);
  text-transform: uppercase;
}

.hud-value {
  font-size: 1.45rem;
  font-weight: 800;
  letter-spacing: 0.04em;
  color: #fff;
  font-variant-numeric: tabular-nums;
}

.hud-value.score {
  color: var(--neon-gold);
  text-shadow:
    0 0 12px rgba(254, 228, 64, 0.65),
    0 0 28px rgba(254, 228, 64, 0.35);
  transition: transform 0.15s ease;
}

.hud-value.score.pulse {
  transform: scale(1.12);
}

.hud-value.high {
  color: var(--neon-cyan);
  text-shadow: 0 0 10px rgba(0, 245, 212, 0.45);
}

.hud-brand {
  display: flex;
  flex-direction: column;
  align-items: center;
  line-height: 1;
  padding: 0 0.5rem;
}

.brand-mark {
  font-size: 0.55rem;
  font-weight: 700;
  letter-spacing: 0.35em;
  color: var(--neon-pink);
  text-shadow: 0 0 10px rgba(255, 0, 110, 0.8);
}

.brand-name {
  font-size: 1.15rem;
  font-weight: 800;
  letter-spacing: 0.22em;
  color: #fff;
  text-shadow:
    0 0 16px rgba(255, 0, 110, 0.5),
    0 0 32px rgba(0, 245, 212, 0.25);
}

.ball-indicators {
  display: flex;
  gap: 0.45rem;
  margin-top: 0.15rem;
}

.ball-indicator {
  width: 15px;
  height: 15px;
  border-radius: 50%;
  background: #1e1a24;
  border: 2px solid #3a3344;
  transition: all 0.3s ease;
}

.ball-indicator.active {
  background: radial-gradient(circle at 30% 28%, #fff 0%, #e2e8f0 35%, #94a3b8 100%);
  border-color: #fff;
  box-shadow:
    0 0 10px rgba(255, 255, 255, 0.7),
    0 0 20px rgba(254, 228, 64, 0.35);
}

.mute-btn {
  position: absolute;
  left: 1rem;
  top: 50%;
  transform: translateY(-50%);
  width: 2.25rem;
  height: 2.25rem;
  border: 1px solid rgba(255, 255, 255, 0.18);
  border-radius: 999px;
  background: rgba(10, 6, 16, 0.65);
  color: #fff;
  font-size: 1rem;
  cursor: pointer;
  display: grid;
  place-items: center;
  backdrop-filter: blur(6px);
  transition: background 0.15s, border-color 0.15s, transform 0.1s;
}

.mute-btn:hover {
  background: rgba(255, 0, 110, 0.25);
  border-color: rgba(255, 0, 110, 0.5);
}

.mute-btn:active {
  transform: translateY(-50%) scale(0.94);
}

.combo-display {
  position: absolute;
  right: 1.25rem;
  top: 50%;
  transform: translateY(-50%);
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  animation: comboPulse 0.45s ease-in-out infinite alternate;
}

.combo-mult {
  font-size: 1.6rem;
  font-weight: 800;
  color: var(--neon-pink);
  text-shadow: 0 0 14px rgba(255, 0, 110, 0.85);
  line-height: 1;
}

.combo-label {
  font-size: 0.65rem;
  font-weight: 700;
  letter-spacing: 0.2em;
  color: #fff;
}

.combo-enter-active,
.combo-leave-active {
  transition: opacity 0.2s, transform 0.2s;
}
.combo-enter-from,
.combo-leave-to {
  opacity: 0;
  transform: translateY(-50%) translateX(12px);
}

@keyframes comboPulse {
  from { filter: brightness(1); }
  to { filter: brightness(1.25); }
}

.game-area {
  position: relative;
  z-index: 1;
  flex: 1;
  display: flex;
  justify-content: center;
  align-items: center;
  min-height: 0;
  width: 100%;
}

.canvas-frame {
  position: relative;
  border-radius: 16px;
  padding: 3px;
  background: linear-gradient(
    145deg,
    #f8fafc 0%,
    #94a3b8 25%,
    #475569 50%,
    #e2e8f0 75%,
    #64748b 100%
  );
  box-shadow:
    0 0 0 1px rgba(0, 0, 0, 0.5),
    0 12px 40px rgba(0, 0, 0, 0.55),
    0 0 60px rgba(255, 0, 110, 0.15),
    0 0 80px rgba(0, 245, 212, 0.08);
}

.pinball-canvas {
  display: block;
  border-radius: 13px;
  background: #0a0610;
}

.frame-shine {
  pointer-events: none;
  position: absolute;
  inset: 0;
  border-radius: 16px;
  background: linear-gradient(
    125deg,
    rgba(255, 255, 255, 0.35) 0%,
    transparent 28%,
    transparent 72%,
    rgba(255, 255, 255, 0.12) 100%
  );
}

.score-effect {
  position: absolute;
  font-size: 1.2rem;
  font-weight: 800;
  pointer-events: none;
  text-shadow:
    0 0 12px currentColor,
    0 2px 4px rgba(0, 0, 0, 0.8);
  transform: translate(-50%, -50%);
  letter-spacing: 0.04em;
  z-index: 5;
}

.effect-enter-active {
  animation: scorePopup 1s ease-out forwards;
}

@keyframes scorePopup {
  0% {
    opacity: 1;
    transform: translate(-50%, -50%) scale(0.4);
  }
  30% {
    opacity: 1;
    transform: translate(-50%, -90%) scale(1.25);
  }
  100% {
    opacity: 0;
    transform: translate(-50%, -160%) scale(1);
  }
}

.launch-hint {
  position: absolute;
  bottom: 28%;
  left: 50%;
  transform: translateX(-50%);
  text-align: center;
  z-index: 4;
  padding: 0.85rem 1.4rem;
  border-radius: 12px;
  background: rgba(10, 6, 16, 0.72);
  border: 1px solid rgba(254, 228, 64, 0.35);
  box-shadow: 0 0 24px rgba(254, 228, 64, 0.2);
  animation: hintBounce 1.2s ease-in-out infinite;
  backdrop-filter: blur(6px);
}

.hint-text {
  display: block;
  font-size: 1.15rem;
  font-weight: 700;
  color: var(--neon-gold);
  text-shadow: 0 0 12px rgba(254, 228, 64, 0.6);
  letter-spacing: 0.04em;
}

.hint-subtext {
  display: block;
  font-size: 0.75rem;
  color: rgba(255, 255, 255, 0.55);
  margin-top: 0.25rem;
}

@keyframes hintBounce {
  0%, 100% { transform: translateX(-50%) translateY(0); }
  50% { transform: translateX(-50%) translateY(-8px); }
}

.game-over-overlay {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(5, 2, 8, 0.82);
  backdrop-filter: blur(8px);
  border-radius: 16px;
  animation: fadeIn 0.35s ease-out;
  z-index: 6;
}

@keyframes fadeIn {
  from { opacity: 0; }
  to { opacity: 1; }
}

.game-over-content {
  text-align: center;
  padding: 2rem;
}

.over-eyebrow {
  margin: 0 0 0.4rem;
  font-size: 0.7rem;
  font-weight: 700;
  letter-spacing: 0.28em;
  color: var(--neon-cyan);
  text-transform: uppercase;
}

.game-over-content h2 {
  font-size: 2.6rem;
  font-weight: 800;
  color: var(--neon-pink);
  margin: 0 0 0.75rem;
  letter-spacing: 0.08em;
  text-shadow:
    0 0 24px rgba(255, 0, 110, 0.7),
    0 0 48px rgba(255, 0, 110, 0.35);
}

.final-score {
  font-size: 2rem;
  font-weight: 800;
  color: var(--neon-gold);
  margin: 0 0 0.5rem;
  text-shadow: 0 0 16px rgba(254, 228, 64, 0.5);
  font-variant-numeric: tabular-nums;
}

.new-highscore {
  font-size: 1rem;
  font-weight: 700;
  letter-spacing: 0.18em;
  color: var(--neon-cyan);
  margin: 0 0 1.5rem;
  animation: comboPulse 0.5s ease-in-out infinite alternate;
}

.restart-btn {
  padding: 0.85rem 2.2rem;
  font-size: 1.05rem;
  font-weight: 700;
  font-family: inherit;
  letter-spacing: 0.06em;
  color: #0a0610;
  background: linear-gradient(135deg, var(--neon-gold), #f59e0b);
  border: none;
  border-radius: 999px;
  cursor: pointer;
  box-shadow: 0 0 24px rgba(254, 228, 64, 0.4);
  transition: transform 0.2s, box-shadow 0.2s;
}

.restart-btn:hover {
  transform: translateY(-2px) scale(1.03);
  box-shadow: 0 0 36px rgba(254, 228, 64, 0.55);
}

.touch-controls {
  position: relative;
  z-index: 2;
  display: flex;
  justify-content: space-between;
  width: 100%;
  padding: 0.65rem 1rem 1rem;
  gap: 1rem;
  flex-shrink: 0;
}

.touch-flipper {
  flex: 1;
  max-width: 200px;
  padding: 1rem;
  border: 1px solid rgba(255, 255, 255, 0.15);
  border-radius: 14px;
  font-weight: 700;
  font-family: inherit;
  cursor: pointer;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 0.2rem;
  transition: transform 0.1s, box-shadow 0.1s;
  touch-action: manipulation;
}

.touch-flipper.left {
  background: linear-gradient(145deg, #ff006e, #c1121f);
  box-shadow: 0 0 20px rgba(255, 0, 110, 0.35);
}

.touch-flipper.right {
  background: linear-gradient(145deg, #00f5d4, #0891b2);
  box-shadow: 0 0 20px rgba(0, 245, 212, 0.35);
}

.touch-flipper:active {
  transform: scale(0.96);
  box-shadow: inset 0 2px 10px rgba(0, 0, 0, 0.35);
}

.flipper-label {
  font-size: 1rem;
  color: #fff;
  letter-spacing: 0.08em;
}

.flipper-key {
  font-size: 0.7rem;
  color: rgba(255, 255, 255, 0.7);
}

@media (max-width: 480px) {
  .pinball-hud {
    gap: 0.75rem;
    padding: 0.55rem 0.75rem 0.4rem;
  }

  .hud-brand {
    display: none;
  }

  .hud-value {
    font-size: 1.15rem;
  }

  .combo-display {
    right: 0.5rem;
  }

  .combo-mult {
    font-size: 1.25rem;
  }

  .hint-text {
    font-size: 1rem;
  }

  .touch-flipper {
    padding: 0.75rem;
  }
}
</style>
