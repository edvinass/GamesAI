<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import type { BattleshipGameState, Room } from '@/types'
import { buildShipSegmentMap, previewSegments, type ShipSegment } from './shipVisual'

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

const previewValid = computed(() => {
  if (!hoverCell.value || !selectedShipId.value) return false
  return previewCells(hoverCell.value.row, hoverCell.value.col) !== null
})

const ownSegments = computed(() => buildShipSegmentMap(placedShips.value))

const enemySegments = computed(() => {
  const ships = (oppFleet.value?.ships ?? []).filter(
    (s) => s.placed && s.cells?.length && (s.sunk || props.gameState.phase === 'game_over'),
  )
  return buildShipSegmentMap(ships)
})

const previewSegmentMap = computed(() => {
  if (props.gameState.phase !== 'placing' || !selectedShipId.value || isReady.value) {
    return new Map<string, ShipSegment>()
  }
  if (!hoverCell.value) return new Map<string, ShipSegment>()
  const ship = unplacedShips.value.find((s) => s.id === selectedShipId.value)
  if (!ship) return new Map<string, ShipSegment>()
  // Always show a ghost hull shape; validity is signaled separately.
  return previewSegments(
    hoverCell.value.row,
    hoverCell.value.col,
    ship.length,
    horizontal.value,
  )
})

function segmentAt(
  map: Map<string, ShipSegment>,
  row: number,
  col: number,
): ShipSegment | null {
  return map.get(`${row},${col}`) ?? null
}

function ownSeg(row: number, col: number): ShipSegment | null {
  return segmentAt(ownSegments.value, row, col) ?? segmentAt(previewSegmentMap.value, row, col)
}

function isPreviewCell(row: number, col: number): boolean {
  return !ownSegments.value.has(`${row},${col}`) && previewSegmentMap.value.has(`${row},${col}`)
}

function enemySeg(row: number, col: number): ShipSegment | null {
  return segmentAt(enemySegments.value, row, col)
}

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
  opts: {
    last?: boolean
    clickable?: boolean
    seg?: ShipSegment | null
    preview?: boolean
    previewInvalid?: boolean
  } = {},
) {
  const seg = opts.seg
  return {
    hit: cell.state === 'hit',
    miss: cell.state === 'miss',
    ship: Boolean(seg) && !opts.preview,
    preview: Boolean(opts.preview && seg),
    'preview-invalid': Boolean(opts.preview && opts.previewInvalid),
    last: opts.last,
    clickable: opts.clickable,
    bow: seg?.role === 'bow',
    mid: seg?.role === 'mid',
    stern: seg?.role === 'stern',
    horizontal: Boolean(seg?.horizontal),
    vertical: Boolean(seg && !seg.horizontal),
    bridge: Boolean(seg?.hasBridge),
    sunk: Boolean(seg?.sunk),
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
                    :class="
                      cellClass(cell, {
                        seg: ownSeg(ri, ci),
                        preview: isPreviewCell(ri, ci),
                        previewInvalid: isPreviewCell(ri, ci) && !previewValid,
                        last:
                          lastShotKey === `${ri},${ci}` &&
                          gameState.last_shot?.target_player_id === viewerId,
                      })
                    "
                    :disabled="gameState.phase !== 'placing' || isReady || isSpectator"
                    :aria-label="`Own ${cols[ci]}${r}`"
                    @mouseenter="hoverCell = { row: ri, col: ci }"
                    @mouseleave="hoverCell = null"
                    @click="onOwnCellClick(ri, ci)"
                  >
                    <span class="cell-fill" />
                    <span
                      v-if="ownSeg(ri, ci) && cell.state !== 'hit'"
                      class="hull-piece"
                      aria-hidden="true"
                    >
                      <i v-if="ownSeg(ri, ci)?.hasBridge" class="superstructure" />
                      <i v-if="ownSeg(ri, ci)?.role === 'mid'" class="porthole" />
                    </span>
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
                    :class="
                      cellClass(cell, {
                        seg: enemySeg(ri, ci),
                        last:
                          lastShotKey === `${ri},${ci}` &&
                          gameState.last_shot?.target_player_id === opponentId,
                        clickable: isMyTurn && legalShotSet.has(`${ri},${ci}`),
                      })
                    "
                    :disabled="!isMyTurn || !legalShotSet.has(`${ri},${ci}`)"
                    :aria-label="`Enemy ${cols[ci]}${r}`"
                    @click="onOppCellClick(ri, ci)"
                  >
                    <span class="cell-fill" />
                    <span
                      v-if="enemySeg(ri, ci) && cell.state !== 'hit'"
                      class="hull-piece"
                      aria-hidden="true"
                    >
                      <i v-if="enemySeg(ri, ci)?.hasBridge" class="superstructure" />
                      <i v-if="enemySeg(ri, ci)?.role === 'mid'" class="porthole" />
                    </span>
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
              <span class="ship-mini" aria-hidden="true" :style="{ '--len': ship.length }">
                <span class="mini-stern" />
                <span v-for="n in Math.max(0, ship.length - 2)" :key="n" class="mini-mid">
                  <i v-if="n === Math.max(1, Math.floor((ship.length - 2) * 0.55))" class="mini-bridge" />
                </span>
                <span class="mini-bow" />
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

/* Connected hull segments — pointed bow, flat stern, tapered mid. */
.cell.ship .cell-fill,
.cell.preview .cell-fill {
  border-radius: 0;
  background:
    linear-gradient(180deg, #ecd7b0 0%, var(--hull) 42%, var(--hull-deep) 100%);
  box-shadow:
    inset 0 1px 0 rgba(255, 255, 255, 0.28),
    inset 0 -2px 3px rgba(0, 0, 0, 0.28),
    0 2px 4px rgba(0, 0, 0, 0.35);
}

.cell.ship.vertical .cell-fill,
.cell.preview.vertical .cell-fill {
  background:
    linear-gradient(90deg, var(--hull-deep) 0%, var(--hull) 45%, #ecd7b0 100%);
}

.cell.ship.horizontal.stern .cell-fill,
.cell.preview.horizontal.stern .cell-fill {
  clip-path: polygon(12% 22%, 100% 16%, 100% 84%, 12% 78%, 0% 50%);
  margin-right: -1px;
}

.cell.ship.horizontal.mid .cell-fill,
.cell.preview.horizontal.mid .cell-fill {
  clip-path: polygon(0% 16%, 100% 16%, 100% 84%, 0% 84%);
  margin: 0 -1px;
}

.cell.ship.horizontal.bow .cell-fill,
.cell.preview.horizontal.bow .cell-fill {
  clip-path: polygon(0% 16%, 62% 10%, 100% 50%, 62% 90%, 0% 84%);
  margin-left: -1px;
}

.cell.ship.vertical.stern .cell-fill,
.cell.preview.vertical.stern .cell-fill {
  /* Flat/rounded stern at top, full width into mid below */
  clip-path: polygon(22% 14%, 50% 4%, 78% 14%, 84% 100%, 16% 100%);
  margin-bottom: -1px;
}

.cell.ship.vertical.mid .cell-fill,
.cell.preview.vertical.mid .cell-fill {
  clip-path: polygon(16% 0%, 84% 0%, 84% 100%, 16% 100%);
  margin: -1px 0;
}

.cell.ship.vertical.bow .cell-fill,
.cell.preview.vertical.bow .cell-fill {
  /* Pointed bow at bottom */
  clip-path: polygon(16% 0%, 84% 0%, 90% 62%, 50% 100%, 10% 62%);
  margin-top: -1px;
}

.cell.ship.sunk .cell-fill {
  filter: grayscale(0.35) brightness(0.72);
  box-shadow:
    inset 0 1px 0 rgba(255, 255, 255, 0.1),
    0 0 6px rgba(232, 93, 76, 0.35);
}

.cell.preview .cell-fill {
  background: linear-gradient(180deg, rgba(190, 230, 240, 0.7), rgba(70, 130, 150, 0.65));
  box-shadow: 0 0 0 1px rgba(180, 230, 240, 0.45);
  animation: previewBob 1.1s ease-in-out infinite;
}

.cell.preview.vertical .cell-fill {
  background: linear-gradient(90deg, rgba(70, 130, 150, 0.65), rgba(190, 230, 240, 0.7));
}

.cell.preview-invalid .cell-fill {
  background: linear-gradient(180deg, rgba(255, 150, 130, 0.65), rgba(180, 60, 50, 0.55));
  box-shadow: 0 0 0 1px rgba(255, 140, 120, 0.55);
}

.hull-piece {
  position: absolute;
  inset: 0;
  z-index: 2;
  pointer-events: none;
}

.superstructure {
  position: absolute;
  display: block;
  background: linear-gradient(180deg, #6a5640, #3d3226);
  border-radius: 2px;
  box-shadow:
    inset 0 1px 0 rgba(255, 255, 255, 0.2),
    0 1px 2px rgba(0, 0, 0, 0.4);
}

.cell.horizontal .superstructure {
  left: 28%;
  right: 28%;
  top: 8%;
  height: 38%;
}

.cell.horizontal .superstructure::after {
  content: '';
  position: absolute;
  left: 35%;
  right: 35%;
  top: -55%;
  height: 55%;
  border-radius: 1px 1px 0 0;
  background: #2e261c;
}

.cell.vertical .superstructure {
  top: 28%;
  bottom: 28%;
  left: 8%;
  width: 38%;
}

.cell.vertical .superstructure::after {
  content: '';
  position: absolute;
  top: 35%;
  bottom: 35%;
  left: -55%;
  width: 55%;
  border-radius: 1px 0 0 1px;
  background: #2e261c;
}

.porthole {
  position: absolute;
  width: 18%;
  height: 18%;
  border-radius: 50%;
  background: radial-gradient(circle at 35% 35%, #4a7a8a, #152830 70%);
  box-shadow: inset 0 0 0 1px rgba(255, 255, 255, 0.15);
  opacity: 0.85;
}

.cell.horizontal .porthole {
  left: 40%;
  top: 41%;
}

.cell.vertical .porthole {
  left: 41%;
  top: 40%;
}

.cell.hit {
  z-index: 3;
}

.cell.hit .cell-fill {
  background:
    radial-gradient(circle at 50% 45%, #ff8a78 0%, var(--hit) 45%, #8a2a20 100%);
  box-shadow: 0 0 8px rgba(232, 93, 76, 0.45);
  border-radius: 50%;
  inset: 16%;
  clip-path: none !important;
  margin: 0 !important;
  filter: none;
}

.cell.hit .hull-piece {
  display: none;
}

.cell.miss .cell-fill {
  background:
    radial-gradient(circle at 50% 45%, rgba(255, 255, 255, 0.35) 0%, transparent 35%),
    linear-gradient(160deg, rgba(36, 120, 135, 0.4), rgba(10, 47, 56, 0.9));
  clip-path: none;
}

.cell.miss .cell-fill::after {
  content: '';
  position: absolute;
  inset: 32%;
  border-radius: 50%;
  background: var(--miss);
  opacity: 0.85;
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

@keyframes previewBob {
  0%,
  100% {
    opacity: 0.72;
  }
  50% {
    opacity: 0.95;
  }
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

.ship-mini {
  --len: 3;
  display: flex;
  align-items: center;
  height: 0.85rem;
  width: calc(0.42rem * var(--len) + 0.35rem);
  filter: drop-shadow(0 1px 1px rgba(0, 0, 0, 0.35));
}

.mini-stern,
.mini-mid,
.mini-bow {
  display: block;
  height: 100%;
  background: linear-gradient(180deg, #e0c89a, var(--hull) 50%, var(--hull-deep));
  position: relative;
}

.mini-stern {
  width: 0.45rem;
  clip-path: polygon(20% 20%, 100% 12%, 100% 88%, 20% 80%, 0% 50%);
}

.mini-mid {
  flex: 1;
  min-width: 0.28rem;
  clip-path: polygon(0% 14%, 100% 14%, 100% 86%, 0% 86%);
  margin: 0 -1px;
}

.mini-bow {
  width: 0.55rem;
  clip-path: polygon(0% 14%, 55% 8%, 100% 50%, 55% 92%, 0% 86%);
}

.mini-bridge {
  position: absolute;
  left: 25%;
  right: 25%;
  top: 4%;
  height: 42%;
  border-radius: 1px;
  background: #4a3b28;
}

.ship-row.selected .mini-stern,
.ship-row.selected .mini-mid,
.ship-row.selected .mini-bow {
  background: linear-gradient(180deg, #f0e0c0, #d4b888 50%, #9a7a48);
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
  .hint.fire,
  .cell.preview .cell-fill {
    animation: none !important;
  }
}
</style>
