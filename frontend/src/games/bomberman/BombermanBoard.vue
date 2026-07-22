<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import type { Room, BombermanGameState } from '@/types'
import {
  interpolateBombers,
  renderFrame,
  snapshotBombers,
  type BomberSnapshot,
} from './bombermanRender'

const props = defineProps<{
  gameState: BombermanGameState
  room: Room
  playerId: string
}>()

const emit = defineEmits<{
  action: [data: Record<string, unknown>]
}>()

const canvasRef = ref<HTMLCanvasElement | null>(null)
const canvasWrapRef = ref<HTMLElement | null>(null)

const myBomber = computed(() => props.gameState.bombers[props.playerId])
const isAlive = computed(() => myBomber.value?.alive ?? false)
const isHost = computed(() => props.room.host_player_id === props.playerId)
const isFinished = computed(() => props.gameState.phase === 'finished')
const canControl = computed(
  () => props.gameState.phase === 'playing' && isAlive.value,
)

const countdownRemaining = computed(() => {
  if (props.gameState.phase !== 'countdown' || !props.gameState.countdown_ends_at) return null
  const end = new Date(props.gameState.countdown_ends_at).getTime()
  return Math.max(0, Math.ceil((end - Date.now()) / 1000))
})

const winnerName = computed(() => {
  const winnerId = props.gameState.winner
  if (!winnerId) return null
  return props.gameState.players.find((p) => p.id === winnerId)?.nickname ?? 'Unknown'
})

const winReasonLabel = computed(() => {
  const reason = props.gameState.win_reason
  if (reason === 'last_standing') return 'Last bomber standing'
  if (reason === 'most_kills') return 'Most kills'
  return null
})

const playerRows = computed(() =>
  props.gameState.players.map((p) => ({
    ...p,
    bomber: props.gameState.bombers[p.id],
  })),
)

const myActiveBombs = computed(() =>
  (props.gameState.bombs ?? []).filter((b) => b.owner_id === props.playerId).length,
)

/** Physical key codes — stable across layouts; most-recent direction wins. */
const codeToDirection: Record<string, string> = {
  ArrowUp: 'up',
  ArrowDown: 'down',
  ArrowLeft: 'left',
  ArrowRight: 'right',
  KeyW: 'up',
  KeyS: 'down',
  KeyA: 'left',
  KeyD: 'right',
}

/** Held directions, oldest → newest (last entry is active). */
const directionStack: string[] = []
let currentDirection = 'stop'

function desiredDirection(): string {
  return directionStack.length ? directionStack[directionStack.length - 1]! : 'stop'
}

function emitDirection(force = false) {
  const next = desiredDirection()
  if (!force && next === currentDirection) return
  currentDirection = next
  emit('action', { type: 'set_direction', direction: next })
}

function clearMovementInput() {
  directionStack.length = 0
  if (currentDirection !== 'stop') {
    currentDirection = 'stop'
    emit('action', { type: 'set_direction', direction: 'stop' })
  } else {
    currentDirection = 'stop'
  }
}

function startNewGame() {
  emit('action', { type: 'start_game' })
}

function onKeyDown(e: KeyboardEvent) {
  if (!canControl.value) return
  if (e.code === 'Space' || e.key === ' ') {
    e.preventDefault()
    if (!e.repeat) emit('action', { type: 'place_bomb' })
    return
  }
  const direction = codeToDirection[e.code]
  if (!direction) return
  e.preventDefault()
  if (e.repeat) return
  const idx = directionStack.indexOf(direction)
  if (idx >= 0) directionStack.splice(idx, 1)
  directionStack.push(direction)
  emitDirection()
}

function onKeyUp(e: KeyboardEvent) {
  const direction = codeToDirection[e.code]
  if (!direction) return
  e.preventDefault()
  const idx = directionStack.indexOf(direction)
  if (idx >= 0) directionStack.splice(idx, 1)
  if (!canControl.value) {
    directionStack.length = 0
    currentDirection = 'stop'
    return
  }
  emitDirection()
}

function onWindowBlur() {
  clearMovementInput()
}

function easeLinear(t: number) {
  return t
}

let rafId = 0
let resizeObserver: ResizeObserver | null = null
let tickReceivedAt = performance.now()
let lastTick = -1
let prevBombers: Record<string, BomberSnapshot> = {}
let targetBombers: Record<string, BomberSnapshot> = {}

function onStateSync() {
  const tick = props.gameState.tick
  const snap = snapshotBombers(props.gameState.bombers)
  if (tick !== lastTick) {
    prevBombers = Object.keys(targetBombers).length ? targetBombers : snap
    targetBombers = snap
    lastTick = tick
    tickReceivedAt = performance.now()
  } else {
    targetBombers = snap
    if (!Object.keys(prevBombers).length) prevBombers = snap
  }
}

watch(() => props.gameState, onStateSync, { deep: true, immediate: true })

watch(canControl, (ok) => {
  if (!ok) {
    directionStack.length = 0
    currentDirection = 'stop'
  } else if (desiredDirection() !== 'stop') {
    // Re-assert held direction after countdown / reconnect.
    emitDirection(true)
  }
})

function paint(now: number) {
  const canvas = canvasRef.value
  const wrap = canvasWrapRef.value
  if (!canvas || !wrap) return
  const ctx = canvas.getContext('2d')
  if (!ctx) return

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

  const tickMs =
    props.gameState.tick_ms ?? Number(props.room.settings?.tick_ms ?? 150)
  const rawT =
    props.gameState.phase === 'playing'
      ? Math.min(1, (now - tickReceivedAt) / Math.max(16, tickMs))
      : 1
  const t = easeLinear(rawT)
  const rendered = interpolateBombers(prevBombers, targetBombers, t)

  renderFrame(ctx, displayW, displayH, {
    gridW: props.gameState.grid_width,
    gridH: props.gameState.grid_height,
    grid: props.gameState.grid,
    bombers: rendered,
    bombs: props.gameState.bombs ?? [],
    explosions: props.gameState.explosions ?? [],
    powerups: props.gameState.powerups ?? [],
    playerId: props.playerId,
    time: now,
  })
}

function loop(now: number) {
  paint(now)
  rafId = requestAnimationFrame(loop)
}

onMounted(() => {
  window.addEventListener('keydown', onKeyDown)
  window.addEventListener('keyup', onKeyUp)
  window.addEventListener('blur', onWindowBlur)
  if (canvasWrapRef.value) {
    resizeObserver = new ResizeObserver(() => {})
    resizeObserver.observe(canvasWrapRef.value)
  }
  rafId = requestAnimationFrame(loop)
})

onUnmounted(() => {
  window.removeEventListener('keydown', onKeyDown)
  window.removeEventListener('keyup', onKeyUp)
  window.removeEventListener('blur', onWindowBlur)
  resizeObserver?.disconnect()
  cancelAnimationFrame(rafId)
})
</script>

<template>
  <div class="bomberman-board">
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
        <span class="overlay-hint">Spectating the rest of the match…</span>
      </div>
    </div>

    <aside class="player-bar">
      <ul class="player-scores">
        <li
          v-for="row in playerRows"
          :key="row.id"
          class="player-score-row"
          :class="{ me: row.id === playerId, dead: !row.bomber?.alive }"
        >
          <span class="color-dot" :style="{ background: row.bomber?.color ?? '#666' }" />
          <span class="name">{{ row.nickname }}</span>
          <span class="stats" title="Bombs / Range / Speed">
            💣{{ row.bomber?.max_bombs ?? 1 }}
            · 🔥{{ row.bomber?.bomb_range ?? 1 }}
            · ⚡{{ row.bomber?.speed_level ?? 0 }}
          </span>
          <span v-if="(row.bomber?.kills ?? 0) > 0" class="kills">×{{ row.bomber?.kills }}</span>
          <span v-if="!row.bomber?.alive" class="status">out</span>
        </li>
      </ul>

      <div class="controls-hint">
        <p v-if="canControl">
          <strong>Controls:</strong> Hold arrows / WASD ·
          <strong>Space</strong> bomb
          <span class="muted">({{ myActiveBombs }}/{{ myBomber?.max_bombs ?? 1 }})</span>
        </p>
        <p v-else-if="gameState.phase === 'playing' && !isAlive" class="muted">Spectating</p>
        <p v-else class="muted">Waiting to start…</p>
        <ul class="power-legend">
          <li><span class="swatch bomb" />Bomb+</li>
          <li><span class="swatch range" />Range+</li>
          <li><span class="swatch speed" />Speed+</li>
        </ul>
      </div>
    </aside>
  </div>
</template>

<style scoped>
.bomberman-board {
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
  border: 1px solid rgba(249, 115, 22, 0.28);
  border-radius: var(--radius);
  background:
    radial-gradient(ellipse at 50% 20%, rgba(180, 70, 20, 0.25), transparent 55%),
    #0c1218;
  box-shadow:
    inset 0 0 40px rgba(0, 0, 0, 0.4),
    0 0 24px rgba(249, 115, 22, 0.08);
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
  background: rgba(8, 10, 14, 0.72);
  backdrop-filter: blur(4px);
  gap: 0.5rem;
  padding: 1rem;
  text-align: center;
}

.overlay-value {
  font-family: 'Outfit', 'DM Sans', system-ui, sans-serif;
  font-size: clamp(1.75rem, 4vw, 2.75rem);
  font-weight: 800;
  letter-spacing: -0.02em;
  text-shadow: 0 0 28px rgba(249, 115, 22, 0.4);
}

.overlay-value.pulse {
  animation: count-pulse 1s ease-in-out infinite;
}

.overlay-value.win-pop {
  animation: win-pop 0.55s cubic-bezier(0.34, 1.56, 0.64, 1);
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
  color: #f3d5b5;
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
  border: 1px solid rgba(249, 115, 22, 0.2);
  border-radius: var(--radius);
  background: linear-gradient(180deg, rgba(40, 28, 18, 0.95), rgba(18, 14, 12, 0.98));
  flex-wrap: wrap;
}

.player-scores {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem 1rem;
}

.player-score-row {
  display: flex;
  align-items: center;
  gap: 0.4rem;
  font-size: 0.85rem;
}

.player-score-row.me {
  font-weight: 700;
}

.player-score-row.dead {
  opacity: 0.45;
}

.color-dot {
  width: 0.65rem;
  height: 0.65rem;
  border-radius: 50%;
  flex-shrink: 0;
}

.name {
  max-width: 7rem;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.stats {
  font-size: 0.75rem;
  color: var(--text-muted);
}

.kills {
  font-size: 0.75rem;
  color: #f97316;
}

.status {
  font-size: 0.7rem;
  text-transform: uppercase;
  color: var(--text-muted);
}

.controls-hint {
  font-size: 0.8rem;
  color: var(--text-muted);
}

.controls-hint .muted {
  opacity: 0.75;
}

.power-legend {
  list-style: none;
  margin: 0.35rem 0 0;
  padding: 0;
  display: flex;
  gap: 0.75rem;
  font-size: 0.75rem;
}

.power-legend li {
  display: flex;
  align-items: center;
  gap: 0.3rem;
}

.swatch {
  width: 0.7rem;
  height: 0.7rem;
  border-radius: 50%;
}

.swatch.bomb {
  background: #f97316;
}

.swatch.range {
  background: #38bdf8;
}

.swatch.speed {
  background: #a3e635;
}

@media (max-width: 720px) {
  .player-bar {
    flex-direction: column;
    align-items: flex-start;
  }
}
</style>
