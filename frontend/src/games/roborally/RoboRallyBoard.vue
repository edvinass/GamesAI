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

const boardAspect = computed(() => `${board.value.width} / ${board.value.height}`)

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
  const map = new Map<string, { playerId: string; facing: string; color: string; nickname: string }>()
  for (const player of props.gameState.players) {
    const robot = props.gameState.robots[player.id]
    if (robot) {
      map.set(`${robot.x},${robot.y}`, {
        playerId: player.id,
        facing: robot.facing,
        color: player.color,
        nickname: player.nickname,
      })
    }
  }
  return map
})

const cols = computed(() => Array.from({ length: board.value.width }, (_, i) => i))
const rows = computed(() => Array.from({ length: board.value.height }, (_, i) => i))

const phaseLabel = computed(() => {
  const gs = props.gameState
  if (gs.winner) return 'Finished'
  if (gs.phase === 'executing') return 'Executing'
  if (isLocked.value) return 'Waiting'
  return 'Programming'
})

const phaseClass = computed(() => {
  const gs = props.gameState
  if (gs.winner) return 'phase--finished'
  if (gs.phase === 'executing') return 'phase--executing'
  if (isLocked.value) return 'phase--waiting'
  return 'phase--programming'
})

const statusText = computed(() => {
  const gs = props.gameState
  if (gs.winner) {
    const winner = gs.players.find((p) => p.id === gs.winner)
    if (gs.win_reason === 'checkpoints') {
      return `${winner?.nickname ?? 'Winner'} reached all checkpoints`
    }
    return `${winner?.nickname ?? 'Winner'} wins`
  }
  if (gs.phase === 'executing') {
    return 'Robots are running this round\'s program…'
  }
  if (isLocked.value) {
    return 'Your program is locked — waiting for other racers'
  }
  if (canProgram.value) {
    return 'Pick cards from your hand and fill every register slot'
  }
  return 'Watch the race unfold'
})

const priorityList = computed(() =>
  props.gameState.register_order.map((pid, i) => ({
    rank: i + 1,
    player: props.gameState.players.find((p) => p.id === pid),
    robot: props.gameState.robots[pid],
    locked: props.gameState.lock_status[pid] ?? false,
    isMe: pid === props.playerId,
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

function isFloor(x: number, y: number): boolean {
  return !isWall(x, y)
}

function floorShade(x: number, y: number): string {
  return (x + y) % 2 === 0 ? 'floor-a' : 'floor-b'
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

function cardTypeClass(type?: string): string {
  if (!type) return 'card--unknown'
  if (type.startsWith('move_')) return 'card--move'
  if (type.startsWith('turn_')) return 'card--turn'
  if (type === 'backup') return 'card--backup'
  return 'card--unknown'
}
</script>

<template>
  <div class="roborally-board">
    <header class="status-bar">
      <div class="status-left">
        <span class="phase-badge" :class="phaseClass">{{ phaseLabel }}</span>
        <div class="status-copy">
          <h2 class="map-name">{{ board.name }}</h2>
          <p class="status-line">{{ statusText }}</p>
        </div>
      </div>

      <div class="status-stats">
        <div class="stat-pill">
          <span class="stat-label">Round</span>
          <span class="stat-value">{{ gameState.round }}</span>
        </div>
        <div v-if="myRobot && !isSpectator" class="stat-pill stat-pill--accent">
          <span class="stat-label">Checkpoints</span>
          <span class="stat-value">{{ myRobot.checkpoints_reached }} / {{ gameState.total_checkpoints }}</span>
        </div>
      </div>

      <button
        v-if="!isSpectator && !gameState.winner"
        type="button"
        class="btn-secondary forfeit-btn"
        @click="resign"
      >
        Forfeit
      </button>
    </header>

    <div class="main-stage">
      <div class="arena">
        <div class="grid-frame">
          <div
            class="grid"
            :style="{
              aspectRatio: boardAspect,
              gridTemplateColumns: `repeat(${board.width}, 1fr)`,
              gridTemplateRows: `repeat(${board.height}, 1fr)`,
            }"
          >
            <template v-for="y in rows" :key="'row-' + y">
              <div
                v-for="x in cols"
                :key="`${x}-${y}`"
                class="cell"
                :class="[
                  floorShade(x, y),
                  {
                    wall: isWall(x, y),
                    floor: isFloor(x, y),
                    antenna: isAntenna(x, y),
                    checkpoint: checkpointNum(x, y) != null,
                  },
                ]"
              >
                <span v-if="checkpointNum(x, y)" class="cp-ring">
                  <span class="cp-num">{{ checkpointNum(x, y) }}</span>
                </span>
                <span v-if="isAntenna(x, y)" class="antenna-glow">
                  <span class="antenna-icon">📡</span>
                </span>
                <div
                  v-if="robotOn(x, y)"
                  class="robot"
                  :class="{ 'robot--me': robotOn(x, y)?.playerId === playerId }"
                  :style="{ '--robot-color': robotOn(x, y)?.color }"
                  :title="robotOn(x, y)?.nickname"
                >
                  <span class="robot-shell" />
                  <span class="robot-arrow">{{ FACING_ARROW[robotOn(x, y)!.facing] }}</span>
                </div>
              </div>
            </template>
          </div>
        </div>
      </div>

      <aside class="racers-panel">
        <div class="panel-head">
          <h3>Register order</h3>
          <span class="panel-sub">Closest to antenna first</span>
        </div>
        <ol class="racer-list">
          <li
            v-for="entry in priorityList"
            :key="entry.player?.id"
            class="racer-card"
            :class="{ 'racer-card--me': entry.isMe, 'racer-card--locked': entry.locked }"
          >
            <span class="racer-rank">{{ entry.rank }}</span>
            <span class="racer-dot" :style="{ background: entry.player?.color }" />
            <div class="racer-info">
              <span class="racer-name">
                {{ entry.player?.nickname }}
                <span v-if="entry.isMe" class="you-tag">You</span>
              </span>
              <div class="cp-track">
                <div
                  class="cp-fill"
                  :style="{ width: `${((entry.robot?.checkpoints_reached ?? 0) / gameState.total_checkpoints) * 100}%`, background: entry.player?.color }"
                />
              </div>
            </div>
            <span class="racer-meta">
              <span class="racer-cp">{{ entry.robot?.checkpoints_reached ?? 0 }}/{{ gameState.total_checkpoints }}</span>
              <span v-if="entry.locked" class="lock-icon" title="Program locked">🔒</span>
            </span>
          </li>
        </ol>
      </aside>
    </div>

    <section v-if="!isSpectator" class="programming-dock">
      <div class="dock-section dock-register">
        <div class="dock-head">
          <span class="dock-label">Register</span>
          <span class="dock-count">{{ myProgram.filter(Boolean).length }} / {{ gameState.register_size }}</span>
        </div>
        <div class="register-slots">
          <button
            v-for="(slot, i) in myProgram"
            :key="'slot-' + i"
            type="button"
            class="slot"
            :class="[
              cardTypeClass(slot?.type),
              {
                filled: slot && !slot.hidden,
                active: canProgram,
                pulsing: canProgram && !slot,
              },
            ]"
            :disabled="!canProgram"
            :title="slot && !slot.hidden ? cardTitle(slot) : `Register slot ${i + 1}`"
            @click="onSlotClick(i)"
          >
            <span class="slot-num">{{ i + 1 }}</span>
            <span v-if="slot && !slot.hidden" class="slot-card">{{ cardLabel(slot) }}</span>
            <span v-else class="slot-empty">+</span>
          </button>
        </div>
      </div>

      <div class="dock-section dock-hand">
        <div class="dock-head">
          <span class="dock-label">Hand</span>
          <span v-if="canProgram" class="dock-hint">Select a card, then a slot</span>
        </div>
        <div class="hand-cards">
          <button
            v-for="card in myHand"
            :key="card.id"
            type="button"
            class="hand-card"
            :class="[
              cardTypeClass(card.type),
              { selected: selectedCardId === card.id, hidden: card.hidden },
            ]"
            :disabled="!canProgram || card.hidden"
            :title="cardTitle(card)"
            @click="selectCard(card.id)"
          >
            <span class="hand-card-glyph">{{ card.hidden ? '?' : cardLabel(card) }}</span>
            <span v-if="!card.hidden && card.type" class="hand-card-name">{{ CARD_LABELS[card.type] }}</span>
          </button>
        </div>
      </div>

      <div class="dock-actions">
        <button
          type="button"
          class="lock-btn"
          :class="{ ready: registerFilled && canProgram, locked: isLocked }"
          :disabled="!canProgram || !registerFilled"
          @click="lockProgram"
        >
          <span class="lock-btn-icon">{{ isLocked ? '✓' : '🔒' }}</span>
          <span>{{ isLocked ? 'Locked in' : 'Lock program' }}</span>
        </button>
      </div>
    </section>

    <section v-else class="spectator-dock">
      <p>Spectating — you are not racing in this game.</p>
    </section>
  </div>
</template>

<style scoped>
.roborally-board {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
  padding: 0.65rem 1rem 1rem;
  background:
    radial-gradient(ellipse 80% 50% at 50% -20%, rgba(99, 102, 241, 0.12), transparent),
    linear-gradient(180deg, rgba(15, 23, 42, 0.4) 0%, transparent 30%);
}

/* ── Status bar ── */
.status-bar {
  flex-shrink: 0;
  display: flex;
  align-items: center;
  gap: 1rem;
  flex-wrap: wrap;
  padding: 0.85rem 1.15rem;
  border-radius: 14px;
  background: rgba(15, 23, 42, 0.75);
  border: 1px solid rgba(148, 163, 184, 0.15);
  backdrop-filter: blur(8px);
}

.status-left {
  display: flex;
  align-items: center;
  gap: 0.85rem;
  flex: 1;
  min-width: 200px;
}

.phase-badge {
  flex-shrink: 0;
  padding: 0.35rem 0.75rem;
  border-radius: 999px;
  font-size: 0.72rem;
  font-weight: 800;
  letter-spacing: 0.06em;
  text-transform: uppercase;
}

.phase--programming {
  background: rgba(34, 197, 94, 0.18);
  color: #86efac;
  border: 1px solid rgba(34, 197, 94, 0.35);
}

.phase--waiting {
  background: rgba(234, 179, 8, 0.18);
  color: #fde047;
  border: 1px solid rgba(234, 179, 8, 0.35);
}

.phase--executing {
  background: rgba(59, 130, 246, 0.18);
  color: #93c5fd;
  border: 1px solid rgba(59, 130, 246, 0.35);
  animation: pulse-phase 1.5s ease-in-out infinite;
}

.phase--finished {
  background: rgba(168, 85, 247, 0.18);
  color: #d8b4fe;
  border: 1px solid rgba(168, 85, 247, 0.35);
}

@keyframes pulse-phase {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.65; }
}

.status-copy {
  min-width: 0;
}

.map-name {
  margin: 0;
  font-size: 1.15rem;
  font-weight: 700;
  letter-spacing: -0.02em;
}

.status-line {
  margin: 0.15rem 0 0;
  font-size: 0.88rem;
  color: var(--text-muted);
}

.status-stats {
  display: flex;
  gap: 0.6rem;
  flex-wrap: wrap;
}

.stat-pill {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 0.4rem 0.85rem;
  border-radius: 10px;
  background: rgba(30, 41, 59, 0.8);
  border: 1px solid rgba(148, 163, 184, 0.12);
  min-width: 4.5rem;
}

.stat-pill--accent {
  border-color: rgba(250, 204, 21, 0.25);
  background: rgba(250, 204, 21, 0.06);
}

.stat-label {
  font-size: 0.65rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: var(--text-muted);
}

.stat-value {
  font-size: 1rem;
  font-weight: 800;
  margin-top: 0.1rem;
}

.forfeit-btn {
  flex-shrink: 0;
}

/* ── Main stage ── */
.main-stage {
  flex: 1;
  min-height: 0;
  display: grid;
  grid-template-columns: 1fr min(240px, 24vw);
  gap: 0.75rem;
}

@media (max-width: 860px) {
  .main-stage {
    grid-template-columns: 1fr;
    grid-template-rows: 1fr auto;
  }

  .racers-panel {
    max-height: 140px;
  }

  .racer-list {
    flex-direction: row !important;
    overflow-x: auto;
  }

  .racer-card {
    min-width: 180px;
  }
}

.arena {
  min-height: 0;
  min-width: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 0.5rem;
  border-radius: 16px;
  background:
    linear-gradient(145deg, rgba(15, 23, 42, 0.9), rgba(30, 41, 59, 0.6));
  border: 1px solid rgba(148, 163, 184, 0.12);
  box-shadow:
    inset 0 1px 0 rgba(255, 255, 255, 0.04),
    0 8px 32px rgba(0, 0, 0, 0.25);
}

.grid-frame {
  width: 100%;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 0.75rem;
}

.grid {
  display: grid;
  gap: 3px;
  height: 100%;
  width: auto;
  max-width: 100%;
  padding: 6px;
  border-radius: 12px;
  background: rgba(0, 0, 0, 0.35);
  box-shadow: inset 0 2px 12px rgba(0, 0, 0, 0.4);
}

.cell {
  position: relative;
  min-width: 0;
  min-height: 0;
  border-radius: 5px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.cell.floor-a {
  background: linear-gradient(145deg, #1a2744, #152038);
}

.cell.floor-b {
  background: linear-gradient(145deg, #162035, #121a2e);
}

.cell.floor::after {
  content: '';
  position: absolute;
  inset: 2px;
  border-radius: 3px;
  border: 1px solid rgba(255, 255, 255, 0.03);
  pointer-events: none;
}

.cell.wall {
  background: linear-gradient(160deg, #64748b, #334155);
  box-shadow:
    inset 0 2px 4px rgba(255, 255, 255, 0.12),
    inset 0 -2px 4px rgba(0, 0, 0, 0.35);
}

.cell.checkpoint {
  box-shadow: inset 0 0 0 2px rgba(250, 204, 21, 0.45);
}

.cell.antenna {
  background: radial-gradient(circle at center, #4338ca, #312e81);
}

.cp-ring {
  position: absolute;
  inset: 12%;
  border-radius: 50%;
  border: 2px solid rgba(250, 204, 21, 0.55);
  background: rgba(250, 204, 21, 0.08);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1;
}

.cp-num {
  font-size: clamp(0.7rem, 1.4vmin, 1.15rem);
  font-weight: 900;
  color: #fde047;
  text-shadow: 0 1px 3px rgba(0, 0, 0, 0.8);
}

.antenna-glow {
  position: relative;
  z-index: 1;
  animation: antenna-pulse 2s ease-in-out infinite;
}

.antenna-icon {
  font-size: clamp(0.9rem, 2vmin, 1.4rem);
  filter: drop-shadow(0 0 6px rgba(129, 140, 248, 0.8));
}

@keyframes antenna-pulse {
  0%, 100% { transform: scale(1); opacity: 0.9; }
  50% { transform: scale(1.08); opacity: 1; }
}

.robot {
  position: relative;
  width: 78%;
  height: 78%;
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 3;
}

.robot--me .robot-shell {
  box-shadow:
    0 0 0 2px rgba(255, 255, 255, 0.85),
    0 0 14px var(--robot-color),
    0 4px 10px rgba(0, 0, 0, 0.45);
}

.robot-shell {
  width: 100%;
  height: 100%;
  border-radius: 6px;
  background: linear-gradient(145deg, var(--robot-color), color-mix(in srgb, var(--robot-color) 70%, black));
  border: 2px solid rgba(255, 255, 255, 0.4);
  box-shadow: 0 3px 8px rgba(0, 0, 0, 0.45);
}

.robot-arrow {
  position: absolute;
  font-size: clamp(0.9rem, 2.2vmin, 1.5rem);
  font-weight: 900;
  color: white;
  text-shadow: 0 1px 3px rgba(0, 0, 0, 0.9);
}

/* ── Racers panel ── */
.racers-panel {
  min-height: 0;
  display: flex;
  flex-direction: column;
  padding: 0.85rem 1rem;
  border-radius: 14px;
  background: rgba(15, 23, 42, 0.75);
  border: 1px solid rgba(148, 163, 184, 0.12);
  overflow: hidden;
}

.panel-head h3 {
  margin: 0;
  font-size: 0.95rem;
  font-weight: 700;
}

.panel-sub {
  display: block;
  margin-top: 0.15rem;
  font-size: 0.72rem;
  color: var(--text-muted);
}

.racer-list {
  list-style: none;
  margin: 0.75rem 0 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
  overflow-y: auto;
  flex: 1;
}

.racer-card {
  display: flex;
  align-items: center;
  gap: 0.55rem;
  padding: 0.55rem 0.65rem;
  border-radius: 10px;
  background: rgba(30, 41, 59, 0.55);
  border: 1px solid transparent;
}

.racer-card--me {
  border-color: rgba(99, 102, 241, 0.45);
  background: rgba(99, 102, 241, 0.1);
}

.racer-card--locked {
  opacity: 0.85;
}

.racer-rank {
  width: 1.25rem;
  font-size: 0.8rem;
  font-weight: 800;
  color: var(--text-muted);
  text-align: center;
}

.racer-dot {
  width: 0.75rem;
  height: 0.75rem;
  border-radius: 50%;
  flex-shrink: 0;
  box-shadow: 0 0 6px currentColor;
}

.racer-info {
  flex: 1;
  min-width: 0;
}

.racer-name {
  display: block;
  font-size: 0.82rem;
  font-weight: 600;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.you-tag {
  margin-left: 0.35rem;
  font-size: 0.65rem;
  font-weight: 700;
  color: #a5b4fc;
}

.cp-track {
  margin-top: 0.3rem;
  height: 4px;
  border-radius: 999px;
  background: rgba(148, 163, 184, 0.15);
  overflow: hidden;
}

.cp-fill {
  height: 100%;
  border-radius: 999px;
  transition: width 0.35s ease;
}

.racer-meta {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 0.15rem;
}

.racer-cp {
  font-size: 0.72rem;
  font-weight: 700;
  color: var(--text-muted);
}

.lock-icon {
  font-size: 0.75rem;
}

/* ── Programming dock ── */
.programming-dock {
  flex-shrink: 0;
  display: grid;
  grid-template-columns: 1fr 1.4fr auto;
  gap: 1rem;
  align-items: end;
  padding: 1rem 1.15rem;
  border-radius: 16px;
  background: linear-gradient(180deg, rgba(15, 23, 42, 0.92), rgba(30, 41, 59, 0.85));
  border: 1px solid rgba(148, 163, 184, 0.14);
  box-shadow: 0 -4px 24px rgba(0, 0, 0, 0.2);
}

@media (max-width: 960px) {
  .programming-dock {
    grid-template-columns: 1fr;
    align-items: stretch;
  }

  .dock-actions {
    justify-content: stretch;
  }

  .lock-btn {
    width: 100%;
  }
}

.dock-section {
  min-width: 0;
}

.dock-head {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 0.5rem;
  margin-bottom: 0.55rem;
}

.dock-label {
  font-size: 0.72rem;
  font-weight: 800;
  text-transform: uppercase;
  letter-spacing: 0.07em;
  color: var(--text-muted);
}

.dock-count,
.dock-hint {
  font-size: 0.72rem;
  color: var(--text-muted);
}

.register-slots,
.hand-cards {
  display: flex;
  gap: 0.55rem;
  flex-wrap: wrap;
}

.slot,
.hand-card {
  border: none;
  cursor: pointer;
  color: white;
  transition:
    transform 0.15s ease,
    box-shadow 0.15s ease,
    border-color 0.15s ease;
}

.slot {
  width: clamp(3.75rem, 6vw, 5rem);
  height: clamp(4.75rem, 8vw, 6.25rem);
  border-radius: 12px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 0.2rem;
  background: rgba(30, 41, 59, 0.8);
  border: 2px dashed rgba(148, 163, 184, 0.35);
}

.slot.pulsing.active:not(:disabled) {
  animation: slot-pulse 2s ease-in-out infinite;
}

@keyframes slot-pulse {
  0%, 100% { border-color: rgba(148, 163, 184, 0.35); }
  50% { border-color: rgba(99, 102, 241, 0.55); }
}

.slot.active:not(:disabled):hover {
  transform: translateY(-2px);
  border-color: rgba(99, 102, 241, 0.65);
}

.slot.filled {
  border-style: solid;
}

.slot.card--move.filled {
  background: linear-gradient(160deg, #059669, #047857);
  border-color: rgba(110, 231, 183, 0.5);
}

.slot.card--turn.filled {
  background: linear-gradient(160deg, #0284c7, #0369a1);
  border-color: rgba(125, 211, 252, 0.5);
}

.slot.card--backup.filled {
  background: linear-gradient(160deg, #d97706, #b45309);
  border-color: rgba(253, 186, 116, 0.5);
}

.slot:disabled {
  opacity: 0.55;
  cursor: default;
}

.slot-num {
  font-size: 0.68rem;
  font-weight: 700;
  opacity: 0.75;
}

.slot-card {
  font-size: clamp(1.35rem, 2.5vw, 1.85rem);
  font-weight: 900;
  line-height: 1;
}

.slot-empty {
  font-size: 1.75rem;
  font-weight: 300;
  opacity: 0.45;
}

.hand-card {
  width: clamp(4rem, 6.5vw, 5.25rem);
  height: clamp(5rem, 9vw, 6.75rem);
  padding: 0.45rem 0.35rem;
  border-radius: 12px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 0.25rem;
  border: 2px solid rgba(255, 255, 255, 0.12);
}

.hand-card.card--move {
  background: linear-gradient(165deg, #10b981, #065f46);
}

.hand-card.card--turn {
  background: linear-gradient(165deg, #0ea5e9, #075985);
}

.hand-card.card--backup {
  background: linear-gradient(165deg, #f59e0b, #92400e);
}

.hand-card.card--unknown,
.hand-card.hidden {
  background: linear-gradient(165deg, #64748b, #334155);
}

.hand-card.selected {
  transform: translateY(-4px) scale(1.04);
  box-shadow:
    0 0 0 3px rgba(99, 102, 241, 0.55),
    0 8px 20px rgba(0, 0, 0, 0.35);
}

.hand-card:not(:disabled):hover {
  transform: translateY(-2px);
}

.hand-card:disabled {
  opacity: 0.45;
  cursor: default;
}

.hand-card-glyph {
  font-size: clamp(1.4rem, 2.8vw, 2rem);
  font-weight: 900;
  line-height: 1;
}

.hand-card-name {
  font-size: 0.58rem;
  font-weight: 700;
  text-align: center;
  line-height: 1.15;
  opacity: 0.9;
}

.dock-actions {
  display: flex;
  align-items: flex-end;
  padding-bottom: 0.15rem;
}

.lock-btn {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.85rem 1.35rem;
  border-radius: 12px;
  border: 2px solid rgba(148, 163, 184, 0.25);
  background: rgba(30, 41, 59, 0.9);
  color: var(--text-muted);
  font-size: 0.95rem;
  font-weight: 700;
  cursor: pointer;
  white-space: nowrap;
  transition: all 0.2s ease;
}

.lock-btn.ready:not(:disabled) {
  background: linear-gradient(145deg, #6366f1, #4f46e5);
  border-color: rgba(165, 180, 252, 0.5);
  color: white;
  box-shadow: 0 4px 16px rgba(99, 102, 241, 0.35);
}

.lock-btn.ready:not(:disabled):hover {
  transform: translateY(-1px);
  box-shadow: 0 6px 20px rgba(99, 102, 241, 0.45);
}

.lock-btn.locked {
  background: rgba(34, 197, 94, 0.15);
  border-color: rgba(34, 197, 94, 0.4);
  color: #86efac;
}

.lock-btn:disabled:not(.locked) {
  opacity: 0.5;
  cursor: default;
}

.lock-btn-icon {
  font-size: 1.1rem;
}

.spectator-dock {
  flex-shrink: 0;
  padding: 1rem 1.15rem;
  border-radius: 14px;
  background: rgba(15, 23, 42, 0.75);
  border: 1px solid rgba(148, 163, 184, 0.12);
  text-align: center;
}

.spectator-dock p {
  margin: 0;
  color: var(--text-muted);
}
</style>
