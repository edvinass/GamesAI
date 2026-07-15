<script setup lang="ts">
import { computed, ref } from 'vue'
import type { RoboRallyGameState, Room } from '@/types'
import { CARD_LABELS, CARD_SHORT, FACING_ARROW } from './rules'

const props = defineProps<{
  gameState: RoboRallyGameState
  room: Room
  playerId: string
}>()

const emit = defineEmits<{
  action: [data: Record<string, unknown>]
}>()

const selectedCardId = ref<string | null>(null)

const myPlayer = computed(() =>
  props.gameState.players.find((p) => p.id === props.playerId),
)

const isSpectator = computed(() => !myPlayer.value)

const myRobot = computed(() => props.gameState.robots[props.playerId])

const myHand = computed(() => props.gameState.hands[props.playerId] ?? [])

const myProgram = computed(() => props.gameState.programs[props.playerId] ?? [])

const isLocked = computed(() => props.gameState.lock_status[props.playerId] ?? false)

const canProgram = computed(
  () =>
    props.gameState.phase === 'programming' &&
    !isLocked.value &&
    !props.gameState.winner &&
    !isSpectator.value,
)

const registerFilled = computed(() =>
  myProgram.value.every((slot) => slot && !slot.hidden),
)

const board = computed(() => props.gameState.board)

const wallSet = computed(() => {
  const set = new Set<string>()
  for (const [x, y] of board.value.walls) {
    set.add(`${x},${y}`)
  }
  return set
})

const checkpointMap = computed(() => {
  const map = new Map<string, number>()
  for (const [x, y, num] of board.value.checkpoints) {
    map.set(`${x},${y}`, num)
  }
  return map
})

const robotAt = computed(() => {
  const map = new Map<string, { playerId: string; facing: string; color: string }>()
  for (const player of props.gameState.players) {
    const robot = props.gameState.robots[player.id]
    if (robot) {
      map.set(`${robot.x},${robot.y}`, {
        playerId: player.id,
        facing: robot.facing,
        color: player.color,
      })
    }
  }
  return map
})

const cols = computed(() => Array.from({ length: board.value.width }, (_, i) => i))
const rows = computed(() => Array.from({ length: board.value.height }, (_, i) => i))

const statusText = computed(() => {
  const gs = props.gameState
  if (gs.winner) {
    const winner = gs.players.find((p) => p.id === gs.winner)
    if (gs.win_reason === 'checkpoints') {
      return `🏁 ${winner?.nickname ?? 'Winner'} reached all checkpoints!`
    }
    return `${winner?.nickname ?? 'Winner'} wins (${gs.win_reason})`
  }
  if (gs.phase === 'executing') {
    return `Round ${gs.round} — robots executing…`
  }
  if (isLocked.value) {
    return `Round ${gs.round} — program locked, waiting for others…`
  }
  if (canProgram.value) {
    return `Round ${gs.round} — fill your register and lock in`
  }
  return `Round ${gs.round} — ${gs.phase}`
})

const priorityList = computed(() =>
  props.gameState.register_order.map((pid, i) => ({
    rank: i + 1,
    player: props.gameState.players.find((p) => p.id === pid),
    robot: props.gameState.robots[pid],
  })),
)

function isAntenna(x: number, y: number): boolean {
  const [ax, ay] = board.value.antenna
  return x === ax && y === ay
}

function isWall(x: number, y: number): boolean {
  return wallSet.value.has(`${x},${y}`)
}

function checkpointNum(x: number, y: number): number | null {
  return checkpointMap.value.get(`${x},${y}`) ?? null
}

function robotOn(x: number, y: number) {
  return robotAt.value.get(`${x},${y}`)
}

function selectCard(cardId: string) {
  if (!canProgram.value) return
  selectedCardId.value = selectedCardId.value === cardId ? null : cardId
}

function onSlotClick(slotIndex: number) {
  if (!canProgram.value) return
  const slot = myProgram.value[slotIndex]
  if (selectedCardId.value) {
    emit('action', {
      type: 'place_card',
      slot_index: slotIndex,
      card_id: selectedCardId.value,
    })
    selectedCardId.value = null
    return
  }
  if (slot && !slot.hidden) {
    emit('action', { type: 'clear_slot', slot_index: slotIndex })
  }
}

function lockProgram() {
  if (!canProgram.value || !registerFilled.value) return
  emit('action', { type: 'lock_program' })
}

function resign() {
  if (isSpectator.value || props.gameState.winner) return
  if (window.confirm('Forfeit this race?')) {
    emit('action', { type: 'resign' })
  }
}

function cardLabel(card: { type?: string; hidden?: boolean }) {
  if (card.hidden || !card.type) return '?'
  return CARD_SHORT[card.type] ?? card.type
}

function cardTitle(card: { type?: string; hidden?: boolean }) {
  if (card.hidden || !card.type) return 'Hidden card'
  return CARD_LABELS[card.type] ?? card.type
}
</script>

<template>
  <div class="roborally-board">
    <header class="game-status card">
      <div class="status-main">
        <h2>{{ board.name }}</h2>
        <p>{{ statusText }}</p>
      </div>
      <div v-if="myRobot && !isSpectator" class="my-progress">
        Checkpoints: {{ myRobot.checkpoints_reached }} / {{ gameState.total_checkpoints }}
      </div>
      <button
        v-if="!isSpectator && !gameState.winner"
        type="button"
        class="btn-secondary resign-btn"
        @click="resign"
      >
        Forfeit
      </button>
    </header>

    <div class="layout">
      <aside class="sidebar card">
        <h3>Priority</h3>
        <ol class="priority-list">
          <li v-for="entry in priorityList" :key="entry.player?.id">
            <span class="rank">{{ entry.rank }}</span>
            <span
              class="dot"
              :style="{ background: entry.player?.color }"
            />
            <span class="name">{{ entry.player?.nickname }}</span>
            <span v-if="gameState.lock_status[entry.player?.id ?? '']" class="locked">🔒</span>
            <span class="cp">CP {{ entry.robot?.checkpoints_reached ?? 0 }}</span>
          </li>
        </ol>
      </aside>

      <div class="grid-wrap card">
        <div
          class="grid"
          :style="{
            gridTemplateColumns: `repeat(${board.width}, 1fr)`,
            gridTemplateRows: `repeat(${board.height}, 1fr)`,
          }"
        >
          <div
            v-for="y in rows"
            :key="'row-' + y"
            class="grid-row"
            :style="{ display: 'contents' }"
          >
            <div
              v-for="x in cols"
              :key="`${x}-${y}`"
              class="cell"
              :class="{
                wall: isWall(x, y),
                antenna: isAntenna(x, y),
                checkpoint: checkpointNum(x, y) != null,
              }"
            >
              <span v-if="checkpointNum(x, y)" class="cp-label">{{ checkpointNum(x, y) }}</span>
              <span v-if="isAntenna(x, y)" class="antenna-icon">📡</span>
              <div
                v-if="robotOn(x, y)"
                class="robot"
                :style="{ '--robot-color': robotOn(x, y)?.color }"
                :title="gameState.players.find(p => p.id === robotOn(x, y)?.playerId)?.nickname"
              >
                <span class="robot-body" />
                <span class="robot-arrow">{{ FACING_ARROW[robotOn(x, y)!.facing] }}</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <section v-if="!isSpectator" class="programming card">
      <div class="register-row">
        <span class="section-label">Register</span>
        <div class="register-slots">
          <button
            v-for="(slot, i) in myProgram"
            :key="'slot-' + i"
            type="button"
            class="slot"
            :class="{ filled: slot && !slot.hidden, active: canProgram }"
            :disabled="!canProgram"
            @click="onSlotClick(i)"
          >
            <span class="slot-num">{{ i + 1 }}</span>
            <span v-if="slot" class="slot-card">{{ cardLabel(slot) }}</span>
            <span v-else class="slot-empty">+</span>
          </button>
        </div>
        <button
          type="button"
          class="btn-primary lock-btn"
          :disabled="!canProgram || !registerFilled"
          @click="lockProgram"
        >
          {{ isLocked ? 'Locked' : 'Lock program' }}
        </button>
      </div>

      <div class="hand-row">
        <span class="section-label">Hand</span>
        <div class="hand-cards">
          <button
            v-for="card in myHand"
            :key="card.id"
            type="button"
            class="hand-card"
            :class="{ selected: selectedCardId === card.id, hidden: card.hidden }"
            :disabled="!canProgram || card.hidden"
            :title="cardTitle(card)"
            @click="selectCard(card.id)"
          >
            {{ card.hidden ? '?' : cardLabel(card) }}
          </button>
        </div>
        <p v-if="canProgram" class="hint">
          Click a card, then a register slot. Click a filled slot to return the card to your hand.
        </p>
      </div>
    </section>

    <section v-else class="spectator-note card">
      <p>Spectating — you are not racing in this game.</p>
    </section>
  </div>
</template>

<style scoped>
.roborally-board {
  display: flex;
  flex-direction: column;
  gap: 1rem;
  max-width: 960px;
  margin: 0 auto;
  padding: 0 1rem 1.5rem;
}

.game-status {
  display: flex;
  align-items: center;
  gap: 1rem;
  flex-wrap: wrap;
}

.status-main h2 {
  margin: 0;
  font-size: 1.1rem;
}

.status-main p {
  margin: 0.25rem 0 0;
  color: var(--text-muted);
  font-size: 0.9rem;
}

.my-progress {
  margin-left: auto;
  font-weight: 600;
  font-size: 0.9rem;
}

.resign-btn {
  margin-left: auto;
}

.layout {
  display: grid;
  grid-template-columns: 180px 1fr;
  gap: 1rem;
}

@media (max-width: 720px) {
  .layout {
    grid-template-columns: 1fr;
  }
}

.sidebar h3 {
  margin: 0 0 0.75rem;
  font-size: 0.95rem;
}

.priority-list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 0.45rem;
}

.priority-list li {
  display: flex;
  align-items: center;
  gap: 0.4rem;
  font-size: 0.85rem;
}

.rank {
  width: 1.2rem;
  color: var(--text-muted);
}

.dot {
  width: 0.65rem;
  height: 0.65rem;
  border-radius: 50%;
  flex-shrink: 0;
}

.name {
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.locked {
  font-size: 0.75rem;
}

.cp {
  color: var(--text-muted);
  font-size: 0.75rem;
}

.grid-wrap {
  overflow: auto;
  padding: 0.75rem;
}

.grid {
  display: grid;
  gap: 2px;
  min-width: min(100%, 520px);
  aspect-ratio: 13 / 11;
  max-height: 60vh;
}

.cell {
  position: relative;
  background: #1e293b;
  border-radius: 3px;
  min-height: 0;
  display: flex;
  align-items: center;
  justify-content: center;
}

.cell.wall {
  background: #475569;
}

.cell.checkpoint {
  background: #334155;
  box-shadow: inset 0 0 0 2px rgba(250, 204, 21, 0.5);
}

.cell.antenna {
  background: #312e81;
}

.cp-label {
  position: absolute;
  top: 2px;
  left: 3px;
  font-size: 0.55rem;
  font-weight: 700;
  color: #facc15;
  z-index: 1;
}

.antenna-icon {
  font-size: 0.7rem;
  opacity: 0.85;
}

.robot {
  position: relative;
  width: 70%;
  height: 70%;
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 2;
}

.robot-body {
  width: 100%;
  height: 100%;
  border-radius: 4px;
  background: var(--robot-color);
  border: 2px solid rgba(255, 255, 255, 0.35);
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.4);
}

.robot-arrow {
  position: absolute;
  font-size: 0.75rem;
  font-weight: 800;
  color: white;
  text-shadow: 0 1px 2px rgba(0, 0, 0, 0.8);
}

.programming {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.section-label {
  font-size: 0.8rem;
  font-weight: 600;
  color: var(--text-muted);
  text-transform: uppercase;
  letter-spacing: 0.04em;
}

.register-row,
.hand-row {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.register-slots {
  display: flex;
  gap: 0.5rem;
  flex-wrap: wrap;
}

.slot {
  width: 3.5rem;
  height: 4rem;
  border: 2px dashed var(--border);
  border-radius: 8px;
  background: var(--surface);
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 0.15rem;
  cursor: pointer;
  color: var(--text);
}

.slot.active:not(:disabled):hover {
  border-color: var(--accent);
}

.slot.filled {
  border-style: solid;
  background: var(--surface-elevated);
}

.slot:disabled {
  opacity: 0.6;
  cursor: default;
}

.slot-num {
  font-size: 0.65rem;
  color: var(--text-muted);
}

.slot-card {
  font-size: 1.25rem;
  font-weight: 700;
}

.slot-empty {
  font-size: 1.25rem;
  color: var(--text-muted);
}

.lock-btn {
  align-self: flex-start;
  margin-top: 0.25rem;
}

.hand-cards {
  display: flex;
  gap: 0.45rem;
  flex-wrap: wrap;
}

.hand-card {
  min-width: 2.75rem;
  height: 3.25rem;
  padding: 0 0.5rem;
  border-radius: 8px;
  border: 2px solid var(--border);
  background: linear-gradient(145deg, #334155, #1e293b);
  color: white;
  font-size: 1.1rem;
  font-weight: 700;
  cursor: pointer;
}

.hand-card.selected {
  border-color: var(--accent);
  box-shadow: 0 0 0 2px rgba(99, 102, 241, 0.35);
}

.hand-card.hidden {
  background: #64748b;
}

.hand-card:disabled {
  opacity: 0.5;
  cursor: default;
}

.hint {
  margin: 0;
  font-size: 0.8rem;
  color: var(--text-muted);
}

.spectator-note p {
  margin: 0;
  color: var(--text-muted);
}
</style>
