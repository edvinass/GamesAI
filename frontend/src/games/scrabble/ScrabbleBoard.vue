<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import type { ScrabbleGameState, ScrabbleTile } from '@/types'

const props = defineProps<{
  gameState: ScrabbleGameState
  playerId: string
}>()

const emit = defineEmits<{
  action: [data: Record<string, unknown>]
}>()

const LETTER_VALUES: Record<string, number> = {
  A: 1, B: 3, C: 3, D: 2, E: 1, F: 4, G: 2, H: 4, I: 1, J: 8, K: 5, L: 1, M: 3,
  N: 1, O: 1, P: 3, Q: 10, R: 1, S: 1, T: 1, U: 1, V: 4, W: 4, X: 8, Y: 4, Z: 10,
}

interface PendingTile {
  tile: ScrabbleTile
  row: number
  col: number
  letter: string
}

interface DragState {
  tile: ScrabbleTile
  letter: string
  from: { row: number; col: number } | null
  x: number
  y: number
  ox: number
  oy: number
  moved: boolean
}

const pending = ref<PendingTile[]>([])
const selectedId = ref<string | null>(null)
const exchangeMode = ref(false)
const exchangeIds = ref<string[]>([])
const blankPrompt = ref<{ tile: ScrabbleTile; row: number; col: number } | null>(null)
const order = ref<string[]>([])
const drag = ref<DragState | null>(null)
const suppressClick = ref(false)

const myTurn = computed(
  () =>
    props.gameState.phase === 'playing' &&
    props.gameState.current_actor_id === props.playerId,
)

const actor = computed(() =>
  props.gameState.players.find((seat) => seat.id === props.gameState.current_actor_id) ?? null,
)

const freshCells = computed(() => {
  const last = props.gameState.last_move
  if (!last || last.kind !== 'play') return new Set<string>()
  return new Set(last.placements.map((cell) => `${cell.row},${cell.col}`))
})

watch(
  () => props.gameState.rack.map((tile) => tile.id).join(','),
  () => {
    const ids = props.gameState.rack.map((tile) => tile.id)
    const known = new Set(ids)
    const kept = order.value.filter((id) => known.has(id))
    order.value = [...kept, ...ids.filter((id) => !kept.includes(id))]
  },
  { immediate: true },
)

watch(
  () => [props.gameState.turn_index, props.gameState.phase] as const,
  () => {
    pending.value = []
    selectedId.value = null
    exchangeMode.value = false
    exchangeIds.value = []
    blankPrompt.value = null
    drag.value = null
  },
)

const rackTiles = computed(() => {
  const pendingIds = new Set(pending.value.map((item) => item.tile.id))
  const byId = new Map(props.gameState.rack.map((tile) => [tile.id, tile]))
  return order.value
    .filter((id) => byId.has(id) && !pendingIds.has(id))
    .map((id) => byId.get(id) as ScrabbleTile)
})

const selectedTile = computed(
  () => rackTiles.value.find((tile) => tile.id === selectedId.value) ?? null,
)

function pendingAt(row: number, col: number) {
  return pending.value.find((item) => item.row === row && item.col === col) ?? null
}

function cellModel(row: number, col: number) {
  const staged = pendingAt(row, col)
  if (staged) {
    return {
      letter: staged.letter || '?',
      blank: staged.tile.blank,
      value: staged.tile.blank ? 0 : staged.tile.value,
      pending: true,
      tile: staged.tile,
    }
  }
  const committed = props.gameState.board[row]?.[col]
  if (!committed) return null
  return {
    letter: committed.letter,
    blank: committed.blank,
    value: committed.blank ? 0 : LETTER_VALUES[committed.letter] ?? 0,
    pending: false,
    tile: null,
  }
}

function premiumOf(row: number, col: number) {
  return props.gameState.premiums[row]?.[col] ?? ''
}

function premiumLabel(row: number, col: number) {
  if (row === 7 && col === 7 && !props.gameState.board[row][col]) return '★'
  const code = premiumOf(row, col)
  if (code === 'tw') return 'TW'
  if (code === 'dw') return 'DW'
  if (code === 'tl') return 'TL'
  if (code === 'dl') return 'DL'
  return ''
}

function tryPlace(
  tile: ScrabbleTile,
  letter: string,
  row: number,
  col: number,
  from: { row: number; col: number } | null,
) {
  if (!myTurn.value) return
  if (props.gameState.board[row][col]) return
  const other = pendingAt(row, col)
  if (other && other.tile.id !== tile.id) return
  if (tile.blank && !letter) {
    if (from) pending.value = pending.value.filter((item) => item.tile.id !== tile.id)
    blankPrompt.value = { tile, row, col }
    selectedId.value = null
    return
  }
  pending.value = [
    ...pending.value.filter((item) => item.tile.id !== tile.id),
    { tile, row, col, letter: letter || tile.letter },
  ]
  selectedId.value = null
}

function onCellClick(event: MouseEvent, row: number, col: number) {
  if (suppressClick.value) {
    suppressClick.value = false
    return
  }
  const staged = pendingAt(row, col)
  if (staged && (event.target as HTMLElement).closest('.tile')) {
    selectedId.value = staged.tile.id
    pending.value = pending.value.filter((item) => item.tile.id !== staged.tile.id)
    return
  }
  if (!selectedTile.value || props.gameState.board[row][col]) return
  tryPlace(
    selectedTile.value,
    selectedTile.value.blank ? '' : selectedTile.value.letter,
    row,
    col,
    null,
  )
}

function onRackClick(tile: ScrabbleTile) {
  if (suppressClick.value) {
    suppressClick.value = false
    return
  }
  if (!myTurn.value) return
  if (exchangeMode.value) {
    exchangeIds.value = exchangeIds.value.includes(tile.id)
      ? exchangeIds.value.filter((id) => id !== tile.id)
      : [...exchangeIds.value, tile.id]
    return
  }
  selectedId.value = selectedId.value === tile.id ? null : tile.id
}

function startDrag(event: PointerEvent, tile: ScrabbleTile, from: { row: number; col: number } | null) {
  if (!myTurn.value || exchangeMode.value || props.gameState.phase !== 'playing') return
  const staged = from ? pending.value.find((item) => item.tile.id === tile.id) : null
  drag.value = {
    tile,
    letter: staged?.letter || (tile.blank ? '' : tile.letter),
    from,
    x: event.clientX,
    y: event.clientY,
    ox: event.clientX,
    oy: event.clientY,
    moved: false,
  }
  ;(event.currentTarget as HTMLElement).setPointerCapture(event.pointerId)
}

function moveDrag(event: PointerEvent) {
  const current = drag.value
  if (!current) return
  const moved =
    current.moved || Math.hypot(event.clientX - current.ox, event.clientY - current.oy) > 6
  drag.value = { ...current, x: event.clientX, y: event.clientY, moved }
}

function endDrag(event: PointerEvent) {
  const current = drag.value
  if (!current) return
  drag.value = null
  if (!current.moved) return
  suppressClick.value = true
  setTimeout(() => {
    suppressClick.value = false
  }, 0)
  const target = document.elementFromPoint(event.clientX, event.clientY)
  const cell = target?.closest('[data-cell]') as HTMLElement | null
  if (!cell) {
    if (current.from) {
      pending.value = pending.value.filter((item) => item.tile.id !== current.tile.id)
    }
    return
  }
  const row = Number(cell.dataset.row)
  const col = Number(cell.dataset.col)
  tryPlace(current.tile, current.letter, row, col, current.from)
}

function chooseBlank(letter: string) {
  const prompt = blankPrompt.value
  if (!prompt) return
  blankPrompt.value = null
  tryPlace(prompt.tile, letter, prompt.row, prompt.col, null)
}

function recall() {
  pending.value = []
  selectedId.value = null
  blankPrompt.value = null
}

function shuffleRack() {
  const ids = [...rackTiles.value.map((tile) => tile.id)]
  for (let index = ids.length - 1; index > 0; index -= 1) {
    const swap = Math.floor(Math.random() * (index + 1))
    const current = ids[index]
    ids[index] = ids[swap]
    ids[swap] = current
  }
  const pendingIds = pending.value.map((item) => item.tile.id)
  order.value = [...ids, ...pendingIds]
}

function playWord() {
  if (!pending.value.length || !myTurn.value) return
  emit('action', {
    type: 'play',
    placements: pending.value.map((item) => ({
      row: item.row,
      col: item.col,
      tile_id: item.tile.id,
      letter: item.letter,
    })),
  })
}

function passTurn() {
  if (!myTurn.value || pending.value.length) return
  emit('action', { type: 'pass' })
}

function exchangeTiles() {
  if (!myTurn.value || !exchangeIds.value.length || props.gameState.bag_count < 7) return
  emit('action', { type: 'exchange', tile_ids: exchangeIds.value })
}

function resign() {
  emit('action', { type: 'resign' })
}

const statusText = computed(() => {
  if (props.gameState.phase === 'game_over') return resultText.value
  if (myTurn.value) return exchangeMode.value ? 'Select tiles to swap' : 'Your turn'
  return actor.value ? `Waiting for ${actor.value.nickname}` : 'Waiting'
})

const resultText = computed(() => {
  const names = props.gameState.winner_ids
    .map((id) => props.gameState.players.find((seat) => seat.id === id)?.nickname ?? 'Player')
  if (props.gameState.winner) {
    const name = props.gameState.players.find((seat) => seat.id === props.gameState.winner)?.nickname
    return `${name ?? 'Player'} wins`
  }
  if (names.length > 1) return `${names.join(' and ')} tie`
  return 'Game over'
})

const reasonText = computed(() => {
  if (props.gameState.win_reason === 'out') return 'Last tile played, bag empty.'
  if (props.gameState.win_reason === 'passes') return 'Six scoreless turns in a row.'
  if (props.gameState.win_reason === 'resign') return 'A player resigned.'
  return ''
})

function logLine(entry: ScrabbleGameState['move_log'][number]) {
  if (entry.kind === 'pass') return `${entry.nickname} passed`
  if (entry.kind === 'exchange') return `${entry.nickname} exchanged tiles`
  if (entry.kind === 'resign') return `${entry.nickname} resigned`
  const words = entry.words.map((word) => word.word).join(', ')
  const bingo = entry.bingo ? ' +50' : ''
  return `${entry.nickname} played ${words} for ${entry.score}${bingo}`
}

const canExchange = computed(() => myTurn.value && props.gameState.bag_count >= 7 && !pending.value.length)
</script>

<template>
  <div class="scrabble">
    <section class="table">
      <div class="status-bar">
        <p class="status" :class="{ mine: myTurn && gameState.phase === 'playing' }">{{ statusText }}</p>
        <p class="bag">Bag {{ gameState.bag_count }}</p>
        <p v-if="gameState.phase === 'playing' && gameState.zero_turns" class="zero">
          Scoreless turns {{ gameState.zero_turns }} / 6
        </p>
      </div>

      <div v-if="gameState.phase === 'game_over'" class="result card">
        <h2>{{ resultText }}</h2>
        <p>{{ reasonText }}</p>
      </div>

      <div class="board" role="grid" aria-label="Scrabble board">
        <button
          v-for="index in 225"
          :key="index"
          type="button"
          class="sq"
          :class="[
            premiumOf(Math.floor((index - 1) / 15), (index - 1) % 15),
            {
              fresh: freshCells.has(`${Math.floor((index - 1) / 15)},${(index - 1) % 15}`),
              staged: !!pendingAt(Math.floor((index - 1) / 15), (index - 1) % 15),
            },
          ]"
          :data-row="Math.floor((index - 1) / 15)"
          :data-col="(index - 1) % 15"
          data-cell
          @click="onCellClick($event, Math.floor((index - 1) / 15), (index - 1) % 15)"
        >
          <span
            v-if="cellModel(Math.floor((index - 1) / 15), (index - 1) % 15)"
            class="tile"
            :class="{ blank: cellModel(Math.floor((index - 1) / 15), (index - 1) % 15)?.blank }"
            @pointerdown.stop="
              cellModel(Math.floor((index - 1) / 15), (index - 1) % 15)?.pending &&
                startDrag(
                  $event,
                  cellModel(Math.floor((index - 1) / 15), (index - 1) % 15)!.tile!,
                  {
                    row: Math.floor((index - 1) / 15),
                    col: (index - 1) % 15,
                  },
                )
            "
            @pointermove="moveDrag"
            @pointerup="endDrag"
          >
            <span class="glyph">{{ cellModel(Math.floor((index - 1) / 15), (index - 1) % 15)?.letter }}</span>
            <span class="pts">{{
              cellModel(Math.floor((index - 1) / 15), (index - 1) % 15)?.blank
                ? ''
                : cellModel(Math.floor((index - 1) / 15), (index - 1) % 15)?.value
            }}</span>
          </span>
          <span v-else class="prem">{{ premiumLabel(Math.floor((index - 1) / 15), (index - 1) % 15) }}</span>
        </button>
      </div>

      <div class="rack-panel">
        <p class="rack-label">{{ gameState.rack.length ? 'Your tiles' : 'No tiles in hand' }}</p>
        <div class="rack" aria-label="Your rack">
          <button
            v-for="tile in rackTiles"
            :key="tile.id"
            type="button"
            class="tile rack-tile"
            :class="{
              selected: selectedId === tile.id || exchangeIds.includes(tile.id),
              blank: tile.blank,
            }"
            @click="onRackClick(tile)"
            @pointerdown="startDrag($event, tile, null)"
            @pointermove="moveDrag"
            @pointerup="endDrag"
          >
            <span class="glyph">{{ tile.blank ? '' : tile.letter }}</span>
            <span class="pts">{{ tile.blank ? '' : tile.value }}</span>
          </button>
        </div>
        <div class="actions">
          <button type="button" class="btn-secondary" :disabled="!rackTiles.length" @click="shuffleRack">Shuffle</button>
          <button type="button" class="btn-secondary" :disabled="!pending.length" @click="recall">Recall</button>
          <button type="button" class="btn-primary" :disabled="!myTurn || !pending.length" @click="playWord">Play</button>
          <button type="button" class="btn-secondary" :disabled="!myTurn || !!pending.length" @click="passTurn">Pass</button>
          <button
            type="button"
            class="btn-secondary"
            :disabled="!canExchange"
            @click="exchangeMode = !exchangeMode"
          >
            {{ exchangeMode ? 'Cancel swap' : 'Exchange' }}
          </button>
          <button
            v-if="exchangeMode"
            type="button"
            class="btn-primary"
            :disabled="!exchangeIds.length"
            @click="exchangeTiles"
          >
            Swap {{ exchangeIds.length }}
          </button>
          <button v-if="gameState.phase === 'playing'" type="button" class="btn-secondary danger" @click="resign">
            Resign
          </button>
        </div>
        <p v-if="exchangeMode" class="hint">Tap the tiles you want to put back. The bag needs at least 7 tiles.</p>
        <p v-else-if="myTurn" class="hint">Drag a tile onto the board, or select it and tap a square. Blanks ask for a letter.</p>
      </div>
    </section>

    <aside class="side">
      <section class="card scores">
        <h2>Scores</h2>
        <ul>
          <li
            v-for="seat in gameState.players"
            :key="seat.id"
            :class="{ current: seat.id === gameState.current_actor_id, you: seat.id === playerId }"
          >
            <div>
              <strong>{{ seat.nickname }}</strong>
              <span v-if="seat.is_ai" class="tag">AI</span>
              <span v-if="seat.id === playerId" class="tag">You</span>
            </div>
            <div class="score-col">
              <b>{{ seat.score }}</b>
              <span>{{ seat.rack_count }} tiles</span>
              <span v-if="gameState.end_adjustments && gameState.end_adjustments[seat.id]" class="delta">
                {{ gameState.end_adjustments[seat.id] > 0 ? '+' : '' }}{{ gameState.end_adjustments[seat.id] }}
              </span>
            </div>
          </li>
        </ul>
      </section>

      <section v-if="gameState.last_move?.kind === 'play'" class="card last-play">
        <h2>Last play</h2>
        <p>
          {{ gameState.last_move.nickname }}
          <strong>{{ gameState.last_move.score }}</strong>
        </p>
        <ul>
          <li v-for="word in gameState.last_move.words" :key="word.word + word.score">
            {{ word.word }} <span>{{ word.score }}</span>
          </li>
          <li v-if="gameState.last_move.bingo">Bingo <span>50</span></li>
        </ul>
      </section>

      <section class="card log">
        <h2>Moves</h2>
        <ol>
          <li v-for="(entry, index) in [...gameState.move_log].reverse()" :key="index">
            {{ logLine(entry) }}
          </li>
          <li v-if="!gameState.move_log.length" class="empty">No plays yet.</li>
        </ol>
      </section>
    </aside>

    <div v-if="blankPrompt" class="modal-back" @click.self="blankPrompt = null">
      <div class="modal card" role="dialog" aria-label="Choose a blank letter">
        <h2>Blank tile</h2>
        <p>Pick the letter this blank will be for the rest of the game. It still scores 0.</p>
        <div class="letters">
          <button v-for="letter in 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'" :key="letter" type="button" @click="chooseBlank(letter)">
            {{ letter }}
          </button>
        </div>
        <button type="button" class="btn-secondary" @click="blankPrompt = null">Cancel</button>
      </div>
    </div>

    <div
      v-if="drag?.moved"
      class="tile drag-ghost"
      :style="{ left: `${drag.x}px`, top: `${drag.y}px` }"
    >
      <span class="glyph">{{ drag.letter || '?' }}</span>
      <span class="pts">{{ drag.tile.blank ? '' : drag.tile.value }}</span>
    </div>
  </div>
</template>

<style scoped>
.scrabble {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 280px;
  gap: 1rem;
  max-width: 1120px;
  margin: 0 auto;
  padding: 0 1rem 2rem;
  align-items: start;
}

.table {
  display: flex;
  flex-direction: column;
  gap: 0.85rem;
  min-width: 0;
}

.status-bar {
  display: flex;
  flex-wrap: wrap;
  gap: 0.75rem 1.25rem;
  align-items: baseline;
}

.status {
  font-size: 1.15rem;
  font-weight: 700;
}

.status.mine {
  color: #f0d7a2;
}

.bag,
.zero,
.hint,
.rack-label {
  color: var(--text-muted);
  font-size: 0.9rem;
}

.result h2 {
  font-size: 1.4rem;
}

.result p {
  color: var(--text-muted);
  margin-top: 0.25rem;
}

.board {
  display: grid;
  grid-template-columns: repeat(15, 1fr);
  gap: 2px;
  width: min(100%, 680px);
  aspect-ratio: 1;
  padding: 8px;
  border-radius: 12px;
  background:
    linear-gradient(180deg, rgba(255, 255, 255, 0.08), transparent 30%),
    #6b4a2b;
  box-shadow: 0 16px 40px rgba(0, 0, 0, 0.35);
}

.sq {
  position: relative;
  border: none;
  border-radius: 3px;
  padding: 0;
  background: #f4ead4;
  color: #6a5a48;
  font-size: clamp(0.45rem, 1.15vw, 0.68rem);
  font-weight: 700;
  letter-spacing: 0.02em;
  cursor: pointer;
}

.sq.tw { background: #d64545; color: #fff; }
.sq.dw { background: #f0b4b4; color: #6d2b2b; }
.sq.tl { background: #3d6fd6; color: #fff; }
.sq.dl { background: #b7cff8; color: #243e73; }
.sq.fresh { outline: 2px solid #f6c453; outline-offset: -2px; }
.sq.staged { outline: 2px dashed #2a2118; outline-offset: -3px; }

.prem {
  pointer-events: none;
}

.tile {
  position: absolute;
  inset: 1px;
  display: grid;
  place-items: center;
  border-radius: 3px;
  background: linear-gradient(180deg, #fffaf0 0%, #f3d7a0 100%);
  color: #2c2116;
  box-shadow: 0 1px 0 rgba(90, 60, 20, 0.35);
  font-family: Georgia, 'Iowan Old Style', serif;
  touch-action: none;
}

.glyph {
  font-size: clamp(0.75rem, 2vw, 1.15rem);
  font-weight: 700;
  line-height: 1;
}

.pts {
  position: absolute;
  right: 2px;
  bottom: 1px;
  font-family: inherit;
  font-size: clamp(0.45rem, 1.1vw, 0.62rem);
  font-weight: 700;
}

.tile.blank .glyph {
  font-size: 0.95em;
}

.rack-panel {
  display: flex;
  flex-direction: column;
  gap: 0.55rem;
  width: min(100%, 680px);
}

.rack {
  display: flex;
  flex-wrap: wrap;
  gap: 0.4rem;
  min-height: 58px;
}

.rack-tile {
  position: relative;
  width: 52px;
  height: 58px;
  inset: auto;
  border: none;
  cursor: grab;
}

.rack-tile.selected {
  outline: 3px solid #d4a24a;
  transform: translateY(-4px);
}

.actions {
  display: flex;
  flex-wrap: wrap;
  gap: 0.45rem;
}

.danger {
  margin-left: auto;
}

.side {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

.scores h2,
.last-play h2,
.log h2 {
  font-size: 0.95rem;
  margin-bottom: 0.55rem;
}

.scores ul,
.last-play ul,
.log ol {
  list-style: none;
  display: flex;
  flex-direction: column;
  gap: 0.45rem;
  margin: 0;
  padding: 0;
}

.scores li,
.last-play li {
  display: flex;
  justify-content: space-between;
  gap: 0.75rem;
  align-items: center;
}

.scores li.current strong {
  color: #f0d7a2;
}

.tag {
  margin-left: 0.35rem;
  font-size: 0.68rem;
  color: var(--text-muted);
}

.score-col {
  text-align: right;
}

.score-col b {
  display: block;
  font-size: 1.15rem;
}

.score-col span,
.last-play li span,
.log li {
  color: var(--text-muted);
  font-size: 0.8rem;
}

.delta {
  color: #d4a24a !important;
}

.log {
  max-height: 280px;
  overflow: auto;
}

.empty {
  color: var(--text-muted);
}

.modal-back {
  position: fixed;
  inset: 0;
  background: rgba(6, 10, 18, 0.72);
  display: grid;
  place-items: center;
  z-index: 20;
  padding: 1rem;
}

.modal {
  width: min(100%, 420px);
}

.modal p {
  color: var(--text-muted);
  margin: 0.4rem 0 0.8rem;
}

.letters {
  display: grid;
  grid-template-columns: repeat(7, 1fr);
  gap: 0.35rem;
  margin-bottom: 0.8rem;
}

.letters button {
  border: 1px solid var(--border);
  background: #f4ead4;
  color: #2c2116;
  border-radius: 6px;
  font-family: Georgia, serif;
  font-weight: 700;
  padding: 0.45rem 0;
  cursor: pointer;
}

.drag-ghost {
  position: fixed;
  width: 52px;
  height: 58px;
  margin-left: -26px;
  margin-top: -29px;
  z-index: 30;
  pointer-events: none;
  inset: auto;
}

@media (max-width: 860px) {
  .scrabble {
    grid-template-columns: 1fr;
  }

  .danger {
    margin-left: 0;
  }
}
</style>
