<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import type { Room, TetrisBoardState, TetrisGameState } from '@/types'
import { pieceCells } from './pieces'
import {
  computeBoardMetrics,
  computeGhostCells,
  drawBlock,
  drawBoardEffects,
  effectDuration,
  type BoardEffect,
  type Particle,
} from './render'
import NextPiecePreview from './NextPiecePreview.vue'

const props = defineProps<{
  gameState: TetrisGameState
  room: Room
  playerId: string
}>()

const emit = defineEmits<{
  action: [data: Record<string, unknown>]
}>()

const canvasRefs = ref<Record<string, HTMLCanvasElement | null>>({})

const myBoard = computed(() => props.gameState.boards[props.playerId])
const isAlive = computed(() => myBoard.value?.alive ?? false)
const isHost = computed(() => props.room.host_player_id === props.playerId)
const isSinglePlayer = computed(() => Boolean(props.gameState.settings?.single_player))
const canControl = computed(
  () => props.gameState.phase === 'playing' && isAlive.value,
)

const finalScore = computed(() => {
  if (props.gameState.final_score != null) return props.gameState.final_score
  const board = myBoard.value
  return board?.lines_cleared ?? 0
})

const finalLevel = computed(() => myBoard.value?.level ?? 1)

const countdownRemaining = computed(() => {
  if (props.gameState.phase !== 'countdown' || !props.gameState.countdown_ends_at) return null
  const end = new Date(props.gameState.countdown_ends_at).getTime()
  return Math.max(0, Math.ceil((end - Date.now()) / 1000))
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
    board: props.gameState.boards[p.id],
  })),
)

const boardLayoutClass = computed(() => {
  const n = props.gameState.players.length
  if (n === 1) return 'layout-1'
  if (n <= 2) return 'layout-2'
  if (n === 3) return 'layout-3'
  return 'layout-4'
})

const overlayState = computed(() => {
  if (props.gameState.phase === 'countdown') return 'countdown'
  if (props.gameState.phase === 'finished') return 'finished'
  if (!isAlive.value && !isSinglePlayer.value) return 'eliminated'
  return null
})

const lineClearPop = ref<{ lines: number; key: number } | null>(null)
let lineClearPopTimer: ReturnType<typeof setTimeout> | null = null

const boardEffects = ref<Record<string, BoardEffect[]>>({})
const boardParticles = ref<Record<string, Particle[]>>({})
const shakingPanels = ref<Record<string, boolean>>({})
const flashingLevels = ref<Record<string, boolean>>({})
const prevBoardSnapshots = ref<
  Record<string, { lines: number; level: number; alive: boolean; filled: number }>
>({})

function nextPieceType(board: TetrisBoardState | undefined): string | null {
  return board?.next_queue?.[0] ?? null
}

function nextPieceColor(board: TetrisBoardState | undefined): string | null {
  return board?.next_colors?.[0] ?? null
}

function setCanvasRef(id: string, el: HTMLCanvasElement | null) {
  canvasRefs.value[id] = el
}

function startNewGame() {
  emit('action', { type: 'start_game' })
}

function onKeyDown(e: KeyboardEvent) {
  if (!canControl.value) return

  const keyMap: Record<string, Record<string, unknown>> = {
    ArrowLeft: { type: 'move', direction: 'left' },
    ArrowRight: { type: 'move', direction: 'right' },
    ArrowDown: { type: 'move', direction: 'down' },
    ArrowUp: { type: 'rotate', direction: 'cw' },
    x: { type: 'rotate', direction: 'cw' },
    X: { type: 'rotate', direction: 'cw' },
    z: { type: 'rotate', direction: 'ccw' },
    Z: { type: 'rotate', direction: 'ccw' },
    ' ': { type: 'hard_drop' },
  }

  const action = keyMap[e.key]
  if (!action) return
  e.preventDefault()
  emit('action', action)
}

function filledCount(grid: (string | null)[][]): number {
  return grid.reduce((total, row) => total + row.filter(Boolean).length, 0)
}

function pushEffect(playerId: string, effect: BoardEffect) {
  if (!boardEffects.value[playerId]) boardEffects.value[playerId] = []
  boardEffects.value[playerId].push(effect)
}

function pruneEffects(playerId: string, now: number) {
  const effects = boardEffects.value[playerId]
  if (!effects?.length) return
  boardEffects.value[playerId] = effects.filter(
    (effect) => now - effect.startedAt < effectDuration(effect.type),
  )
}

function detectBoardChanges(playerId: string, board: TetrisBoardState) {
  const prev = prevBoardSnapshots.value[playerId]
  const now = performance.now()
  const currentFilled = filledCount(board.grid)

  if (prev) {
    if (board.lines_cleared > prev.lines) {
      const lines = board.lines_cleared - prev.lines
      pushEffect(playerId, { type: 'line_clear', startedAt: now, lines })
      if (playerId === props.playerId) {
        lineClearPop.value = { lines, key: Date.now() }
        if (lineClearPopTimer) clearTimeout(lineClearPopTimer)
        lineClearPopTimer = setTimeout(() => {
          lineClearPop.value = null
        }, 900)
      }
    } else if (currentFilled > prev.filled) {
      pushEffect(playerId, { type: 'lock', startedAt: now })
    }

    if (board.level > prev.level) {
      pushEffect(playerId, { type: 'level_up', startedAt: now })
      flashingLevels.value[playerId] = true
      setTimeout(() => {
        flashingLevels.value[playerId] = false
      }, 700)
    }

    if (prev.alive && !board.alive) {
      pushEffect(playerId, { type: 'death', startedAt: now })
      shakingPanels.value[playerId] = true
      setTimeout(() => {
        shakingPanels.value[playerId] = false
      }, 400)
    }
  }

  prevBoardSnapshots.value[playerId] = {
    lines: board.lines_cleared,
    level: board.level,
    alive: board.alive,
    filled: currentFilled,
  }
}

function syncBoardSnapshots() {
  for (const player of props.gameState.players) {
    const board = props.gameState.boards[player.id]
    if (!board) continue
    detectBoardChanges(player.id, board)
  }
}

function drawBoard(
  canvas: HTMLCanvasElement,
  board: TetrisBoardState,
  playerId: string,
  width: number,
  height: number,
  featured: boolean,
  now: number,
) {
  const ctx = canvas.getContext('2d')
  if (!ctx) return

  const displayW = canvas.clientWidth
  const displayH = canvas.clientHeight
  if (displayW <= 0 || displayH <= 0) return

  const dpr = window.devicePixelRatio || 1
  canvas.width = Math.floor(displayW * dpr)
  canvas.height = Math.floor(displayH * dpr)
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0)

  const metrics = computeBoardMetrics(displayW, displayH, width, height)
  const { offsetX, offsetY, boardW, boardH, cell } = metrics
  const pulse = 0.5 + 0.5 * Math.sin(now / 180)

  ctx.fillStyle = '#0f1419'
  ctx.fillRect(0, 0, displayW, displayH)
  ctx.fillRect(offsetX, offsetY, boardW, boardH)

  ctx.strokeStyle = '#1e293b'
  ctx.lineWidth = 1
  for (let x = 0; x <= width; x++) {
    ctx.beginPath()
    ctx.moveTo(offsetX + x * cell, offsetY)
    ctx.lineTo(offsetX + x * cell, offsetY + boardH)
    ctx.stroke()
  }
  for (let y = 0; y <= height; y++) {
    ctx.beginPath()
    ctx.moveTo(offsetX, offsetY + y * cell)
    ctx.lineTo(offsetX + boardW, offsetY + y * cell)
    ctx.stroke()
  }

  const alpha = board.alive ? 1 : 0.35
  const ghostCells = computeGhostCells(board, width, height)
  if (ghostCells && board.active_color) {
    for (const [x, y] of ghostCells) {
      if (y < 0) continue
      drawBlock(ctx, metrics, x, y, board.active_color, { alpha: 0.28, ghost: true })
    }
  }

  ctx.globalAlpha = alpha
  for (let y = 0; y < height; y++) {
    for (let x = 0; x < width; x++) {
      const color = board.grid[y]?.[x]
      if (!color) continue
      drawBlock(ctx, metrics, x, y, color)
    }
  }

  if (board.active && board.active_color) {
    const cells = pieceCells(
      board.active.type,
      board.active.rotation,
      board.active.x,
      board.active.y,
    )
    for (const [x, y] of cells) {
      if (y < 0) continue
      drawBlock(ctx, metrics, x, y, board.active_color, {
        glow: featured,
        pulse: featured ? pulse : 0.3,
      })
    }
  }
  ctx.globalAlpha = 1

  if (!boardParticles.value[playerId]) boardParticles.value[playerId] = []
  pruneEffects(playerId, now)
  drawBoardEffects(
    ctx,
    metrics,
    boardEffects.value[playerId] ?? [],
    now,
    boardParticles.value[playerId],
    board.color ?? '#5b9cff',
  )

  if (featured && board.alive) {
    ctx.strokeStyle = board.color ?? '#fff'
    ctx.lineWidth = Math.max(2, cell * 0.12)
    ctx.shadowColor = board.color ?? '#5b9cff'
    ctx.shadowBlur = 6 + pulse * 8
    ctx.strokeRect(offsetX + 1, offsetY + 1, boardW - 2, boardH - 2)
    ctx.shadowBlur = 0
  }
}

function drawAll(now = performance.now()) {
  const { board_width, board_height, boards } = props.gameState
  for (const player of props.gameState.players) {
    const canvas = canvasRefs.value[player.id]
    const board = boards[player.id]
    if (!canvas || !board) continue
    drawBoard(
      canvas,
      board,
      player.id,
      board_width,
      board_height,
      player.id === props.playerId,
      now,
    )
  }
}

let resizeObserver: ResizeObserver | null = null
let animationFrame = 0
const gridRef = ref<HTMLElement | null>(null)

watch(
  () => props.gameState,
  () => {
    syncBoardSnapshots()
  },
  { deep: true },
)

function animationLoop(now: number) {
  drawAll(now)
  animationFrame = requestAnimationFrame(animationLoop)
}

onMounted(() => {
  window.addEventListener('keydown', onKeyDown)
  if (gridRef.value) {
    resizeObserver = new ResizeObserver(() => drawAll())
    resizeObserver.observe(gridRef.value)
  }
  for (const player of props.gameState.players) {
    const board = props.gameState.boards[player.id]
    if (board) {
      prevBoardSnapshots.value[player.id] = {
        lines: board.lines_cleared,
        level: board.level,
        alive: board.alive,
        filled: filledCount(board.grid),
      }
    }
  }
  animationFrame = requestAnimationFrame(animationLoop)
})

onUnmounted(() => {
  window.removeEventListener('keydown', onKeyDown)
  resizeObserver?.disconnect()
  cancelAnimationFrame(animationFrame)
  if (lineClearPopTimer) clearTimeout(lineClearPopTimer)
})
</script>

<template>
  <div class="tetris-board">
    <div ref="gridRef" class="boards-grid" :class="boardLayoutClass">
      <div
        v-for="(player, index) in gameState.players"
        :key="player.id"
        class="board-panel stagger-in"
        :style="{ animationDelay: `${index * 0.08}s` }"
        :class="{
          featured: player.id === playerId,
          dead: !gameState.boards[player.id]?.alive,
          'panel-shake': shakingPanels[player.id],
        }"
      >
        <div class="board-header">
          <span class="color-dot" :style="{ background: gameState.boards[player.id]?.color }" />
          <span class="board-name">{{ player.nickname }}</span>
          <span v-if="player.id === playerId" class="you-tag">You</span>
          <span
            class="board-stats"
            :class="{ 'level-flash': flashingLevels[player.id] }"
          >
            L{{ gameState.boards[player.id]?.level ?? 1 }}
            · {{ gameState.boards[player.id]?.lines_cleared ?? 0 }} lines
          </span>
        </div>
        <div class="board-body">
          <canvas
            :ref="(el) => setCanvasRef(player.id, el as HTMLCanvasElement | null)"
            class="board-canvas"
          />
          <div
            class="next-overlay"
            :class="{ compact: player.id !== playerId }"
          >
            <NextPiecePreview
              :piece-type="nextPieceType(gameState.boards[player.id])"
              :color="nextPieceColor(gameState.boards[player.id])"
              :compact="player.id !== playerId"
            />
          </div>
        </div>
        <Transition name="line-pop">
          <div
            v-if="lineClearPop && player.id === playerId"
            :key="lineClearPop.key"
            class="line-clear-pop"
          >
            {{ lineClearPop.lines }} line{{ lineClearPop.lines === 1 ? '' : 's' }}!
          </div>
        </Transition>
        <div v-if="!gameState.boards[player.id]?.alive" class="board-out">OUT</div>
      </div>

      <Transition name="overlay-fade">
        <div v-if="overlayState" :key="overlayState" class="overlay" :class="overlayState">
          <template v-if="overlayState === 'countdown'">
            <span class="overlay-value countdown-pulse">{{ countdownRemaining ?? '…' }}</span>
            <span class="overlay-label">Get ready!</span>
          </template>

          <template v-else-if="overlayState === 'finished'">
            <span class="overlay-label">Game over</span>
            <template v-if="isSinglePlayer">
              <span class="overlay-value celebrate-text">{{ finalScore }} lines</span>
              <span class="overlay-hint">Level {{ finalLevel }} reached</span>
            </template>
            <span v-else class="overlay-value celebrate-text">{{ winnerName }} wins!</span>
            <button v-if="isHost" type="button" class="btn-primary play-again-btn" @click="startNewGame">
              Play Again
            </button>
            <p v-else class="overlay-hint">Waiting for host to start a new game…</p>
          </template>

          <template v-else-if="overlayState === 'eliminated'">
            <span class="overlay-label">You were eliminated</span>
            <span class="overlay-hint">Watch the others continue…</span>
          </template>
        </div>
      </Transition>
    </div>

    <aside class="player-bar">
      <ul class="player-scores">
        <li
          v-for="row in playerRows"
          :key="row.id"
          class="player-score-row"
          :class="{ me: row.id === playerId, dead: !row.board?.alive }"
        >
          <span class="color-dot" :style="{ background: row.board?.color ?? '#666' }" />
          <span class="name">{{ row.nickname }}</span>
          <span class="score">Lv {{ row.board?.level ?? 1 }}</span>
          <span class="lines">{{ row.board?.lines_cleared ?? 0 }} lines</span>
          <span v-if="!row.board?.alive" class="status">out</span>
        </li>
      </ul>

      <div class="controls-hint">
        <p v-if="canControl"><strong>Controls:</strong> Arrows · Z/X rotate · Space drop</p>
        <p v-else-if="gameState.phase === 'playing' && !isAlive" class="muted">Spectating</p>
        <p v-else class="muted">Waiting to start…</p>
      </div>
    </aside>
  </div>
</template>

<style scoped>
.tetris-board {
  flex: 1;
  width: 100%;
  min-height: 0;
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
  padding: 0 0.5rem 0.5rem;
}

.boards-grid {
  position: relative;
  flex: 1;
  min-height: 0;
  display: grid;
  gap: 0.5rem;
}

.layout-1 {
  grid-template-columns: 1fr;
  max-width: 420px;
  margin: 0 auto;
  width: 100%;
}

.layout-2 {
  grid-template-columns: 1fr 1fr;
}

.layout-3 {
  grid-template-columns: 1fr 1fr;
  grid-template-rows: 1.2fr 1fr;
}

.layout-3 .featured {
  grid-column: 1 / -1;
}

.layout-4 {
  grid-template-columns: 1fr 1fr;
  grid-template-rows: 1fr 1fr;
}

.board-panel {
  position: relative;
  display: flex;
  flex-direction: column;
  min-height: 0;
  border: 1px solid var(--border);
  border-radius: var(--radius);
  background: #0f1419;
  overflow: hidden;
  transition: border-color 0.3s, box-shadow 0.3s, transform 0.3s var(--ease-smooth);
}

.board-panel.featured {
  border-color: var(--accent);
  animation: glowPulse 2.5s ease-in-out infinite;
}

.board-panel.dead {
  opacity: 0.7;
}

.board-panel.panel-shake {
  animation: shake 0.4s;
}

.board-header {
  flex-shrink: 0;
  display: flex;
  align-items: center;
  gap: 0.4rem;
  padding: 0.35rem 0.6rem;
  font-size: 0.8rem;
  background: var(--surface);
  border-bottom: 1px solid var(--border);
}

.board-name {
  font-weight: 600;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.board-stats {
  margin-left: auto;
  color: var(--text-muted);
  font-variant-numeric: tabular-nums;
  transition: color 0.2s, transform 0.2s var(--ease-bounce);
}

.board-stats.level-flash {
  color: #f59e0b;
  transform: scale(1.08);
}

.you-tag {
  font-size: 0.65rem;
  padding: 0.1rem 0.35rem;
  border-radius: 4px;
  background: var(--accent-muted);
  color: var(--accent);
}

.board-canvas {
  width: 100%;
  height: 100%;
  min-height: 0;
  display: block;
}

.board-body {
  position: relative;
  flex: 1;
  min-height: 0;
  width: 100%;
}

.next-overlay {
  position: absolute;
  top: 0.5rem;
  right: 0.5rem;
  z-index: 1;
  pointer-events: none;
  padding: 0.3rem 0.4rem 0.35rem;
  border-radius: 6px;
  background: rgba(10, 14, 20, 0.85);
  border: 1px solid rgba(255, 255, 255, 0.08);
  backdrop-filter: blur(4px);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.35);
}

.next-overlay.compact {
  top: 0.35rem;
  right: 0.35rem;
  padding: 0.2rem 0.28rem 0.25rem;
}

.board-panel.featured .next-overlay:not(.compact) {
  top: 0.6rem;
  right: 0.6rem;
  padding: 0.35rem 0.45rem 0.4rem;
}

.line-clear-pop {
  position: absolute;
  left: 50%;
  top: 45%;
  transform: translate(-50%, -50%);
  padding: 0.35rem 0.85rem;
  border-radius: 999px;
  font-size: 1.1rem;
  font-weight: 800;
  letter-spacing: 0.02em;
  color: #fff;
  background: linear-gradient(135deg, rgba(91, 156, 255, 0.95), rgba(168, 85, 247, 0.9));
  box-shadow: 0 8px 24px rgba(91, 156, 255, 0.35);
  pointer-events: none;
  z-index: 3;
}

.line-pop-enter-active {
  animation: linePopIn 0.45s var(--ease-bounce);
}

.line-pop-leave-active {
  animation: linePopOut 0.35s var(--ease-smooth);
}

@keyframes linePopIn {
  from {
    opacity: 0;
    transform: translate(-50%, -50%) scale(0.5) rotate(-8deg);
  }
  to {
    opacity: 1;
    transform: translate(-50%, -50%) scale(1) rotate(0);
  }
}

@keyframes linePopOut {
  from {
    opacity: 1;
    transform: translate(-50%, -70%) scale(1);
  }
  to {
    opacity: 0;
    transform: translate(-50%, -90%) scale(0.85);
  }
}

.board-out {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 1.5rem;
  font-weight: 800;
  color: rgba(255, 255, 255, 0.55);
  pointer-events: none;
  animation: outStamp 0.5s var(--ease-bounce);
  text-shadow: 0 0 20px rgba(239, 68, 68, 0.5);
}

@keyframes outStamp {
  0% {
    opacity: 0;
    transform: scale(2) rotate(-12deg);
  }
  60% {
    transform: scale(0.92) rotate(2deg);
  }
  100% {
    opacity: 1;
    transform: scale(1) rotate(0);
  }
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
  z-index: 2;
  backdrop-filter: blur(4px);
}

.overlay-fade-enter-active {
  animation: fadeInUp 0.4s var(--ease-smooth);
}

.overlay-fade-leave-active {
  animation: fadeInUp 0.25s var(--ease-smooth) reverse;
}

.overlay-value {
  font-size: clamp(1.75rem, 4vw, 2.5rem);
  font-weight: 800;
}

.countdown-pulse {
  animation: countdownPulse 1s ease-in-out infinite;
}

@keyframes countdownPulse {
  0%, 100% {
    transform: scale(1);
    text-shadow: 0 0 0 transparent;
  }
  50% {
    transform: scale(1.12);
    text-shadow: 0 0 24px rgba(91, 156, 255, 0.6);
  }
}

.celebrate-text {
  animation: celebrate 0.6s var(--ease-bounce);
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
  animation: fadeInUp 0.45s var(--ease-smooth) 0.15s backwards;
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
  transition: opacity 0.3s, transform 0.3s var(--ease-smooth);
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
  max-width: 8rem;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.score,
.lines {
  font-variant-numeric: tabular-nums;
  color: var(--text-muted);
  font-size: 0.85rem;
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

.muted {
  color: var(--text-muted);
}

@media (max-width: 640px) {
  .layout-2,
  .layout-4 {
    grid-template-columns: 1fr;
  }

  .player-bar {
    flex-direction: column;
    align-items: flex-start;
  }

  .controls-hint {
    text-align: left;
  }
}
</style>
