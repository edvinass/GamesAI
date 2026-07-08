<script setup lang="ts">
import { computed } from 'vue'
import type { GoGameState, Room } from '@/types'

const props = defineProps<{
  gameState: GoGameState
  room: Room
  playerId: string
}>()

const emit = defineEmits<{
  action: [data: Record<string, unknown>]
}>()

const FILES = 'abcdefghi'.split('')
const SIZE = 9

const viewerColor = computed(() => props.gameState.viewer_color)
const flipBoard = computed(() => viewerColor.value === 'W')

const isMyTurn = computed(() => {
  if (props.gameState.phase !== 'playing') return false
  return props.gameState.current_actor_id === props.playerId
})

const isSpectator = computed(() => !props.gameState.viewer_color)

const blackPlayer = computed(() => props.gameState.players.find((p) => p.color === 'B'))
const whitePlayer = computed(() => props.gameState.players.find((p) => p.color === 'W'))
const topPlayer = computed(() => (flipBoard.value ? blackPlayer.value : whitePlayer.value))
const bottomPlayer = computed(() => (flipBoard.value ? whitePlayer.value : blackPlayer.value))

const ranks = computed(() => {
  const order = Array.from({ length: SIZE }, (_, i) => i)
  return flipBoard.value ? [...order].reverse() : order
})

const files = computed(() => (flipBoard.value ? [...FILES].reverse() : FILES))

const legalCoords = computed(() => new Set(props.gameState.legal_plays.map((p) => p.coord)))

const lastPlayCoord = computed(() => {
  const move = props.gameState.last_move
  if (!move || move.type !== 'play') return null
  return move.coord
})

const captured = computed(() => props.gameState.captured ?? { B: 0, W: 0 })

const statusText = computed(() => {
  const gs = props.gameState
  if (gs.phase === 'game_over') {
    if (gs.win_reason === 'resign') {
      const winner = gs.players.find((p) => p.id === gs.winner)
      return `${winner?.nickname ?? 'Player'} wins by resignation`
    }
    if (gs.win_reason === 'score_draw') return 'Game drawn — equal scores'
    if (gs.score) {
      const winner = gs.players.find((p) => p.color === gs.winner_color)
      const b = gs.score.black_score.toFixed(1)
      const w = gs.score.white_score.toFixed(1)
      return `${winner?.nickname ?? 'Player'} wins ${b} – ${w}`
    }
    return 'Game over'
  }
  if (isSpectator.value) return `${props.gameState.current_color === 'B' ? 'Black' : 'White'} to play`
  if (isMyTurn.value) return 'Your turn'
  const actor = gs.players.find((p) => p.id === gs.current_actor_id)
  return actor?.is_ai ? 'AI is thinking…' : `${actor?.nickname ?? 'Opponent'} is thinking…`
})

const statusTone = computed(() => {
  if (props.gameState.phase === 'game_over') return 'over'
  if (isMyTurn.value) return 'active'
  return 'idle'
})

function stoneAt(row: number, col: number): string | null {
  return props.gameState.board[row]?.[col] ?? null
}

function coordOf(row: number, col: number): string {
  return `${FILES[col]}${row + 1}`
}

function onIntersectionClick(row: number, col: number) {
  if (!isMyTurn.value) return
  const coord = coordOf(row, col)
  if (!legalCoords.value.has(coord)) return
  emit('action', { type: 'play', coord })
}

function passTurn() {
  emit('action', { type: 'pass' })
}

function resign() {
  if (confirm('Resign this game?')) {
    emit('action', { type: 'resign' })
  }
}

function isPlayerToMove(color: 'B' | 'W' | undefined): boolean {
  return (
    props.gameState.phase === 'playing' &&
    Boolean(color) &&
    props.gameState.current_color === color
  )
}

const historyRows = computed(() => {
  const moves = props.gameState.move_history
  const rows: { n: number; black: string; white: string }[] = []
  for (let i = 0; i < moves.length; i += 2) {
    const n = Math.floor(i / 2) + 1
    const blackMove = moves[i]
    const whiteMove = moves[i + 1]
    rows.push({
      n,
      black: blackMove?.type === 'pass' ? 'pass' : blackMove?.coord?.toUpperCase() ?? '—',
      white: whiteMove?.type === 'pass' ? 'pass' : whiteMove?.coord?.toUpperCase() ?? '',
    })
  }
  return rows
})
</script>

<template>
  <div class="go-board">
    <div class="go-shell">
      <div class="play-column">
        <div
          class="player-bar"
          :class="{
            active: isPlayerToMove(topPlayer?.color),
            ai: topPlayer?.is_ai,
          }"
        >
          <span class="stone-badge" :class="topPlayer?.color === 'B' ? 'black' : 'white'" aria-hidden="true" />
          <div class="player-meta">
            <p class="player-name">
              {{ topPlayer?.nickname ?? 'Opponent' }}
              <span v-if="topPlayer?.is_ai" class="tag">AI</span>
              <span v-if="topPlayer?.id === playerId" class="tag you">You</span>
            </p>
            <p class="player-side">
              {{ topPlayer?.color === 'B' ? 'Black' : 'White' }} · captured
              {{ topPlayer?.color === 'B' ? captured.B : captured.W }}
            </p>
          </div>
          <span v-if="isPlayerToMove(topPlayer?.color)" class="turn-pill">
            {{ topPlayer?.is_ai ? 'Thinking' : 'To move' }}
          </span>
        </div>

        <div class="board-stage">
          <div class="board-frame" :class="{ disabled: !isMyTurn }">
            <div class="grid-lines" aria-hidden="true">
              <div v-for="r in SIZE" :key="`h-${r}`" class="hline" :style="{ top: `${((r - 1) / (SIZE - 1)) * 100}%` }" />
              <div v-for="c in SIZE" :key="`v-${c}`" class="vline" :style="{ left: `${((c - 1) / (SIZE - 1)) * 100}%` }" />
            </div>

            <div class="intersections">
              <div v-for="row in ranks" :key="row" class="rank-row">
                <button
                  v-for="file in files"
                  :key="`${file}${row}`"
                  type="button"
                  class="intersection"
                  :class="{
                    legal: isMyTurn && legalCoords.has(coordOf(row, FILES.indexOf(file))),
                    last: lastPlayCoord === coordOf(row, FILES.indexOf(file)),
                  }"
                  @click="onIntersectionClick(row, FILES.indexOf(file))"
                >
                  <span v-if="file === files[0]" class="coord rank">{{ row + 1 }}</span>
                  <span
                    v-if="stoneAt(row, FILES.indexOf(file))"
                    class="stone"
                    :class="stoneAt(row, FILES.indexOf(file)) === 'B' ? 'black' : 'white'"
                  />
                  <span
                    v-else-if="isMyTurn && legalCoords.has(coordOf(row, FILES.indexOf(file)))"
                    class="hint-dot"
                  />
                  <span v-if="row === ranks[ranks.length - 1]" class="coord file">{{ file }}</span>
                </button>
              </div>
            </div>
          </div>

          <div v-if="gameState.phase === 'game_over'" class="game-over-overlay">
            <div class="game-over-card">
              <p class="game-over-title">{{ statusText }}</p>
              <p v-if="gameState.score" class="game-over-score">
                Black {{ gameState.score.black_score.toFixed(1) }} ·
                White {{ gameState.score.white_score.toFixed(1) }}
                <span class="komi">(komi {{ gameState.score.komi }})</span>
              </p>
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
          <span class="stone-badge" :class="bottomPlayer?.color === 'B' ? 'black' : 'white'" aria-hidden="true" />
          <div class="player-meta">
            <p class="player-name">
              {{ bottomPlayer?.nickname ?? 'You' }}
              <span v-if="bottomPlayer?.is_ai" class="tag">AI</span>
              <span v-if="bottomPlayer?.id === playerId" class="tag you">You</span>
            </p>
            <p class="player-side">
              {{ bottomPlayer?.color === 'B' ? 'Black' : 'White' }} · captured
              {{ bottomPlayer?.color === 'B' ? captured.B : captured.W }}
            </p>
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
          <button type="button" class="btn-secondary" @click="passTurn">Pass</button>
          <button type="button" class="btn-secondary danger" @click="resign">Resign</button>
        </div>

        <div class="history-panel">
          <div class="history-header">
            <h3>Moves</h3>
            <span class="move-count">{{ gameState.move_history.length }}</span>
          </div>
          <div v-if="historyRows.length" class="move-table">
            <div v-for="row in historyRows" :key="row.n" class="move-row">
              <span class="move-n">{{ row.n }}.</span>
              <span class="move-coord">{{ row.black }}</span>
              <span class="move-coord">{{ row.white }}</span>
            </div>
          </div>
          <p v-else class="muted">No moves yet</p>
        </div>
      </aside>
    </div>
  </div>
</template>

<style scoped>
.go-board {
  --wood: #c4a574;
  --wood-dark: #8b6914;
  --grid: rgba(0, 0, 0, 0.72);
  flex: 1;
  min-height: 0;
  width: 100%;
  display: flex;
  padding: 0.5rem 0.75rem 0.75rem;
  overflow: hidden;
}

.go-shell {
  flex: 1;
  min-height: 0;
  display: grid;
  grid-template-columns: minmax(0, 1fr) 220px;
  gap: 0.85rem;
  max-width: 960px;
  margin: 0 auto;
  width: 100%;
}

.play-column {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
  min-height: 0;
}

.player-bar {
  display: flex;
  align-items: center;
  gap: 0.65rem;
  padding: 0.5rem 0.75rem;
  border-radius: 12px;
  border: 1px solid var(--border);
  background: var(--surface-2);
}

.player-bar.active {
  border-color: color-mix(in srgb, var(--accent) 50%, var(--border));
  box-shadow: 0 0 0 1px color-mix(in srgb, var(--accent) 25%, transparent);
}

.stone-badge {
  width: 22px;
  height: 22px;
  border-radius: 50%;
  flex-shrink: 0;
}

.stone-badge.black {
  background: radial-gradient(circle at 35% 35%, #444, #111);
}

.stone-badge.white {
  background: radial-gradient(circle at 35% 35%, #fff, #ddd);
  border: 1px solid #aaa;
}

.player-name {
  margin: 0;
  font-weight: 600;
  font-size: 0.92rem;
}

.player-side {
  margin: 0.1rem 0 0;
  font-size: 0.78rem;
  color: var(--text-muted);
}

.tag {
  font-size: 0.65rem;
  padding: 0.1rem 0.35rem;
  border-radius: 999px;
  margin-left: 0.25rem;
  font-weight: 600;
  background: color-mix(in srgb, var(--accent) 20%, transparent);
  color: var(--accent);
}

.tag.you {
  background: color-mix(in srgb, #4ade80 20%, transparent);
  color: #4ade80;
}

.turn-pill {
  margin-left: auto;
  font-size: 0.72rem;
  padding: 0.2rem 0.5rem;
  border-radius: 999px;
  background: color-mix(in srgb, var(--accent) 18%, transparent);
  color: var(--accent);
  font-weight: 600;
}

.board-stage {
  position: relative;
  flex: 1;
  min-height: 0;
  display: flex;
  align-items: center;
  justify-content: center;
}

.board-frame {
  position: relative;
  width: min(100%, 420px);
  aspect-ratio: 1;
  background: linear-gradient(160deg, #d4b896 0%, var(--wood) 45%, #a08050 100%);
  border: 3px solid #5c3d28;
  border-radius: 4px;
  box-shadow: inset 0 0 30px rgba(0, 0, 0, 0.08);
  padding: 4%;
}

.board-frame.disabled {
  opacity: 0.92;
}

.grid-lines {
  position: absolute;
  inset: 4%;
  pointer-events: none;
}

.hline,
.vline {
  position: absolute;
  background: var(--grid);
}

.hline {
  left: 0;
  right: 0;
  height: 1px;
}

.vline {
  top: 0;
  bottom: 0;
  width: 1px;
}

.intersections {
  position: relative;
  width: 100%;
  height: 100%;
  display: flex;
  flex-direction: column;
}

.rank-row {
  flex: 1;
  display: flex;
}

.intersection {
  flex: 1;
  position: relative;
  border: none;
  background: transparent;
  cursor: pointer;
  padding: 0;
  min-width: 0;
}

.intersection.legal:hover .hint-dot {
  transform: scale(1.2);
  background: color-mix(in srgb, var(--accent) 70%, #333);
}

.intersection.last::after {
  content: '';
  position: absolute;
  width: 28%;
  height: 28%;
  border-radius: 50%;
  background: rgba(255, 200, 50, 0.75);
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  pointer-events: none;
  z-index: 1;
}

.stone {
  position: absolute;
  width: 88%;
  height: 88%;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  border-radius: 50%;
  z-index: 2;
  pointer-events: none;
}

.stone.black {
  background: radial-gradient(circle at 32% 28%, #555, #0a0a0a);
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.45);
}

.stone.white {
  background: radial-gradient(circle at 32% 28%, #fff, #ccc);
  border: 1px solid #999;
  box-shadow: 0 2px 3px rgba(0, 0, 0, 0.2);
}

.hint-dot {
  position: absolute;
  width: 22%;
  height: 22%;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  border-radius: 50%;
  background: rgba(0, 0, 0, 0.35);
  pointer-events: none;
  transition: transform 0.12s ease;
}

.coord {
  position: absolute;
  font-size: 0.58rem;
  color: rgba(0, 0, 0, 0.55);
  pointer-events: none;
  font-weight: 600;
}

.coord.rank {
  left: -12%;
  top: 50%;
  transform: translateY(-50%);
}

.coord.file {
  bottom: -18%;
  left: 50%;
  transform: translateX(-50%);
}

.game-over-overlay {
  position: absolute;
  inset: 0;
  display: grid;
  place-items: center;
  background: rgba(0, 0, 0, 0.35);
  border-radius: 8px;
}

.game-over-card {
  background: var(--surface-1);
  border: 1px solid var(--border);
  border-radius: 14px;
  padding: 1.25rem 1.5rem;
  text-align: center;
  max-width: 90%;
}

.game-over-title {
  margin: 0;
  font-weight: 700;
  font-size: 1.05rem;
}

.game-over-score {
  margin: 0.5rem 0 0;
  font-size: 0.88rem;
  color: var(--text-muted);
}

.komi {
  font-size: 0.78rem;
}

.side-rail {
  display: flex;
  flex-direction: column;
  gap: 0.65rem;
  min-height: 0;
}

.status-chip {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.55rem 0.7rem;
  border-radius: 10px;
  border: 1px solid var(--border);
  background: var(--surface-2);
  font-size: 0.85rem;
}

.status-chip.active {
  border-color: color-mix(in srgb, var(--accent) 45%, var(--border));
}

.status-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--text-muted);
}

.status-chip.active .status-dot {
  background: var(--accent);
}

.action-row {
  display: flex;
  gap: 0.45rem;
}

.action-row .btn-secondary {
  flex: 1;
  font-size: 0.82rem;
}

.danger {
  color: #f87171;
}

.history-panel {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
  border: 1px solid var(--border);
  border-radius: 12px;
  background: var(--surface-2);
  overflow: hidden;
}

.history-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0.55rem 0.7rem;
  border-bottom: 1px solid var(--border);
}

.history-header h3 {
  margin: 0;
  font-size: 0.85rem;
}

.move-count {
  font-size: 0.75rem;
  color: var(--text-muted);
}

.move-table {
  overflow-y: auto;
  flex: 1;
  padding: 0.35rem 0;
}

.move-row {
  display: grid;
  grid-template-columns: 1.8rem 1fr 1fr;
  gap: 0.25rem;
  padding: 0.2rem 0.7rem;
  font-size: 0.8rem;
  font-family: ui-monospace, monospace;
}

.move-n {
  color: var(--text-muted);
}

.muted {
  padding: 0.75rem;
  margin: 0;
  font-size: 0.82rem;
  color: var(--text-muted);
}

@media (max-width: 768px) {
  .go-shell {
    grid-template-columns: 1fr;
    grid-template-rows: auto auto;
  }

  .side-rail {
    order: -1;
  }

  .history-panel {
    max-height: 140px;
  }
}
</style>
