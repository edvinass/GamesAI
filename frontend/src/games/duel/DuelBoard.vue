<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import type { Room, DuelGameState } from '@/types'

const props = defineProps<{
  gameState: DuelGameState
  room: Room
  playerId: string
}>()

const emit = defineEmits<{
  action: [data: Record<string, unknown>]
}>()

const canvasRef = ref<HTMLCanvasElement | null>(null)
const canvasWrapRef = ref<HTMLElement | null>(null)

const myFighter = computed(() => props.gameState.fighters[props.playerId])
const isAlive = computed(() => myFighter.value?.alive ?? false)
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
  if (!winnerId) return 'Draw'
  const player = props.gameState.players.find((p) => p.id === winnerId)
  return player?.nickname ?? 'Unknown'
})

const playerRows = computed(() =>
  props.gameState.players.map((p) => ({
    ...p,
    fighter: props.gameState.fighters[p.id],
  })),
)

const heldMove = ref<'up' | 'down' | null>(null)

function startNewGame() {
  emit('action', { type: 'start_game' })
}

function sendMove(direction: 'up' | 'down' | 'stop') {
  emit('action', { type: 'set_move', direction })
}

function sendShoot() {
  emit('action', { type: 'shoot' })
}

function onKeyDown(e: KeyboardEvent) {
  if (!canControl.value) return

  if (e.key === 'ArrowUp' || e.key === 'w' || e.key === 'W') {
    e.preventDefault()
    if (heldMove.value !== 'up') {
      heldMove.value = 'up'
      sendMove('up')
    }
    return
  }

  if (e.key === 'ArrowDown' || e.key === 's' || e.key === 'S') {
    e.preventDefault()
    if (heldMove.value !== 'down') {
      heldMove.value = 'down'
      sendMove('down')
    }
    return
  }

  if (e.key === ' ') {
    e.preventDefault()
    sendShoot()
  }
}

function onKeyUp(e: KeyboardEvent) {
  if (!canControl.value) return

  if (
    (e.key === 'ArrowUp' || e.key === 'w' || e.key === 'W') &&
    heldMove.value === 'up'
  ) {
    heldMove.value = null
    sendMove('stop')
    return
  }

  if (
    (e.key === 'ArrowDown' || e.key === 's' || e.key === 'S') &&
    heldMove.value === 'down'
  ) {
    heldMove.value = null
    sendMove('stop')
  }
}

function draw() {
  const canvas = canvasRef.value
  const wrap = canvasWrapRef.value
  if (!canvas || !wrap) return
  const ctx = canvas.getContext('2d')
  if (!ctx) return

  const { grid_width, grid_height, fighter_height, fighters, bullets } = props.gameState
  const barCount = fighter_height ?? 3
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

  ctx.fillStyle = 'rgba(91, 156, 255, 0.08)'
  ctx.fillRect(offsetX, offsetY, cell * 2, boardH)
  ctx.fillRect(offsetX + boardW - cell * 2, offsetY, cell * 2, boardH)

  for (const bullet of bullets) {
    ctx.fillStyle = '#fbbf24'
    const pad = Math.max(2, cell * 0.2)
    ctx.beginPath()
    ctx.arc(
      offsetX + bullet.x * cell + cell / 2,
      offsetY + bullet.y * cell + cell / 2,
      cell / 2 - pad,
      0,
      Math.PI * 2,
    )
    ctx.fill()
  }

  for (const [pid, fighter] of Object.entries(fighters)) {
    const isMe = pid === props.playerId
    const alpha = fighter.alive ? 1 : 0.35
    ctx.globalAlpha = alpha
    const inset = Math.max(1, cell * 0.1)
    const barGap = Math.max(1, cell * 0.06)
    const barH = (cell * barCount - barGap * (barCount - 1)) / barCount

    for (let i = 0; i < barCount; i++) {
      ctx.fillStyle = fighter.color
      const barY = fighter.y + i
      ctx.fillRect(
        offsetX + fighter.x * cell + inset,
        offsetY + barY * cell + (cell - barH) / 2,
        cell - inset * 2,
        barH,
      )
    }

    if (isMe && fighter.alive) {
      ctx.strokeStyle = '#fff'
      ctx.lineWidth = Math.max(1, cell * 0.08)
      ctx.strokeRect(
        offsetX + fighter.x * cell + 1,
        offsetY + fighter.y * cell + 1,
        cell - 2,
        cell * barCount - 2,
      )
    }
    ctx.globalAlpha = 1
  }
}

let resizeObserver: ResizeObserver | null = null

watch(() => props.gameState, draw, { deep: true })

onMounted(() => {
  window.addEventListener('keydown', onKeyDown)
  window.addEventListener('keyup', onKeyUp)
  if (canvasWrapRef.value) {
    resizeObserver = new ResizeObserver(() => draw())
    resizeObserver.observe(canvasWrapRef.value)
  }
  draw()
})

onUnmounted(() => {
  window.removeEventListener('keydown', onKeyDown)
  window.removeEventListener('keyup', onKeyUp)
  resizeObserver?.disconnect()
})
</script>

<template>
  <div class="duel-board">
    <div ref="canvasWrapRef" class="canvas-wrap">
      <canvas ref="canvasRef" class="game-canvas" />

      <div v-if="gameState.phase === 'countdown'" class="overlay countdown">
        <span class="overlay-value">{{ countdownRemaining ?? '…' }}</span>
        <span class="overlay-label">Get ready!</span>
      </div>

      <div v-else-if="isFinished" class="overlay finished">
        <span class="overlay-label">Duel over</span>
        <span class="overlay-value">{{ winnerName }} wins!</span>
        <button v-if="isHost" type="button" class="btn-primary play-again-btn" @click="startNewGame">
          Play Again
        </button>
        <p v-else class="overlay-hint">Waiting for host to start a new duel…</p>
      </div>

      <div v-else-if="!isAlive" class="overlay eliminated">
        <span class="overlay-label">You were hit!</span>
        <span class="overlay-hint">Watch the duel continue…</span>
      </div>
    </div>

    <aside class="player-bar">
      <ul class="player-scores">
        <li
          v-for="row in playerRows"
          :key="row.id"
          class="player-score-row"
          :class="{ me: row.id === playerId, dead: !row.fighter?.alive }"
        >
          <span class="color-dot" :style="{ background: row.fighter?.color ?? '#666' }" />
          <span class="name">{{ row.nickname }}</span>
          <span class="side-label">{{ row.fighter?.side === 'left' ? 'Left' : 'Right' }}</span>
          <span v-if="!row.fighter?.alive" class="status">out</span>
        </li>
      </ul>

      <div class="controls-hint">
        <p v-if="canControl"><strong>Controls:</strong> W/S or ↑/↓ to move · Space to shoot</p>
        <p v-else-if="gameState.phase === 'playing' && !isAlive" class="muted">Spectating</p>
        <p v-else class="muted">Waiting to start…</p>
      </div>
    </aside>
  </div>
</template>

<style scoped>
.duel-board {
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

.side-label {
  font-size: 0.75rem;
  color: var(--text-muted);
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
