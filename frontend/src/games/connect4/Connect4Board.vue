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

const lastDropDistance = computed(() => {
  const move = props.gameState.last_move
  if (!move) return 1
  return Math.max(1, move.row + 1)
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

function colorLabel(color: 'red' | 'yellow' | undefined): string {
  return color === 'yellow' ? 'Yellow' : 'Red'
}
</script>

<template>
  <div class="connect4-board" :class="{ 'my-turn': isMyTurn }">
    <div class="connect4-shell">
      <div class="play-column">
        <div
          class="player-bar"
          :class="[
            topPlayer?.color ?? 'yellow',
            {
              active: isPlayerToMove(topPlayer?.color),
              ai: topPlayer?.is_ai,
            },
          ]"
        >
          <span class="disc-badge" :class="topPlayer?.color ?? 'yellow'" aria-hidden="true" />
          <div class="player-meta">
            <p class="player-name">
              {{ topPlayer?.nickname ?? 'Opponent' }}
              <span v-if="topPlayer?.is_ai" class="tag">AI</span>
              <span v-if="topPlayer?.id === playerId" class="tag you">You</span>
            </p>
            <p class="player-side">{{ colorLabel(topPlayer?.color) }}</p>
          </div>
          <span v-if="isPlayerToMove(topPlayer?.color)" class="turn-pill">
            {{ topPlayer?.is_ai ? 'Thinking' : 'To move' }}
          </span>
        </div>

        <div class="board-stage">
          <div class="board-glow" aria-hidden="true" />
          <div
            class="board"
            :class="{
              disabled: !isMyTurn || gameState.phase !== 'playing',
              interactive: isMyTurn && gameState.phase === 'playing',
            }"
            :style="{ '--drop-rows': lastDropDistance }"
          >
            <div class="board-frame">
              <div class="column-hints">
                <button
                  v-for="col in gameState.cols"
                  :key="`hint-${col - 1}`"
                  type="button"
                  class="col-hint"
                  :class="{
                    hovered: hoveredCol === col - 1 && legalCols.has(col - 1),
                    legal: legalCols.has(col - 1),
                  }"
                  :aria-label="`Drop in column ${col}`"
                  :disabled="!legalCols.has(col - 1)"
                  @mouseenter="onColumnHover(col - 1)"
                  @mouseleave="onColumnHover(null)"
                  @focus="onColumnHover(col - 1)"
                  @blur="onColumnHover(null)"
                  @click="onColumnClick(col - 1)"
                >
                  <span class="hint-arrow" :class="viewerColor" aria-hidden="true" />
                </button>
              </div>

              <div class="grid" role="grid" :aria-label="`Connect Four board, ${gameState.rows} by ${gameState.cols}`">
                <div
                  v-for="row in gameState.rows"
                  :key="`row-${row - 1}`"
                  class="grid-row"
                  role="row"
                >
                  <button
                    v-for="col in gameState.cols"
                    :key="`${row - 1}-${col - 1}`"
                    type="button"
                    class="cell"
                    role="gridcell"
                    :class="{
                      last: lastMoveCell === `${row - 1}-${col - 1}`,
                      winning: winningCells.has(`${row - 1}-${col - 1}`),
                      'preview-target':
                        hoveredCol === col - 1 &&
                        getPreviewRow(col - 1) === row - 1 &&
                        legalCols.has(col - 1),
                      occupied: Boolean(gameState.board[row - 1][col - 1]),
                    }"
                    :aria-label="
                      gameState.board[row - 1][col - 1]
                        ? `${gameState.board[row - 1][col - 1]} disc, row ${row}, column ${col}`
                        : `Empty, row ${row}, column ${col}`
                    "
                    @mouseenter="onColumnHover(col - 1)"
                    @mouseleave="onColumnHover(null)"
                    @click="onColumnClick(col - 1)"
                  >
                    <span class="cell-hole" aria-hidden="true" />
                    <span
                      v-if="gameState.board[row - 1][col - 1]"
                      class="disc"
                      :class="[
                        gameState.board[row - 1][col - 1],
                        {
                          'drop-anim': lastMoveCell === `${row - 1}-${col - 1}`,
                          winning: winningCells.has(`${row - 1}-${col - 1}`),
                        },
                      ]"
                    />
                    <span
                      v-else-if="
                        hoveredCol === col - 1 &&
                        getPreviewRow(col - 1) === row - 1 &&
                        legalCols.has(col - 1)
                      "
                      class="disc preview"
                      :class="viewerColor"
                    />
                  </button>
                </div>
              </div>
            </div>
            <div class="board-feet" aria-hidden="true">
              <span />
              <span />
            </div>
          </div>

          <div v-if="gameState.phase === 'game_over'" class="game-over-overlay">
            <div class="game-over-card">
              <span
                class="game-over-disc"
                :class="gameState.players.find((p) => p.id === gameState.winner)?.color ?? 'red'"
                aria-hidden="true"
              />
              <p class="game-over-title">{{ statusText }}</p>
            </div>
          </div>
        </div>

        <div
          class="player-bar"
          :class="[
            bottomPlayer?.color ?? 'red',
            {
              active: isPlayerToMove(bottomPlayer?.color),
              ai: bottomPlayer?.is_ai,
              me: bottomPlayer?.id === playerId,
            },
          ]"
        >
          <span class="disc-badge" :class="bottomPlayer?.color ?? 'red'" aria-hidden="true" />
          <div class="player-meta">
            <p class="player-name">
              {{ bottomPlayer?.nickname ?? 'You' }}
              <span v-if="bottomPlayer?.is_ai" class="tag">AI</span>
              <span v-if="bottomPlayer?.id === playerId" class="tag you">You</span>
            </p>
            <p class="player-side">{{ colorLabel(bottomPlayer?.color) }}</p>
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
              <span class="move-disc" :class="move.color" aria-hidden="true" />
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
  --c4-red: #ef4444;
  --c4-red-deep: #b91c1c;
  --c4-red-shine: #fca5a5;
  --c4-yellow: #fbbf24;
  --c4-yellow-deep: #d97706;
  --c4-yellow-shine: #fde68a;
  --c4-board: #1d6fd4;
  --c4-board-mid: #1557b0;
  --c4-board-dark: #0d3f86;
  --c4-board-edge: #0a2f66;
  --c4-hole: #07111f;
  --c4-hole-rim: rgba(255, 255, 255, 0.12);
  flex: 1;
  min-height: 0;
  width: 100%;
  display: flex;
  padding: 0.5rem 0.75rem 0.75rem;
  overflow: hidden;
  background:
    radial-gradient(ellipse 70% 55% at 40% 45%, rgba(29, 111, 212, 0.14), transparent 55%),
    radial-gradient(ellipse 50% 40% at 80% 80%, rgba(239, 68, 68, 0.06), transparent 50%),
    radial-gradient(ellipse 40% 35% at 10% 85%, rgba(251, 191, 36, 0.05), transparent 50%);
  animation: boardSceneIn 0.5s var(--ease-smooth) both;
}

@keyframes boardSceneIn {
  from {
    opacity: 0;
  }
  to {
    opacity: 1;
  }
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
  gap: 0.5rem;
}

.player-bar {
  display: flex;
  align-items: center;
  gap: 0.7rem;
  padding: 0.5rem 0.75rem;
  border-radius: 12px;
  border: 1px solid var(--border);
  background: rgba(21, 28, 44, 0.55);
  backdrop-filter: blur(8px);
  flex-shrink: 0;
  position: relative;
  overflow: hidden;
  transition:
    border-color 0.25s var(--ease-smooth),
    box-shadow 0.25s var(--ease-smooth),
    background 0.25s;
}

.player-bar::before {
  content: '';
  position: absolute;
  left: 0;
  top: 0;
  bottom: 0;
  width: 3px;
  background: var(--text-muted);
  opacity: 0.35;
  transition: opacity 0.25s, background 0.25s;
}

.player-bar.red::before {
  background: var(--c4-red);
}

.player-bar.yellow::before {
  background: var(--c4-yellow);
}

.player-bar.active {
  background: rgba(21, 28, 44, 0.85);
}

.player-bar.active.red {
  border-color: rgba(239, 68, 68, 0.45);
  box-shadow: 0 0 0 1px rgba(239, 68, 68, 0.12), 0 8px 24px rgba(239, 68, 68, 0.08);
}

.player-bar.active.yellow {
  border-color: rgba(251, 191, 36, 0.45);
  box-shadow: 0 0 0 1px rgba(251, 191, 36, 0.12), 0 8px 24px rgba(251, 191, 36, 0.08);
}

.player-bar.active::before {
  opacity: 1;
  width: 4px;
}

.player-bar.me {
  border-color: rgba(91, 156, 255, 0.35);
}

.disc-badge {
  width: 1.85rem;
  height: 1.85rem;
  border-radius: 50%;
  flex-shrink: 0;
  position: relative;
}

.disc-badge.red {
  background:
    radial-gradient(circle at 32% 28%, var(--c4-red-shine) 0%, var(--c4-red) 42%, var(--c4-red-deep) 100%);
  box-shadow:
    0 2px 6px rgba(185, 28, 28, 0.45),
    inset 0 -2px 4px rgba(0, 0, 0, 0.25),
    inset 0 2px 3px rgba(255, 255, 255, 0.25);
}

.disc-badge.yellow {
  background:
    radial-gradient(circle at 32% 28%, var(--c4-yellow-shine) 0%, var(--c4-yellow) 42%, var(--c4-yellow-deep) 100%);
  box-shadow:
    0 2px 6px rgba(217, 119, 6, 0.4),
    inset 0 -2px 4px rgba(0, 0, 0, 0.2),
    inset 0 2px 3px rgba(255, 255, 255, 0.3);
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
  font-size: 0.7rem;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  color: var(--text-muted);
}

.tag {
  font-size: 0.62rem;
  padding: 0.08rem 0.32rem;
  border-radius: 4px;
  background: rgba(29, 111, 212, 0.18);
  color: #7eb6ff;
  font-weight: 700;
}

.tag.you {
  background: rgba(91, 156, 255, 0.18);
  color: var(--accent);
}

.turn-pill {
  font-size: 0.66rem;
  font-weight: 700;
  letter-spacing: 0.05em;
  text-transform: uppercase;
  padding: 0.3rem 0.55rem;
  border-radius: 8px;
  background: rgba(29, 111, 212, 0.16);
  color: #8ec0ff;
  flex-shrink: 0;
  animation: turnPulse 1.8s ease-in-out infinite;
}

.player-bar.red .turn-pill {
  background: rgba(239, 68, 68, 0.16);
  color: #fca5a5;
}

.player-bar.yellow .turn-pill {
  background: rgba(251, 191, 36, 0.16);
  color: #fcd34d;
}

@keyframes turnPulse {
  0%,
  100% {
    opacity: 1;
  }
  50% {
    opacity: 0.7;
  }
}

.board-stage {
  position: relative;
  flex: 1;
  min-height: 0;
  display: grid;
  place-items: center;
  container-type: size;
}

.board-glow {
  position: absolute;
  width: min(90cqw, 90cqh);
  height: min(90cqw, 90cqh);
  border-radius: 50%;
  background: radial-gradient(circle, rgba(29, 111, 212, 0.22), transparent 68%);
  filter: blur(20px);
  pointer-events: none;
  z-index: 0;
  transition: opacity 0.4s;
}

.connect4-board.my-turn .board-glow {
  opacity: 1.15;
  background: radial-gradient(circle, rgba(29, 111, 212, 0.3), transparent 68%);
}

.board {
  --drop-rows: 1;
  position: relative;
  z-index: 1;
  width: min(100cqw, calc(100cqh * 7 / 7.35));
  height: auto;
  aspect-ratio: 7 / 7.35;
  container-type: size;
  display: flex;
  flex-direction: column;
  animation: boardSettle 0.55s var(--ease-bounce) both;
}

@keyframes boardSettle {
  from {
    opacity: 0;
    transform: translateY(12px) scale(0.97);
  }
  to {
    opacity: 1;
    transform: translateY(0) scale(1);
  }
}

@supports not (width: 1cqw) {
  .board {
    width: min(100%, calc(100dvh - 12rem));
    height: auto;
    max-height: 100%;
  }
}

.board.disabled {
  cursor: default;
}

.board-frame {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
  border-radius: 18px 18px 14px 14px;
  overflow: hidden;
  background:
    linear-gradient(165deg, #2a7fe0 0%, var(--c4-board) 28%, var(--c4-board-mid) 72%, var(--c4-board-dark) 100%);
  border: 3px solid var(--c4-board-edge);
  box-shadow:
    0 20px 48px rgba(0, 0, 0, 0.5),
    0 4px 12px rgba(13, 63, 134, 0.4),
    inset 0 2px 0 rgba(255, 255, 255, 0.22),
    inset 0 -3px 0 rgba(0, 0, 0, 0.25);
  padding: 2.5% 2.5% 3%;
}

.board-feet {
  display: flex;
  justify-content: space-between;
  padding: 0 6% 0;
  margin-top: -1px;
  height: 4.5%;
  min-height: 10px;
}

.board-feet span {
  width: 14%;
  height: 100%;
  border-radius: 0 0 8px 8px;
  background: linear-gradient(180deg, var(--c4-board-dark), var(--c4-board-edge));
  box-shadow: 0 4px 8px rgba(0, 0, 0, 0.35);
}

.column-hints {
  display: grid;
  grid-template-columns: repeat(7, 1fr);
  height: calc(100% / 7.2);
  min-height: 28px;
  margin-bottom: 1.5%;
  gap: 1.5%;
}

.col-hint {
  display: flex;
  align-items: center;
  justify-content: center;
  border: none;
  border-radius: 10px;
  background: rgba(7, 17, 31, 0.25);
  cursor: pointer;
  transition:
    background 0.18s var(--ease-smooth),
    transform 0.18s var(--ease-smooth);
  position: relative;
}

.col-hint.legal {
  background: rgba(7, 17, 31, 0.35);
}

.col-hint.legal:hover,
.col-hint.legal:focus-visible,
.col-hint.hovered {
  background: rgba(255, 255, 255, 0.12);
  transform: translateY(-1px);
}

.col-hint:not(.legal),
.col-hint:disabled {
  cursor: default;
  opacity: 0.45;
}

.hint-arrow {
  width: 0;
  height: 0;
  border-left: 0.35em solid transparent;
  border-right: 0.35em solid transparent;
  border-top: 0.5em solid rgba(255, 255, 255, 0.25);
  font-size: min(5.5cqw, 5.5cqh);
  transition:
    border-top-color 0.18s,
    transform 0.18s var(--ease-bounce),
    opacity 0.18s;
  opacity: 0.5;
}

.col-hint.legal .hint-arrow {
  opacity: 0.85;
  border-top-color: rgba(255, 255, 255, 0.55);
}

.col-hint.hovered .hint-arrow,
.col-hint.legal:focus-visible .hint-arrow {
  opacity: 1;
  transform: translateY(2px);
  animation: arrowBounce 0.7s var(--ease-bounce) infinite;
}

.col-hint.hovered .hint-arrow.red,
.col-hint.legal:focus-visible .hint-arrow.red {
  border-top-color: var(--c4-red);
  filter: drop-shadow(0 0 6px rgba(239, 68, 68, 0.6));
}

.col-hint.hovered .hint-arrow.yellow,
.col-hint.legal:focus-visible .hint-arrow.yellow {
  border-top-color: var(--c4-yellow);
  filter: drop-shadow(0 0 6px rgba(251, 191, 36, 0.6));
}

@keyframes arrowBounce {
  0%,
  100% {
    transform: translateY(0);
  }
  50% {
    transform: translateY(3px);
  }
}

.grid {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 1.5%;
  min-height: 0;
}

.grid-row {
  display: grid;
  grid-template-columns: repeat(7, 1fr);
  flex: 1;
  min-height: 0;
  gap: 1.5%;
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
  background: transparent;
  aspect-ratio: 1;
  min-height: 0;
}

.board.interactive .cell {
  cursor: pointer;
}

.board.disabled .cell {
  cursor: default;
}

.cell-hole {
  position: absolute;
  inset: 4%;
  border-radius: 50%;
  background:
    radial-gradient(circle at 50% 42%, #0c1a2e 0%, var(--c4-hole) 70%);
  box-shadow:
    inset 0 3px 6px rgba(0, 0, 0, 0.65),
    inset 0 -1px 0 var(--c4-hole-rim),
    0 1px 0 rgba(255, 255, 255, 0.1);
  transition: box-shadow 0.15s;
}

.cell.preview-target .cell-hole {
  box-shadow:
    inset 0 3px 6px rgba(0, 0, 0, 0.55),
    inset 0 -1px 0 var(--c4-hole-rim),
    0 0 0 2px rgba(255, 255, 255, 0.18),
    0 1px 0 rgba(255, 255, 255, 0.1);
}

.cell.last .cell-hole {
  box-shadow:
    inset 0 3px 6px rgba(0, 0, 0, 0.55),
    0 0 0 2px rgba(255, 255, 255, 0.28),
    0 1px 0 rgba(255, 255, 255, 0.1);
}

.disc {
  position: relative;
  z-index: 1;
  width: 86%;
  height: 86%;
  border-radius: 50%;
  flex-shrink: 0;
  user-select: none;
}

.disc.red {
  background:
    radial-gradient(circle at 32% 28%, var(--c4-red-shine) 0%, var(--c4-red) 38%, var(--c4-red-deep) 100%);
  box-shadow:
    0 3px 6px rgba(0, 0, 0, 0.4),
    inset 0 -3px 5px rgba(0, 0, 0, 0.28),
    inset 0 3px 4px rgba(255, 255, 255, 0.28);
}

.disc.yellow {
  background:
    radial-gradient(circle at 32% 28%, var(--c4-yellow-shine) 0%, var(--c4-yellow) 38%, var(--c4-yellow-deep) 100%);
  box-shadow:
    0 3px 6px rgba(0, 0, 0, 0.35),
    inset 0 -3px 5px rgba(0, 0, 0, 0.22),
    inset 0 3px 4px rgba(255, 255, 255, 0.35);
}

.disc.preview {
  opacity: 0.42;
  animation: previewPulse 1.1s ease-in-out infinite;
}

@keyframes previewPulse {
  0%,
  100% {
    opacity: 0.35;
    transform: scale(0.96);
  }
  50% {
    opacity: 0.55;
    transform: scale(1);
  }
}

.disc.drop-anim {
  animation: discDrop calc(0.18s + var(--drop-rows) * 0.06s) cubic-bezier(0.22, 0.9, 0.35, 1.15) both;
}

@keyframes discDrop {
  0% {
    transform: translateY(calc(-100% * var(--drop-rows) - 40%));
    opacity: 0.85;
  }
  70% {
    opacity: 1;
  }
  85% {
    transform: translateY(3%);
  }
  100% {
    transform: translateY(0);
  }
}

.disc.winning {
  animation: winShine 1.1s ease-in-out infinite;
}

.disc.winning.drop-anim {
  animation:
    discDrop calc(0.18s + var(--drop-rows) * 0.06s) cubic-bezier(0.22, 0.9, 0.35, 1.15) both,
    winShine 1.1s ease-in-out 0.4s infinite;
}

@keyframes winShine {
  0%,
  100% {
    filter: brightness(1);
    box-shadow:
      0 3px 6px rgba(0, 0, 0, 0.4),
      inset 0 -3px 5px rgba(0, 0, 0, 0.28),
      inset 0 3px 4px rgba(255, 255, 255, 0.28),
      0 0 0 0 rgba(255, 255, 255, 0);
  }
  50% {
    filter: brightness(1.18);
    box-shadow:
      0 3px 6px rgba(0, 0, 0, 0.4),
      inset 0 -3px 5px rgba(0, 0, 0, 0.28),
      inset 0 3px 4px rgba(255, 255, 255, 0.4),
      0 0 14px 2px rgba(255, 255, 255, 0.45);
  }
}

.cell.winning::after {
  content: '';
  position: absolute;
  inset: -2%;
  border-radius: 50%;
  border: 2px solid rgba(255, 255, 255, 0.75);
  pointer-events: none;
  z-index: 2;
  animation: winRing 1.1s ease-in-out infinite;
}

@keyframes winRing {
  0%,
  100% {
    transform: scale(1);
    opacity: 0.7;
  }
  50% {
    transform: scale(1.06);
    opacity: 1;
  }
}

.game-over-overlay {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(6, 10, 18, 0.5);
  backdrop-filter: blur(3px);
  border-radius: 16px;
  z-index: 5;
  animation: overlayIn 0.35s var(--ease-smooth) both;
}

@keyframes overlayIn {
  from {
    opacity: 0;
  }
  to {
    opacity: 1;
  }
}

.game-over-card {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 0.85rem;
  padding: 1.35rem 1.75rem;
  border-radius: 16px;
  border: 1px solid rgba(29, 111, 212, 0.4);
  background: linear-gradient(165deg, rgba(30, 42, 68, 0.97), rgba(16, 24, 40, 0.98));
  box-shadow: 0 16px 40px rgba(0, 0, 0, 0.45), 0 0 0 1px rgba(255, 255, 255, 0.04);
  max-width: 90%;
  animation: cardPop 0.45s var(--ease-bounce) both;
}

@keyframes cardPop {
  from {
    opacity: 0;
    transform: scale(0.9) translateY(8px);
  }
  to {
    opacity: 1;
    transform: scale(1) translateY(0);
  }
}

.game-over-disc {
  width: 2.5rem;
  height: 2.5rem;
  border-radius: 50%;
}

.game-over-disc.red {
  background:
    radial-gradient(circle at 32% 28%, var(--c4-red-shine) 0%, var(--c4-red) 42%, var(--c4-red-deep) 100%);
  box-shadow: 0 4px 16px rgba(239, 68, 68, 0.45);
}

.game-over-disc.yellow {
  background:
    radial-gradient(circle at 32% 28%, var(--c4-yellow-shine) 0%, var(--c4-yellow) 42%, var(--c4-yellow-deep) 100%);
  box-shadow: 0 4px 16px rgba(251, 191, 36, 0.45);
}

.game-over-title {
  margin: 0;
  font-family: 'Outfit', 'DM Sans', system-ui, sans-serif;
  font-weight: 650;
  font-size: 1.15rem;
  text-align: center;
  line-height: 1.35;
}

.side-rail {
  min-height: 0;
  display: flex;
  flex-direction: column;
  gap: 0.65rem;
  padding: 0.8rem;
  border-radius: 14px;
  border: 1px solid var(--border);
  background: rgba(21, 28, 44, 0.62);
  backdrop-filter: blur(8px);
}

.status-chip {
  display: flex;
  align-items: flex-start;
  gap: 0.55rem;
  padding: 0.7rem 0.75rem;
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
  animation: turnPulse 1.5s ease-in-out infinite;
}

.status-chip.over {
  border-color: rgba(29, 111, 212, 0.45);
  background: rgba(29, 111, 212, 0.08);
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
  font-variant-numeric: tabular-nums;
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
  gap: 0.4rem;
  padding: 0.3rem 0.4rem;
  border-radius: 7px;
  font-size: 0.8rem;
  animation: moveIn 0.25s var(--ease-smooth) both;
}

@keyframes moveIn {
  from {
    opacity: 0;
    transform: translateX(4px);
  }
  to {
    opacity: 1;
    transform: translateX(0);
  }
}

.move-entry:nth-child(odd) {
  background: rgba(10, 14, 23, 0.35);
}

.move-num {
  width: 1.6rem;
  color: var(--text-muted);
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
  font-variant-numeric: tabular-nums;
}

.move-disc {
  width: 0.75rem;
  height: 0.75rem;
  border-radius: 50%;
  flex-shrink: 0;
}

.move-disc.red {
  background: radial-gradient(circle at 35% 30%, var(--c4-red-shine), var(--c4-red) 55%, var(--c4-red-deep));
}

.move-disc.yellow {
  background: radial-gradient(circle at 35% 30%, var(--c4-yellow-shine), var(--c4-yellow) 55%, var(--c4-yellow-deep));
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

  .board-frame {
    border-radius: 14px 14px 10px 10px;
  }
}

@media (prefers-reduced-motion: reduce) {
  .connect4-board,
  .board,
  .disc.drop-anim,
  .disc.preview,
  .disc.winning,
  .turn-pill,
  .hint-arrow,
  .game-over-overlay,
  .game-over-card,
  .move-entry,
  .cell.winning::after {
    animation: none !important;
  }
}
</style>
