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
const cellSize = 18

const mySnake = computed(() => props.gameState.snakes[props.playerId])
const isAlive = computed(() => mySnake.value?.alive ?? false)
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

function onKeyDown(e: KeyboardEvent) {
  if (!canControl.value) return
  const direction = keyToDirection[e.key]
  if (!direction) return
  e.preventDefault()
  emit('action', { type: 'set_direction', direction })
}

function draw() {
  const canvas = canvasRef.value
  if (!canvas) return
  const ctx = canvas.getContext('2d')
  if (!ctx) return

  const { grid_width, grid_height, snakes, food } = props.gameState
  canvas.width = grid_width * cellSize
  canvas.height = grid_height * cellSize

  ctx.fillStyle = '#0f1419'
  ctx.fillRect(0, 0, canvas.width, canvas.height)

  ctx.strokeStyle = '#1e293b'
  ctx.lineWidth = 1
  for (let x = 0; x <= grid_width; x++) {
    ctx.beginPath()
    ctx.moveTo(x * cellSize, 0)
    ctx.lineTo(x * cellSize, canvas.height)
    ctx.stroke()
  }
  for (let y = 0; y <= grid_height; y++) {
    ctx.beginPath()
    ctx.moveTo(0, y * cellSize)
    ctx.lineTo(canvas.width, y * cellSize)
    ctx.stroke()
  }

  if (food) {
    ctx.fillStyle = '#f43f5e'
    const pad = 3
    ctx.beginPath()
    ctx.arc(
      food[0] * cellSize + cellSize / 2,
      food[1] * cellSize + cellSize / 2,
      cellSize / 2 - pad,
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
      const inset = i === 0 ? 1 : 2
      ctx.fillRect(
        seg[0] * cellSize + inset,
        seg[1] * cellSize + inset,
        cellSize - inset * 2,
        cellSize - inset * 2,
      )
      if (isMe && i === 0 && snake.alive) {
        ctx.strokeStyle = '#fff'
        ctx.lineWidth = 2
        ctx.strokeRect(
          seg[0] * cellSize + 1,
          seg[1] * cellSize + 1,
          cellSize - 2,
          cellSize - 2,
        )
      }
    })
    ctx.globalAlpha = 1
  }
}

watch(() => props.gameState, draw, { deep: true })

onMounted(() => {
  window.addEventListener('keydown', onKeyDown)
  draw()
})

onUnmounted(() => {
  window.removeEventListener('keydown', onKeyDown)
})
</script>

<template>
  <div class="snake-board container-wide">
    <div class="board-layout">
      <div class="canvas-wrap card">
        <canvas ref="canvasRef" class="game-canvas" />

        <div v-if="gameState.phase === 'countdown'" class="overlay countdown">
          <span class="overlay-value">{{ countdownRemaining ?? '…' }}</span>
          <span class="overlay-label">Get ready!</span>
        </div>

        <div v-else-if="gameState.phase === 'finished'" class="overlay finished">
          <span class="overlay-label">Game over</span>
          <span class="overlay-value">{{ winnerName }} wins!</span>
        </div>

        <div v-else-if="!isAlive" class="overlay eliminated">
          <span class="overlay-label">You were eliminated</span>
          <span class="overlay-hint">Watch the battle continue…</span>
        </div>
      </div>

      <aside class="sidebar card">
        <h2>Players</h2>
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
  </div>
</template>

<style scoped>
.snake-board {
  padding-top: 0.5rem;
}

.board-layout {
  display: grid;
  grid-template-columns: 1fr 220px;
  gap: 1rem;
  align-items: start;
}

@media (max-width: 768px) {
  .board-layout {
    grid-template-columns: 1fr;
  }
}

.canvas-wrap {
  position: relative;
  overflow: auto;
  padding: 0.5rem;
  display: flex;
  justify-content: center;
}

.game-canvas {
  display: block;
  border-radius: 4px;
}

.overlay {
  position: absolute;
  inset: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  background: rgba(0, 0, 0, 0.65);
  border-radius: 4px;
  gap: 0.35rem;
}

.overlay-value {
  font-size: 2.5rem;
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

.sidebar h2 {
  font-size: 1rem;
  margin-bottom: 0.75rem;
}

.player-scores {
  list-style: none;
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
  margin-bottom: 1rem;
}

.player-score-row {
  display: flex;
  align-items: center;
  gap: 0.5rem;
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
  flex: 1;
  min-width: 0;
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
  font-size: 0.85rem;
  color: var(--text-muted);
  border-top: 1px solid var(--border);
  padding-top: 0.75rem;
}

.muted {
  color: var(--text-muted);
}
</style>
