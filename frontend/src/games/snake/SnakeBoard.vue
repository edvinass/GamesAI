<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import type { Room, SnakeGameState } from '@/types'

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

const playerRows = computed(() =>
  props.gameState.players.map((p) => ({
    ...p,
    snake: props.gameState.snakes[p.id],
  })),
)

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
  const direction = keyToDirection[e.key]
  if (!direction) return
  e.preventDefault()
  emit('action', { type: 'set_direction', direction })
}

function draw() {
  const canvas = canvasRef.value
  const wrap = canvasWrapRef.value
  if (!canvas || !wrap) return
  const ctx = canvas.getContext('2d')
  if (!ctx) return

  const { grid_width, grid_height, snakes, food } = props.gameState
  const displayW = wrap.clientWidth
  const displayH = wrap.clientHeight
  if (displayW <= 0 || displayH <= 0) return

  const dpr = window.devicePixelRatio || 1
  canvas.width = Math.floor(displayW * dpr)
  canvas.height = Math.floor(displayH * dpr)
  canvas.style.width = `${displayW}px`
  canvas.style.height = `${displayH}px`
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0)

  const cell = Math.min(displayW / grid_width, displayH / grid_height)
  const boardW = cell * grid_width
  const boardH = cell * grid_height
  const offsetX = (displayW - boardW) / 2
  const offsetY = (displayH - boardH) / 2

  ctx.fillStyle = '#0f1419'
  ctx.fillRect(0, 0, displayW, displayH)
  ctx.fillRect(offsetX, offsetY, boardW, boardH)

  ctx.strokeStyle = '#1e293b'
  ctx.lineWidth = 1
  for (let x = 0; x <= grid_width; x++) {
    ctx.beginPath()
    ctx.moveTo(offsetX + x * cell, offsetY)
    ctx.lineTo(offsetX + x * cell, offsetY + boardH)
    ctx.stroke()
  }
  for (let y = 0; y <= grid_height; y++) {
    ctx.beginPath()
    ctx.moveTo(offsetX, offsetY + y * cell)
    ctx.lineTo(offsetX + boardW, offsetY + y * cell)
    ctx.stroke()
  }

  if (food) {
    ctx.fillStyle = '#f43f5e'
    const pad = Math.max(2, cell * 0.15)
    ctx.beginPath()
    ctx.arc(
      offsetX + food[0] * cell + cell / 2,
      offsetY + food[1] * cell + cell / 2,
      cell / 2 - pad,
      0,
      Math.PI * 2,
    )
    ctx.fill()
  }

  for (const [pid, snake] of Object.entries(snakes)) {
    const isMe = pid === props.playerId
    const alpha = snake.alive ? 1 : 0.35
    snake.body.forEach((seg, i) => {
      const color = snake.color
      ctx.globalAlpha = alpha
      ctx.fillStyle = i === 0 ? color : color + 'cc'
      const inset = Math.max(1, cell * 0.08)
      ctx.fillRect(
        offsetX + seg[0] * cell + inset,
        offsetY + seg[1] * cell + inset,
        cell - inset * 2,
        cell - inset * 2,
      )
      if (isMe && i === 0 && snake.alive) {
        ctx.strokeStyle = '#fff'
        ctx.lineWidth = Math.max(1, cell * 0.08)
        ctx.strokeRect(
          offsetX + seg[0] * cell + 1,
          offsetY + seg[1] * cell + 1,
          cell - 2,
          cell - 2,
        )
      }
    })
    ctx.globalAlpha = 1
  }
}

let resizeObserver: ResizeObserver | null = null

watch(() => props.gameState, draw, { deep: true })

onMounted(() => {
  window.addEventListener('keydown', onKeyDown)
  if (canvasWrapRef.value) {
    resizeObserver = new ResizeObserver(() => draw())
    resizeObserver.observe(canvasWrapRef.value)
  }
  draw()
})

onUnmounted(() => {
  window.removeEventListener('keydown', onKeyDown)
  resizeObserver?.disconnect()
})
</script>

<template>
  <div class="snake-board">
    <div ref="canvasWrapRef" class="canvas-wrap">
      <canvas ref="canvasRef" class="game-canvas" />

      <div v-if="gameState.phase === 'countdown'" class="overlay countdown">
        <span class="overlay-value">{{ countdownRemaining ?? '…' }}</span>
        <span class="overlay-label">Get ready!</span>
      </div>

      <div v-else-if="isFinished" class="overlay finished">
        <span class="overlay-label">Game over</span>
        <span class="overlay-value">{{ winnerName }} wins!</span>
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
          <span class="score">{{ row.snake?.score ?? 0 }}</span>
          <span v-if="!row.snake?.alive" class="status">out</span>
        </li>
      </ul>

      <div class="controls-hint">
        <p v-if="canControl"><strong>Controls:</strong> Arrow keys or WASD</p>
        <p v-else-if="gameState.phase === 'playing' && !isAlive" class="muted">Spectating</p>
        <p v-else class="muted">Waiting to start…</p>
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
  border: 1px solid var(--border);
  border-radius: var(--radius);
  background: #0f1419;
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
  background: rgba(0, 0, 0, 0.65);
  gap: 0.5rem;
  padding: 1rem;
  text-align: center;
}

.overlay-value {
  font-size: clamp(1.75rem, 4vw, 2.5rem);
  font-weight: 800;
}

.overlay-label {
  font-size: 1.1rem;
  font-weight: 600;
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
  border: 1px solid var(--border);
  border-radius: var(--radius);
  background: var(--surface);
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
}

.player-score-row.me {
  font-weight: 700;
}

.player-score-row.dead {
  opacity: 0.55;
}

.color-dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  flex-shrink: 0;
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
}

.status {
  font-size: 0.7rem;
  text-transform: uppercase;
  color: var(--text-muted);
}

.controls-hint {
  flex-shrink: 0;
  font-size: 0.85rem;
  color: var(--text-muted);
  text-align: right;
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
