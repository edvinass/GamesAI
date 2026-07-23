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

/** Space Cadet–style ball counter (Ball 1 / 2 / 3). */
const currentBallNumber = computed(() => Math.min(3, Math.max(1, 4 - ballsRemaining.value)))

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

  // Allow launching from the flipper buttons, but still flip once the ball is out.
  if (!physicsWorld.value.ballInPlay) {
    launchBall()
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
  const hud = container.querySelector('.pinball-hud') as HTMLElement | null
  const controls = container.querySelector('.touch-controls') as HTMLElement | null
  const reservedY =
    (hud?.offsetHeight ?? 64) + (controls?.offsetHeight ?? 72) + 16
  const scaleX = container.clientWidth / level.worldWidth
  const scaleY = Math.max(100, container.clientHeight - reservedY) / level.worldHeight
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

function drawChromeCurve(
  ctx: CanvasRenderingContext2D,
  points: [number, number][],
  width: number
) {
  if (points.length < 2) return
  ctx.save()
  ctx.lineCap = 'round'
  ctx.lineJoin = 'round'
  ctx.lineWidth = width + 3
  ctx.strokeStyle = 'rgba(0,0,0,0.4)'
  ctx.beginPath()
  ctx.moveTo(points[0][0], points[0][1])
  for (let i = 1; i < points.length; i++) ctx.lineTo(points[i][0], points[i][1])
  ctx.stroke()

  const last = points[points.length - 1]
  const g = ctx.createLinearGradient(points[0][0], points[0][1], last[0], last[1])
  g.addColorStop(0, '#e8eef5')
  g.addColorStop(0.4, '#8a97a8')
  g.addColorStop(0.7, '#d5dde8')
  g.addColorStop(1, '#6b7788')
  ctx.lineWidth = width
  ctx.strokeStyle = g
  ctx.beginPath()
  ctx.moveTo(points[0][0], points[0][1])
  for (let i = 1; i < points.length; i++) ctx.lineTo(points[i][0], points[i][1])
  ctx.stroke()
  ctx.restore()
}

function drawLightningCracks(
  ctx: CanvasRenderingContext2D,
  t: number
) {
  const cracks: [number, number][][] = [
    [[40, 200], [90, 250], [70, 310], [130, 360], [110, 420], [160, 470]],
    [[220, 180], [250, 240], [230, 300], [270, 360], [255, 430]],
    [[300, 220], [320, 280], [300, 340], [330, 400]],
    [[80, 120], [120, 150], [100, 190]],
  ]
  ctx.save()
  ctx.lineCap = 'round'
  ctx.lineJoin = 'round'
  for (let i = 0; i < cracks.length; i++) {
    const pulse = 0.3 + 0.28 * Math.sin(t * 1.8 + i)
    ctx.strokeStyle = `rgba(150, 80, 220, ${pulse})`
    ctx.lineWidth = 2.4
    ctx.shadowColor = '#a855f7'
    ctx.shadowBlur = 10
    ctx.beginPath()
    const pts = cracks[i]
    ctx.moveTo(pts[0][0], pts[0][1])
    for (let j = 1; j < pts.length; j++) ctx.lineTo(pts[j][0], pts[j][1])
    ctx.stroke()
  }
  ctx.restore()
}

function drawStarfield(ctx: CanvasRenderingContext2D, w: number, h: number, t: number) {
  ctx.save()
  for (let i = 0; i < 48; i++) {
    const x = (i * 73) % w
    const y = ((i * 131) % (h * 0.85)) + 20
    const twinkle = 0.25 + 0.75 * (0.5 + 0.5 * Math.sin(t * 3 + i * 1.7))
    ctx.globalAlpha = twinkle * 0.7
    ctx.fillStyle = i % 5 === 0 ? '#a5d8ff' : '#ffffff'
    const s = i % 7 === 0 ? 1.8 : 1.1
    ctx.fillRect(x, y, s, s)
  }
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

  // —— Space Cadet playfield ——
  const W = level.worldWidth
  const H = level.worldHeight

  const felt = ctx.createLinearGradient(0, 0, 0, H)
  felt.addColorStop(0, '#0a1a3a')
  felt.addColorStop(0.25, '#0c2048')
  felt.addColorStop(0.55, '#081530')
  felt.addColorStop(0.8, '#0a1838')
  felt.addColorStop(1, '#050d1c')
  ctx.fillStyle = felt
  ctx.fillRect(0, 0, W, H)

  // Nebula glow
  const nebula = ctx.createRadialGradient(W * 0.35, H * 0.28, 20, W * 0.4, H * 0.35, 220)
  nebula.addColorStop(0, 'rgba(90, 40, 160, 0.35)')
  nebula.addColorStop(0.5, 'rgba(40, 60, 140, 0.12)')
  nebula.addColorStop(1, 'transparent')
  ctx.fillStyle = nebula
  ctx.fillRect(0, 0, W, H)

  const nebula2 = ctx.createRadialGradient(W * 0.7, H * 0.55, 10, W * 0.65, H * 0.5, 160)
  nebula2.addColorStop(0, 'rgba(30, 80, 160, 0.2)')
  nebula2.addColorStop(1, 'transparent')
  ctx.fillStyle = nebula2
  ctx.fillRect(0, 0, W, H)

  drawStarfield(ctx, W, H, animTime)
  drawLightningCracks(ctx, animTime)

  // Center mission light array (decorative)
  {
    const cx = 200
    const cy = 430
    ctx.save()
    ctx.beginPath()
    ctx.arc(cx, cy, 58, 0, Math.PI * 2)
    const ring = ctx.createRadialGradient(cx, cy, 10, cx, cy, 58)
    ring.addColorStop(0, 'rgba(40, 180, 255, 0.35)')
    ring.addColorStop(0.45, 'rgba(20, 80, 180, 0.18)')
    ring.addColorStop(1, 'transparent')
    ctx.fillStyle = ring
    ctx.fill()

    ctx.beginPath()
    ctx.arc(cx, cy, 22, 0, Math.PI * 2)
    ctx.fillStyle = `rgba(60, 200, 255, ${0.45 + 0.25 * Math.sin(animTime * 3)})`
    ctx.shadowColor = '#3cc8ff'
    ctx.shadowBlur = 22
    ctx.fill()
    ctx.shadowBlur = 0

    for (let i = 0; i < 12; i++) {
      const a = (i / 12) * Math.PI * 2 + animTime * 0.15
      const lx = cx + Math.cos(a) * 42
      const ly = cy + Math.sin(a) * 42
      const on = 0.4 + 0.6 * (0.5 + 0.5 * Math.sin(animTime * 4 + i))
      ctx.beginPath()
      ctx.arc(lx, ly, 3.2, 0, Math.PI * 2)
      ctx.fillStyle = `rgba(100, 200, 255, ${on})`
      ctx.shadowColor = '#6ec8ff'
      ctx.shadowBlur = 8
      ctx.fill()
    }
    ctx.shadowBlur = 0
    ctx.restore()
  }

  // Left purple ramp (decorative Space Cadet ramp)
  {
    ctx.save()
    ctx.beginPath()
    ctx.moveTo(18, 160)
    ctx.quadraticCurveTo(55, 220, 48, 320)
    ctx.quadraticCurveTo(42, 400, 70, 470)
    ctx.lineTo(95, 465)
    ctx.quadraticCurveTo(70, 390, 78, 310)
    ctx.quadraticCurveTo(85, 220, 42, 155)
    ctx.closePath()
    const rampGrad = ctx.createLinearGradient(20, 160, 100, 470)
    rampGrad.addColorStop(0, '#6b2db3')
    rampGrad.addColorStop(0.5, '#8b3fd4')
    rampGrad.addColorStop(1, '#4a1a80')
    ctx.fillStyle = rampGrad
    ctx.globalAlpha = 0.85
    ctx.fill()
    ctx.globalAlpha = 1
    ctx.strokeStyle = '#c084fc'
    ctx.lineWidth = 2
    ctx.shadowColor = '#a855f7'
    ctx.shadowBlur = 12
    ctx.stroke()
    ctx.shadowBlur = 0

    // Chevrons on ramp
    ctx.fillStyle = 'rgba(255, 220, 80, 0.55)'
    for (let i = 0; i < 5; i++) {
      const y = 200 + i * 48
      const x = 48 + Math.sin(i) * 4
      ctx.beginPath()
      ctx.moveTo(x, y)
      ctx.lineTo(x + 10, y + 8)
      ctx.lineTo(x, y + 16)
      ctx.closePath()
      ctx.fill()
    }
    ctx.restore()
  }

  // Yellow lane arrows / indicators
  const drawArrow = (x: number, y: number, rot: number, color: string) => {
    ctx.save()
    ctx.translate(x, y)
    ctx.rotate(rot)
    ctx.beginPath()
    ctx.moveTo(0, -8)
    ctx.lineTo(7, 6)
    ctx.lineTo(0, 2)
    ctx.lineTo(-7, 6)
    ctx.closePath()
    ctx.fillStyle = color
    ctx.globalAlpha = 0.55 + 0.35 * Math.sin(animTime * 3 + x * 0.05)
    ctx.shadowColor = color
    ctx.shadowBlur = 8
    ctx.fill()
    ctx.restore()
  }
  drawArrow(55, 70, 0.3, '#f5c542')
  drawArrow(120, 55, 0, '#f5c542')
  drawArrow(280, 55, 0, '#f5c542')
  drawArrow(330, 75, -0.3, '#f5c542')
  drawArrow(100, 380, 0.6, '#ff5a6a')
  drawArrow(280, 380, -0.6, '#ff5a6a')

  // Top rollover lights
  for (let i = 0; i < 5; i++) {
    const lx = 110 + i * 40
    const pulse = 0.5 + 0.5 * Math.sin(animTime * 5 + i * 1.1)
    ctx.beginPath()
    ctx.arc(lx, 32, 5, 0, Math.PI * 2)
    ctx.fillStyle = i % 2 === 0 ? `rgba(255, 80, 80, ${0.5 + pulse * 0.5})` : `rgba(80, 220, 120, ${0.5 + pulse * 0.5})`
    ctx.shadowColor = ctx.fillStyle as string
    ctx.shadowBlur = 10
    ctx.fill()
  }
  ctx.shadowBlur = 0

  // Drain sunburst between flippers
  {
    ctx.save()
    ctx.translate(175, 690)
    ctx.fillStyle = 'rgba(140, 60, 200, 0.55)'
    for (let i = 0; i < 10; i++) {
      const a = -Math.PI / 2 + (i - 4.5) * 0.14
      ctx.beginPath()
      ctx.moveTo(0, 0)
      ctx.lineTo(Math.cos(a - 0.05) * 55, Math.sin(a - 0.05) * 40)
      ctx.lineTo(Math.cos(a + 0.05) * 55, Math.sin(a + 0.05) * 40)
      ctx.closePath()
      ctx.fill()
    }
    ctx.restore()
  }

  // Slingshot wedges (above flippers) with lightning art
  const drawSling = (pts: [number, number][], mirror: boolean) => {
    ctx.beginPath()
    ctx.moveTo(pts[0][0], pts[0][1])
    for (let i = 1; i < pts.length; i++) ctx.lineTo(pts[i][0], pts[i][1])
    ctx.closePath()
    ctx.fillStyle = 'rgba(20, 35, 70, 0.92)'
    ctx.fill()
    ctx.strokeStyle = '#c0c8d4'
    ctx.lineWidth = 3
    ctx.stroke()
    // Lightning bolt graphic
    const mx = (pts[0][0] + pts[1][0] + pts[2][0]) / 3
    const my = (pts[0][1] + pts[1][1] + pts[2][1]) / 3
    ctx.strokeStyle = `rgba(120, 200, 255, ${0.55 + 0.25 * Math.sin(animTime * 6)})`
    ctx.lineWidth = 2
    ctx.shadowColor = '#7ec8ff'
    ctx.shadowBlur = 8
    ctx.beginPath()
    if (!mirror) {
      ctx.moveTo(mx - 8, my - 18)
      ctx.lineTo(mx + 4, my - 4)
      ctx.lineTo(mx - 2, my - 2)
      ctx.lineTo(mx + 10, my + 18)
    } else {
      ctx.moveTo(mx + 8, my - 18)
      ctx.lineTo(mx - 4, my - 4)
      ctx.lineTo(mx + 2, my - 2)
      ctx.lineTo(mx - 10, my + 18)
    }
    ctx.stroke()
    ctx.shadowBlur = 0
  }
  drawSling([[18, 520], [108, 585], [18, 635]], false)
  drawSling([[332, 520], [255, 585], [332, 630]], true)

  // Chrome outer rails
  drawChromeRail(ctx, 14, 18, 14, 660, 6)
  drawChromeRail(ctx, 386, 18, 386, 520, 6)
  drawChromeRail(ctx, 14, 18, 386, 18, 6)
  drawChromeCurve(ctx, [[14, 18], [30, 8], [200, 4], [370, 8], [386, 18]], 5)

  // Shooter lane
  {
    const laneGrad = ctx.createLinearGradient(350, 200, 400, 700)
    laneGrad.addColorStop(0, 'rgba(40, 70, 120, 0.45)')
    laneGrad.addColorStop(1, 'rgba(20, 30, 60, 0.3)')
    ctx.fillStyle = laneGrad
    ctx.fillRect(353, 200, 35, 480)

    drawChromeRail(ctx, 350, 200, 350, 680, 5)

    // Lane chevrons
    ctx.fillStyle = 'rgba(245, 197, 66, 0.4)'
    for (let y = 280; y < 620; y += 36) {
      ctx.beginPath()
      ctx.moveTo(365, y)
      ctx.lineTo(372, y + 10)
      ctx.lineTo(379, y)
      ctx.closePath()
      ctx.fill()
    }
  }

  // One-way lane gate (closed after ball enters play)
  if (world.laneGateClosed) {
    drawChromeRail(ctx, 350, 20, 350, 205, 5)
    ctx.save()
    ctx.strokeStyle = '#c0c8d4'
    ctx.lineWidth = 3
    ctx.lineCap = 'round'
    ctx.shadowColor = '#e2e8f0'
    ctx.shadowBlur = 6
    ctx.beginPath()
    ctx.moveTo(350, 198)
    ctx.lineTo(388, 188)
    ctx.stroke()
    ctx.beginPath()
    ctx.moveTo(350, 205)
    ctx.lineTo(385, 198)
    ctx.stroke()
    ctx.restore()
  }

  // Top curve rails into playfield
  drawChromeCurve(
    ctx,
    [[390, 165], [395, 110], [380, 70], [340, 42], [300, 35]],
    6
  )
  drawChromeCurve(
    ctx,
    [[395, 180], [398, 130], [375, 80], [350, 55]],
    4
  )

  // Corner brand marks
  ctx.save()
  ctx.font = 'bold 9px sans-serif'
  ctx.fillStyle = 'rgba(220, 60, 70, 0.85)'
  ctx.fillText('CINEMATRONICS', 22, 685)
  ctx.textAlign = 'right'
  ctx.fillText('MAXIS', 340, 685)
  ctx.restore()

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

  // Space Cadet pop bumpers — white body, colored cap
  for (const [body, spec] of world.bumperBodies) {
    const pos = body.getPosition()
    const flash = bumperFlashes.find(
      (f) => Math.hypot(f.x - pos.x, f.y - pos.y) < 8
    )
    const pulse = flash ? 1.12 : 1 + Math.sin(animTime * 3 + pos.x) * 0.02
    const r = spec.radius * pulse

    ctx.beginPath()
    ctx.arc(pos.x, pos.y, r + 6, 0, Math.PI * 2)
    const glow = ctx.createRadialGradient(pos.x, pos.y, r * 0.3, pos.x, pos.y, r + 8)
    glow.addColorStop(0, flash ? `${spec.color}99` : `${spec.color}33`)
    glow.addColorStop(1, 'transparent')
    ctx.fillStyle = glow
    ctx.fill()

    const bodyGrad = ctx.createRadialGradient(
      pos.x - r * 0.3,
      pos.y - r * 0.35,
      r * 0.1,
      pos.x,
      pos.y,
      r
    )
    bodyGrad.addColorStop(0, '#ffffff')
    bodyGrad.addColorStop(0.35, '#e8eef5')
    bodyGrad.addColorStop(0.85, '#b0bcc8')
    bodyGrad.addColorStop(1, '#6a7888')

    ctx.beginPath()
    ctx.arc(pos.x, pos.y, r, 0, Math.PI * 2)
    ctx.fillStyle = bodyGrad
    ctx.shadowColor = 'rgba(255,255,255,0.5)'
    ctx.shadowBlur = flash ? 18 : 8
    ctx.fill()
    ctx.shadowBlur = 0

    ctx.beginPath()
    ctx.arc(pos.x, pos.y, r, 0, Math.PI * 2)
    ctx.strokeStyle = '#8a96a4'
    ctx.lineWidth = 2
    ctx.stroke()

    // Colored cap
    const capR = r * 0.42
    const capGrad = ctx.createRadialGradient(
      pos.x - capR * 0.2,
      pos.y - capR * 0.25,
      1,
      pos.x,
      pos.y,
      capR
    )
    capGrad.addColorStop(0, flash ? '#fff' : '#fff8f0')
    capGrad.addColorStop(0.35, spec.color)
    capGrad.addColorStop(1, '#1a1010')
    ctx.beginPath()
    ctx.arc(pos.x, pos.y, capR, 0, Math.PI * 2)
    ctx.fillStyle = capGrad
    ctx.fill()
    ctx.strokeStyle = 'rgba(255,255,255,0.5)'
    ctx.lineWidth = 1
    ctx.stroke()
  }

  // Drop targets
  for (const [body, spec] of world.targetBodies) {
    if (world.hitTargets.has(spec.id)) continue

    const pos = body.getPosition()
    const blink = 0.65 + 0.35 * Math.sin(animTime * 6 + pos.x * 0.05)
    ctx.save()
    ctx.translate(pos.x, pos.y)

    ctx.shadowColor = spec.color
    ctx.shadowBlur = 12 * blink
    ctx.fillStyle = spec.color
    ctx.globalAlpha = 0.85 + blink * 0.15
    ctx.fillRect(-spec.width / 2, -spec.height / 2, spec.width, spec.height)

    ctx.strokeStyle = '#fff'
    ctx.lineWidth = 1.5
    ctx.globalAlpha = 1
    ctx.strokeRect(-spec.width / 2, -spec.height / 2, spec.width, spec.height)

    ctx.fillStyle = 'rgba(255,255,255,0.4)'
    ctx.fillRect(-spec.width / 2 + 2, -spec.height / 2 + 2, spec.width - 4, Math.max(2, spec.height * 0.28))
    ctx.restore()
  }

  for (const [body, spec] of world.targetBodies) {
    if (!world.hitTargets.has(spec.id)) continue
    const pos = body.getPosition()
    ctx.save()
    ctx.translate(pos.x, pos.y)
    ctx.globalAlpha = 0.18
    ctx.fillStyle = '#64748b'
    ctx.fillRect(-spec.width / 2, -spec.height / 2, spec.width, spec.height)
    ctx.restore()
  }

  // Space Cadet flippers — blue body, red tip
  const flippers = getFlipperTransforms(world)

  const drawFlipper = (
    x: number,
    y: number,
    angle: number,
    mirrored: boolean
  ) => {
    ctx.save()
    ctx.translate(x, y)
    ctx.rotate(angle)

    const tip = mirrored ? -level.flipperLength : level.flipperLength
    const tipStart = tip * 0.62

    // Blue rubber body
    const bodyGrad = ctx.createLinearGradient(0, 0, tipStart, 0)
    bodyGrad.addColorStop(0, '#1e4a8c')
    bodyGrad.addColorStop(0.4, '#3b82c4')
    bodyGrad.addColorStop(1, '#2563a8')
    ctx.fillStyle = bodyGrad
    ctx.shadowColor = '#3b82c4'
    ctx.shadowBlur = 10

    ctx.beginPath()
    if (!mirrored) {
      ctx.moveTo(0, -level.flipperWidth / 2)
      ctx.lineTo(level.flipperLength * 0.65, -level.flipperWidth / 3)
      ctx.lineTo(level.flipperLength * 0.65, level.flipperWidth / 3)
      ctx.lineTo(0, level.flipperWidth / 2)
    } else {
      ctx.moveTo(0, -level.flipperWidth / 2)
      ctx.lineTo(-level.flipperLength * 0.65, -level.flipperWidth / 3)
      ctx.lineTo(-level.flipperLength * 0.65, level.flipperWidth / 3)
      ctx.lineTo(0, level.flipperWidth / 2)
    }
    ctx.closePath()
    ctx.fill()

    // Red tip
    const tipGrad = ctx.createLinearGradient(tipStart, 0, tip, 0)
    tipGrad.addColorStop(0, '#e11d2e')
    tipGrad.addColorStop(0.5, '#ff4d5a')
    tipGrad.addColorStop(1, '#b01020')
    ctx.fillStyle = tipGrad
    ctx.shadowColor = '#ff4d5a'
    ctx.beginPath()
    if (!mirrored) {
      ctx.moveTo(level.flipperLength * 0.62, -level.flipperWidth / 3)
      ctx.lineTo(level.flipperLength, -level.flipperWidth / 3.5)
      ctx.lineTo(level.flipperLength, level.flipperWidth / 3.5)
      ctx.lineTo(level.flipperLength * 0.62, level.flipperWidth / 3)
    } else {
      ctx.moveTo(-level.flipperLength * 0.62, -level.flipperWidth / 3)
      ctx.lineTo(-level.flipperLength, -level.flipperWidth / 3.5)
      ctx.lineTo(-level.flipperLength, level.flipperWidth / 3.5)
      ctx.lineTo(-level.flipperLength * 0.62, level.flipperWidth / 3)
    }
    ctx.closePath()
    ctx.fill()
    ctx.shadowBlur = 0

    ctx.strokeStyle = 'rgba(255,255,255,0.45)'
    ctx.lineWidth = 1.5
    ctx.beginPath()
    if (!mirrored) {
      ctx.moveTo(0, -level.flipperWidth / 2)
      ctx.lineTo(level.flipperLength, -level.flipperWidth / 3.5)
      ctx.lineTo(level.flipperLength, level.flipperWidth / 3.5)
      ctx.lineTo(0, level.flipperWidth / 2)
    } else {
      ctx.moveTo(0, -level.flipperWidth / 2)
      ctx.lineTo(-level.flipperLength, -level.flipperWidth / 3.5)
      ctx.lineTo(-level.flipperLength, level.flipperWidth / 3.5)
      ctx.lineTo(0, level.flipperWidth / 2)
    }
    ctx.closePath()
    ctx.stroke()

    // Pivot cap
    ctx.beginPath()
    ctx.arc(0, 0, 7, 0, Math.PI * 2)
    const pivotGrad = ctx.createRadialGradient(-2, -2, 1, 0, 0, 7)
    pivotGrad.addColorStop(0, '#f0f4f8')
    pivotGrad.addColorStop(1, '#7a8794')
    ctx.fillStyle = pivotGrad
    ctx.fill()
    ctx.strokeStyle = '#4a5560'
    ctx.lineWidth = 1.5
    ctx.stroke()

    ctx.restore()
  }

  drawFlipper(flippers.left.x, flippers.left.y, flippers.left.angle, false)
  drawFlipper(flippers.right.x, flippers.right.y, flippers.right.angle, true)

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
      ctx.fillStyle = `rgba(160, 210, 255, ${life * 0.45})`
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
        <span class="brand-mark">3D PINBALL</span>
        <span class="brand-name">SPACE CADET</span>
      </div>
      <div class="hud-section">
        <span class="hud-label">High</span>
        <span class="hud-value high">{{ formatScore(highScore) }}</span>
      </div>
      <div class="hud-section balls">
        <span class="hud-label">Ball {{ currentBallNumber }}</span>
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
          <p class="over-eyebrow">Mission failed</p>
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
  --neon-pink: #ff4d5a;
  --neon-cyan: #3cc8ff;
  --neon-gold: #f5c542;
  --cabinet: #06101f;

  position: relative;
  display: flex;
  flex-direction: column;
  align-items: center;
  height: 100%;
  width: 100%;
  background:
    radial-gradient(ellipse 80% 50% at 50% 0%, rgba(60, 100, 200, 0.22), transparent 55%),
    radial-gradient(ellipse 60% 40% at 80% 100%, rgba(120, 60, 180, 0.14), transparent 50%),
    linear-gradient(180deg, #0a1830 0%, var(--cabinet) 40%, #030810 100%);
  overflow: hidden;
  user-select: none;
  font-family: 'Segoe UI', 'Trebuchet MS', 'Outfit', system-ui, sans-serif;
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
  background: linear-gradient(180deg, rgba(0, 0, 0, 0.55) 0%, rgba(0, 0, 0, 0.2) 100%);
  border-bottom: 1px solid rgba(255, 255, 255, 0.08);
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
  color: #ffffff;
  text-shadow:
    0 0 10px rgba(100, 180, 255, 0.55),
    0 0 24px rgba(60, 120, 220, 0.35);
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
  letter-spacing: 0.28em;
  color: #7ec8ff;
  text-shadow: 0 0 10px rgba(60, 160, 255, 0.75);
}

.brand-name {
  font-size: 1.05rem;
  font-weight: 800;
  letter-spacing: 0.14em;
  color: #fff;
  text-shadow:
    0 0 14px rgba(100, 160, 255, 0.55),
    0 0 28px rgba(140, 80, 200, 0.3);
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
  background: rgba(60, 120, 220, 0.3);
  border-color: rgba(100, 180, 255, 0.55);
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
  color: var(--neon-gold);
  text-shadow: 0 0 14px rgba(245, 197, 66, 0.85);
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
  overflow: hidden;
  padding: 0.35rem 0;
}

.canvas-frame {
  position: relative;
  border-radius: 10px;
  padding: 4px;
  max-height: 100%;
  background: linear-gradient(
    145deg,
    #d8dee8 0%,
    #8a96a8 25%,
    #5a6678 50%,
    #c8d0dc 75%,
    #707c8c 100%
  );
  box-shadow:
    0 0 0 1px rgba(0, 0, 0, 0.55),
    0 12px 40px rgba(0, 0, 0, 0.55),
    0 0 50px rgba(60, 120, 220, 0.2),
    0 0 70px rgba(120, 60, 180, 0.1);
}

.pinball-canvas {
  display: block;
  border-radius: 7px;
  background: #081530;
  max-height: calc(100% - 8px);
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
  background: linear-gradient(145deg, #2b6cb0, #1e4a8c);
  box-shadow: 0 0 20px rgba(59, 130, 196, 0.4);
  border-bottom: 3px solid #e11d2e;
}

.touch-flipper.right {
  background: linear-gradient(145deg, #2b6cb0, #1e4a8c);
  box-shadow: 0 0 20px rgba(59, 130, 196, 0.4);
  border-bottom: 3px solid #e11d2e;
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
