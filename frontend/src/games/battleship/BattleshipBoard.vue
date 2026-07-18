<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import type { BattleshipGameState, Room } from '@/types'

const props = defineProps<{
  gameState: BattleshipGameState
  room: Room
  playerId: string
}>()

const emit = defineEmits<{
  action: [data: Record<string, unknown>]
}>()

const selectedShipId = ref<string | null>(null)
const horizontal = ref(true)
const hoverCell = ref<{ row: number; col: number } | null>(null)

const viewerId = computed(() => props.gameState.viewer_id)
const opponentId = computed(() => props.gameState.opponent_id)
const isSpectator = computed(() => !viewerId.value || !props.gameState.fleets[viewerId.value!])
const isReady = computed(() =>
  Boolean(viewerId.value && props.gameState.fleets[viewerId.value!]?.ready),
)

const ownFleet = computed(() =>
  viewerId.value ? props.gameState.fleets[viewerId.value] : null,
)
const oppFleet = computed(() =>
  opponentId.value ? props.gameState.fleets[opponentId.value] : null,
)

const ownBoard = computed(() =>
  viewerId.value ? props.gameState.boards[viewerId.value]?.grid : null,
)
const oppBoard = computed(() =>
  opponentId.value ? props.gameState.boards[opponentId.value]?.grid : null,
)

const unplacedShips = computed(() =>
  (ownFleet.value?.ships ?? []).filter((s) => !s.placed),
)
const placedShips = computed(() =>
  (ownFleet.value?.ships ?? []).filter((s) => s.placed),
)

const isMyTurn = computed(() => {
  if (props.gameState.phase !== 'playing') return false
  return props.gameState.current_actor_id === props.playerId
})

const actorNickname = computed(() => {
  const id = props.gameState.current_actor_id
  if (!id) return null
  return props.gameState.players.find((p) => p.id === id)?.nickname ?? null
})

const opponentPlayer = computed(() =>
  props.gameState.players.find((p) => p.id === opponentId.value) ?? null,
)
const mePlayer = computed(() =>
  props.gameState.players.find((p) => p.id === viewerId.value) ?? null,
)

const legalShotSet = computed(() => {
  const set = new Set<string>()
  for (const s of props.gameState.legal_shots) {
    set.add(`${s.row},${s.col}`)
  }
  return set
})

const cols = computed(() =>
  Array.from({ length: props.gameState.size }, (_, i) => String.fromCharCode(65 + i)),
)
const rows = computed(() =>
  Array.from({ length: props.gameState.size }, (_, i) => i + 1),
)

watch(
  () => props.gameState.phase,
  (phase) => {
    if (phase !== 'placing') {
      selectedShipId.value = null
      hoverCell.value = null
    }
  },
)

watch(
  unplacedShips,
  (ships) => {
    if (!selectedShipId.value && ships.length) {
      selectedShipId.value = ships[0].id
    }
    if (selectedShipId.value && !ships.some((s) => s.id === selectedShipId.value)) {
      selectedShipId.value = ships[0]?.id ?? null
    }
  },
  { immediate: true },
)

function previewCells(row: number, col: number): Array<[number, number]> | null {
  if (props.gameState.phase !== 'placing' || !selectedShipId.value || isReady.value) return null
  const ship = unplacedShips.value.find((s) => s.id === selectedShipId.value)
  if (!ship) return null
  const cells: Array<[number, number]> = []
  for (let i = 0; i < ship.length; i++) {
    const r = horizontal.value ? row : row + i
    const c = horizontal.value ? col + i : col
    if (r < 0 || c < 0 || r >= props.gameState.size || c >= props.gameState.size) {
      return null
    }
    cells.push([r, c])
  }
  const occupied = new Set<string>()
  for (const s of placedShips.value) {
    for (const [sr, sc] of s.cells ?? []) {
      occupied.add(`${sr},${sc}`)
    }
  }
  if (cells.some(([r, c]) => occupied.has(`${r},${c}`))) return null
  return cells
}

const previewSet = computed(() => {
  if (!hoverCell.value) return new Set<string>()
  const cells = previewCells(hoverCell.value.row, hoverCell.value.col)
  if (!cells) return new Set<string>()
  return new Set(cells.map(([r, c]) => `${r},${c}`))
})

const previewValid = computed(() => {
  if (!hoverCell.value || !selectedShipId.value) return false
  return previewCells(hoverCell.value.row, hoverCell.value.col) !== null
})

function onOwnCellClick(row: number, col: number) {
  if (props.gameState.phase !== 'placing' || isSpectator.value || isReady.value) return
  if (!selectedShipId.value) return
  if (!previewCells(row, col)) return
  emit('action', {
    type: 'place_ship',
    ship_id: selectedShipId.value,
    row,
    col,
    horizontal: horizontal.value,
  })
}

function onOppCellClick(row: number, col: number) {
  if (!isMyTurn.value) return
  if (!legalShotSet.value.has(`${row},${col}`)) return
  emit('action', { type: 'fire', row, col })
}

function removeShip(shipId: string) {
  if (props.gameState.phase !== 'placing' || isReady.value) return
  emit('action', { type: 'remove_ship', ship_id: shipId })
}

function autoPlace() {
  if (props.gameState.phase !== 'placing' || isReady.value) return
  emit('action', { type: 'auto_place' })
}

function readyUp() {
  if (props.gameState.phase !== 'placing' || isReady.value) return
  if (placedShips.value.length < props.gameState.ship_defs.length) return
  emit('action', { type: 'ready' })
}

function resign() {
  if (props.gameState.phase === 'game_over' || isSpectator.value) return
  if (window.confirm('Resign this game?')) {
    emit('action', { type: 'resign' })
  }
}

function cellClass(
  cell: { state: string },
  opts: { preview?: boolean; last?: boolean; clickable?: boolean } = {},
) {
  return {
    [cell.state]: true,
    preview: opts.preview,
    last: opts.last,
    clickable: opts.clickable,
  }
}

const lastShotKey = computed(() => {
  const shot = props.gameState.last_shot
  if (!shot) return null
  return `${shot.row},${shot.col}`
})

const statusText = computed(() => {
  const gs = props.gameState
  if (gs.phase === 'game_over') {
    if (gs.win_reason === 'fleet_sunk') {
      const winner = gs.players.find((p) => p.id === gs.winner)
      return `${winner?.nickname ?? 'Winner'} wins — fleet destroyed!`
    }
    if (gs.win_reason === 'resign') {
      const winner = gs.players.find((p) => p.id === gs.winner)
      return `${winner?.nickname ?? 'Winner'} wins — opponent resigned`
    }
    return 'Game over'
  }
  if (gs.phase === 'placing') {
    if (isReady.value) {
      const oppReady = oppFleet.value?.ready
      return oppReady ? 'Battle starting…' : 'Waiting for opponent to ready…'
    }
    const left = props.gameState.ship_defs.length - placedShips.value.length
    if (left > 0) return `Place your ships — ${left} remaining`
    return 'All ships placed — press Ready'
  }
  if (!isMyTurn.value && actorNickname.value) {
    const actor = gs.players.find((p) => p.id === gs.current_actor_id)
    if (actor?.is_ai) return 'AI is targeting…'
    return `${actorNickname.value}'s turn`
  }
  return isMyTurn.value ? 'Your turn — fire!' : 'Waiting…'
})

const statusTone = computed(() => {
  if (props.gameState.phase === 'game_over') return 'over'
  if (props.gameState.phase === 'placing') return isReady.value ? 'idle' : 'mine'
  if (isMyTurn.value) return 'mine'
  return 'idle'
})

const lastShotLabel = computed(() => {
  const shot = props.gameState.last_shot
  if (!shot) return null
  const coord = `${String.fromCharCode(65 + shot.col)}${shot.row + 1}`
  const who = props.gameState.players.find((p) => p.id === shot.player_id)?.nickname ?? 'Player'
  if (shot.result === 'sunk') return `${who} sank a ship at ${coord}!`
  if (shot.result === 'hit') return `${who} hit at ${coord}`
  return `${who} missed at ${coord}`
})
</script>

<template>
  <div class="battleship-board" :class="{ 'my-turn': isMyTurn }">
    <div class="shell">
      <div class="play-area">
        <div class="player-bar me" :class="{ active: isMyTurn || gameState.phase === 'placing' }">
          <span class="mark" aria-hidden="true">🚢</span>
          <div class="meta">
            <p class="name">
              {{ mePlayer?.nickname ?? 'You' }}
              <span v-if="mePlayer?.id === playerId" class="tag you">You</span>
            </p>
            <p class="sub">
              <template v-if="gameState.phase === 'placing'">
                {{ isReady ? 'Ready' : `${placedShips.length}/${gameState.ship_defs.length} placed` }}
              </template>
              <template v-else>
                {{ ownFleet?.ships_remaining ?? 0 }} ships left
              </template>
            </p>
          </div>
        </div>

        <div class="boards">
          <section class="board-panel own">
            <header class="board-header">
              <h3>Your waters</h3>
              <span v-if="gameState.phase === 'placing' && !isReady" class="hint">
                {{ selectedShipId ? 'Click to place' : 'Select a ship' }}
              </span>
            </header>
            <div
              class="grid-wrap"
              :class="{ interactive: gameState.phase === 'placing' && !isReady && !isSpectator }"
            >
              <div class="col-labels">
                <span class="corner" />
                <span v-for="c in cols" :key="c" class="label">{{ c }}</span>
              </div>
              <div class="grid-body">
                <div v-for="(r, ri) in rows" :key="r" class="grid-row">
                  <span class="label">{{ r }}</span>
                  <button
                    v-for="(cell, ci) in ownBoard?.[ri] ?? []"
                    :key="`${ri}-${ci}`"
                    type="button"
                    class="cell"
                    :class="cellClass(cell, {
                      preview: previewSet.has(`${ri},${ci}`),
                      last:
                        lastShotKey === `${ri},${ci}` &&
                        gameState.last_shot?.target_player_id === viewerId,
                    })"
                    :disabled="gameState.phase !== 'placing' || isReady || isSpectator"
                    :aria-label="`Own ${cols[ci]}${r}`"
                    @mouseenter="hoverCell = { row: ri, col: ci }"
                    @mouseleave="hoverCell = null"
                    @click="onOwnCellClick(ri, ci)"
                  >
                    <span class="cell-fill" />
                  </button>
                </div>
              </div>
              <div
                v-if="hoverCell && selectedShipId && gameState.phase === 'placing' && !isReady"
                class="preview-banner"
                :class="{ invalid: !previewValid }"
              >
                {{ previewValid ? 'Valid placement' : 'Does not fit' }}
              </div>
            </div>
          </section>

          <section class="board-panel enemy" :class="{ armed: isMyTurn }">
            <header class="board-header">
              <h3>Enemy waters</h3>
              <span v-if="isMyTurn" class="hint fire">Fire when ready</span>
              <span v-else-if="gameState.phase === 'placing'" class="hint">Hidden until battle</span>
            </header>
            <div class="grid-wrap" :class="{ interactive: isMyTurn }">
              <div class="col-labels">
                <span class="corner" />
                <span v-for="c in cols" :key="`e-${c}`" class="label">{{ c }}</span>
              </div>
              <div class="grid-body">
                <div v-for="(r, ri) in rows" :key="`e-${r}`" class="grid-row">
                  <span class="label">{{ r }}</span>
                  <button
                    v-for="(cell, ci) in oppBoard?.[ri] ?? []"
                    :key="`e-${ri}-${ci}`"
                    type="button"
                    class="cell"
                    :class="cellClass(cell, {
                      last:
                        lastShotKey === `${ri},${ci}` &&
                        gameState.last_shot?.target_player_id === opponentId,
                      clickable: isMyTurn && legalShotSet.has(`${ri},${ci}`),
                    })"
                    :disabled="!isMyTurn || !legalShotSet.has(`${ri},${ci}`)"
                    :aria-label="`Enemy ${cols[ci]}${r}`"
                    @click="onOppCellClick(ri, ci)"
                  >
                    <span class="cell-fill" />
                    <span
                      v-if="
                        gameState.phase === 'game_over' &&
                        cell.state === 'ship'
                      "
                      class="reveal-ship"
                    />
                  </button>
                </div>
              </div>
            </div>
          </section>
        </div>

        <div class="player-bar foe" :class="{ active: !isMyTurn && gameState.phase === 'playing' }">
          <span class="mark" aria-hidden="true">{{ opponentPlayer?.is_ai ? '🤖' : '🚢' }}</span>
          <div class="meta">
            <p class="name">
              {{ opponentPlayer?.nickname ?? 'Opponent' }}
              <span v-if="opponentPlayer?.is_ai" class="tag">AI</span>
            </p>
            <p class="sub">
              <template v-if="gameState.phase === 'placing'">
                {{ oppFleet?.ready ? 'Ready' : 'Placing…' }}
              </template>
              <template v-else>
                {{ oppFleet?.ships_remaining ?? '?' }} ships left
              </template>
            </p>
          </div>
          <span
            v-if="gameState.phase === 'playing' && gameState.current_actor_id === opponentId"
            class="turn-pill"
          >
            {{ opponentPlayer?.is_ai ? 'Thinking' : 'To fire' }}
          </span>
        </div>
      </div>

      <aside class="side-rail">
        <div class="status-chip" :class="statusTone">
          <span class="status-dot" aria-hidden="true" />
          <p>{{ statusText }}</p>
        </div>

        <p v-if="lastShotLabel" class="last-shot">{{ lastShotLabel }}</p>

        <template v-if="gameState.phase === 'placing' && !isSpectator && !isReady">
          <div class="place-controls">
            <button
              type="button"
              class="btn-secondary"
              :class="{ active: horizontal }"
              @click="horizontal = true"
            >
              Horizontal
            </button>
            <button
              type="button"
              class="btn-secondary"
              :class="{ active: !horizontal }"
              @click="horizontal = false"
            >
              Vertical
            </button>
          </div>

          <div class="ship-list">
            <h3>Fleet</h3>
            <button
              v-for="ship in gameState.ship_defs"
              :key="ship.id"
              type="button"
              class="ship-row"
              :class="{
                selected: selectedShipId === ship.id && !placedShips.some((s) => s.id === ship.id),
                placed: placedShips.some((s) => s.id === ship.id),
              }"
              @click="
                placedShips.some((s) => s.id === ship.id)
                  ? removeShip(ship.id)
                  : (selectedShipId = ship.id)
              "
            >
              <span class="ship-name">{{ ship.name }}</span>
              <span class="ship-len" aria-hidden="true">
                <i v-for="n in ship.length" :key="n" />
              </span>
              <span class="ship-action">
                {{ placedShips.some((s) => s.id === ship.id) ? 'Remove' : 'Place' }}
              </span>
            </button>
          </div>

          <div class="action-row">
            <button type="button" class="btn-secondary" @click="autoPlace">Auto-place</button>
            <button
              type="button"
              class="btn-primary"
              :disabled="placedShips.length < gameState.ship_defs.length"
              @click="readyUp"
            >
              Ready
            </button>
          </div>
        </template>

        <template v-else-if="gameState.phase === 'placing' && isReady">
          <p class="muted">Fleet locked. Waiting for the other captain…</p>
        </template>

        <div v-if="!isSpectator && gameState.phase !== 'game_over'" class="action-row">
          <button type="button" class="btn-secondary danger" @click="resign">Resign</button>
        </div>

        <div class="history-panel">
          <div class="history-header">
            <h3>Shots</h3>
            <span class="move-count">{{ gameState.shot_history.length }}</span>
          </div>
          <div v-if="gameState.shot_history.length" class="move-list">
            <div
              v-for="(shot, idx) in gameState.shot_history.slice().reverse()"
              :key="idx"
              class="move-entry"
              :class="shot.result"
            >
              <span class="move-num">{{ gameState.shot_history.length - idx }}.</span>
              <span class="move-coord">
                {{ String.fromCharCode(65 + shot.col) }}{{ shot.row + 1 }}
              </span>
              <span class="move-result">{{ shot.result }}</span>
            </div>
          </div>
          <p v-else class="muted">No shots yet</p>
        </div>

        <div v-if="gameState.phase === 'game_over'" class="game-over-card">
          <p class="game-over-title">{{ statusText }}</p>
        </div>
      </aside>
    </div>
  </div>
</template>

<style scoped>
.battleship-board {
  --sea: #1a6b7a;
  --sea-mid: #15707f;
  --sea-deep: #0a2f38;
  --hull: #c4a574;
  --hull-deep: #8a6f45;
  --hit: #e85d4c;
  --miss: #8ec8d4;
  flex: 1;
  min-height: 0;
  width: 100%;
  display: flex;
  padding: 0.5rem 0.75rem 0.75rem;
  overflow: hidden;
  background:
    radial-gradient(ellipse 70% 55% at 35% 40%, rgba(45, 156, 170, 0.14), transparent 55%),
    radial-gradient(ellipse 45% 35% at 85% 75%, rgba(196, 165, 116, 0.07), transparent 50%);
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

.shell {
  flex: 1;
  min-height: 0;
  width: 100%;
  max-width: 1600px;
  margin: 0 auto;
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(200px, 250px);
  gap: 0.85rem;
  align-items: stretch;
}

.play-area {
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
}

.player-bar.active {
  border-color: rgba(45, 156, 170, 0.45);
  box-shadow: 0 0 0 1px rgba(45, 156, 170, 0.12);
}

.mark {
  width: 2rem;
  height: 2rem;
  display: grid;
  place-items: center;
  border-radius: 8px;
  background: rgba(13, 61, 74, 0.55);
  font-size: 1rem;
}

.meta {
  min-width: 0;
  flex: 1;
}

.name {
  margin: 0;
  font-weight: 650;
  font-size: 0.92rem;
  display: flex;
  align-items: center;
  gap: 0.35rem;
}

.sub {
  margin: 0;
  font-size: 0.72rem;
  color: var(--text-muted);
  text-transform: uppercase;
  letter-spacing: 0.04em;
}

.tag {
  font-size: 0.62rem;
  padding: 0.08rem 0.32rem;
  border-radius: 4px;
  background: rgba(45, 156, 170, 0.18);
  color: #7ec8d4;
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
  background: rgba(45, 156, 170, 0.16);
  color: #8ed4e0;
  animation: turnPulse 1.8s ease-in-out infinite;
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

.boards {
  flex: 1;
  min-height: 0;
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 0.75rem;
  align-items: stretch;
}

.board-panel {
  min-width: 0;
  min-height: 0;
  display: flex;
  flex-direction: column;
  gap: 0.4rem;
  padding: 0.55rem;
  border-radius: 14px;
  border: 1px solid var(--border);
  background: rgba(10, 18, 26, 0.55);
}

.board-panel.enemy.armed {
  border-color: rgba(232, 93, 76, 0.4);
  box-shadow: 0 0 0 1px rgba(232, 93, 76, 0.12);
}

.board-header {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 0.5rem;
}

.board-header h3 {
  margin: 0;
  font-size: 0.78rem;
  letter-spacing: 0.05em;
  text-transform: uppercase;
  color: var(--text-muted);
}

.hint {
  font-size: 0.72rem;
  color: #7ec8d4;
}

.hint.fire {
  color: #f0a090;
  animation: turnPulse 1.5s ease-in-out infinite;
}

.grid-wrap {
  position: relative;
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
  container-type: size;
}

.col-labels {
  display: grid;
  grid-template-columns: 1.4rem repeat(10, 1fr);
  gap: 2px;
  margin-bottom: 2px;
}

.grid-body {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.grid-row {
  flex: 1;
  min-height: 0;
  display: grid;
  grid-template-columns: 1.4rem repeat(10, 1fr);
  gap: 2px;
}

.label {
  display: grid;
  place-items: center;
  font-size: 0.62rem;
  color: var(--text-muted);
  font-variant-numeric: tabular-nums;
}

.corner {
  width: 1.4rem;
}

.cell {
  position: relative;
  border: none;
  padding: 0;
  aspect-ratio: 1;
  min-height: 0;
  border-radius: 3px;
  background: transparent;
  cursor: default;
}

.grid-wrap.interactive .cell {
  cursor: pointer;
}

.cell-fill {
  position: absolute;
  inset: 0;
  border-radius: 3px;
  background:
    linear-gradient(160deg, rgba(36, 120, 135, 0.55), rgba(10, 47, 56, 0.85));
  box-shadow: inset 0 0 0 1px rgba(255, 255, 255, 0.06);
  transition:
    background 0.15s,
    box-shadow 0.15s,
    transform 0.12s;
}

.cell.ship .cell-fill {
  background: linear-gradient(180deg, #e0c89a, var(--hull) 50%, var(--hull-deep));
  box-shadow:
    inset 0 1px 0 rgba(255, 255, 255, 0.25),
    0 1px 2px rgba(0, 0, 0, 0.3);
}

.cell.hit .cell-fill {
  background:
    radial-gradient(circle at 50% 45%, #ff8a78 0%, var(--hit) 45%, #8a2a20 100%);
  box-shadow: 0 0 8px rgba(232, 93, 76, 0.45);
}

.cell.miss .cell-fill {
  background:
    radial-gradient(circle at 50% 45%, rgba(255, 255, 255, 0.35) 0%, transparent 35%),
    linear-gradient(160deg, rgba(36, 120, 135, 0.4), rgba(10, 47, 56, 0.9));
}

.cell.miss .cell-fill::after {
  content: '';
  position: absolute;
  inset: 32%;
  border-radius: 50%;
  background: var(--miss);
  opacity: 0.85;
}

.cell.preview .cell-fill {
  background: linear-gradient(180deg, rgba(224, 200, 154, 0.75), rgba(138, 111, 69, 0.85));
  box-shadow: 0 0 0 1px rgba(224, 200, 154, 0.5);
}

.cell.clickable:hover .cell-fill,
.cell.clickable:focus-visible .cell-fill {
  transform: scale(1.06);
  box-shadow: 0 0 0 1px rgba(232, 93, 76, 0.55), 0 0 10px rgba(232, 93, 76, 0.25);
}

.cell.last .cell-fill {
  box-shadow: 0 0 0 2px rgba(255, 255, 255, 0.55);
  animation: lastPulse 0.8s var(--ease-smooth);
}

@keyframes lastPulse {
  from {
    transform: scale(1.15);
  }
  to {
    transform: scale(1);
  }
}

.reveal-ship {
  position: absolute;
  inset: 18%;
  border-radius: 2px;
  background: rgba(196, 165, 116, 0.55);
  pointer-events: none;
}

.preview-banner {
  position: absolute;
  left: 50%;
  bottom: 0.35rem;
  transform: translateX(-50%);
  font-size: 0.7rem;
  font-weight: 650;
  padding: 0.2rem 0.55rem;
  border-radius: 999px;
  background: rgba(61, 214, 140, 0.18);
  color: #7dffb5;
  pointer-events: none;
}

.preview-banner.invalid {
  background: rgba(232, 93, 76, 0.18);
  color: #ff9a8e;
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
  border-color: rgba(45, 156, 170, 0.4);
  background: rgba(45, 156, 170, 0.08);
}

.status-chip.mine .status-dot {
  background: #7ec8d4;
  box-shadow: 0 0 8px rgba(45, 156, 170, 0.6);
  animation: turnPulse 1.5s ease-in-out infinite;
}

.status-chip.over {
  border-color: rgba(196, 165, 116, 0.45);
  background: rgba(196, 165, 116, 0.08);
}

.last-shot {
  margin: 0;
  font-size: 0.8rem;
  color: var(--text-muted);
  padding: 0 0.15rem;
}

.place-controls {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 0.4rem;
}

.place-controls .btn-secondary.active {
  border-color: var(--sea);
  background: rgba(45, 156, 170, 0.14);
  color: #8ed4e0;
}

.ship-list {
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
}

.ship-list h3 {
  margin: 0;
  font-size: 0.7rem;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  color: var(--text-muted);
}

.ship-row {
  display: grid;
  grid-template-columns: 1fr auto auto;
  align-items: center;
  gap: 0.45rem;
  padding: 0.45rem 0.5rem;
  border-radius: 8px;
  border: 1px solid var(--border);
  background: rgba(10, 14, 23, 0.4);
  color: var(--text);
  cursor: pointer;
  text-align: left;
  font-size: 0.8rem;
}

.ship-row.selected {
  border-color: var(--sea);
  background: rgba(45, 156, 170, 0.12);
}

.ship-row.placed {
  opacity: 0.75;
}

.ship-name {
  font-weight: 600;
}

.ship-len {
  display: flex;
  gap: 2px;
}

.ship-len i {
  width: 7px;
  height: 7px;
  border-radius: 1px;
  background: var(--hull);
}

.ship-action {
  font-size: 0.68rem;
  color: var(--text-muted);
  text-transform: uppercase;
  letter-spacing: 0.04em;
}

.action-row {
  display: flex;
  gap: 0.45rem;
}

.action-row .btn-secondary,
.action-row .btn-primary {
  flex: 1;
  font-size: 0.78rem;
  padding: 0.45rem 0.5rem;
}

.action-row .danger {
  border-color: rgba(255, 92, 108, 0.4);
  color: #ff8a96;
}

.btn-primary:disabled {
  opacity: 0.45;
  cursor: not-allowed;
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
}

.move-entry {
  display: flex;
  align-items: center;
  gap: 0.4rem;
  padding: 0.3rem 0.4rem;
  border-radius: 7px;
  font-size: 0.8rem;
}

.move-entry:nth-child(odd) {
  background: rgba(10, 14, 23, 0.35);
}

.move-num {
  width: 1.6rem;
  color: var(--text-muted);
  font-variant-numeric: tabular-nums;
}

.move-coord {
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
  font-weight: 650;
}

.move-result {
  margin-left: auto;
  text-transform: uppercase;
  font-size: 0.68rem;
  letter-spacing: 0.04em;
  font-weight: 700;
}

.move-entry.hit .move-result,
.move-entry.sunk .move-result {
  color: #ff9a8e;
}

.move-entry.miss .move-result {
  color: #8ec8d4;
}

.muted {
  margin: 0;
  color: var(--text-muted);
  font-size: 0.85rem;
}

.game-over-card {
  padding: 0.85rem;
  border-radius: 10px;
  border: 1px solid rgba(196, 165, 116, 0.4);
  background: linear-gradient(165deg, rgba(40, 36, 28, 0.9), rgba(16, 24, 40, 0.95));
  animation: cardPop 0.45s var(--ease-bounce) both;
}

@keyframes cardPop {
  from {
    opacity: 0;
    transform: scale(0.94) translateY(6px);
  }
  to {
    opacity: 1;
    transform: scale(1) translateY(0);
  }
}

.game-over-title {
  margin: 0;
  font-weight: 650;
  font-size: 0.95rem;
  text-align: center;
  line-height: 1.35;
}

@media (max-width: 960px) {
  .shell {
    grid-template-columns: 1fr;
    overflow: auto;
  }

  .boards {
    grid-template-columns: 1fr;
  }

  .history-panel {
    max-height: 180px;
  }
}

@media (prefers-reduced-motion: reduce) {
  .battleship-board,
  .turn-pill,
  .cell.last .cell-fill,
  .game-over-card,
  .hint.fire {
    animation: none !important;
  }
}
</style>
