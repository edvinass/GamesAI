<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import type { Room, SnakeGameState } from '@/types'
import {
  interpolateBody,
  renderFrame,
  spawnEatParticles,
  updateParticles,
  FOOD_PARTICLE_COLORS,
  type Particle,
  type Point,
  type SnakeSnapshot,
} from './snakeRender'
import type { SnakeFood, SnakeFoodType } from '@/types'

const props = defineProps<{
  gameState: SnakeGameState
  room: Room
  playerId: string
}>()

const emit = defineEmits<{
  action: [data: Record<string, unknown>]
}>()

const canvasRef = ref<HTMLCanvasElement | null>(null)
const canvasWrapRef = ref<HTMLElement | null>(null)

const mySnake = computed(() => props.gameState.snakes[props.playerId])
const isAlive = computed(() => mySnake.value?.alive ?? false)
const isHost = computed(() => props.room.host_player_id === props.playerId)
const isFinished = computed(() => props.gameState.phase === 'finished')
const canControl = computed(
  () => props.gameState.phase === 'playing' && isAlive.value,
)

const countdownRemaining = computed(() => {
  if (props.gameState.phase !== 'countdown' || !props.gameState.countdown_ends_at) return null
  const end = new Date(props.gameState.countdown_ends_at).getTime()
  const sec = Math.max(0, Math.ceil((end - Date.now()) / 1000))
  return sec
})

const winnerName = computed(() => {
  const winnerId = props.gameState.winner
  if (!winnerId) return null
  const player = props.gameState.players.find((p) => p.id === winnerId)
  return player?.nickname ?? 'Unknown'
})

const scoreToWin = computed(() => props.gameState.score_to_win ?? 50)

const winReasonLabel = computed(() => {
  const reason = props.gameState.win_reason
  if (reason === 'score_limit') return `First to ${scoreToWin.value}`
  if (reason === 'last_standing') return 'Last snake standing'
  if (reason === 'highest_score') return 'Highest score'
  return null
})

const playerRows = computed(() =>
  props.gameState.players.map((p) => ({
    ...p,
    snake: props.gameState.snakes[p.id],
  })),
)

const myAmmo = computed(() => mySnake.value?.ammo ?? 0)

const keyToDirection: Record<string, string> = {
  ArrowUp: 'up',
  ArrowDown: 'down',
  ArrowLeft: 'left',
  ArrowRight: 'right',
  w: 'up',
  W: 'up',
  s: 'down',
  S: 'down',
  a: 'left',
  A: 'left',
  d: 'right',
  D: 'right',
}

function startNewGame() {
  emit('action', { type: 'start_game' })
}

function onKeyDown(e: KeyboardEvent) {
  if (!canControl.value) return
  if (e.key === ' ' || e.code === 'Space') {
    e.preventDefault()
    if (myAmmo.value > 0) {
      emit('action', { type: 'shoot' })
    }
    return
  }
  const direction = keyToDirection[e.key]
  if (!direction) return
  e.preventDefault()
  emit('action', { type: 'set_direction', direction })
}

function snapshotSnakes(state: SnakeGameState): Record<string, SnakeSnapshot> {
  const out: Record<string, SnakeSnapshot> = {}
  const tick = state.tick
  for (const [pid, snake] of Object.entries(state.snakes)) {
    out[pid] = {
      body: snake.body.map((s) => [...s]),
      direction: snake.direction,
      alive: snake.alive,
      color: snake.color,
      score: snake.score,
      ghost: (snake.ghost_until_tick ?? -1) >= tick,
    }
  }
  return out
}

function easeOutCubic(t: number) {
  return 1 - (1 - t) ** 3
}

let rafId = 0
let resizeObserver: ResizeObserver | null = null
let lastFrameTime = performance.now()
let tickReceivedAt = performance.now()
let lastTick = -1
/** Bodies from the previous tick — lerp origin. */
let prevSnakes: Record<string, SnakeSnapshot> = {}
/** Bodies from the current tick — lerp target. */
let targetSnakes: Record<string, SnakeSnapshot> = {}
let particles: Particle[] = []
let lastFoods: SnakeFood[] = []

function onStateSync() {
  const tick = props.gameState.tick
  const snap = snapshotSnakes(props.gameState)

  if (tick !== lastTick) {
    prevSnakes = Object.keys(targetSnakes).length ? targetSnakes : snap
    targetSnakes = snap
    lastTick = tick
    tickReceivedAt = performance.now()
  } else {
    // Same tick but state refreshed (e.g. direction change) — keep motion origin
    targetSnakes = snap
    if (!Object.keys(prevSnakes).length) prevSnakes = snap
  }

  const foods = props.gameState.foods ?? []
  for (const prev of lastFoods) {
    const stillThere = foods.some(
      (f) => f.x === prev.x && f.y === prev.y && f.type === prev.type,
    )
    if (!stillThere) {
      const foodType = (prev.type in FOOD_PARTICLE_COLORS ? prev.type : 'apple') as SnakeFoodType
      particles.push(...spawnEatParticles([prev.x, prev.y], FOOD_PARTICLE_COLORS[foodType]))
    }
  }
  lastFoods = foods.map((f) => ({ ...f }))
}

watch(() => props.gameState, onStateSync, { deep: true, immediate: true })

function paint(now: number) {
  const canvas = canvasRef.value
  const wrap = canvasWrapRef.value
  if (!canvas || !wrap) return
  const ctx = canvas.getContext('2d')
  if (!ctx) return

  const dt = Math.min(0.05, (now - lastFrameTime) / 1000)
  lastFrameTime = now
  particles = updateParticles(particles, dt)

  const displayW = wrap.clientWidth
  const displayH = wrap.clientHeight
  if (displayW <= 0 || displayH <= 0) return

  const dpr = window.devicePixelRatio || 1
  const needW = Math.floor(displayW * dpr)
  const needH = Math.floor(displayH * dpr)
  if (canvas.width !== needW || canvas.height !== needH) {
    canvas.width = needW
    canvas.height = needH
    canvas.style.width = `${displayW}px`
    canvas.style.height = `${displayH}px`
  }
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0)

  const { grid_width, grid_height, foods } = props.gameState
  const tickMs =
    props.gameState.tick_ms ?? Number(props.room.settings?.tick_ms ?? 130)

  const rawT =
    props.gameState.phase === 'playing'
      ? Math.min(1, (now - tickReceivedAt) / Math.max(16, tickMs))
      : 1
  const t = easeOutCubic(rawT)

  const rendered: Record<
    string,
    { body: Point[]; direction: string; color: string; alive: boolean; ghost?: boolean }
  > = {}

  for (const [pid, snake] of Object.entries(props.gameState.snakes)) {
    const prev = prevSnakes[pid]
    const target = targetSnakes[pid] ?? snake
    rendered[pid] = {
      body: interpolateBody(prev?.body, target.body, t, grid_width, grid_height),
      direction: target.direction,
      color: target.color,
      alive: target.alive,
      ghost: target.ghost,
    }
  }

  renderFrame(ctx, displayW, displayH, {
    gridW: grid_width,
    gridH: grid_height,
    foods: foods ?? [],
    projectiles: props.gameState.projectiles ?? [],
    snakes: rendered,
    playerId: props.playerId,
    particles,
    time: now,
  })
}

function loop(now: number) {
  paint(now)
  rafId = requestAnimationFrame(loop)
}

onMounted(() => {
  window.addEventListener('keydown', onKeyDown)
  if (canvasWrapRef.value) {
    resizeObserver = new ResizeObserver(() => {
      /* next rAF paints at new size */
    })
    resizeObserver.observe(canvasWrapRef.value)
  }
  lastFrameTime = performance.now()
  rafId = requestAnimationFrame(loop)
})

onUnmounted(() => {
  window.removeEventListener('keydown', onKeyDown)
  resizeObserver?.disconnect()
  cancelAnimationFrame(rafId)
})
</script>

<template>
  <div class="snake-board">
    <div ref="canvasWrapRef" class="canvas-wrap">
      <canvas ref="canvasRef" class="game-canvas" />

      <div v-if="gameState.phase === 'countdown'" class="overlay countdown">
        <span class="overlay-value pulse">{{ countdownRemaining ?? '…' }}</span>
        <span class="overlay-label">Get ready!</span>
      </div>

      <div v-else-if="isFinished" class="overlay finished">
        <span class="overlay-label">{{ winReasonLabel ?? 'Game over' }}</span>
        <span class="overlay-value win-pop">{{ winnerName }} wins!</span>
        <button v-if="isHost" type="button" class="btn-primary play-again-btn" @click="startNewGame">
          Play Again
        </button>
        <p v-else class="overlay-hint">Waiting for host to start a new game…</p>
      </div>

      <div v-else-if="!isAlive" class="overlay eliminated">
        <span class="overlay-label">You were eliminated</span>
        <span class="overlay-hint">Watch the battle continue…</span>
      </div>
    </div>

    <aside class="player-bar">
      <ul class="player-scores">
        <li
          v-for="row in playerRows"
          :key="row.id"
          class="player-score-row"
          :class="{ me: row.id === playerId, dead: !row.snake?.alive }"
        >
          <span class="color-dot" :style="{ background: row.snake?.color ?? '#666' }" />
          <span class="name">{{ row.nickname }}</span>
          <span class="score">{{ row.snake?.score ?? 0 }}<span class="score-cap">/{{ scoreToWin }}</span></span>
          <span v-if="(row.snake?.ammo ?? 0) > 0" class="ammo" title="Shots">⚡{{ row.snake?.ammo }}</span>
          <span v-if="!row.snake?.alive" class="status">out</span>
        </li>
      </ul>

      <div class="controls-hint">
        <p v-if="canControl">
          <strong>Controls:</strong> Arrow keys / WASD
          <span v-if="myAmmo > 0"> · <strong>Space</strong> shoot ({{ myAmmo }})</span>
          <span v-else class="muted"> · eat orange ammo to shoot</span>
        </p>
        <p v-else-if="gameState.phase === 'playing' && !isAlive" class="muted">Spectating</p>
        <p v-else class="muted">Waiting to start…</p>
        <ul class="food-legend">
          <li><span class="swatch apple" />Apple +1</li>
          <li><span class="swatch golden" />Gold +3</li>
          <li><span class="swatch poison" />Poison shrink</li>
          <li><span class="swatch ghost" />Ghost phase</li>
          <li><span class="swatch ammo" />Ammo shots</li>
        </ul>
      </div>
    </aside>
  </div>
</template>

<style scoped>
.snake-board {
  flex: 1;
  width: 100%;
  min-height: 0;
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
  padding: 0 0.5rem 0.5rem;
}

.canvas-wrap {
  position: relative;
  flex: 1;
  min-height: 0;
  width: 100%;
  overflow: hidden;
  border: 1px solid rgba(74, 222, 128, 0.22);
  border-radius: var(--radius);
  background:
    radial-gradient(ellipse at 50% 30%, rgba(34, 100, 60, 0.35), transparent 55%),
    #0a1210;
  box-shadow:
    inset 0 0 40px rgba(0, 0, 0, 0.35),
    0 0 24px rgba(34, 197, 94, 0.08);
}

.game-canvas {
  display: block;
  width: 100%;
  height: 100%;
}

.overlay {
  position: absolute;
  inset: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  background: rgba(4, 12, 8, 0.72);
  backdrop-filter: blur(4px);
  gap: 0.5rem;
  padding: 1rem;
  text-align: center;
  animation: overlay-in 0.35s var(--ease-smooth);
}

@keyframes overlay-in {
  from {
    opacity: 0;
  }
  to {
    opacity: 1;
  }
}

.overlay-value {
  font-family: 'Outfit', 'DM Sans', system-ui, sans-serif;
  font-size: clamp(1.75rem, 4vw, 2.75rem);
  font-weight: 800;
  letter-spacing: -0.02em;
  text-shadow: 0 0 28px rgba(74, 222, 128, 0.35);
}

.overlay-value.pulse {
  animation: count-pulse 1s var(--ease-bounce) infinite;
}

.overlay-value.win-pop {
  animation: win-pop 0.55s var(--ease-bounce);
}

@keyframes count-pulse {
  0%,
  100% {
    transform: scale(1);
  }
  50% {
    transform: scale(1.12);
  }
}

@keyframes win-pop {
  0% {
    transform: scale(0.6);
    opacity: 0;
  }
  100% {
    transform: scale(1);
    opacity: 1;
  }
}

.overlay-label {
  font-size: 1.1rem;
  font-weight: 600;
  color: #c8e6d0;
}

.overlay-hint {
  font-size: 0.9rem;
  color: var(--text-muted);
}

.play-again-btn {
  margin-top: 0.5rem;
}

.player-bar {
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1rem;
  padding: 0.65rem 1rem;
  border: 1px solid rgba(74, 222, 128, 0.18);
  border-radius: var(--radius);
  background: linear-gradient(180deg, rgba(22, 40, 30, 0.95), rgba(15, 24, 20, 0.98));
}

.player-scores {
  list-style: none;
  display: flex;
  flex-wrap: wrap;
  gap: 0.75rem 1.25rem;
  flex: 1;
  min-width: 0;
}

.player-score-row {
  display: flex;
  align-items: center;
  gap: 0.45rem;
  font-size: 0.9rem;
  transition:
    opacity 0.3s var(--ease-smooth),
    transform 0.3s var(--ease-smooth);
}

.player-score-row.me {
  font-weight: 700;
}

.player-score-row.me .color-dot {
  animation: me-glow 1.6s ease-in-out infinite;
}

.player-score-row.dead {
  opacity: 0.45;
  transform: scale(0.97);
}

@keyframes me-glow {
  0%,
  100% {
    box-shadow: 0 0 6px rgba(255, 255, 255, 0.35);
  }
  50% {
    box-shadow: 0 0 14px rgba(74, 222, 128, 0.7);
  }
}

.color-dot {
  width: 12px;
  height: 12px;
  border-radius: 50%;
  flex-shrink: 0;
  border: 1px solid rgba(255, 255, 255, 0.25);
}

.name {
  max-width: 10rem;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.score {
  font-variant-numeric: tabular-nums;
  font-weight: 600;
  min-width: 1.25rem;
}

.score-cap {
  font-weight: 500;
  font-size: 0.75em;
  opacity: 0.55;
  margin-left: 0.05rem;
}

.ammo {
  font-size: 0.75rem;
  font-variant-numeric: tabular-nums;
  color: #fb923c;
  font-weight: 700;
}

.status {
  font-size: 0.7rem;
  text-transform: uppercase;
  color: var(--text-muted);
  letter-spacing: 0.04em;
}

.controls-hint {
  flex-shrink: 0;
  font-size: 0.85rem;
  color: var(--text-muted);
  text-align: right;
}

.food-legend {
  list-style: none;
  display: flex;
  flex-wrap: wrap;
  justify-content: flex-end;
  gap: 0.35rem 0.75rem;
  margin-top: 0.35rem;
  font-size: 0.72rem;
  color: var(--text-muted);
}

.food-legend li {
  display: flex;
  align-items: center;
  gap: 0.28rem;
}

.swatch {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  flex-shrink: 0;
  box-shadow: 0 0 6px currentColor;
}

.swatch.apple {
  background: #ef4444;
  color: #ef4444;
}

.swatch.golden {
  background: #fbbf24;
  color: #fbbf24;
}

.swatch.poison {
  background: #84cc16;
  color: #84cc16;
}

.swatch.ghost {
  background: #22d3ee;
  color: #22d3ee;
}

.swatch.ammo {
  background: #fb923c;
  color: #fb923c;
}

@media (max-width: 640px) {
  .player-bar {
    flex-direction: column;
    align-items: flex-start;
  }

  .controls-hint {
    text-align: left;
  }
}

.muted {
  color: var(--text-muted);
}
</style>
