<script setup lang="ts">
import { computed, ref, watch } from 'vue'
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
const STAR_POINTS = [
  [2, 2],
  [2, 6],
  [6, 2],
  [6, 6],
  [4, 4],
] as const

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

const gridLines = computed(() => Array.from({ length: SIZE }, (_, i) => i))

const boardPoints = computed(() => {
  const points: { row: number; col: number; coord: string }[] = []
  for (let row = 0; row < SIZE; row++) {
    for (let col = 0; col < SIZE; col++) {
      points.push({ row, col, coord: coordOf(row, col) })
    }
  }
  return points
})

const legalCoords = computed(
  () => new Set(props.gameState.legal_plays.map((p) => p.coord.toLowerCase())),
)

const lastPlayCoord = computed(() => {
  const move = props.gameState.last_move
  if (!move || move.type !== 'play' || !move.coord) return null
  return move.coord.toLowerCase()
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

/** Map board row/col to visual % position on the grid (lines cross at these points). */
function intersectionPos(row: number, col: number): { left: string; top: string } {
  const visRow = flipBoard.value ? SIZE - 1 - row : row
  const visCol = flipBoard.value ? SIZE - 1 - col : col
  const pos = (index: number) => `calc(var(--grid-inset) + ${index} * var(--step))`
  return { left: pos(visCol), top: pos(visRow) }
}

function linePos(index: number): string {
  return `${(index / (SIZE - 1)) * 100}%`
}

function isStarPoint(row: number, col: number): boolean {
  return STAR_POINTS.some(([r, c]) => r === row && c === col)
}

function onPlayClick(coord: string) {
  if (!isMyTurn.value) return
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

const latestHistoryRow = computed(() =>
  historyRows.value.length ? historyRows.value[historyRows.value.length - 1].n : null,
)

const animatingPlaced = ref<string | null>(null)
const fadingStones = ref<Map<string, 'B' | 'W'>>(new Map())

watch(lastPlayCoord, (coord) => {
  if (!coord) return
  animatingPlaced.value = coord
  window.setTimeout(() => {
    if (animatingPlaced.value === coord) animatingPlaced.value = null
  }, 450)
})

watch(
  () => props.gameState.board,
  (newBoard, oldBoard) => {
    if (!oldBoard) return
    const fading = new Map<string, 'B' | 'W'>()
    for (let row = 0; row < SIZE; row++) {
      for (let col = 0; col < SIZE; col++) {
        const prev = oldBoard[row]?.[col]
        const next = newBoard[row]?.[col]
        if (prev && !next && (prev === 'B' || prev === 'W')) {
          fading.set(coordOf(row, col), prev)
        }
      }
    }
    if (fading.size === 0) return
    fadingStones.value = fading
    window.setTimeout(() => {
      fadingStones.value = new Map()
    }, 380)
  },
  { deep: true },
)

function isAiThinking(color: 'B' | 'W' | undefined): boolean {
  if (!color || props.gameState.phase !== 'playing') return false
  const player = props.gameState.players.find((p) => p.color === color)
  return Boolean(player?.is_ai && props.gameState.current_color === color)
}
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
            thinking: isAiThinking(topPlayer?.color),
          }"
        >
          <span class="stone-badge" :class="topPlayer?.color === 'B' ? 'stone-b' : 'stone-w'" aria-hidden="true" />
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
          <div class="board-frame" :class="{ disabled: !isMyTurn && gameState.phase === 'playing' }">
            <div class="coord-left" aria-hidden="true">
              <span v-for="row in ranks" :key="`r-${row}`" class="coord-label">{{ row + 1 }}</span>
            </div>

            <div class="grid-area">
              <div class="grid-surface" aria-hidden="true" />
              <div class="grid-lines" aria-hidden="true">
                <div
                  v-for="i in gridLines"
                  :key="`h-${i}`"
                  class="hline"
                  :class="{ edge: i === 0 || i === SIZE - 1 }"
                  :style="{ top: linePos(i) }"
                />
                <div
                  v-for="i in gridLines"
                  :key="`v-${i}`"
                  class="vline"
                  :class="{ edge: i === 0 || i === SIZE - 1 }"
                  :style="{ left: linePos(i) }"
                />
              </div>

              <div class="board-layer visuals-layer" aria-hidden="true">
                <div
                  v-for="pt in boardPoints"
                  :key="`v-${pt.coord}`"
                  class="board-node"
                  :style="intersectionPos(pt.row, pt.col)"
                >
                  <span
                    v-if="fadingStones.has(pt.coord)"
                    class="stone fading"
                    :class="fadingStones.get(pt.coord) === 'B' ? 'stone-b' : 'stone-w'"
                  />
                  <span
                    v-if="stoneAt(pt.row, pt.col)"
                    class="stone"
                    :class="[
                      stoneAt(pt.row, pt.col) === 'B' ? 'stone-b' : 'stone-w',
                      { placed: animatingPlaced === pt.coord },
                    ]"
                  />
                  <span v-else-if="isStarPoint(pt.row, pt.col)" class="star-dot" />
                  <span v-if="lastPlayCoord === pt.coord" class="last-marker" />
                </div>
              </div>

              <div v-if="isMyTurn" class="board-layer click-layer">
                <button
                  v-for="play in gameState.legal_plays"
                  :key="play.coord"
                  type="button"
                  class="play-target"
                  :style="intersectionPos(play.row, play.col)"
                  :aria-label="`Play ${play.coord}`"
                  @click="onPlayClick(play.coord.toLowerCase())"
                >
                  <span class="hint-dot" aria-hidden="true" />
                </button>
              </div>
            </div>

            <div class="coord-bottom" aria-hidden="true">
              <span v-for="file in files" :key="`f-${file}`" class="coord-label">{{ file }}</span>
            </div>
          </div>

          <Transition name="go-overlay">
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
          </Transition>
        </div>

        <div
          class="player-bar"
          :class="{
            active: isPlayerToMove(bottomPlayer?.color),
            ai: bottomPlayer?.is_ai,
            me: bottomPlayer?.id === playerId,
            thinking: isAiThinking(bottomPlayer?.color),
          }"
        >
          <span class="stone-badge" :class="bottomPlayer?.color === 'B' ? 'stone-b' : 'stone-w'" aria-hidden="true" />
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
            <div
              v-for="row in historyRows"
              :key="row.n"
              class="move-row"
              :class="{ latest: row.n === latestHistoryRow }"
            >
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
  --wood-light: #d4b896;
  --wood-dark: #a08050;
  --wood-frame: #5c3d28;
  --wood-grain: rgba(92, 61, 40, 0.06);
  --grid: rgba(0, 0, 0, 0.72);
  --grid-edge: rgba(0, 0, 0, 0.88);
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
    border-color 0.25s var(--ease-smooth),
    box-shadow 0.25s var(--ease-smooth),
    background 0.25s var(--ease-smooth);
}

.player-bar.active {
  border-color: color-mix(in srgb, var(--accent) 50%, var(--border));
  box-shadow: 0 0 0 1px color-mix(in srgb, var(--accent) 25%, transparent);
}

.player-bar.me {
  border-color: color-mix(in srgb, var(--accent) 35%, var(--border));
}

.player-bar.thinking {
  animation: aiThinking 1.8s ease-in-out infinite;
}

@keyframes aiThinking {
  0%, 100% {
    box-shadow: 0 0 0 1px color-mix(in srgb, #c9a0ff 20%, transparent);
  }
  50% {
    box-shadow:
      0 0 0 1px color-mix(in srgb, #c9a0ff 35%, transparent),
      0 0 16px color-mix(in srgb, #c9a0ff 15%, transparent);
  }
}

.stone-badge {
  width: 22px;
  height: 22px;
  border-radius: 50%;
  flex-shrink: 0;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.3);
}

.stone-badge.stone-b {
  background: radial-gradient(circle at 34% 30%, #4a4a4a, #0d0d0d);
}

.stone-badge.stone-w {
  background: radial-gradient(circle at 34% 30%, #fff, #d8d8d0);
  border: 1px solid rgba(0, 0, 0, 0.18);
}

.player-name {
  margin: 0;
  font-weight: 600;
  font-size: 0.92rem;
  color: var(--text);
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
  display: grid;
  place-items: center;
  container-type: size;
}

.board-frame {
  /* Largest square that fits the stage */
  width: min(100cqw, 100cqh);
  height: min(100cqw, 100cqh);
  display: grid;
  grid-template-columns: 1.85rem 1fr;
  grid-template-rows: 1fr 1.85rem;
  gap: 0.25rem 0.4rem;
  padding: 0.8rem;
  background:
    linear-gradient(160deg, var(--wood-light) 0%, var(--wood) 45%, var(--wood-dark) 100%);
  border: 3px solid var(--wood-frame);
  border-radius: 10px;
  box-shadow:
    0 16px 48px rgba(0, 0, 0, 0.45),
    inset 0 0 0 1px rgba(255, 255, 255, 0.1),
    inset 0 2px 8px rgba(255, 255, 255, 0.06);
  animation: boardEnter 0.5s var(--ease-smooth);
  position: relative;
  overflow: visible;
}

.board-frame::before {
  content: '';
  position: absolute;
  inset: 0;
  background:
    repeating-linear-gradient(
      92deg,
      transparent 0,
      transparent 18px,
      var(--wood-grain) 18px,
      var(--wood-grain) 19px
    ),
    repeating-linear-gradient(
      8deg,
      transparent 0,
      transparent 42px,
      rgba(255, 255, 255, 0.03) 42px,
      rgba(255, 255, 255, 0.03) 43px
    );
  pointer-events: none;
  z-index: 0;
}

@keyframes boardEnter {
  from {
    opacity: 0;
    transform: scale(0.97);
  }
  to {
    opacity: 1;
    transform: scale(1);
  }
}

@supports not (width: 1cqw) {
  .board-frame {
    width: min(100%, calc(100dvh - 11.5rem));
    height: auto;
    aspect-ratio: 1;
    max-height: 100%;
  }
}

.board-frame.disabled {
  opacity: 0.96;
}

.board-frame.disabled .play-target {
  cursor: default;
}

.coord-left {
  grid-column: 1;
  grid-row: 1;
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  align-items: center;
  padding: 0;
  z-index: 1;
}

.coord-bottom {
  grid-column: 2;
  grid-row: 2;
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0 0.05rem;
  z-index: 1;
}

.coord-label {
  font-size: 1rem;
  font-weight: 700;
  color: rgba(0, 0, 0, 0.55);
  line-height: 1;
  user-select: none;
  font-family: 'Outfit', 'DM Sans', system-ui, sans-serif;
  text-shadow: 0 1px 0 rgba(255, 255, 255, 0.25);
}

.grid-area {
  grid-column: 2;
  grid-row: 1;
  position: relative;
  min-width: 0;
  min-height: 0;
  z-index: 1;
  overflow: visible;
  --cell: calc(100% / 8);
  --grid-inset: calc(var(--cell) * 0.24);
  --step: calc((100% - 2 * var(--grid-inset)) / 8);
  --stone-size: calc(var(--step) * 0.658);
  --hit-size: calc(var(--step) * 1.05);
}

.visuals-layer {
  z-index: 2;
}

.board-layer {
  position: absolute;
  inset: 0;
  pointer-events: none;
}

.click-layer {
  z-index: 4;
  pointer-events: none;
}

.board-node {
  position: absolute;
  width: var(--stone-size);
  height: var(--stone-size);
  transform: translate(-50%, -50%);
  pointer-events: none;
}

.play-target {
  position: absolute;
  width: var(--hit-size);
  height: var(--hit-size);
  padding: 0;
  border: none;
  background: transparent;
  cursor: pointer;
  transform: translate(-50%, -50%);
  pointer-events: auto;
  border-radius: 50%;
  z-index: 1;
}

.play-target:active {
  transform: translate(-50%, -50%) scale(0.98);
}

.play-target:hover {
  background: color-mix(in srgb, var(--accent) 10%, transparent);
}

.play-target:hover .hint-dot {
  background: color-mix(in srgb, var(--accent) 75%, #333);
  box-shadow: 0 0 8px color-mix(in srgb, var(--accent) 35%, transparent);
}

.grid-surface {
  position: absolute;
  inset: var(--grid-inset);
  border-radius: 3px;
  background: linear-gradient(145deg, rgba(255, 255, 255, 0.04) 0%, transparent 50%, rgba(0, 0, 0, 0.04) 100%);
  box-shadow:
    inset 0 1px 4px rgba(0, 0, 0, 0.12),
    inset 0 -1px 2px rgba(255, 255, 255, 0.08);
  pointer-events: none;
}

.grid-lines {
  position: absolute;
  inset: var(--grid-inset);
  pointer-events: none;
}

.hline,
.vline {
  position: absolute;
  background: var(--grid);
  pointer-events: none;
}

.hline {
  left: 0;
  right: 0;
  height: 1px;
  transform: translateY(-50%);
}

.vline {
  top: 0;
  bottom: 0;
  width: 1px;
  transform: translateX(-50%);
}

.hline {
  left: 0;
  right: 0;
  height: 1px;
  transform: translateY(-50%);
}

.hline.edge {
  height: 1.5px;
  background: var(--grid-edge);
}

.vline {
  top: 0;
  bottom: 0;
  width: 1px;
  transform: translateX(-50%);
}

.vline.edge {
  width: 1.5px;
  background: var(--grid-edge);
}

.stone {
  position: absolute;
  inset: 0;
  border-radius: 50%;
  pointer-events: none;
}

.stone.placed {
  animation: stonePlace 0.38s var(--ease-bounce);
}

.stone.fading {
  animation: stoneCapture 0.36s var(--ease-smooth) forwards;
  z-index: 4;
}

@keyframes stonePlace {
  0% {
    transform: scale(0);
    opacity: 0.6;
  }
  60% {
    transform: scale(1.08);
    opacity: 1;
  }
  100% {
    transform: scale(1);
    opacity: 1;
  }
}

@keyframes stoneCapture {
  0% {
    transform: scale(1);
    opacity: 1;
  }
  100% {
    transform: scale(0.4);
    opacity: 0;
  }
}

.stone.stone-b {
  background: radial-gradient(circle at 34% 28%, #555 0%, #222 35%, #0a0a0a 100%);
  box-shadow:
    0 2px 4px rgba(0, 0, 0, 0.4),
    inset 0 2px 3px rgba(255, 255, 255, 0.08),
    inset 0 -2px 4px rgba(0, 0, 0, 0.35);
}

.stone.stone-w {
  background: radial-gradient(circle at 34% 28%, #fff 0%, #eee 40%, #ccc 100%);
  border: 1px solid rgba(0, 0, 0, 0.2);
  box-shadow:
    0 2px 4px rgba(0, 0, 0, 0.22),
    inset 0 2px 4px rgba(255, 255, 255, 0.95),
    inset 0 -2px 3px rgba(0, 0, 0, 0.08);
}

.star-dot {
  position: absolute;
  width: calc(var(--step) * 0.14);
  height: calc(var(--step) * 0.14);
  min-width: 4px;
  min-height: 4px;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  border-radius: 50%;
  background: var(--grid);
  pointer-events: none;
  box-shadow: 0 0 0 0.5px rgba(255, 255, 255, 0.15);
}

.hint-dot {
  position: absolute;
  width: calc(var(--stone-size) * 0.32);
  height: calc(var(--stone-size) * 0.32);
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  border-radius: 50%;
  background: rgba(0, 0, 0, 0.28);
  pointer-events: none;
  transition: background 0.15s var(--ease-smooth), box-shadow 0.15s var(--ease-smooth);
  animation: hintPulse 2s ease-in-out infinite;
}

@keyframes hintPulse {
  0%, 100% { opacity: 0.65; }
  50% { opacity: 1; }
}

.last-marker {
  position: absolute;
  inset: -3px;
  border-radius: 50%;
  border: 2px solid rgba(255, 190, 40, 0.9);
  pointer-events: none;
  box-shadow: 0 0 6px rgba(255, 190, 40, 0.35);
  animation: lastMovePulse 2s ease-in-out infinite;
}

@keyframes lastMovePulse {
  0%, 100% {
    border-color: rgba(255, 190, 40, 0.75);
    box-shadow: 0 0 4px rgba(255, 190, 40, 0.25);
  }
  50% {
    border-color: rgba(255, 210, 80, 1);
    box-shadow: 0 0 10px rgba(255, 190, 40, 0.45);
  }
}

.go-overlay-enter-active {
  transition: opacity 0.35s var(--ease-smooth);
}

.go-overlay-leave-active {
  transition: opacity 0.25s var(--ease-smooth);
}

.go-overlay-enter-from,
.go-overlay-leave-to {
  opacity: 0;
}

.go-overlay-enter-active .game-over-card {
  animation: celebrate 0.45s var(--ease-bounce);
}

.game-over-overlay {
  position: absolute;
  inset: 0;
  display: grid;
  place-items: center;
  background: rgba(0, 0, 0, 0.42);
  backdrop-filter: blur(2px);
  border-radius: 10px;
  z-index: 10;
}

.game-over-card {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 14px;
  padding: 1.25rem 1.5rem;
  text-align: center;
  max-width: 90%;
  box-shadow: var(--shadow);
}

.game-over-title {
  margin: 0;
  font-weight: 700;
  font-size: 1.05rem;
  color: var(--text);
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
  background: rgba(21, 28, 44, 0.72);
  font-size: 0.85rem;
  color: var(--text);
  flex-shrink: 0;
  transition: border-color 0.25s var(--ease-smooth);
}

.status-chip.active {
  border-color: color-mix(in srgb, var(--accent) 45%, var(--border));
}

.status-chip.active .status-dot {
  background: var(--accent);
  animation: statusPulse 1.5s ease-in-out infinite;
}

@keyframes statusPulse {
  0%, 100% { box-shadow: 0 0 0 0 var(--accent-glow); }
  50% { box-shadow: 0 0 0 4px transparent; }
}

.status-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--text-muted);
  flex-shrink: 0;
}

.status-chip.active .status-dot {
  background: var(--accent);
}

.action-row {
  display: flex;
  gap: 0.45rem;
  flex-shrink: 0;
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
  background: rgba(21, 28, 44, 0.72);
  overflow: hidden;
}

.history-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0.55rem 0.7rem;
  border-bottom: 1px solid var(--border);
  flex-shrink: 0;
}

.history-header h3 {
  margin: 0;
  font-size: 0.85rem;
  color: var(--text);
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
  color: var(--text);
  border-radius: 6px;
  transition: background 0.2s var(--ease-smooth);
}

.move-row.latest {
  background: color-mix(in srgb, var(--accent) 12%, transparent);
  animation: moveRowIn 0.3s var(--ease-smooth);
}

@keyframes moveRowIn {
  from {
    opacity: 0;
    transform: translateX(-4px);
  }
  to {
    opacity: 1;
    transform: translateX(0);
  }
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

@media (max-width: 860px) {
  .go-shell {
    grid-template-columns: 1fr;
    grid-template-rows: auto 1fr;
  }

  .side-rail {
    order: -1;
    flex-direction: row;
    flex-wrap: wrap;
    align-items: stretch;
  }

  .status-chip {
    flex: 1;
    min-width: 140px;
  }

  .action-row {
    flex: 1;
    min-width: 160px;
  }

  .history-panel {
    width: 100%;
    max-height: 120px;
  }
}

@media (max-width: 520px) {
  .go-board {
    padding: 0.35rem 0.45rem 0.5rem;
  }

  .board-frame {
    padding: 0.55rem;
    grid-template-columns: 1.55rem 1fr;
    grid-template-rows: 1fr 1.55rem;
  }

  .coord-label {
    font-size: 0.88rem;
  }
}
</style>
