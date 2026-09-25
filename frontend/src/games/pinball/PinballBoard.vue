<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import type { Room, PinballGameState } from '@/types'
import { PinballGame, type FlipperState, type PinballEvent } from './physics'
import type { TableLayout, Vec } from './table'
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
  playDrain,
  playGameOver,
  playHighScore,
  playUiClick,
  playSling,
  playRollover,
  playSaucer,
  playKickout,
  playAward,
  playKnocker,
  playCombo,
} from './sounds'

const props = defineProps<{
  gameState: PinballGameState
  room: Room
  playerId: string
}>()

const emit = defineEmits<{
  action: [data: Record<string, unknown>]
}>()

interface ScorePopup {
  id: number
  x: number
  y: number
  text: string
  big: boolean
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

const HIGH_SCORE_KEY = 'pinball_highscore'

const canvasRef = ref<HTMLCanvasElement | null>(null)
const areaRef = ref<HTMLDivElement | null>(null)
const scale = ref(1)

const score = ref(0)
const ballNumber = ref(1)
const totalBalls = ref(3)
const bonus = ref(0)
const multiplier = ref(1)
const ballInLane = ref(true)
const gameOver = ref(false)
const message = ref<{ text: string; sub?: string } | null>(null)
const popups = ref<ScorePopup[]>([])
const soundMuted = ref(isSoundMuted())
const storedHigh = ref(readStoredHigh())

let game: PinballGame | null = null
let staticLayer: HTMLCanvasElement | null = null
let raf = 0
let lastFrame = 0
let popupId = 0
let resizeObserver: ResizeObserver | null = null
const particles: Particle[] = []
const trail: Vec[] = []
const pointerSides = new Map<number, 'left' | 'right'>()

const highScore = computed(() =>
  Math.max(storedHigh.value, Number(props.gameState.high_score ?? 0), score.value),
)
const isNewHigh = computed(() => gameOver.value && score.value > 0 && score.value >= highScore.value)

function readStoredHigh(): number {
  try {
    return parseInt(localStorage.getItem(HIGH_SCORE_KEY) ?? '0', 10) || 0
  } catch {
    return 0
  }
}

function formatScore(n: number): string {
  return n.toLocaleString()
}

function startingBalls(): number {
  const raw = Number((props.gameState.settings as Record<string, unknown>)?.starting_balls ?? 3)
  return Number.isFinite(raw) ? raw : 3
}

// —— Game lifecycle ——————————————————————————————————————————

function newGame() {
  game = new PinballGame(startingBalls())
  totalBalls.value = game.totalBalls
  gameOver.value = false
  particles.length = 0
  trail.length = 0
  popups.value = []
  pointerSides.clear()
  syncHud()
}

function restartGame() {
  void unlockAudio()
  playUiClick()
  newGame()
  emit('action', { type: 'restart_game' })
}

function syncHud() {
  if (!game) return
  score.value = game.score
  ballNumber.value = game.ballNumber
  bonus.value = game.bonus
  multiplier.value = game.multiplier
  ballInLane.value = game.phase === 'play' && game.ballInLane
  const d = game.display
  message.value = d && d.until > game.time ? { text: d.text, sub: d.sub } : null
}

function reportScore() {
  if (!game) return
  emit('action', {
    type: 'update_score',
    score: game.score,
    balls_remaining: Math.max(0, game.totalBalls - game.ballNumber) + game.extraBalls,
  })
}

function finishGame() {
  if (!game) return
  gameOver.value = true
  const final = game.score
  const beat = final > storedHigh.value && final > 0
  if (beat) {
    try {
      localStorage.setItem(HIGH_SCORE_KEY, String(final))
    } catch {
      /* ignore */
    }
    storedHigh.value = final
    setTimeout(() => playHighScore(), 350)
  } else {
    setTimeout(() => playGameOver(), 280)
  }
  emit('action', { type: 'game_over', score: final })
}

// —— Events → sound / FX ——————————————————————————————————————

function addPopup(x: number, y: number, text: string, big = false) {
  const id = ++popupId
  popups.value.push({ id, x, y, text, big })
  setTimeout(() => {
    popups.value = popups.value.filter((p) => p.id !== id)
  }, 1100)
}

function spawnParticles(x: number, y: number, color: string, count: number, speed = 3) {
  for (let i = 0; i < count; i++) {
    const a = (Math.PI * 2 * i) / count + Math.random() * 0.5
    const m = speed * (0.4 + Math.random() * 0.8)
    particles.push({
      x,
      y,
      vx: Math.cos(a) * m,
      vy: Math.sin(a) * m,
      life: 1,
      maxLife: 0.35 + Math.random() * 0.4,
      color,
      size: 1.2 + Math.random() * 2.2,
    })
  }
}

function handleEvent(e: PinballEvent) {
  switch (e.type) {
    case 'bumper':
      playBumper(150)
      spawnParticles(e.x, e.y, '#fff6d0', 10, 4)
      break
    case 'sling':
      playSling()
      spawnParticles(e.x, e.y, '#ffffff', 5, 2.5)
      break
    case 'rollover':
      playRollover(e.points >= 500)
      break
    case 'drop':
    case 'standup':
      playTarget(e.points)
      spawnParticles(e.x, e.y, '#ffd84a', 8, 3)
      break
    case 'dropBank':
    case 'standupSet':
    case 'laneComplete':
    case 'skillShot':
      playAward()
      spawnParticles(e.x, e.y, '#7df9ff', 18, 5)
      break
    case 'extraBall':
      playKnocker()
      setTimeout(() => playAward(), 150)
      break
    case 'saucer':
      playSaucer()
      spawnParticles(e.x, e.y, '#ff7ad9', 14, 3.5)
      break
    case 'saucerEject':
      playKickout()
      break
    case 'inlane':
    case 'outlane':
      playRollover(true)
      break
    case 'flipperHit':
      playFlipperHit()
      break
    case 'wall':
      playWall()
      break
    case 'launch':
      playLaunch()
      break
    case 'ballSaved':
      playCombo(4)
      break
    case 'drain':
      playDrain()
      reportScore()
      break
    case 'shootAgain':
      playKnocker()
      break
    case 'gameOver':
      finishGame()
      break
  }

  if (e.label) addPopup(e.x || 209, e.y || 440, e.label, true)
  else if (e.points >= 500 && e.type !== 'drain') addPopup(e.x, e.y, `+${formatScore(e.points)}`)
}

// —— Input ————————————————————————————————————————————————————

const LEFT_KEYS = new Set(['KeyZ', 'KeyA', 'ArrowLeft', 'ShiftLeft'])
const RIGHT_KEYS = new Set(['Slash', 'KeyM', 'KeyD', 'ArrowRight', 'ShiftRight'])
const PLUNGER_KEYS = new Set(['Space', 'Enter', 'ArrowDown', 'KeyS'])

function flip(side: 'left' | 'right', pressed: boolean) {
  if (!game || gameOver.value) return
  if (pressed) {
    void unlockAudio()
    playFlipper()
  }
  game.setFlipper(side, pressed)
}

function handleKeyDown(e: KeyboardEvent) {
  const target = e.target as HTMLElement | null
  if (target && (target.tagName === 'INPUT' || target.tagName === 'TEXTAREA')) return
  if (gameOver.value) {
    if (e.code === 'Enter' || e.code === 'KeyR') {
      e.preventDefault()
      restartGame()
    }
    return
  }
  if (LEFT_KEYS.has(e.code)) {
    e.preventDefault()
    if (!e.repeat) flip('left', true)
  } else if (RIGHT_KEYS.has(e.code)) {
    e.preventDefault()
    if (!e.repeat) flip('right', true)
  } else if (PLUNGER_KEYS.has(e.code)) {
    e.preventDefault()
    if (!e.repeat && game) {
      void unlockAudio()
      game.setPlunger(true)
    }
  }
}

function handleKeyUp(e: KeyboardEvent) {
  if (LEFT_KEYS.has(e.code)) flip('left', false)
  else if (RIGHT_KEYS.has(e.code)) flip('right', false)
  else if (PLUNGER_KEYS.has(e.code)) game?.setPlunger(false)
}

/** Tap the table: launch if the ball is waiting, otherwise left/right half flips. */
function handleAreaPointerDown(e: PointerEvent) {
  if (!game || gameOver.value) return
  void unlockAudio()
  if (game.phase === 'play' && game.ballInLane) {
    game.autoLaunch()
    return
  }
  const rect = (e.currentTarget as HTMLElement).getBoundingClientRect()
  const side = e.clientX - rect.left < rect.width / 2 ? 'left' : 'right'
  pointerSides.set(e.pointerId, side)
  flip(side, true)
}

function handleAreaPointerUp(e: PointerEvent) {
  const side = pointerSides.get(e.pointerId)
  if (!side) return
  pointerSides.delete(e.pointerId)
  if (![...pointerSides.values()].includes(side)) flip(side, false)
}

function buttonFlip(side: 'left' | 'right', pressed: boolean) {
  flip(side, pressed)
}

function buttonPlunger(held: boolean) {
  if (!game || gameOver.value) return
  void unlockAudio()
  game.setPlunger(held)
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

// —— Layout ——————————————————————————————————————————————————

function updateScale() {
  const area = areaRef.value
  if (!area || !game) return
  const { width, height } = game.table
  const next = Math.max(0.3, Math.min(area.clientWidth / width, area.clientHeight / height, 1.6))
  if (Math.abs(next - scale.value) > 0.001 || !staticLayer) {
    scale.value = next
    resizeCanvas()
  }
}

function resizeCanvas() {
  const canvas = canvasRef.value
  if (!canvas || !game) return
  const dpr = window.devicePixelRatio || 1
  const { width, height } = game.table
  canvas.width = Math.round(width * scale.value * dpr)
  canvas.height = Math.round(height * scale.value * dpr)
  canvas.style.width = `${width * scale.value}px`
  canvas.style.height = `${height * scale.value}px`
  staticLayer = renderStaticLayer(game.table, scale.value * dpr)
}

// —— Rendering: static layer ————————————————————————————————

function playfieldPath(ctx: CanvasRenderingContext2D, t: TableLayout) {
  ctx.beginPath()
  ctx.moveTo(t.playLeft, t.height)
  ctx.lineTo(t.playLeft, t.domeCenter.y)
  ctx.arc(t.domeCenter.x, t.domeCenter.y, t.domeRadius, Math.PI, Math.PI * 2)
  ctx.lineTo(t.laneRight, t.height)
  ctx.closePath()
}

function rail(ctx: CanvasRenderingContext2D, pts: Vec[], width = 4) {
  if (pts.length < 2) return
  ctx.save()
  ctx.lineCap = 'round'
  ctx.lineJoin = 'round'
  ctx.beginPath()
  ctx.moveTo(pts[0].x, pts[0].y)
  for (let i = 1; i < pts.length; i++) ctx.lineTo(pts[i].x, pts[i].y)
  ctx.lineWidth = width + 3
  ctx.strokeStyle = 'rgba(0,0,0,0.55)'
  ctx.stroke()
  ctx.lineWidth = width
  ctx.strokeStyle = '#b9c3cf'
  ctx.stroke()
  ctx.lineWidth = Math.max(1, width * 0.35)
  ctx.strokeStyle = 'rgba(255,255,255,0.85)'
  ctx.stroke()
  ctx.restore()
}

function renderStaticLayer(t: TableLayout, pixelScale: number): HTMLCanvasElement {
  const layer = document.createElement('canvas')
  layer.width = Math.round(t.width * pixelScale)
  layer.height = Math.round(t.height * pixelScale)
  const ctx = layer.getContext('2d')!
  ctx.scale(pixelScale, pixelScale)
  const cx = (t.playLeft + t.playRight) / 2

  // Cabinet wood around the playfield.
  const wood = ctx.createLinearGradient(0, 0, t.width, 0)
  wood.addColorStop(0, '#2a1608')
  wood.addColorStop(0.5, '#4a2a12')
  wood.addColorStop(1, '#2a1608')
  ctx.fillStyle = wood
  ctx.fillRect(0, 0, t.width, t.height)

  // Playfield artwork.
  ctx.save()
  playfieldPath(ctx, t)
  ctx.clip()

  const base = ctx.createLinearGradient(0, 0, 0, t.height)
  base.addColorStop(0, '#12205e')
  base.addColorStop(0.35, '#2a1470')
  base.addColorStop(0.7, '#170a45')
  base.addColorStop(1, '#0a0624')
  ctx.fillStyle = base
  ctx.fillRect(0, 0, t.width, t.height)

  // Sunburst behind the bonus ladder.
  ctx.save()
  ctx.translate(cx, 470)
  for (let i = 0; i < 24; i++) {
    const a0 = (i / 24) * Math.PI * 2
    const a1 = a0 + Math.PI / 24
    ctx.beginPath()
    ctx.moveTo(0, 0)
    ctx.arc(0, 0, 520, a0, a1)
    ctx.closePath()
    ctx.fillStyle = i % 2 ? 'rgba(255, 90, 180, 0.07)' : 'rgba(255, 200, 80, 0.06)'
    ctx.fill()
  }
  const glow = ctx.createRadialGradient(0, 0, 10, 0, 0, 260)
  glow.addColorStop(0, 'rgba(255, 170, 60, 0.28)')
  glow.addColorStop(1, 'rgba(255, 170, 60, 0)')
  ctx.fillStyle = glow
  ctx.fillRect(-300, -300, 600, 600)
  ctx.restore()

  // Stars.
  for (let i = 0; i < 70; i++) {
    const x = (i * 97.3) % t.width
    const y = (i * 151.7) % (t.height * 0.9)
    ctx.fillStyle = i % 4 === 0 ? 'rgba(160,220,255,0.7)' : 'rgba(255,255,255,0.45)'
    ctx.fillRect(x, y, i % 6 === 0 ? 2 : 1.2, i % 6 === 0 ? 2 : 1.2)
  }

  // Colour bands sweeping toward the flippers.
  const band = (color: string, x0: number, x1: number) => {
    ctx.beginPath()
    ctx.moveTo(x0, 430)
    ctx.quadraticCurveTo(x0 - 20, 640, cx - 20, 860)
    ctx.lineTo(cx + 20, 860)
    ctx.quadraticCurveTo(x1 + 20, 640, x1, 430)
    ctx.closePath()
    ctx.fillStyle = color
    ctx.fill()
  }
  band('rgba(255, 60, 120, 0.10)', 90, 328)
  band('rgba(80, 200, 255, 0.08)', 130, 288)

  // Table name.
  ctx.save()
  ctx.translate(cx, 440)
  ctx.rotate(-0.08)
  ctx.font = 'italic 900 40px "Trebuchet MS", system-ui, sans-serif'
  ctx.textAlign = 'center'
  ctx.textBaseline = 'middle'
  ctx.lineWidth = 6
  ctx.strokeStyle = 'rgba(40, 0, 60, 0.8)'
  ctx.strokeText('STARLITE', 0, 0)
  const title = ctx.createLinearGradient(0, -20, 0, 20)
  title.addColorStop(0, '#fff3a8')
  title.addColorStop(0.5, '#ffb52e')
  title.addColorStop(1, '#ff5a1f')
  ctx.fillStyle = title
  ctx.fillText('STARLITE', 0, 0)
  ctx.restore()

  // Shooter lane floor.
  const lane = ctx.createLinearGradient(t.playRight, 0, t.laneRight, 0)
  lane.addColorStop(0, '#1b0f2e')
  lane.addColorStop(0.5, '#2b1a44')
  lane.addColorStop(1, '#1b0f2e')
  ctx.fillStyle = lane
  ctx.fillRect(t.playRight, 212, t.laneRight - t.playRight, t.height)
  ctx.fillStyle = 'rgba(255, 210, 90, 0.35)'
  for (let y = 300; y < 800; y += 40) {
    const lx = (t.playRight + t.laneRight) / 2
    ctx.beginPath()
    ctx.moveTo(lx, y)
    ctx.lineTo(lx + 7, y + 10)
    ctx.lineTo(lx - 7, y + 10)
    ctx.closePath()
    ctx.fill()
  }

  // Side pockets.
  for (const mirror of [false, true]) {
    const mx = (x: number) => (mirror ? 2 * cx - x : x)
    ctx.beginPath()
    ctx.moveTo(mx(t.playLeft), 262)
    ctx.lineTo(mx(34), 282)
    ctx.lineTo(mx(34), 396)
    ctx.lineTo(mx(t.playLeft), 416)
    ctx.closePath()
    ctx.fillStyle = '#0c0718'
    ctx.fill()
  }

  // Saucer hole.
  {
    const { c, r } = t.saucer
    const hole = ctx.createRadialGradient(c.x, c.y, 2, c.x, c.y, r + 4)
    hole.addColorStop(0, '#000')
    hole.addColorStop(0.7, '#110818')
    hole.addColorStop(1, '#6b5a7a')
    ctx.beginPath()
    ctx.arc(c.x, c.y, r + 4, 0, Math.PI * 2)
    ctx.fillStyle = hole
    ctx.fill()
    ctx.lineWidth = 2
    ctx.strokeStyle = '#c9d2dc'
    ctx.stroke()
  }

  // Rollover buttons in the top lanes.
  for (const p of t.rollovers) {
    ctx.beginPath()
    ctx.ellipse(p.x, p.y, 4, 9, 0, 0, Math.PI * 2)
    ctx.fillStyle = '#d6dde6'
    ctx.fill()
  }

  // Inlane / outlane labels.
  ctx.font = 'bold 7px system-ui, sans-serif'
  ctx.textAlign = 'center'
  ctx.fillStyle = 'rgba(255,255,255,0.55)'
  for (const s of t.sensors) {
    if (s.kind === 'rollover') continue
    ctx.save()
    ctx.translate(s.c.x, s.c.y + 18)
    ctx.fillText(s.kind === 'inlane' ? '500' : '2K', 0, 0)
    ctx.restore()
  }

  // Slingshot plastics.
  for (const s of t.slings) {
    const [A, B, C] = s.points
    ctx.beginPath()
    ctx.moveTo(A.x, A.y)
    ctx.lineTo(B.x, B.y)
    ctx.lineTo(C.x, C.y)
    ctx.closePath()
    const g = ctx.createLinearGradient(A.x, A.y, C.x, C.y)
    g.addColorStop(0, '#ff3d6e')
    g.addColorStop(1, '#8a1240')
    ctx.fillStyle = g
    ctx.fill()
  }
  ctx.restore()

  // Metal rails (outer wall, guides, dividers).
  ctx.save()
  playfieldPath(ctx, t)
  ctx.lineWidth = 10
  ctx.strokeStyle = '#1a0d05'
  ctx.stroke()
  ctx.restore()
  for (const seg of t.segments) {
    if (seg.kind === 'wall') rail(ctx, [seg.a, seg.b], seg.a.y > t.height || seg.b.y > t.height ? 5 : 4)
  }

  return layer
}

// —— Rendering: dynamic ——————————————————————————————————————

function lamp(
  ctx: CanvasRenderingContext2D,
  x: number,
  y: number,
  r: number,
  color: string,
  on: boolean,
  label?: string,
) {
  ctx.save()
  ctx.beginPath()
  ctx.arc(x, y, r, 0, Math.PI * 2)
  if (on) {
    const g = ctx.createRadialGradient(x - r * 0.3, y - r * 0.3, 1, x, y, r)
    g.addColorStop(0, '#ffffff')
    g.addColorStop(0.4, color)
    g.addColorStop(1, color)
    ctx.fillStyle = g
    ctx.shadowColor = color
    ctx.shadowBlur = r * 1.8
  } else {
    ctx.fillStyle = color
    ctx.globalAlpha = 0.22
  }
  ctx.fill()
  ctx.shadowBlur = 0
  ctx.globalAlpha = 1
  ctx.lineWidth = 1
  ctx.strokeStyle = 'rgba(0,0,0,0.5)'
  ctx.stroke()
  if (label) {
    ctx.font = `bold ${Math.max(6, r * 0.8)}px system-ui, sans-serif`
    ctx.textAlign = 'center'
    ctx.textBaseline = 'middle'
    ctx.fillStyle = on ? '#2a0a00' : 'rgba(255,255,255,0.55)'
    ctx.fillText(label, x, y + 0.5)
  }
  ctx.restore()
}

function arrowLamp(ctx: CanvasRenderingContext2D, x: number, y: number, angle: number, color: string, on: boolean) {
  ctx.save()
  ctx.translate(x, y)
  ctx.rotate(angle)
  ctx.beginPath()
  ctx.moveTo(0, -10)
  ctx.lineTo(8, 4)
  ctx.lineTo(3, 3)
  ctx.lineTo(3, 10)
  ctx.lineTo(-3, 10)
  ctx.lineTo(-3, 3)
  ctx.lineTo(-8, 4)
  ctx.closePath()
  ctx.fillStyle = color
  ctx.globalAlpha = on ? 1 : 0.22
  if (on) {
    ctx.shadowColor = color
    ctx.shadowBlur = 12
  }
  ctx.fill()
  ctx.restore()
}

function drawBumper(ctx: CanvasRenderingContext2D, c: Vec, r: number, color: string, lit: boolean) {
  ctx.save()
  // Skirt.
  ctx.beginPath()
  ctx.arc(c.x, c.y, r + 5, 0, Math.PI * 2)
  ctx.fillStyle = lit ? 'rgba(255,255,255,0.55)' : 'rgba(220,230,240,0.25)'
  ctx.fill()
  // Body.
  ctx.beginPath()
  ctx.arc(c.x, c.y, r, 0, Math.PI * 2)
  const body = ctx.createRadialGradient(c.x, c.y - r * 0.2, r * 0.2, c.x, c.y, r)
  body.addColorStop(0, lit ? '#ffffff' : color)
  body.addColorStop(0.55, color)
  body.addColorStop(1, '#2a0508')
  ctx.fillStyle = body
  if (lit) {
    ctx.shadowColor = color
    ctx.shadowBlur = 28
  }
  ctx.fill()
  ctx.shadowBlur = 0
  ctx.lineWidth = 2
  ctx.strokeStyle = 'rgba(255,255,255,0.7)'
  ctx.stroke()
  // Cap with star.
  const capR = r * 0.62
  ctx.beginPath()
  ctx.arc(c.x, c.y, capR, 0, Math.PI * 2)
  const cap = ctx.createRadialGradient(c.x - capR * 0.3, c.y - capR * 0.4, 1, c.x, c.y, capR)
  cap.addColorStop(0, '#ffffff')
  cap.addColorStop(1, lit ? '#fff4c2' : '#d9dfe8')
  ctx.fillStyle = cap
  ctx.fill()
  ctx.beginPath()
  for (let i = 0; i < 10; i++) {
    const a = -Math.PI / 2 + (i * Math.PI) / 5
    const rr = i % 2 === 0 ? capR * 0.75 : capR * 0.32
    const px = c.x + Math.cos(a) * rr
    const py = c.y + Math.sin(a) * rr
    if (i === 0) ctx.moveTo(px, py)
    else ctx.lineTo(px, py)
  }
  ctx.closePath()
  ctx.fillStyle = color
  ctx.fill()
  ctx.restore()
}

function drawPost(ctx: CanvasRenderingContext2D, c: Vec, r: number) {
  ctx.beginPath()
  ctx.arc(c.x, c.y, r + 1.5, 0, Math.PI * 2)
  ctx.fillStyle = '#f2f2f2'
  ctx.fill()
  ctx.beginPath()
  ctx.arc(c.x, c.y, Math.max(1.5, r * 0.45), 0, Math.PI * 2)
  ctx.fillStyle = '#e0a526'
  ctx.fill()
}

function drawFlipper(ctx: CanvasRenderingContext2D, f: FlipperState) {
  const { pivot, length, r0, r1 } = f.spec
  const a = f.angle
  const tip = { x: pivot.x + Math.cos(a) * length, y: pivot.y + Math.sin(a) * length }
  ctx.save()
  ctx.beginPath()
  ctx.arc(pivot.x, pivot.y, r0, a + Math.PI / 2, a + (Math.PI * 3) / 2)
  ctx.arc(tip.x, tip.y, r1, a - Math.PI / 2, a + Math.PI / 2)
  ctx.closePath()
  ctx.shadowColor = 'rgba(0,0,0,0.6)'
  ctx.shadowBlur = 6
  ctx.shadowOffsetY = 3
  const g = ctx.createLinearGradient(pivot.x, pivot.y - r0, pivot.x, pivot.y + r0)
  g.addColorStop(0, '#ffffff')
  g.addColorStop(1, '#cfd6de')
  ctx.fillStyle = g
  ctx.fill()
  ctx.shadowColor = 'transparent'
  ctx.lineWidth = 3
  ctx.strokeStyle = '#d7263d'
  ctx.stroke()
  ctx.beginPath()
  ctx.arc(pivot.x, pivot.y, 3.5, 0, Math.PI * 2)
  ctx.fillStyle = '#8a95a3'
  ctx.fill()
  ctx.restore()
}

function drawBall(ctx: CanvasRenderingContext2D, x: number, y: number, r: number) {
  ctx.save()
  ctx.beginPath()
  ctx.arc(x + 2, y + 3, r, 0, Math.PI * 2)
  ctx.fillStyle = 'rgba(0,0,0,0.35)'
  ctx.fill()
  const g = ctx.createRadialGradient(x - r * 0.35, y - r * 0.4, r * 0.1, x, y, r)
  g.addColorStop(0, '#ffffff')
  g.addColorStop(0.3, '#e6ebf1')
  g.addColorStop(0.75, '#8994a3')
  g.addColorStop(1, '#3d4550')
  ctx.beginPath()
  ctx.arc(x, y, r, 0, Math.PI * 2)
  ctx.fillStyle = g
  ctx.fill()
  ctx.beginPath()
  ctx.arc(x - r * 0.35, y - r * 0.4, r * 0.25, 0, Math.PI * 2)
  ctx.fillStyle = 'rgba(255,255,255,0.9)'
  ctx.fill()
  ctx.restore()
}

function drawPlunger(ctx: CanvasRenderingContext2D, g: PinballGame) {
  const { x0, x1 } = g.table.plunger
  const top = g.plungerY
  const mid = (x0 + x1) / 2
  const bottom = g.table.height
  ctx.save()
  // Spring.
  ctx.beginPath()
  const coils = 7
  for (let i = 0; i <= coils * 2; i++) {
    const y = top + 8 + ((bottom - top - 8) * i) / (coils * 2)
    const x = mid + (i % 2 ? 8 : -8)
    if (i === 0) ctx.moveTo(mid, top + 8)
    else ctx.lineTo(x, y)
  }
  ctx.lineWidth = 2
  ctx.strokeStyle = '#9aa4b0'
  ctx.stroke()
  // Tip.
  ctx.fillStyle = '#e8ecf0'
  ctx.fillRect(x0 + 5, top, x1 - x0 - 10, 8)
  ctx.fillStyle = '#d7263d'
  ctx.fillRect(x0 + 5, top, x1 - x0 - 10, 3)
  ctx.restore()
}

function drawApron(ctx: CanvasRenderingContext2D, g: PinballGame) {
  const t = g.table
  const top = 842
  ctx.save()
  ctx.beginPath()
  ctx.moveTo(t.playLeft - 5, t.height + 5)
  ctx.lineTo(t.playLeft - 5, top)
  ctx.lineTo(t.playRight + 3, top)
  ctx.lineTo(t.playRight + 3, t.height + 5)
  ctx.closePath()
  const grad = ctx.createLinearGradient(0, top, 0, t.height)
  grad.addColorStop(0, '#2d2f36')
  grad.addColorStop(1, '#15161a')
  ctx.fillStyle = grad
  ctx.fill()
  ctx.lineWidth = 2
  ctx.strokeStyle = '#8a929c'
  ctx.stroke()

  ctx.font = 'bold 10px system-ui, sans-serif'
  ctx.textBaseline = 'middle'
  ctx.fillStyle = '#ffcf5a'
  ctx.textAlign = 'left'
  ctx.fillText(`BALL ${g.ballNumber} / ${g.totalBalls}`, t.playLeft + 10, top + 19)
  ctx.textAlign = 'right'
  ctx.fillStyle = 'rgba(255,255,255,0.6)'
  ctx.fillText('LANES ➜ BONUS X  •  TARGETS ➜ EXTRA BALL', t.playRight - 8, top + 19)
  ctx.restore()
}

function render() {
  const canvas = canvasRef.value
  const g = game
  if (!canvas || !g || !staticLayer) return
  const ctx = canvas.getContext('2d')
  if (!ctx) return
  const t = g.table
  const cx = (t.playLeft + t.playRight) / 2
  const time = g.time
  const blink = Math.floor(time * 4) % 2 === 0
  const slowBlink = Math.floor(time * 2) % 2 === 0

  ctx.setTransform(1, 0, 0, 1, 0, 0)
  ctx.drawImage(staticLayer, 0, 0)
  const px = canvas.width / t.width
  ctx.setTransform(px, 0, 0, px, 0, 0)

  // Top lane lamps (skill-shot lane blinks while the ball waits / is in flight).
  const skill = g.phase === 'play' && (g.ballInLane || g.skillShotLive)
  t.rollovers.forEach((p, i) => {
    const on = g.lanesLit[i] || (skill && i === g.skillLane && blink)
    lamp(ctx, p.x, 128, 7, '#ffd84a', on)
  })

  // Bonus ladder.
  for (let i = 0; i < 10; i++) {
    const row = Math.floor(i / 5)
    const col = i % 5
    lamp(ctx, cx - 60 + col * 30, 505 + row * 28, 10, '#ff9f1c', g.bonus > i, `${i + 1}K`)
  }
  lamp(ctx, cx + 90, 519, 8, '#ff9f1c', g.bonus > 10, '+')

  // Bonus multipliers.
  const mults: [number, number, string][] = [
    [cx - 44, 590, '2X'],
    [cx, 600, '3X'],
    [cx + 44, 590, '5X'],
  ]
  mults.forEach(([x, y, label], i) => lamp(ctx, x, y, 12, '#3ee07a', g.multiplierIndex > i, label))

  // Shoot again / ball save.
  const saveOn = g.extraBalls > 0 || (g.ballSaveActive && !g.ballInLane && slowBlink)
  lamp(ctx, cx, 690, 11, '#ff3b4a', saveOn)
  ctx.font = 'bold 7px system-ui, sans-serif'
  ctx.textAlign = 'center'
  ctx.fillStyle = 'rgba(255,255,255,0.75)'
  ctx.fillText('SHOOT AGAIN', cx, 710)

  // Drop-target and standup status lamps.
  t.dropTargets.forEach((d, i) => lamp(ctx, 60, (d.a.y + d.b.y) / 2, 5, '#ffd84a', g.dropsDown[i]))
  t.standups.forEach((s, i) => lamp(ctx, 2 * cx - 60, (s.a.y + s.b.y) / 2, 5, '#7df9ff', g.standupsLit[i]))
  const litStandups = g.standupsLit.filter(Boolean).length
  arrowLamp(
    ctx,
    2 * cx - 84,
    339,
    Math.PI / 2,
    '#ff3b4a',
    !g.extraBallAwarded && (litStandups >= 2 ? blink : true),
  )
  arrowLamp(ctx, 84, 337, -Math.PI / 2, '#ffd84a', g.dropsDown.some(Boolean) && slowBlink)

  // Lane arrows.
  for (const s of t.sensors) {
    if (s.kind === 'rollover') continue
    arrowLamp(ctx, s.c.x, s.c.y - 6, Math.PI, s.kind === 'inlane' ? '#7df9ff' : '#ff7ad9', g.isLit(s.id))
  }

  // Saucer ring.
  lamp(ctx, t.saucer.c.x, t.saucer.c.y - 26, 6, '#ff7ad9', g.isLit('saucer') ? blink : g.multiplierIndex > 0)

  // Drop targets.
  t.dropTargets.forEach((d, i) => {
    ctx.save()
    if (g.dropsDown[i]) {
      ctx.fillStyle = 'rgba(255,255,255,0.12)'
      ctx.fillRect(d.a.x - 3, d.a.y, 6, d.b.y - d.a.y)
    } else {
      ctx.fillStyle = '#ffd84a'
      ctx.shadowColor = 'rgba(0,0,0,0.5)'
      ctx.shadowBlur = 4
      ctx.fillRect(d.a.x - 3, d.a.y + 1, 7, d.b.y - d.a.y - 2)
      ctx.fillStyle = '#b36b00'
      ctx.fillRect(d.a.x + 2, d.a.y + 1, 2, d.b.y - d.a.y - 2)
    }
    ctx.restore()
  })

  // Standup targets.
  t.standups.forEach((s) => {
    const lit = g.isLit(s.id)
    ctx.save()
    ctx.fillStyle = lit ? '#ffffff' : '#7df9ff'
    if (lit) {
      ctx.shadowColor = '#7df9ff'
      ctx.shadowBlur = 14
    }
    ctx.fillRect(s.a.x - 4, s.a.y + 1, 7, s.b.y - s.a.y - 2)
    ctx.restore()
  })

  // Slingshot rubbers.
  for (const s of t.slings) {
    const [A, B, C] = s.points
    const lit = g.isLit(s.id)
    ctx.save()
    ctx.beginPath()
    ctx.moveTo(A.x, A.y)
    ctx.lineTo(B.x, B.y)
    ctx.lineTo(C.x, C.y)
    ctx.closePath()
    ctx.lineJoin = 'round'
    ctx.lineWidth = 4
    ctx.strokeStyle = lit ? '#fff9c4' : '#f4f4f4'
    if (lit) {
      ctx.shadowColor = '#ffec80'
      ctx.shadowBlur = 16
      ctx.fillStyle = 'rgba(255, 240, 150, 0.35)'
      ctx.fill()
    }
    ctx.stroke()
    ctx.restore()
  }

  // Posts and bumpers.
  for (const c of t.circles) {
    if (c.kind === 'post') drawPost(ctx, c.c, c.r)
    else drawBumper(ctx, c.c, c.r, c.color ?? '#ff3b4a', g.isLit(c.id))
  }

  // One-way gate wire.
  for (const seg of t.segments) {
    if (seg.kind !== 'gate') continue
    ctx.save()
    ctx.lineCap = 'round'
    ctx.lineWidth = 2
    ctx.strokeStyle = '#e3e8ee'
    ctx.beginPath()
    ctx.moveTo(seg.a.x, seg.a.y)
    ctx.lineTo(seg.b.x, seg.b.y)
    ctx.stroke()
    ctx.restore()
  }

  drawPlunger(ctx, g)
  for (const f of g.flippers) drawFlipper(ctx, f)

  // Ball + short motion trail.
  if (g.ball) {
    const b = g.ball
    trail.push({ x: b.x, y: b.y })
    if (trail.length > 6) trail.shift()
    trail.forEach((p, i) => {
      ctx.beginPath()
      ctx.arc(p.x, p.y, t.ballRadius * (0.4 + (i / trail.length) * 0.5), 0, Math.PI * 2)
      ctx.fillStyle = `rgba(200, 225, 255, ${(i / trail.length) * 0.18})`
      ctx.fill()
    })
    drawBall(ctx, b.x, b.y, t.ballRadius)
  } else {
    trail.length = 0
  }

  // Particles.
  for (let i = particles.length - 1; i >= 0; i--) {
    const p = particles[i]
    p.x += p.vx
    p.y += p.vy
    p.vy += 0.1
    p.life -= 1 / 60 / p.maxLife
    if (p.life <= 0) {
      particles.splice(i, 1)
      continue
    }
    ctx.globalAlpha = p.life
    ctx.fillStyle = p.color
    ctx.beginPath()
    ctx.arc(p.x, p.y, p.size * p.life, 0, Math.PI * 2)
    ctx.fill()
  }
  ctx.globalAlpha = 1

  drawApron(ctx, g)
}

function frame(now: number) {
  const dt = lastFrame ? (now - lastFrame) / 1000 : 1 / 60
  lastFrame = now
  if (game) {
    game.update(dt)
    for (const e of game.drainEvents()) handleEvent(e)
    syncHud()
  }
  render()
  raf = requestAnimationFrame(frame)
}

onMounted(() => {
  newGame()
  updateScale()
  if (areaRef.value) {
    resizeObserver = new ResizeObserver(() => updateScale())
    resizeObserver.observe(areaRef.value)
  }
  window.addEventListener('keydown', handleKeyDown)
  window.addEventListener('keyup', handleKeyUp)
  window.addEventListener('pointerdown', unlockAudio, { once: true })
  raf = requestAnimationFrame(frame)
})

onUnmounted(() => {
  cancelAnimationFrame(raf)
  resizeObserver?.disconnect()
  window.removeEventListener('keydown', handleKeyDown)
  window.removeEventListener('keyup', handleKeyUp)
})
</script>

<template>
  <div class="pinball-container">
    <div class="pinball-hud">
      <button
        type="button"
        class="mute-btn"
        :aria-label="soundMuted ? 'Unmute sound' : 'Mute sound'"
        :title="soundMuted ? 'Unmute' : 'Mute'"
        @click="toggleSoundMute"
      >
        {{ soundMuted ? '🔇' : '🔊' }}
      </button>

      <div class="dmd" role="status" aria-live="polite">
        <template v-if="message">
          <div class="dmd-main flash">{{ message.text }}</div>
          <div class="dmd-sub">{{ message.sub }}</div>
        </template>
        <template v-else>
          <div class="dmd-main">{{ formatScore(score) }}</div>
          <div class="dmd-sub">
            <span>BALL {{ ballNumber }}/{{ totalBalls }}</span>
            <span>BONUS {{ bonus }}K ×{{ multiplier }}</span>
            <span>HI {{ formatScore(highScore) }}</span>
          </div>
        </template>
      </div>
    </div>

    <div
      ref="areaRef"
      class="game-area"
      @pointerdown="handleAreaPointerDown"
      @pointerup="handleAreaPointerUp"
      @pointercancel="handleAreaPointerUp"
      @pointerleave="handleAreaPointerUp"
      @contextmenu.prevent
    >
      <div class="canvas-frame">
        <canvas ref="canvasRef" class="pinball-canvas" />
        <TransitionGroup name="popup">
          <div
            v-for="p in popups"
            :key="p.id"
            class="score-popup"
            :class="{ big: p.big }"
            :style="{ left: `${p.x * scale}px`, top: `${p.y * scale}px` }"
          >
            {{ p.text }}
          </div>
        </TransitionGroup>

        <div v-if="ballInLane && !gameOver" class="launch-hint">
          <span class="hint-text">Hold SPACE, release to plunge</span>
          <span class="hint-subtext">or tap the table · flippers change the skill-shot lane</span>
        </div>

        <div v-if="gameOver" class="game-over-overlay" @pointerdown.stop>
          <div class="game-over-content">
            <p class="over-eyebrow">Game over</p>
            <p class="final-score">{{ formatScore(score) }}</p>
            <p v-if="isNewHigh" class="new-highscore">NEW HIGH SCORE</p>
            <button class="restart-btn" @click="restartGame">Play Again</button>
            <p class="restart-hint">or press Enter</p>
          </div>
        </div>
      </div>
    </div>

    <div class="touch-controls">
      <button
        class="touch-btn flipper"
        @pointerdown.prevent="buttonFlip('left', true)"
        @pointerup.prevent="buttonFlip('left', false)"
        @pointerleave="buttonFlip('left', false)"
        @pointercancel="buttonFlip('left', false)"
      >
        <span class="btn-label">LEFT</span>
        <span class="btn-key">Z / ← / A</span>
      </button>
      <button
        class="touch-btn plunger"
        :disabled="!ballInLane || gameOver"
        @pointerdown.prevent="buttonPlunger(true)"
        @pointerup.prevent="buttonPlunger(false)"
        @pointerleave="buttonPlunger(false)"
        @pointercancel="buttonPlunger(false)"
      >
        <span class="btn-label">PLUNGER</span>
        <span class="btn-key">hold SPACE</span>
      </button>
      <button
        class="touch-btn flipper"
        @pointerdown.prevent="buttonFlip('right', true)"
        @pointerup.prevent="buttonFlip('right', false)"
        @pointerleave="buttonFlip('right', false)"
        @pointercancel="buttonFlip('right', false)"
      >
        <span class="btn-label">RIGHT</span>
        <span class="btn-key">/ / → / D</span>
      </button>
    </div>
  </div>
</template>

<style scoped>
.pinball-container {
  position: relative;
  display: flex;
  flex-direction: column;
  align-items: center;
  height: 100%;
  width: 100%;
  background:
    radial-gradient(ellipse 70% 40% at 50% 0%, rgba(255, 140, 40, 0.12), transparent 60%),
    linear-gradient(180deg, #120a06 0%, #070403 100%);
  overflow: hidden;
  user-select: none;
  -webkit-user-select: none;
  touch-action: none;
  font-family: 'Trebuchet MS', system-ui, sans-serif;
}

.pinball-hud {
  position: relative;
  display: flex;
  justify-content: center;
  align-items: center;
  width: 100%;
  padding: 0.5rem 1rem 0.4rem;
  flex-shrink: 0;
}

.dmd {
  min-width: min(440px, 80vw);
  padding: 0.35rem 1rem 0.4rem;
  border-radius: 6px;
  border: 2px solid #3a2a1a;
  background-color: #0b0603;
  background-image: radial-gradient(rgba(255, 140, 30, 0.08) 1px, transparent 1.2px);
  background-size: 4px 4px;
  box-shadow:
    inset 0 0 18px rgba(0, 0, 0, 0.9),
    0 0 0 1px #000,
    0 4px 14px rgba(0, 0, 0, 0.6);
  color: #ff8c1a;
  text-align: center;
  font-family: ui-monospace, 'SF Mono', Menlo, Consolas, monospace;
  text-shadow: 0 0 6px rgba(255, 140, 26, 0.85), 0 0 14px rgba(255, 100, 0, 0.45);
}

.dmd-main {
  font-size: 1.7rem;
  font-weight: 800;
  letter-spacing: 0.12em;
  line-height: 1.1;
  font-variant-numeric: tabular-nums;
}

.dmd-main.flash {
  animation: dmdFlash 0.4s steps(2) infinite;
}

.dmd-sub {
  display: flex;
  justify-content: center;
  gap: 1.1rem;
  min-height: 1em;
  font-size: 0.72rem;
  font-weight: 700;
  letter-spacing: 0.14em;
  opacity: 0.85;
}

@keyframes dmdFlash {
  50% {
    opacity: 0.55;
  }
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
  background: rgba(20, 10, 4, 0.7);
  color: #fff;
  font-size: 1rem;
  cursor: pointer;
  display: grid;
  place-items: center;
}

.game-area {
  position: relative;
  flex: 1;
  display: flex;
  justify-content: center;
  align-items: center;
  min-height: 0;
  width: 100%;
  overflow: hidden;
  cursor: pointer;
}

.canvas-frame {
  position: relative;
  border-radius: 8px;
  box-shadow:
    0 0 0 3px #1a0d05,
    0 0 0 5px #6b4a2a,
    0 14px 40px rgba(0, 0, 0, 0.7);
  line-height: 0;
}

.pinball-canvas {
  display: block;
  border-radius: 8px;
}

.score-popup {
  position: absolute;
  transform: translate(-50%, -50%);
  pointer-events: none;
  font-size: 0.95rem;
  font-weight: 800;
  line-height: 1;
  white-space: nowrap;
  color: #fff6c8;
  text-shadow: 0 0 8px rgba(255, 190, 60, 0.9), 0 2px 3px rgba(0, 0, 0, 0.9);
  z-index: 3;
}

.score-popup.big {
  font-size: 1.25rem;
  color: #7df9ff;
  text-shadow: 0 0 10px rgba(80, 220, 255, 0.95), 0 2px 3px rgba(0, 0, 0, 0.9);
}

.popup-enter-active {
  animation: popupRise 1.1s ease-out forwards;
}

@keyframes popupRise {
  0% {
    opacity: 0;
    transform: translate(-50%, -50%) scale(0.5);
  }
  15% {
    opacity: 1;
    transform: translate(-50%, -80%) scale(1.15);
  }
  100% {
    opacity: 0;
    transform: translate(-50%, -220%) scale(1);
  }
}

.launch-hint {
  position: absolute;
  left: 50%;
  top: 56%;
  transform: translateX(-50%);
  text-align: center;
  padding: 0.6rem 1rem;
  border-radius: 10px;
  background: rgba(10, 5, 2, 0.78);
  border: 1px solid rgba(255, 180, 60, 0.4);
  pointer-events: none;
  line-height: 1.3;
  z-index: 2;
  width: max-content;
  max-width: 90%;
}

.hint-text {
  display: block;
  font-size: 0.95rem;
  font-weight: 700;
  color: #ffcf5a;
}

.hint-subtext {
  display: block;
  font-size: 0.7rem;
  color: rgba(255, 255, 255, 0.6);
}

.game-over-overlay {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(5, 2, 1, 0.8);
  border-radius: 8px;
  line-height: 1.2;
  z-index: 4;
  cursor: default;
}

.game-over-content {
  text-align: center;
  padding: 1.5rem;
}

.over-eyebrow {
  margin: 0 0 0.4rem;
  font-size: 1.6rem;
  font-weight: 800;
  letter-spacing: 0.18em;
  color: #ff8c1a;
  text-shadow: 0 0 14px rgba(255, 140, 26, 0.7);
}

.final-score {
  margin: 0 0 0.5rem;
  font-size: 2.2rem;
  font-weight: 800;
  color: #fff;
  font-variant-numeric: tabular-nums;
}

.new-highscore {
  margin: 0 0 1rem;
  font-weight: 700;
  letter-spacing: 0.18em;
  color: #7df9ff;
  animation: dmdFlash 0.5s steps(2) infinite;
}

.restart-btn {
  padding: 0.75rem 2rem;
  font: inherit;
  font-weight: 800;
  letter-spacing: 0.06em;
  color: #1a0a00;
  background: linear-gradient(135deg, #ffcf5a, #ff8c1a);
  border: none;
  border-radius: 999px;
  cursor: pointer;
}

.restart-hint {
  margin: 0.5rem 0 0;
  font-size: 0.75rem;
  color: rgba(255, 255, 255, 0.5);
}

.touch-controls {
  display: flex;
  justify-content: center;
  gap: 0.75rem;
  width: 100%;
  padding: 0.5rem 1rem 0.85rem;
  flex-shrink: 0;
}

.touch-btn {
  flex: 1;
  max-width: 180px;
  padding: 0.7rem 0.5rem;
  border-radius: 12px;
  border: 1px solid rgba(255, 255, 255, 0.15);
  font: inherit;
  font-weight: 700;
  color: #fff;
  cursor: pointer;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 0.15rem;
  touch-action: none;
  transition: transform 0.08s;
}

.touch-btn.flipper {
  background: linear-gradient(160deg, #f4f4f4, #c9cfd6);
  color: #2a0a0a;
  border-bottom: 3px solid #d7263d;
}

.touch-btn.plunger {
  max-width: 140px;
  background: linear-gradient(160deg, #ff9f1c, #c85a00);
}

.touch-btn:disabled {
  opacity: 0.35;
  cursor: default;
}

.touch-btn:active:not(:disabled) {
  transform: scale(0.96);
}

.btn-label {
  font-size: 0.9rem;
  letter-spacing: 0.08em;
}

.btn-key {
  font-size: 0.65rem;
  opacity: 0.7;
}

@media (max-width: 480px) {
  .dmd-main {
    font-size: 1.3rem;
  }

  .dmd-sub {
    gap: 0.6rem;
    font-size: 0.6rem;
  }

  .mute-btn {
    left: 0.4rem;
  }
}
</style>
