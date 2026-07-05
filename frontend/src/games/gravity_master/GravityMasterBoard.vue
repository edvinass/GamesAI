<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import type { Room, GravityMasterGameState } from '@/types'
import {
  strokeCentroid,
  triangulateStroke,
  worldToLocal,
} from './strokeMesh'
import {
  addStrokeToWorld,
  createPhysicsWorld,
  getBallCanvasTransform,
  getShapeCanvasTransform,
  isBallLost,
  isBallReleased,
  isBallSettled,
  releaseBall,
  removeAllDrawnShapes,
  removeShapeFromWorld,
  type DrawnShape,
  type PhysicsWorld,
} from './physics'

const props = defineProps<{
  gameState: GravityMasterGameState
  room: Room
  playerId: string
}>()

const emit = defineEmits<{
  action: [data: Record<string, unknown>]
}>()

const canvasRef = ref<HTMLCanvasElement | null>(null)
const physicsLoading = ref(true)

const strokes = ref<{ x: number; y: number }[][]>([])
const drawnShapes = ref<DrawnShape[]>([])
const currentStroke = ref<{ x: number; y: number }[]>([])
const isDrawing = ref(false)
const simMessage = ref('')
const ballReleased = ref(false)

let physics: PhysicsWorld | null = null
let animFrame = 0
let simTimer = 0
let settledFrames = 0

const level = computed(() => props.gameState.level)
const phase = computed(() => props.gameState.phase)
const isFinished = computed(() => phase.value === 'finished')
const isHost = computed(() => props.room.host_player_id === props.playerId)
const canDraw = computed(() => !isFinished.value && !physicsLoading.value)
const hasDrawnShapes = computed(() => drawnShapes.value.length > 0)

const levelLabel = computed(
  () => `Level ${props.gameState.level_index + 1} / ${props.gameState.levels_total}`,
)

function canvasPoint(e: MouseEvent): { x: number; y: number } | null {
  const canvas = canvasRef.value
  if (!canvas) return null
  const rect = canvas.getBoundingClientRect()
  const scaleX = canvas.width / rect.width
  const scaleY = canvas.height / rect.height
  return {
    x: (e.clientX - rect.left) * scaleX,
    y: (e.clientY - rect.top) * scaleY,
  }
}

function startStroke(e: MouseEvent) {
  if (!canDraw.value) return
  const pt = canvasPoint(e)
  if (!pt) return
  isDrawing.value = true
  currentStroke.value = [pt]
}

function moveStroke(e: MouseEvent) {
  if (!isDrawing.value || !canDraw.value) return
  const pt = canvasPoint(e)
  if (!pt) return
  const prev = currentStroke.value[currentStroke.value.length - 1]
  const delta = Math.hypot(pt.x - prev.x, pt.y - prev.y)
  if (delta < 3) return
  currentStroke.value.push(pt)
  drawFrame()
}

function endStroke() {
  if (!isDrawing.value) return
  isDrawing.value = false
  if (currentStroke.value.length >= 2 && physics) {
    const shape = addStrokeToWorld(physics, currentStroke.value)
    if (shape) {
      strokes.value.push([...currentStroke.value])
      drawnShapes.value.push(shape)
    }
  }
  currentStroke.value = []
  drawFrame()
}

function undoStroke() {
  if (!canDraw.value || drawnShapes.value.length === 0 || !physics) return
  const shape = drawnShapes.value.pop()
  if (shape) removeShapeFromWorld(physics, shape)
  strokes.value.pop()
  drawFrame()
}

function clearStrokes() {
  if (!canDraw.value || !physics) return
  removeAllDrawnShapes(physics)
  drawnShapes.value = []
  strokes.value = []
  currentStroke.value = []
  drawFrame()
}

function dropBall() {
  if (!physics || ballReleased.value || isFinished.value) return
  releaseBall(physics)
  ballReleased.value = true
  simMessage.value = ''
  settledFrames = 0
  emit('action', { type: 'start_simulation' })
  simTimer = window.setTimeout(() => {
    if (ballReleased.value && simMessage.value === '') {
      simMessage.value = 'Time up — try again!'
    }
  }, 30000)
}

function retryLevel() {
  emit('action', { type: 'retry_level' })
  resetLevelLocal()
}

function restartGame() {
  emit('action', { type: 'restart_game' })
  resetLevelLocal()
}

function onWin() {
  if (simMessage.value === 'Level complete!') return
  simMessage.value = 'Level complete!'
  if (simTimer) {
    window.clearTimeout(simTimer)
    simTimer = 0
  }
  emit('action', { type: 'level_complete' })
}

function initPhysics() {
  stopPhysics()
  physicsLoading.value = true
  try {
    physics = createPhysicsWorld(level.value, onWin)
    ballReleased.value = false
    runLoop()
  } finally {
    physicsLoading.value = false
    drawFrame()
  }
}

function stopPhysics() {
  if (simTimer) {
    window.clearTimeout(simTimer)
    simTimer = 0
  }
  if (animFrame) {
    cancelAnimationFrame(animFrame)
    animFrame = 0
  }
  physics?.cleanup()
  physics = null
}

function runLoop() {
  const tick = () => {
    if (!physics) return
    physics.step()
    if (ballReleased.value && isBallReleased(physics)) {
      if (isBallLost(physics)) {
        simMessage.value = 'Ball fell off — retry!'
      } else if (isBallSettled(physics)) {
        settledFrames += 1
        if (settledFrames > 120 && simMessage.value === '') {
          simMessage.value = 'Ball stopped — draw more or retry!'
        }
      } else {
        settledFrames = 0
      }
    }
    drawFrame()
    animFrame = requestAnimationFrame(tick)
  }
  animFrame = requestAnimationFrame(tick)
}

function drawShape(ctx: CanvasRenderingContext2D, shape: DrawnShape) {
  if (!physics || shape.localPolygon.length < 3) return
  const { x, y, angle } = getShapeCanvasTransform(shape)
  ctx.save()
  ctx.translate(x, y)
  ctx.rotate(angle)
  ctx.beginPath()
  ctx.moveTo(shape.localPolygon[0].x, shape.localPolygon[0].y)
  for (let i = 1; i < shape.localPolygon.length; i++) {
    ctx.lineTo(shape.localPolygon[i].x, shape.localPolygon[i].y)
  }
  ctx.closePath()
  ctx.fillStyle = '#f59e0b'
  ctx.fill()
  ctx.strokeStyle = '#d97706'
  ctx.lineWidth = 1.5
  ctx.stroke()
  ctx.restore()
}

function drawBall(ctx: CanvasRenderingContext2D) {
  if (!physics) return
  const { x, y } = getBallCanvasTransform(physics)
  ctx.beginPath()
  ctx.arc(x, y, level.value.ball.radius, 0, Math.PI * 2)
  ctx.fillStyle = ballReleased.value ? '#ef4444' : 'rgba(239, 68, 68, 0.55)'
  ctx.fill()
  ctx.strokeStyle = '#fca5a5'
  ctx.lineWidth = 2
  if (!ballReleased.value) {
    ctx.setLineDash([4, 4])
  }
  ctx.stroke()
  ctx.setLineDash([])
}

function drawFrame() {
  const canvas = canvasRef.value
  if (!canvas) return
  const ctx = canvas.getContext('2d')
  if (!ctx) return

  const w = level.value.world_width
  const h = level.value.world_height

  ctx.clearRect(0, 0, w, h)

  const gradient = ctx.createLinearGradient(0, 0, 0, h)
  gradient.addColorStop(0, '#0f172a')
  gradient.addColorStop(1, '#1e293b')
  ctx.fillStyle = gradient
  ctx.fillRect(0, 0, w, h)

  for (const body of level.value.static_bodies) {
    ctx.save()
    ctx.translate(body.x, body.y)
    if (body.angle) ctx.rotate(body.angle)
    ctx.fillStyle = '#64748b'
    if (body.type === 'circle') {
      ctx.beginPath()
      ctx.arc(0, 0, body.radius ?? 20, 0, Math.PI * 2)
      ctx.fill()
    } else {
      ctx.fillRect(-(body.width ?? 40) / 2, -(body.height ?? 16) / 2, body.width ?? 40, body.height ?? 16)
    }
    ctx.restore()
  }

  const target = level.value.target
  ctx.beginPath()
  ctx.arc(target.x, target.y, target.radius, 0, Math.PI * 2)
  ctx.fillStyle = 'rgba(34, 197, 94, 0.35)'
  ctx.fill()
  ctx.strokeStyle = '#22c55e'
  ctx.lineWidth = 3
  ctx.stroke()
  ctx.fillStyle = '#22c55e'
  ctx.font = 'bold 13px system-ui, sans-serif'
  ctx.textAlign = 'center'
  ctx.fillText('TARGET', target.x, target.y + 4)

  if (physics) {
    for (const shape of physics.drawnShapes) {
      drawShape(ctx, shape)
    }
    drawBall(ctx)
  }

  if (currentStroke.value.length >= 2) {
    const center = strokeCentroid(currentStroke.value)
    const local = worldToLocal(center, currentStroke.value)
    const preview = triangulateStroke(local)
    if (preview) {
      ctx.save()
      ctx.translate(center.x, center.y)
      ctx.beginPath()
      ctx.moveTo(preview.outline[0].x, preview.outline[0].y)
      for (let i = 1; i < preview.outline.length; i++) {
        ctx.lineTo(preview.outline[i].x, preview.outline[i].y)
      }
      ctx.closePath()
      ctx.fillStyle = 'rgba(245, 158, 11, 0.35)'
      ctx.fill()
      ctx.strokeStyle = 'rgba(245, 158, 11, 0.8)'
      ctx.lineWidth = 1.5
      ctx.stroke()
      ctx.restore()
    }
  }

  if (physicsLoading.value) {
    ctx.fillStyle = 'rgba(15, 23, 42, 0.65)'
    ctx.fillRect(0, 0, w, h)
    ctx.fillStyle = '#e2e8f0'
    ctx.font = '600 16px system-ui, sans-serif'
    ctx.textAlign = 'center'
    ctx.fillText('Loading physics…', w / 2, h / 2)
  }
}

function resizeCanvas() {
  const canvas = canvasRef.value
  if (!canvas) return
  canvas.width = level.value.world_width
  canvas.height = level.value.world_height
  drawFrame()
}

function resetLevelLocal() {
  stopPhysics()
  simMessage.value = ''
  strokes.value = []
  drawnShapes.value = []
  currentStroke.value = []
  ballReleased.value = false
  resizeCanvas()
  initPhysics()
}

watch(
  () => props.gameState.level_index,
  () => {
    resetLevelLocal()
  },
)

watch(
  () => props.gameState.phase,
  (newPhase, prevPhase) => {
    if (newPhase === 'finished') {
      stopPhysics()
      return
    }
    if (newPhase === 'drawing' && prevPhase === 'simulating') {
      resetLevelLocal()
    }
  },
)

onMounted(() => {
  resizeCanvas()
  initPhysics()
  window.addEventListener('resize', resizeCanvas)
})

onUnmounted(() => {
  stopPhysics()
  window.removeEventListener('resize', resizeCanvas)
})
</script>

<template>
  <div class="gravity-board">
    <aside class="sidebar card">
      <div class="level-badge">{{ levelLabel }}</div>
      <h2>{{ level.name }}</h2>
      <p class="hint">{{ level.hint }}</p>

      <div v-if="!isFinished" class="actions">
        <button
          type="button"
          class="btn-primary go-btn"
          :disabled="ballReleased || physicsLoading"
          @click="dropBall"
        >
          {{ ballReleased ? 'Ball rolling…' : 'Drop ball' }}
        </button>
        <button type="button" class="btn-secondary" :disabled="!hasDrawnShapes || physicsLoading" @click="undoStroke">
          Undo
        </button>
        <button type="button" class="btn-secondary" :disabled="!hasDrawnShapes || physicsLoading" @click="clearStrokes">
          Clear
        </button>
      </div>

      <p v-if="simMessage" class="sim-message" :class="{ success: simMessage.includes('complete') }">
        {{ simMessage }}
      </p>

      <div v-if="simMessage && !simMessage.includes('complete') && !isFinished" class="actions">
        <button type="button" class="btn-primary" @click="retryLevel">Retry level</button>
      </div>

      <div v-if="isFinished" class="victory card-inner">
        <h3>Gravity Master!</h3>
        <p>You cleared all {{ gameState.levels_total }} levels.</p>
        <button v-if="isHost" type="button" class="btn-primary" @click="restartGame">Play again</button>
      </div>

      <ul class="tips">
        <li>Draw any number of shapes — each one drops as a single piece.</li>
        <li>Build ramps and walls, then drop the ball.</li>
        <li>Keep drawing while the ball rolls if you need to.</li>
      </ul>
    </aside>

    <div class="canvas-wrap card">
      <canvas
        ref="canvasRef"
        class="game-canvas"
        :class="{ drawing: canDraw }"
        @mousedown="startStroke"
        @mousemove="moveStroke"
        @mouseup="endStroke"
        @mouseleave="endStroke"
      />
    </div>
  </div>
</template>

<style scoped>
.gravity-board {
  flex: 1;
  display: flex;
  gap: 1rem;
  padding: 0 1rem 1rem;
  min-height: 0;
  overflow: hidden;
}

.sidebar {
  width: 260px;
  flex-shrink: 0;
  padding: 1rem;
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
  overflow-y: auto;
}

.level-badge {
  font-size: 0.75rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  color: var(--accent);
}

.sidebar h2 {
  font-size: 1.15rem;
  margin: 0;
}

.hint {
  font-size: 0.85rem;
  color: var(--text-muted);
  margin: 0;
  line-height: 1.45;
}

.actions {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
}

.go-btn {
  flex: 1;
  min-width: 100%;
}

.sim-message {
  font-size: 0.9rem;
  font-weight: 600;
  color: var(--error);
  margin: 0;
}

.sim-message.success {
  color: var(--success);
}

.victory {
  background: rgba(34, 197, 94, 0.1);
  border: 1px solid rgba(34, 197, 94, 0.3);
  border-radius: var(--radius);
  padding: 0.75rem;
}

.victory h3 {
  margin: 0 0 0.35rem;
  color: var(--success);
}

.victory p {
  margin: 0 0 0.75rem;
  font-size: 0.85rem;
  color: var(--text-muted);
}

.tips {
  margin: auto 0 0;
  padding-left: 1.1rem;
  font-size: 0.78rem;
  color: var(--text-muted);
  line-height: 1.5;
}

.canvas-wrap {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 0.5rem;
  min-width: 0;
  min-height: 0;
}

.game-canvas {
  max-width: 100%;
  max-height: calc(100vh - 140px);
  width: auto;
  height: auto;
  border-radius: var(--radius);
  display: block;
}

.game-canvas.drawing {
  cursor: crosshair;
}

@media (max-width: 900px) {
  .gravity-board {
    flex-direction: column;
  }

  .sidebar {
    width: 100%;
  }
}
</style>
