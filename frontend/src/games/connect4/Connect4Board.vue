<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import type { Connect4GameState, Room } from '@/types'

const props = defineProps<{
  gameState: Connect4GameState
  room: Room
  playerId: string
}>()

const emit = defineEmits<{
  action: [data: Record<string, unknown>]
}>()

const hoveredCol = ref<number | null>(null)

const viewerColor = computed(() => props.gameState.viewer_color)

const isMyTurn = computed(() => {
  if (props.gameState.phase !== 'playing') return false
  return props.gameState.current_actor_id === props.playerId
})

const isSpectator = computed(() => !props.gameState.viewer_color)

const actorNickname = computed(() => {
  const id = props.gameState.current_actor_id
  if (!id) return null
  return props.gameState.players.find((p) => p.id === id)?.nickname ?? null
})

const redPlayer = computed(() => props.gameState.players.find((p) => p.color === 'red'))
const yellowPlayer = computed(() => props.gameState.players.find((p) => p.color === 'yellow'))

const topPlayer = computed(() => (viewerColor.value === 'yellow' ? redPlayer.value : yellowPlayer.value))
const bottomPlayer = computed(() => (viewerColor.value === 'yellow' ? yellowPlayer.value : redPlayer.value))

const lastMoveCell = computed(() => {
  const move = props.gameState.last_move
  if (!move) return null
  return `${move.row}-${move.col}`
})

const winningCells = computed(() => {
  const cells = props.gameState.winning_cells
  if (!cells) return new Set<string>()
  return new Set(cells.map(([r, c]) => `${r}-${c}`))
})

const legalCols = computed(() => {
  if (!isMyTurn.value) return new Set<number>()
  return new Set(props.gameState.legal_moves.map((m) => m.col))
})

watch(
  () => props.gameState.move_history.length,
  () => {
    hoveredCol.value = null
  },
)

function onColumnClick(col: number) {
  if (!isMyTurn.value) return
  if (!legalCols.value.has(col)) return

  emit('action', { type: 'drop', col })
}

function onColumnHover(col: number | null) {
  hoveredCol.value = col
}

function resign() {
  if (props.gameState.phase !== 'playing' || isSpectator.value) return
  if (window.confirm('Resign this game?')) {
    emit('action', { type: 'resign' })
  }
}

const statusText = computed(() => {
  const gs = props.gameState
  if (gs.phase === 'game_over') {
    if (gs.win_reason === 'connect4') {
      const winner = gs.players.find((p) => p.id === gs.winner)
      return `${winner?.nickname ?? 'Winner'} wins — Connect Four!`
    }
    if (gs.win_reason === 'resign') {
      const winner = gs.players.find((p) => p.id === gs.winner)
      return `${winner?.nickname ?? 'Winner'} wins — opponent resigned`
    }
    if (gs.win_reason === 'draw') return 'Draw — board is full!'
    return 'Game over'
  }
  if (!isMyTurn.value && actorNickname.value) {
    const actor = gs.players.find((p) => p.id === gs.current_actor_id)
    if (actor?.is_ai) return 'AI is thinking…'
    return `${actorNickname.value}'s turn`
  }
  return isMyTurn.value ? 'Your turn — drop a disc!' : 'Waiting…'
})

const statusTone = computed(() => {
  if (props.gameState.phase === 'game_over') return 'over'
  if (isMyTurn.value) return 'mine'
  return 'idle'
})

const moveCount = computed(() => props.gameState.move_history.length)

function isPlayerToMove(color: 'red' | 'yellow' | undefined): boolean {
  return (
    props.gameState.phase === 'playing' &&
    Boolean(color) &&
    props.gameState.current_color === color
  )
}

function getPreviewRow(col: number): number | null {
  const board = props.gameState.board
  for (let row = props.gameState.rows - 1; row >= 0; row--) {
    if (board[row][col] === null) {
      return row
    }
  }
  return null
}
</script>

<template>
  <div class="connect4-board">
    <div class="connect4-shell">
      <div class="play-column">
        <div
          class="player-bar"
          :class="{
            active: isPlayerToMove(topPlayer?.color),
            ai: topPlayer?.is_ai,
          }"
        >
          <span class="disc-badge" :class="topPlayer?.color ?? 'yellow'" aria-hidden="true">●</span>
          <div class="player-meta">
            <p class="player-name">
              {{ topPlayer?.nickname ?? 'Opponent' }}
              <span v-if="topPlayer?.is_ai" class="tag">AI</span>
              <span v-if="topPlayer?.id === playerId" class="tag you">You</span>
            </p>
            <p class="player-side">{{ topPlayer?.color === 'red' ? 'Red' : 'Yellow' }}</p>
          </div>
          <span v-if="isPlayerToMove(topPlayer?.color)" class="turn-pill">
            {{ topPlayer?.is_ai ? 'Thinking' : 'To move' }}
          </span>
        </div>

        <div class="board-stage">
          <div
            class="board"
            :class="{
              disabled: !isMyTurn || gameState.phase !== 'playing',
            }"
          >
            <div class="column-hints">
              <button
                v-for="col in gameState.cols"
                :key="col - 1"
                type="button"
                class="col-hint"
                :class="{
                  hovered: hoveredCol === col - 1 && legalCols.has(col - 1),
                  legal: legalCols.has(col - 1),
                }"
                @mouseenter="onColumnHover(col - 1)"
                @mouseleave="onColumnHover(null)"
                @click="onColumnClick(col - 1)"
              >
                <span
                  v-if="hoveredCol === col - 1 && legalCols.has(col - 1)"
                  class="preview-disc"
                  :class="viewerColor"
                >
                  ●
                </span>
              </button>
            </div>

            <div class="grid">
              <div v-for="row in gameState.rows" :key="row - 1" class="grid-row">
                <button
                  v-for="col in gameState.cols"
                  :key="`${row - 1}-${col - 1}`"
                  type="button"
                  class="cell"
                  :class="{
                    last: lastMoveCell === `${row - 1}-${col - 1}`,
                    winning: winningCells.has(`${row - 1}-${col - 1}`),
                    'preview-target': hoveredCol === col - 1 && getPreviewRow(col - 1) === row - 1 && legalCols.has(col - 1),
                  }"
                  @mouseenter="onColumnHover(col - 1)"
                  @mouseleave="onColumnHover(null)"
                  @click="onColumnClick(col - 1)"
                >
                  <span
                    v-if="gameState.board[row - 1][col - 1]"
                    class="disc"
                    :class="[
                      gameState.board[row - 1][col - 1],
                      { 'drop-anim': lastMoveCell === `${row - 1}-${col - 1}` },
                    ]"
                  >
                    ●
                  </span>
                  <span
                    v-else-if="hoveredCol === col - 1 && getPreviewRow(col - 1) === row - 1 && legalCols.has(col - 1)"
                    class="disc preview"
                    :class="viewerColor"
                  >
                    ●
                  </span>
                </button>
              </div>
            </div>
          </div>

          <div v-if="gameState.phase === 'game_over'" class="game-over-overlay">
            <div class="game-over-card">
              <p class="game-over-title">{{ statusText }}</p>
            </div>
          </div>
        </div>

        <div
          class="player-bar"
          :class="{
            active: isPlayerToMove(bottomPlayer?.color),
            ai: bottomPlayer?.is_ai,
            me: bottomPlayer?.id === playerId,
          }"
        >
          <span class="disc-badge" :class="bottomPlayer?.color ?? 'red'" aria-hidden="true">●</span>
          <div class="player-meta">
            <p class="player-name">
              {{ bottomPlayer?.nickname ?? 'You' }}
              <span v-if="bottomPlayer?.is_ai" class="tag">AI</span>
              <span v-if="bottomPlayer?.id === playerId" class="tag you">You</span>
            </p>
            <p class="player-side">{{ bottomPlayer?.color === 'red' ? 'Red' : 'Yellow' }}</p>
          </div>
          <span v-if="isPlayerToMove(bottomPlayer?.color)" class="turn-pill">To move</span>
        </div>
      </div>

      <aside class="side-rail">
        <div class="status-chip" :class="statusTone">
          <span class="status-dot" aria-hidden="true" />
          <p>{{ statusText }}</p>
        </div>

        <div v-if="!isSpectator && gameState.phase === 'playing'" class="action-row">
          <button type="button" class="btn-secondary danger" @click="resign">Resign</button>
        </div>

        <div class="history-panel">
          <div class="history-header">
            <h3>Moves</h3>
            <span class="move-count">{{ moveCount }}</span>
          </div>
          <div v-if="gameState.move_history.length" class="move-list">
            <div
              v-for="(move, idx) in gameState.move_history"
              :key="idx"
              class="move-entry"
              :class="move.color"
            >
              <span class="move-num">{{ idx + 1 }}.</span>
              <span class="move-disc" :class="move.color">●</span>
              <span class="move-col">Col {{ move.col + 1 }}</span>
            </div>
          </div>
          <p v-else class="muted">No moves yet</p>
        </div>
      </aside>
    </div>
  </div>
</template>

<style scoped>
.connect4-board {
  --c4-red: #e53935;
  --c4-red-glow: rgba(229, 57, 53, 0.4);
  --c4-yellow: #fdd835;
  --c4-yellow-glow: rgba(253, 216, 53, 0.4);
  --c4-board: #1565c0;
  --c4-board-dark: #0d47a1;
  --c4-cell-bg: #0a1929;
  flex: 1;
  min-height: 0;
  width: 100%;
  display: flex;
  padding: 0.5rem 0.75rem 0.75rem;
  overflow: hidden;
}

.connect4-shell {
  flex: 1;
  min-height: 0;
  width: 100%;
  max-width: 1600px;
  margin: 0 auto;
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(200px, 240px);
  gap: 0.85rem;
  align-items: stretch;
}

.play-column {
  min-width: 0;
  min-height: 0;
  display: flex;
  flex-direction: column;
  gap: 0.45rem;
}

.player-bar {
  display: flex;
  align-items: center;
  gap: 0.65rem;
  padding: 0.45rem 0.65rem;
  border-radius: 10px;
  border: 1px solid var(--border);
  background: rgba(21, 28, 44, 0.72);
  flex-shrink: 0;
  transition:
    border-color 0.2s,
    box-shadow 0.2s;
}

.player-bar.active {
  border-color: rgba(21, 101, 192, 0.55);
  box-shadow: 0 0 0 1px rgba(21, 101, 192, 0.18);
}

.player-bar.me {
  border-color: rgba(91, 156, 255, 0.4);
}

.disc-badge {
  width: 2rem;
  height: 2rem;
  border-radius: 50%;
  display: grid;
  place-items: center;
  font-size: 1.5rem;
  flex-shrink: 0;
  line-height: 1;
}

.disc-badge.red {
  color: var(--c4-red);
  filter: drop-shadow(0 0 6px var(--c4-red-glow));
}

.disc-badge.yellow {
  color: var(--c4-yellow);
  filter: drop-shadow(0 0 6px var(--c4-yellow-glow));
}

.player-meta {
  min-width: 0;
  flex: 1;
}

.player-name {
  margin: 0;
  font-weight: 650;
  font-size: 0.92rem;
  display: flex;
  align-items: center;
  gap: 0.35rem;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.player-side {
  margin: 0;
  font-size: 0.72rem;
  letter-spacing: 0.04em;
  text-transform: uppercase;
  color: var(--text-muted);
}

.tag {
  font-size: 0.62rem;
  padding: 0.08rem 0.32rem;
  border-radius: 4px;
  background: rgba(21, 101, 192, 0.18);
  color: var(--c4-board);
  font-weight: 700;
}

.tag.you {
  background: rgba(91, 156, 255, 0.18);
  color: var(--accent);
}

.turn-pill {
  font-size: 0.68rem;
  font-weight: 700;
  letter-spacing: 0.04em;
  text-transform: uppercase;
  padding: 0.28rem 0.5rem;
  border-radius: 999px;
  background: rgba(21, 101, 192, 0.16);
  color: var(--c4-board);
  flex-shrink: 0;
}

.board-stage {
  position: relative;
  flex: 1;
  min-height: 0;
  display: grid;
  place-items: center;
  container-type: size;
}

.board {
  width: min(100cqw, calc(100cqh * 7 / 7));
  height: auto;
  aspect-ratio: 7 / 7;
  container-type: size;
  display: flex;
  flex-direction: column;
  border-radius: 12px;
  overflow: hidden;
  background: var(--c4-board);
  border: 4px solid var(--c4-board-dark);
  box-shadow:
    0 16px 48px rgba(0, 0, 0, 0.45),
    inset 0 0 0 1px rgba(255, 255, 255, 0.06);
}

@supports not (width: 1cqw) {
  .board {
    width: min(100%, calc(100dvh - 11.5rem));
    height: auto;
    max-height: 100%;
  }
}

.board.disabled {
  cursor: default;
}

.column-hints {
  display: grid;
  grid-template-columns: repeat(7, 1fr);
  height: calc(100% / 7);
  background: linear-gradient(to bottom, rgba(10, 25, 41, 0.8), transparent);
}

.col-hint {
  display: flex;
  align-items: center;
  justify-content: center;
  border: none;
  background: transparent;
  cursor: pointer;
  transition: background 0.15s;
}

.col-hint.legal:hover {
  background: rgba(255, 255, 255, 0.08);
}

.col-hint:not(.legal) {
  cursor: default;
}

.preview-disc {
  font-size: min(6cqw, 6cqh);
  line-height: 1;
  opacity: 0.6;
}

.preview-disc.red {
  color: var(--c4-red);
}

.preview-disc.yellow {
  color: var(--c4-yellow);
}

.grid {
  flex: 1;
  display: flex;
  flex-direction: column;
}

.grid-row {
  display: grid;
  grid-template-columns: repeat(7, 1fr);
  flex: 1;
  min-height: 0;
}

.cell {
  position: relative;
  border: none;
  border-radius: 0;
  padding: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  background: var(--c4-board);
  font-size: min(10cqw, 10cqh);
  line-height: 1;
  transition: filter 0.12s ease;
}

.cell::before {
  content: '';
  position: absolute;
  inset: 8%;
  border-radius: 50%;
  background: var(--c4-cell-bg);
  box-shadow: inset 0 4px 8px rgba(0, 0, 0, 0.4);
}

.cell:hover:not(:disabled) {
  filter: brightness(1.05);
}

.cell.last::after {
  content: '';
  position: absolute;
  inset: 4%;
  border-radius: 50%;
  border: 2px solid rgba(255, 255, 255, 0.35);
  pointer-events: none;
}

.cell.winning::after {
  content: '';
  position: absolute;
  inset: 2%;
  border-radius: 50%;
  border: 3px solid rgba(255, 255, 255, 0.8);
  animation: winPulse 1s ease-in-out infinite;
  pointer-events: none;
}

@keyframes winPulse {
  0%, 100% {
    transform: scale(1);
    opacity: 0.8;
  }
  50% {
    transform: scale(1.05);
    opacity: 1;
  }
}

.cell.preview-target::before {
  background: rgba(10, 25, 41, 0.7);
}

.disc {
  z-index: 1;
  user-select: none;
  filter: drop-shadow(0 2px 4px rgba(0, 0, 0, 0.35));
}

.disc.red {
  color: var(--c4-red);
}

.disc.yellow {
  color: var(--c4-yellow);
}

.disc.preview {
  opacity: 0.5;
}

.disc.drop-anim {
  animation: discDrop 0.4s var(--ease-bounce);
}

@keyframes discDrop {
  0% {
    transform: translateY(-200%);
    opacity: 0;
  }
  30% {
    opacity: 1;
  }
  100% {
    transform: translateY(0);
  }
}

.game-over-overlay {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(8, 10, 16, 0.55);
  backdrop-filter: blur(2px);
  border-radius: 12px;
  z-index: 5;
}

.game-over-card {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 0.75rem;
  padding: 1.25rem 1.5rem;
  border-radius: 12px;
  border: 1px solid rgba(21, 101, 192, 0.35);
  background: rgba(21, 28, 44, 0.95);
  box-shadow: var(--shadow);
}

.game-over-title {
  margin: 0;
  font-weight: 650;
  font-size: 1.1rem;
  text-align: center;
}

.side-rail {
  min-height: 0;
  display: flex;
  flex-direction: column;
  gap: 0.65rem;
  padding: 0.75rem;
  border-radius: 12px;
  border: 1px solid var(--border);
  background: rgba(21, 28, 44, 0.72);
}

.status-chip {
  display: flex;
  align-items: flex-start;
  gap: 0.55rem;
  padding: 0.65rem 0.7rem;
  border-radius: 10px;
  background: rgba(10, 14, 23, 0.45);
  border: 1px solid var(--border);
}

.status-chip p {
  margin: 0;
  font-weight: 650;
  font-size: 0.88rem;
  line-height: 1.35;
}

.status-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  margin-top: 0.35rem;
  flex-shrink: 0;
  background: var(--text-muted);
}

.status-chip.mine {
  border-color: rgba(91, 156, 255, 0.4);
  background: rgba(91, 156, 255, 0.08);
}

.status-chip.mine .status-dot {
  background: var(--accent);
  box-shadow: 0 0 8px var(--accent-glow);
}

.status-chip.over {
  border-color: rgba(21, 101, 192, 0.45);
  background: rgba(21, 101, 192, 0.08);
}

.status-chip.over .status-dot {
  background: var(--c4-board);
}

.action-row {
  display: flex;
  gap: 0.45rem;
}

.action-row .btn-secondary {
  flex: 1;
  font-size: 0.78rem;
  padding: 0.45rem 0.5rem;
}

.action-row .danger {
  border-color: rgba(255, 92, 108, 0.4);
  color: #ff8a96;
}

.history-panel {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
  gap: 0.45rem;
}

.history-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.history-header h3 {
  margin: 0;
  font-size: 0.7rem;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  color: var(--text-muted);
}

.move-count {
  font-size: 0.72rem;
  color: var(--text-muted);
}

.move-list {
  flex: 1;
  min-height: 0;
  overflow: auto;
  display: flex;
  flex-direction: column;
  gap: 0.15rem;
  padding-right: 0.15rem;
}

.move-entry {
  display: flex;
  align-items: center;
  gap: 0.35rem;
  padding: 0.28rem 0.35rem;
  border-radius: 6px;
  font-size: 0.8rem;
}

.move-entry:nth-child(odd) {
  background: rgba(10, 14, 23, 0.35);
}

.move-num {
  width: 1.6rem;
  color: var(--text-muted);
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
}

.move-disc {
  font-size: 0.9rem;
  line-height: 1;
}

.move-disc.red {
  color: var(--c4-red);
}

.move-disc.yellow {
  color: var(--c4-yellow);
}

.move-col {
  color: var(--text);
}

.muted {
  margin: 0;
  color: var(--text-muted);
  font-size: 0.85rem;
}

@media (max-width: 860px) {
  .connect4-board {
    overflow: auto;
    padding: 0.5rem;
  }

  .connect4-shell {
    grid-template-columns: 1fr;
    grid-template-rows: auto auto;
    overflow: visible;
  }

  .play-column {
    min-height: auto;
  }

  .board-stage {
    min-height: min(78vw, calc(100dvh - 13rem));
    height: min(78vw, calc(100dvh - 13rem));
  }

  .side-rail {
    max-height: none;
  }

  .history-panel {
    max-height: 180px;
  }
}

@media (max-width: 520px) {
  .action-row {
    grid-template-columns: 1fr;
  }

  .player-bar {
    padding: 0.4rem 0.55rem;
  }
}
</style>
