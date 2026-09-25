<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import type { ChessGameState, Room } from '@/types'
import Chess3DView from './Chess3DView.vue'
import {
  getBoardViewPref,
  isMoveHintsEnabled,
  setBoardViewPref,
  setMoveHintsEnabled,
  type BoardView,
} from './prefs'
import { formatEngineScore, isCheatModeEnabled, useCheatEngine } from './cheatMode'

const props = defineProps<{
  gameState: ChessGameState
  room: Room
  playerId: string
}>()

const emit = defineEmits<{
  action: [data: Record<string, unknown>]
}>()

const FILES = ['a', 'b', 'c', 'd', 'e', 'f', 'g', 'h'] as const

/** cburnett piece set (Colin M.L. Burnett, CC BY-SA 3.0). */
const PIECE_SVG_MODULES = import.meta.glob('../../assets/chess/pieces/*.svg', {
  eager: true,
  query: '?url',
  import: 'default',
}) as Record<string, string>

const PIECE_SRC: Record<string, string> = Object.fromEntries(
  Object.entries(PIECE_SVG_MODULES).map(([path, url]) => [
    path.split('/').pop()!.replace('.svg', ''),
    url,
  ]),
)

const PIECE_NAME: Record<string, string> = {
  k: 'king',
  q: 'queen',
  r: 'rook',
  b: 'bishop',
  n: 'knight',
  p: 'pawn',
}

function isWhitePiece(piece: string): boolean {
  return piece === piece.toUpperCase()
}

function pieceSrc(piece: string): string {
  return PIECE_SRC[`${isWhitePiece(piece) ? 'w' : 'b'}${piece.toUpperCase()}`] ?? ''
}

function pieceAlt(piece: string): string {
  return `${isWhitePiece(piece) ? 'White' : 'Black'} ${PIECE_NAME[piece.toLowerCase()] ?? piece}`
}

const selected = ref<string | null>(null)
const pendingPromotion = ref<{ from: string; to: string } | null>(null)

const viewerColor = computed(() => props.gameState.viewer_color)
const flipBoard = computed(() => viewerColor.value === 'b')
const boardView = ref<BoardView>(
  getBoardViewPref(props.room.id) ?? (props.gameState.settings?.board_view === '3d' ? '3d' : '2d'),
)
watch(boardView, (view) => setBoardViewPref(props.room.id, view))
const is3d = computed(() => boardView.value === '3d')

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

const whitePlayer = computed(() => props.gameState.players.find((p) => p.color === 'w'))
const blackPlayer = computed(() => props.gameState.players.find((p) => p.color === 'b'))

const topPlayer = computed(() => (flipBoard.value ? whitePlayer.value : blackPlayer.value))
const bottomPlayer = computed(() => (flipBoard.value ? blackPlayer.value : whitePlayer.value))

const ranks = computed(() => {
  const order = [7, 6, 5, 4, 3, 2, 1, 0]
  return flipBoard.value ? [...order].reverse() : order
})

const files = computed(() => {
  const order = [...FILES]
  return flipBoard.value ? [...order].reverse() : order
})

const lastMoveSquares = computed(() => {
  const move = props.gameState.last_move
  if (!move) return new Set<string>()
  return new Set([move.from, move.to])
})

const selectedTargets = computed(() => {
  if (!selected.value) return new Map<string, { promotion?: string | null }>()
  const map = new Map<string, { promotion?: string | null }>()
  for (const move of props.gameState.legal_moves) {
    if (move.from === selected.value) {
      map.set(move.to, { promotion: move.promotion })
    }
  }
  return map
})

const showMoveHints = ref(isMoveHintsEnabled())
watch(showMoveHints, setMoveHintsEnabled)

const targetSquares = computed(() =>
  showMoveHints.value ? [...selectedTargets.value.keys()] : [],
)

function isHintTarget(sq: string): boolean {
  return showMoveHints.value && selectedTargets.value.has(sq)
}

const cheatMode = isCheatModeEnabled()
const {
  status: engineStatus,
  engineLabel,
  suggestion: engineSuggestion,
} = useCheatEngine({
  enabled: cheatMode,
  fen: computed(() => props.gameState.fen),
  active: computed(() => isMyTurn.value && !isSpectator.value),
})

const engineHint = computed(() => {
  const s = engineSuggestion.value
  return s ? { from: s.from, to: s.to } : null
})

const engineArrow = computed(() => {
  const hint = engineHint.value
  if (!hint || is3d.value) return null
  const point = (sq: string) => ({
    x: files.value.indexOf(sq[0] as (typeof FILES)[number]) + 0.5,
    y: ranks.value.indexOf(Number(sq[1]) - 1) + 0.5,
  })
  const from = point(hint.from)
  const to = point(hint.to)
  const len = Math.hypot(to.x - from.x, to.y - from.y)
  const trim = 0.3 / len
  return { x1: from.x, y1: from.y, x2: to.x - (to.x - from.x) * trim, y2: to.y - (to.y - from.y) * trim }
})

const engineStatusText = computed(() => {
  if (engineStatus.value === 'loading') return 'Loading engine…'
  if (engineStatus.value === 'error') return 'Engine failed to load'
  if (props.gameState.phase !== 'playing') return 'Game over'
  if (!isMyTurn.value) return 'Waiting for your turn'
  const s = engineSuggestion.value
  if (!s) return 'Thinking…'
  return `${s.final ? 'Best' : 'Searching'} · depth ${s.depth}`
})

function playEngineMove() {
  const s = engineSuggestion.value
  if (!s || !isMyTurn.value || pendingPromotion.value) return
  emit('action', {
    type: 'move',
    from: s.from,
    to: s.to,
    ...(s.promotion ? { promotion: s.promotion } : {}),
  })
  selected.value = null
}

const checkedKingSquare = computed(() => {
  if (!props.gameState.in_check) return null
  const king = props.gameState.current_color === 'w' ? 'K' : 'k'
  for (let r = 0; r < 8; r++) {
    for (let f = 0; f < 8; f++) {
      if (props.gameState.board[r][f] === king) {
        return `${FILES[f]}${r + 1}`
      }
    }
  }
  return null
})

watch(
  () => props.gameState.fen,
  () => {
    selected.value = null
    pendingPromotion.value = null
  },
)

function squareOf(file: string, rankIndex: number): string {
  return `${file}${rankIndex + 1}`
}

function pieceAt(file: string, rankIndex: number): string | null {
  return props.gameState.board[rankIndex][FILES.indexOf(file as (typeof FILES)[number])] ?? null
}

function isLightSquare(file: string, rankIndex: number): boolean {
  const fileIndex = FILES.indexOf(file as (typeof FILES)[number])
  return (fileIndex + rankIndex) % 2 === 1
}

function ownPiece(piece: string | null): boolean {
  if (!piece || !viewerColor.value) return false
  const isWhite = piece === piece.toUpperCase()
  return viewerColor.value === 'w' ? isWhite : !isWhite
}

function onSquareClick(file: string, rankIndex: number) {
  if (!isMyTurn.value || pendingPromotion.value) return

  const sq = squareOf(file, rankIndex)
  const piece = pieceAt(file, rankIndex)

  if (selected.value) {
    if (selectedTargets.value.has(sq)) {
      const promo = selectedTargets.value.get(sq)?.promotion
      if (promo) {
        pendingPromotion.value = { from: selected.value, to: sq }
        return
      }
      emit('action', { type: 'move', from: selected.value, to: sq })
      selected.value = null
      return
    }
    if (ownPiece(piece)) {
      selected.value = sq
      return
    }
    selected.value = null
    return
  }

  if (ownPiece(piece)) {
    selected.value = sq
  }
}

function choosePromotion(piece: string) {
  if (!pendingPromotion.value) return
  emit('action', {
    type: 'move',
    from: pendingPromotion.value.from,
    to: pendingPromotion.value.to,
    promotion: piece,
  })
  pendingPromotion.value = null
  selected.value = null
}

function resign() {
  if (props.gameState.phase !== 'playing' || isSpectator.value) return
  if (window.confirm('Resign this game?')) {
    emit('action', { type: 'resign' })
  }
}

function offerDraw() {
  if (props.gameState.phase !== 'playing' || isSpectator.value) return
  emit('action', { type: 'offer_draw' })
}

function acceptDraw() {
  emit('action', { type: 'accept_draw' })
}

function declineDraw() {
  emit('action', { type: 'decline_draw' })
}

const statusText = computed(() => {
  const gs = props.gameState
  if (gs.phase === 'game_over') {
    if (gs.win_reason === 'checkmate') {
      const winner = gs.players.find((p) => p.id === gs.winner)
      return `Checkmate — ${winner?.nickname ?? 'Winner'} wins`
    }
    if (gs.win_reason === 'resign') {
      const winner = gs.players.find((p) => p.id === gs.winner)
      return `Resignation — ${winner?.nickname ?? 'Winner'} wins`
    }
    if (gs.win_reason === 'stalemate') return 'Draw — stalemate'
    if (gs.win_reason === 'draw_agreement') return 'Draw by agreement'
    if (gs.win_reason === 'fifty_move') return 'Draw — fifty-move rule'
    return 'Game over — draw'
  }
  if (gs.in_check) {
    return `${gs.current_color === 'w' ? 'White' : 'Black'} is in check`
  }
  if (!isMyTurn.value && actorNickname.value) {
    const actor = gs.players.find((p) => p.id === gs.current_actor_id)
    if (actor?.is_ai) return 'AI is thinking…'
    return `${actorNickname.value}'s turn`
  }
  return isMyTurn.value ? 'Your turn' : 'Waiting…'
})

const statusTone = computed(() => {
  if (props.gameState.phase === 'game_over') return 'over'
  if (props.gameState.in_check) return 'check'
  if (isMyTurn.value) return 'mine'
  return 'idle'
})

const showDrawOffer = computed(() => {
  const from = props.gameState.draw_offer_from
  return (
    props.gameState.phase === 'playing' &&
    from &&
    from !== props.playerId &&
    !isSpectator.value
  )
})

const historyRows = computed(() => {
  const history = props.gameState.move_history
  const rows: { n: number; white: string; black: string }[] = []
  for (let i = 0; i < history.length; i += 2) {
    const white = history[i]
    const black = history[i + 1]
    rows.push({
      n: Math.floor(i / 2) + 1,
      white: `${white.from}${white.to}${white.promotion ? `=${white.promotion.toUpperCase()}` : ''}`,
      black: black
        ? `${black.from}${black.to}${black.promotion ? `=${black.promotion.toUpperCase()}` : ''}`
        : '',
    })
  }
  return rows
})

function isPlayerToMove(color: 'w' | 'b' | undefined): boolean {
  return (
    props.gameState.phase === 'playing' &&
    Boolean(color) &&
    props.gameState.current_color === color
  )
}
</script>

<template>
  <div class="chess-board">
    <div class="chess-shell">
      <div class="play-column">
        <div
          class="player-bar"
          :class="{
            active: isPlayerToMove(topPlayer?.color),
            ai: topPlayer?.is_ai,
          }"
        >
          <span class="king-badge" :class="topPlayer?.color ?? 'b'" aria-hidden="true">
            <img :src="pieceSrc(topPlayer?.color === 'w' ? 'K' : 'k')" alt="" draggable="false" />
          </span>
          <div class="player-meta">
            <p class="player-name">
              {{ topPlayer?.nickname ?? 'Opponent' }}
              <span v-if="topPlayer?.is_ai" class="tag">AI</span>
              <span v-if="topPlayer?.id === playerId" class="tag you">You</span>
            </p>
            <p class="player-side">{{ topPlayer?.color === 'w' ? 'White' : 'Black' }}</p>
          </div>
          <span v-if="isPlayerToMove(topPlayer?.color)" class="turn-pill">
            {{ topPlayer?.is_ai ? 'Thinking' : 'To move' }}
          </span>
        </div>

        <div class="board-stage" :class="{ 'is-3d': is3d }">
          <Chess3DView
            v-if="is3d"
            :board="gameState.board"
            :fen="gameState.fen"
            :flipped="flipBoard"
            :interactive="isMyTurn && !pendingPromotion"
            :selected="selected"
            :targets="targetSquares"
            :last-move="gameState.last_move"
            :check-square="checkedKingSquare"
            :hint="engineHint"
            @square-click="onSquareClick"
          />
          <div
            v-else
            class="board"
            :class="{
              disabled: !isMyTurn || !!pendingPromotion,
              check: gameState.in_check && gameState.phase === 'playing',
            }"
          >
            <div class="board-grid">
              <div v-for="rankIndex in ranks" :key="rankIndex" class="rank-row">
                <button
                  v-for="file in files"
                  :key="`${file}${rankIndex}`"
                  type="button"
                  class="square"
                  :class="{
                    light: isLightSquare(file, rankIndex),
                    dark: !isLightSquare(file, rankIndex),
                    selected: selected === squareOf(file, rankIndex),
                    target: isHintTarget(squareOf(file, rankIndex)),
                    last: lastMoveSquares.has(squareOf(file, rankIndex)),
                    capture: isHintTarget(squareOf(file, rankIndex)) && !!pieceAt(file, rankIndex),
                    check: checkedKingSquare === squareOf(file, rankIndex),
                    'engine-hint':
                      engineHint?.from === squareOf(file, rankIndex) ||
                      engineHint?.to === squareOf(file, rankIndex),
                    movable: isMyTurn && !pendingPromotion && ownPiece(pieceAt(file, rankIndex)),
                  }"
                  @click="onSquareClick(file, rankIndex)"
                >
                  <span v-if="file === files[0]" class="coord rank">{{ rankIndex + 1 }}</span>
                  <img
                    v-if="pieceAt(file, rankIndex)"
                    class="piece"
                    :src="pieceSrc(pieceAt(file, rankIndex)!)"
                    :alt="pieceAlt(pieceAt(file, rankIndex)!)"
                    draggable="false"
                  />
                  <span
                    v-if="isHintTarget(squareOf(file, rankIndex)) && !pieceAt(file, rankIndex)"
                    class="target-dot"
                  />
                  <span v-if="rankIndex === ranks[ranks.length - 1]" class="coord file">{{ file }}</span>
                </button>
              </div>
              <svg
                v-if="engineArrow"
                class="engine-arrow"
                viewBox="0 0 8 8"
                aria-hidden="true"
              >
                <defs>
                  <marker
                    id="engine-arrow-head"
                    viewBox="0 0 4 4"
                    refX="1.2"
                    refY="2"
                    markerWidth="3"
                    markerHeight="3"
                    orient="auto"
                  >
                    <path d="M0,0 L4,2 L0,4 Z" />
                  </marker>
                </defs>
                <line
                  :x1="engineArrow.x1"
                  :y1="engineArrow.y1"
                  :x2="engineArrow.x2"
                  :y2="engineArrow.y2"
                  marker-end="url(#engine-arrow-head)"
                />
              </svg>
            </div>
          </div>

          <div v-if="pendingPromotion" class="promotion-overlay">
            <div class="promotion-card">
              <p>Promote to</p>
              <div class="promo-choices">
                <button
                  v-for="p in ['q', 'r', 'b', 'n']"
                  :key="p"
                  type="button"
                  class="promo-btn"
                  @click="choosePromotion(p)"
                >
                  <img
                    :src="pieceSrc(viewerColor === 'b' ? p : p.toUpperCase())"
                    :alt="pieceAlt(viewerColor === 'b' ? p : p.toUpperCase())"
                    draggable="false"
                  />
                </button>
              </div>
              <button
                type="button"
                class="btn-secondary promo-cancel"
                @click="
                  pendingPromotion = null;
                  selected = null
                "
              >
                Cancel
              </button>
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
          <span class="king-badge" :class="bottomPlayer?.color ?? 'w'" aria-hidden="true">
            <img :src="pieceSrc(bottomPlayer?.color === 'b' ? 'k' : 'K')" alt="" draggable="false" />
          </span>
          <div class="player-meta">
            <p class="player-name">
              {{ bottomPlayer?.nickname ?? 'You' }}
              <span v-if="bottomPlayer?.is_ai" class="tag">AI</span>
              <span v-if="bottomPlayer?.id === playerId" class="tag you">You</span>
            </p>
            <p class="player-side">{{ bottomPlayer?.color === 'b' ? 'Black' : 'White' }}</p>
          </div>
          <span v-if="isPlayerToMove(bottomPlayer?.color)" class="turn-pill">To move</span>
        </div>
      </div>

      <aside class="side-rail">
        <div class="status-chip" :class="statusTone">
          <span class="status-dot" aria-hidden="true" />
          <p>{{ statusText }}</p>
        </div>

        <div v-if="showDrawOffer" class="draw-offer">
          <p>Draw offered</p>
          <div class="draw-actions">
            <button type="button" class="btn-primary" @click="acceptDraw">Accept</button>
            <button type="button" class="btn-secondary" @click="declineDraw">Decline</button>
          </div>
        </div>

        <div v-if="cheatMode && !isSpectator" class="engine-panel" :class="engineStatus">
          <div class="engine-header">
            <h3>Engine</h3>
            <span v-if="engineLabel" class="engine-name">{{ engineLabel }}</span>
          </div>
          <div v-if="engineSuggestion" class="engine-line">
            <span class="engine-move">
              {{ engineSuggestion.from }}→{{ engineSuggestion.to
              }}{{ engineSuggestion.promotion ? `=${engineSuggestion.promotion.toUpperCase()}` : '' }}
            </span>
            <span class="engine-score">{{ formatEngineScore(engineSuggestion) }}</span>
          </div>
          <p class="engine-status">{{ engineStatusText }}</p>
          <button
            v-if="engineSuggestion && isMyTurn"
            type="button"
            class="btn-secondary engine-play"
            :disabled="!!pendingPromotion"
            @click="playEngineMove"
          >
            Play suggested move
          </button>
        </div>

        <div v-if="!isSpectator && gameState.phase === 'playing'" class="action-row">
          <button type="button" class="btn-secondary" @click="offerDraw">Offer draw</button>
          <button type="button" class="btn-secondary danger" @click="resign">Resign</button>
        </div>

        <div class="view-switch" role="radiogroup" aria-label="Board view">
          <span class="view-switch-label">Board</span>
          <button
            v-for="view in (['2d', '3d'] as const)"
            :key="view"
            type="button"
            class="view-option"
            :class="{ active: boardView === view }"
            role="radio"
            :aria-checked="boardView === view"
            @click="boardView = view"
          >
            {{ view.toUpperCase() }}
          </button>
        </div>

        <label class="pref-toggle">
          <input v-model="showMoveHints" type="checkbox" />
          <span class="pref-switch" aria-hidden="true" />
          <span>Show move hints</span>
        </label>

        <div class="history-panel">
          <div class="history-header">
            <h3>Moves</h3>
            <span class="move-count">{{ gameState.move_history.length }}</span>
          </div>
          <div v-if="historyRows.length" class="move-table">
            <div v-for="row in historyRows" :key="row.n" class="move-row">
              <span class="move-n">{{ row.n }}.</span>
              <span class="move-san">{{ row.white }}</span>
              <span class="move-san">{{ row.black }}</span>
            </div>
          </div>
          <p v-else class="muted">No moves yet</p>
        </div>
      </aside>
    </div>
  </div>
</template>

<style scoped>
.chess-board {
  --wood-light: #f0dcb8;
  --wood-dark: #b3804f;
  --wood-frame: #3d2c1e;
  --wood-frame-hi: #6b4a2e;
  --wood-accent: #c99a62;
  --select: rgba(92, 170, 110, 0.55);
  --last-move: rgba(214, 222, 80, 0.5);
  --target: rgba(40, 70, 40, 0.32);
  --check-glow: rgba(255, 60, 70, 0.85);
  --engine: rgba(64, 156, 255, 0.82);
  flex: 1;
  min-height: 0;
  width: 100%;
  display: flex;
  padding: 0.5rem 0.75rem 0.75rem;
  overflow: hidden;
}

.chess-shell {
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
  border-color: rgba(201, 154, 98, 0.55);
  box-shadow: 0 0 0 1px rgba(201, 154, 98, 0.18);
}

.player-bar.me {
  border-color: rgba(91, 156, 255, 0.4);
}

.king-badge {
  width: 2rem;
  height: 2rem;
  border-radius: 8px;
  display: grid;
  place-items: center;
  flex-shrink: 0;
  border: 1px solid rgba(255, 255, 255, 0.08);
}

.king-badge img {
  width: 85%;
  height: 85%;
  filter: drop-shadow(0 1px 1px rgba(0, 0, 0, 0.35));
}

.king-badge.w {
  background: linear-gradient(145deg, #f3ebe0, #d6c4a8);
  color: #2a2118;
}

.king-badge.b {
  background: linear-gradient(145deg, #c08d5c, #8a5e37);
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
  background: rgba(201, 154, 98, 0.18);
  color: var(--wood-accent);
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
  background: rgba(201, 154, 98, 0.16);
  color: var(--wood-accent);
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

.board-stage.is-3d {
  grid-template: minmax(0, 1fr) / minmax(0, 1fr);
  place-items: stretch;
}

.board {
  /* Largest square that fits in the stage */
  width: min(100cqw, 100cqh);
  height: min(100cqw, 100cqh);
  aspect-ratio: 1;
  container-type: size;
  box-sizing: border-box;
  display: flex;
  flex-direction: column;
  padding: 1.4cqw;
  border-radius: 14px;
  overflow: hidden;
  background: linear-gradient(145deg, var(--wood-frame-hi), var(--wood-frame) 55%, #2a1e14);
  box-shadow:
    0 20px 56px rgba(0, 0, 0, 0.5),
    0 2px 0 rgba(255, 255, 255, 0.06) inset,
    0 -2px 0 rgba(0, 0, 0, 0.35) inset;
}

@supports not (width: 1cqw) {
  .board {
    width: min(100%, calc(100dvh - 11.5rem));
    height: auto;
    max-height: 100%;
  }
}

.board.check {
  box-shadow:
    0 20px 56px rgba(0, 0, 0, 0.5),
    0 0 0 2px rgba(255, 92, 108, 0.4),
    0 0 32px rgba(255, 92, 108, 0.25);
}

.board.disabled {
  cursor: default;
}

.board-grid {
  position: relative;
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
}

.engine-arrow {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  z-index: 3;
  pointer-events: none;
}

.engine-arrow line {
  stroke: var(--engine);
  stroke-width: 0.18;
  stroke-linecap: round;
}

.engine-arrow path {
  fill: var(--engine);
}

.rank-row {
  display: grid;
  grid-template-columns: repeat(8, 1fr);
  flex: 1;
  min-height: 0;
}

.square {
  position: relative;
  border: none;
  border-radius: 0;
  padding: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: default;
  line-height: 1;
}

.square.light {
  background-color: var(--wood-light);
  background-image: linear-gradient(135deg, rgba(255, 255, 255, 0.16), rgba(0, 0, 0, 0.03));
}

.square.dark {
  background-color: var(--wood-dark);
  background-image: linear-gradient(135deg, rgba(255, 255, 255, 0.08), rgba(0, 0, 0, 0.08));
}

.square.movable,
.square.target {
  cursor: pointer;
}

.square.last {
  background-image: linear-gradient(var(--last-move), var(--last-move));
}

.square.selected {
  background-image: linear-gradient(var(--select), var(--select));
}

.square.engine-hint {
  box-shadow: inset 0 0 0 0.45cqw var(--engine);
}

.square.check {
  background-image: radial-gradient(
    circle at center,
    var(--check-glow) 0%,
    rgba(255, 60, 70, 0.45) 45%,
    transparent 78%
  );
}

.square.target:not(.capture):hover {
  background-image: linear-gradient(var(--target), var(--target));
}

.square.target.capture::after {
  content: '';
  position: absolute;
  inset: 0;
  background: radial-gradient(circle, transparent 66%, var(--target) 67%);
  pointer-events: none;
}

.square.target.capture:hover::after {
  background: var(--target);
}

.piece {
  position: relative;
  z-index: 1;
  width: 94%;
  height: 94%;
  object-fit: contain;
  user-select: none;
  -webkit-user-drag: none;
  pointer-events: none;
  filter: drop-shadow(0 0.35cqw 0.35cqw rgba(0, 0, 0, 0.4));
  transition:
    transform 0.14s var(--ease-smooth),
    filter 0.14s var(--ease-smooth);
}

.square.movable:hover .piece {
  transform: translateY(-3%) scale(1.04);
  filter: drop-shadow(0 0.7cqw 0.6cqw rgba(0, 0, 0, 0.45));
}

.square.selected .piece {
  transform: translateY(-4%) scale(1.07);
  filter: drop-shadow(0 0.9cqw 0.7cqw rgba(0, 0, 0, 0.5));
}

.target-dot {
  width: 30%;
  height: 30%;
  border-radius: 50%;
  background: var(--target);
  pointer-events: none;
}

.coord {
  position: absolute;
  z-index: 2;
  font-size: max(0.6rem, min(0.9rem, 1.9cqw));
  font-weight: 800;
  opacity: 0.8;
  pointer-events: none;
  font-family: 'Outfit', 'DM Sans', system-ui, sans-serif;
}

.coord.rank {
  top: 3px;
  left: 4px;
}

.coord.file {
  bottom: 2px;
  right: 4px;
}

.square.light .coord {
  color: var(--wood-dark);
}

.square.dark .coord {
  color: var(--wood-light);
}

.promotion-overlay,
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

.promotion-card,
.game-over-card {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 0.75rem;
  padding: 1rem 1.2rem;
  border-radius: 12px;
  border: 1px solid rgba(201, 154, 98, 0.35);
  background: rgba(21, 28, 44, 0.95);
  box-shadow: var(--shadow);
}

.promotion-card p,
.game-over-title {
  margin: 0;
  font-weight: 650;
}

.promo-choices {
  display: flex;
  gap: 0.45rem;
}

.promo-btn {
  width: clamp(56px, 10vw, 84px);
  height: clamp(56px, 10vw, 84px);
  padding: 0;
  display: grid;
  place-items: center;
  border-radius: 12px;
  border: 1px solid rgba(201, 154, 98, 0.35);
  background: linear-gradient(145deg, var(--wood-light), #dcc195);
  cursor: pointer;
  transition:
    transform 0.12s var(--ease-smooth),
    box-shadow 0.12s var(--ease-smooth);
}

.promo-btn:hover {
  transform: translateY(-2px);
  box-shadow: 0 6px 16px rgba(0, 0, 0, 0.35);
}

.promo-btn img {
  width: 88%;
  height: 88%;
  pointer-events: none;
  filter: drop-shadow(0 2px 2px rgba(0, 0, 0, 0.35));
}

.promo-cancel {
  font-size: 0.8rem;
  padding: 0.35rem 0.7rem;
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

.status-chip.check {
  border-color: rgba(255, 92, 108, 0.45);
  background: rgba(255, 92, 108, 0.08);
}

.status-chip.check .status-dot {
  background: var(--error);
}

.status-chip.over {
  border-color: rgba(201, 154, 98, 0.45);
  background: rgba(201, 154, 98, 0.08);
}

.status-chip.over .status-dot {
  background: var(--wood-accent);
}

.draw-offer {
  padding: 0.7rem;
  border-radius: 10px;
  border: 1px solid rgba(91, 156, 255, 0.45);
  background: rgba(91, 156, 255, 0.08);
  text-align: center;
}

.draw-offer p {
  margin: 0;
  font-weight: 650;
  font-size: 0.85rem;
}

.draw-actions {
  display: flex;
  gap: 0.45rem;
  justify-content: center;
  margin-top: 0.5rem;
}

.engine-panel {
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
  padding: 0.6rem 0.7rem;
  border-radius: 10px;
  border: 1px solid rgba(64, 156, 255, 0.4);
  background: rgba(64, 156, 255, 0.08);
}

.engine-panel.error {
  border-color: rgba(255, 92, 108, 0.45);
  background: rgba(255, 92, 108, 0.08);
}

.engine-header {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 0.4rem;
}

.engine-header h3 {
  margin: 0;
  font-size: 0.7rem;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  color: var(--text-muted);
}

.engine-name {
  font-size: 0.66rem;
  color: var(--text-muted);
  text-align: right;
}

.engine-line {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
}

.engine-move {
  font-size: 1.05rem;
  font-weight: 700;
  color: var(--engine);
}

.engine-score {
  font-size: 0.85rem;
  font-weight: 650;
}

.engine-status {
  margin: 0;
  font-size: 0.75rem;
  color: var(--text-muted);
}

.engine-play {
  font-size: 0.78rem;
  padding: 0.4rem 0.5rem;
}

.action-row {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 0.45rem;
}

.action-row .btn-secondary {
  font-size: 0.78rem;
  padding: 0.45rem 0.5rem;
}

.action-row .danger {
  border-color: rgba(255, 92, 108, 0.4);
  color: #ff8a96;
}

.view-switch {
  display: flex;
  align-items: center;
  gap: 0.3rem;
  padding: 0.3rem 0.3rem 0.3rem 0.6rem;
  border-radius: 10px;
  border: 1px solid var(--border);
  background: rgba(10, 14, 23, 0.35);
}

.view-switch-label {
  flex: 1;
  font-size: 0.82rem;
  font-weight: 600;
}

.view-option {
  min-width: 2.6rem;
  padding: 0.3rem 0.55rem;
  border-radius: 7px;
  border: 1px solid transparent;
  background: transparent;
  color: var(--text-muted);
  font-size: 0.78rem;
  font-weight: 700;
  cursor: pointer;
  transition:
    background 0.15s ease,
    color 0.15s ease;
}

.view-option:hover:not(.active) {
  color: var(--text);
}

.view-option.active {
  background: rgba(201, 154, 98, 0.2);
  border-color: rgba(201, 154, 98, 0.45);
  color: var(--wood-accent);
}

.view-option:focus-visible {
  outline: 2px solid var(--accent);
  outline-offset: 2px;
}

.pref-toggle {
  display: flex;
  align-items: center;
  gap: 0.55rem;
  padding: 0.5rem 0.6rem;
  border-radius: 10px;
  border: 1px solid var(--border);
  background: rgba(10, 14, 23, 0.35);
  font-size: 0.82rem;
  font-weight: 600;
  cursor: pointer;
  user-select: none;
}

.pref-toggle input {
  position: absolute;
  opacity: 0;
  pointer-events: none;
}

.pref-switch {
  position: relative;
  width: 2rem;
  height: 1.1rem;
  flex-shrink: 0;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.14);
  transition: background 0.15s ease;
}

.pref-switch::after {
  content: '';
  position: absolute;
  top: 0.15rem;
  left: 0.15rem;
  width: 0.8rem;
  height: 0.8rem;
  border-radius: 50%;
  background: #f4efe6;
  transition: transform 0.15s var(--ease-smooth);
}

.pref-toggle input:checked + .pref-switch {
  background: var(--wood-accent);
}

.pref-toggle input:checked + .pref-switch::after {
  transform: translateX(0.9rem);
}

.pref-toggle input:focus-visible + .pref-switch {
  outline: 2px solid var(--accent);
  outline-offset: 2px;
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

.move-table {
  flex: 1;
  min-height: 0;
  overflow: auto;
  display: flex;
  flex-direction: column;
  gap: 0.15rem;
  padding-right: 0.15rem;
}

.move-row {
  display: grid;
  grid-template-columns: 1.6rem 1fr 1fr;
  gap: 0.25rem;
  padding: 0.28rem 0.35rem;
  border-radius: 6px;
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
  font-size: 0.8rem;
}

.move-row:nth-child(odd) {
  background: rgba(10, 14, 23, 0.35);
}

.move-n {
  color: var(--text-muted);
}

.move-san {
  color: var(--text);
}

.muted {
  margin: 0;
  color: var(--text-muted);
  font-size: 0.85rem;
}

@media (max-width: 860px) {
  .chess-board {
    overflow: auto;
    padding: 0.5rem;
  }

  .chess-shell {
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
