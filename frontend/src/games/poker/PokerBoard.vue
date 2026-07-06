<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import type { Room, PokerGameState } from '@/types'
import PlayingCard from './PlayingCard.vue'

const props = defineProps<{
  gameState: PokerGameState
  room: Room
  playerId: string
}>()

const emit = defineEmits<{
  action: [data: Record<string, unknown>]
}>()

const raiseAmount = ref(0)

const isHost = computed(() => props.room.host_player_id === props.playerId)
const isMyTurn = computed(() => props.gameState.current_actor_id === props.playerId)
const myPlayer = computed(() => props.gameState.players.find((p) => p.id === props.playerId))
const phaseLabel = computed(() => {
  const map: Record<string, string> = {
    preflop: 'Pre-flop',
    flop: 'Flop',
    turn: 'Turn',
    river: 'River',
    showdown: 'Showdown',
    hand_complete: 'Hand complete',
    game_over: 'Game over',
  }
  return map[props.gameState.phase] ?? props.gameState.phase
})

const lastActionText = computed(() => {
  const action = props.gameState.last_action
  if (!action) return ''
  const player = props.gameState.players.find((p) => p.id === action.player_id)
  const name = player?.nickname ?? 'Player'
  switch (action.type) {
    case 'fold':
      return `${name} folded`
    case 'check':
      return `${name} checked`
    case 'call':
      return `${name} called ${action.amount}`
    case 'raise':
      return `${name} raised to ${action.amount}`
    case 'all_in':
      return `${name} went all-in (${action.amount})`
    default:
      return ''
  }
})

const canAct = computed(
  () =>
    isMyTurn.value &&
    myPlayer.value?.status === 'active' &&
    ['preflop', 'flop', 'turn', 'river'].includes(props.gameState.phase),
)

const seatPositions = computed(() => {
  const order = props.gameState.seat_order
  const myIndex = order.indexOf(props.playerId)
  const rotated = [...order.slice(myIndex), ...order.slice(0, myIndex)]
  return rotated.map((id, visualIndex) => {
    const player = props.gameState.players.find((p) => p.id === id)
    const angle = (visualIndex / rotated.length) * 360 - 90
    const radiusX = 42
    const radiusY = 38
    const x = 50 + radiusX * Math.cos((angle * Math.PI) / 180)
    const y = 50 + radiusY * Math.sin((angle * Math.PI) / 180)
    return { id, player, x, y, visualIndex }
  })
})

function syncRaiseDefault() {
  raiseAmount.value = props.gameState.min_raise_to || props.gameState.current_bet + props.gameState.min_raise
}

function fold() {
  emit('action', { type: 'fold' })
}

function check() {
  emit('action', { type: 'check' })
}

function call() {
  emit('action', { type: 'call' })
}

function raise() {
  emit('action', { type: 'raise', amount: raiseAmount.value })
}

function allIn() {
  emit('action', { type: 'all_in' })
}

function nextHand() {
  emit('action', { type: 'next_hand' })
}

const showHoleCards = computed(
  () => props.gameState.phase === 'showdown' || props.gameState.phase === 'hand_complete',
)

watch(
  () => props.gameState.min_raise_to,
  (val) => {
    if (val > 0) raiseAmount.value = val
  },
  { immediate: true },
)
</script>

<template>
  <div class="poker-board">
    <div class="status-bar card">
      <span>Hand #{{ gameState.hand_number }}</span>
      <span class="phase">{{ phaseLabel }}</span>
      <span class="pot">Pot: {{ gameState.pot_total }}</span>
    </div>

    <p v-if="lastActionText" class="last-action">{{ lastActionText }}</p>

    <div class="table-wrap">
      <div class="table-felt">
        <div class="community">
          <PlayingCard
            v-for="(card, i) in gameState.community_cards"
            :key="`c-${i}`"
            :rank="card.rank"
            :suit="card.suit"
            small
          />
          <PlayingCard v-for="n in Math.max(0, 5 - gameState.community_cards.length)" :key="`empty-${n}`" face-down small />
        </div>
        <div class="pot-center">Pot {{ gameState.pot_total }}</div>

        <div
          v-for="seat in seatPositions"
          :key="seat.id"
          class="seat"
          :class="{
            active: gameState.current_actor_id === seat.id,
            folded: seat.player?.status === 'folded',
            dealer: gameState.dealer_player_id === seat.id,
            me: seat.id === playerId,
          }"
          :style="{ left: `${seat.x}%`, top: `${seat.y}%` }"
        >
          <div class="seat-info">
            <span class="seat-name">{{ seat.player?.nickname }}</span>
            <span v-if="gameState.dealer_player_id === seat.id" class="dealer-btn">D</span>
            <span class="seat-chips">{{ seat.player?.chips }} chips</span>
            <span v-if="seat.player && seat.player.bet_this_round > 0" class="seat-bet">
              Bet {{ seat.player.bet_this_round }}
            </span>
          </div>
          <div class="hole-cards">
            <template v-if="seat.id === playerId || (showHoleCards && seat.player?.status !== 'folded')">
              <PlayingCard
                v-for="(card, i) in seat.player?.hole_cards ?? []"
                :key="`${seat.id}-${i}`"
                :rank="card.rank"
                :suit="card.suit"
                small
              />
            </template>
            <template v-else-if="seat.player?.status !== 'folded'">
              <PlayingCard face-down small />
              <PlayingCard face-down small />
            </template>
          </div>
          <p v-if="seat.player?.hand_description && showHoleCards" class="hand-desc">
            {{ seat.player.hand_description }}
          </p>
        </div>
      </div>
    </div>

    <div v-if="gameState.winners.length && gameState.phase === 'hand_complete'" class="winners card">
      <h3>Hand winners</h3>
      <ul>
        <li v-for="(w, i) in gameState.winners" :key="i">
          {{ gameState.players.find((p) => p.id === w.player_id)?.nickname }} wins {{ w.amount }}
          <span v-if="w.hand"> ({{ w.hand.replace(/_/g, ' ') }})</span>
        </li>
      </ul>
    </div>

    <div v-if="gameState.phase === 'game_over'" class="game-over card">
      <h2>
        {{ gameState.players.find((p) => p.id === gameState.winner)?.nickname }} wins the game!
      </h2>
    </div>

    <div v-if="canAct" class="action-bar card">
      <p class="turn-hint">Your turn — bet to call: {{ gameState.bet_to_call }}</p>
      <div class="action-buttons">
        <button type="button" class="btn-secondary" @click="fold">Fold</button>
        <button v-if="gameState.can_check" type="button" class="btn-secondary" @click="check">Check</button>
        <button v-if="gameState.bet_to_call > 0" type="button" class="btn-primary" @click="call">
          Call {{ gameState.bet_to_call }}
        </button>
        <button type="button" class="btn-secondary" @click="allIn">All-in</button>
      </div>
      <div class="raise-row">
        <label>
          Raise to
          <input
            v-model.number="raiseAmount"
            type="range"
            :min="gameState.min_raise_to"
            :max="gameState.max_raise_to"
            @focus="syncRaiseDefault"
          />
          <span>{{ raiseAmount || gameState.min_raise_to }}</span>
        </label>
        <button
          type="button"
          class="btn-primary"
          :disabled="raiseAmount < gameState.min_raise_to"
          @click="raise"
        >
          Raise
        </button>
      </div>
    </div>

    <div v-else-if="!canAct && ['preflop', 'flop', 'turn', 'river'].includes(gameState.phase)" class="waiting card">
      <p>Waiting for {{ gameState.players.find((p) => p.id === gameState.current_actor_id)?.nickname }}…</p>
    </div>

    <div v-if="gameState.phase === 'hand_complete' && isHost && !gameState.winner" class="next-hand card">
      <button type="button" class="btn-primary" @click="nextHand">Deal next hand</button>
    </div>
  </div>
</template>

<style scoped>
.poker-board {
  max-width: 900px;
  margin: 0 auto;
  padding: 1rem;
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.status-bar {
  display: flex;
  gap: 1.5rem;
  flex-wrap: wrap;
  font-weight: 600;
}

.phase {
  color: var(--accent);
}

.pot {
  color: var(--success, #2ecc71);
}

.last-action {
  text-align: center;
  color: var(--text-muted);
  font-size: 0.95rem;
}

.table-wrap {
  position: relative;
  width: 100%;
  padding-bottom: 75%;
}

.table-felt {
  position: absolute;
  inset: 0;
  background: radial-gradient(ellipse at center, #1e6b3a 0%, #0d3d22 100%);
  border-radius: 50% / 40%;
  border: 8px solid #5c3d1e;
  box-shadow: inset 0 0 40px rgba(0, 0, 0, 0.4);
}

.community {
  position: absolute;
  top: 38%;
  left: 50%;
  transform: translate(-50%, -50%);
  display: flex;
  gap: 0.35rem;
}

.pot-center {
  position: absolute;
  top: 52%;
  left: 50%;
  transform: translate(-50%, -50%);
  color: #f0e6c8;
  font-weight: 700;
  font-size: 0.9rem;
}

.seat {
  position: absolute;
  transform: translate(-50%, -50%);
  text-align: center;
  min-width: 100px;
}

.seat.active .seat-info {
  outline: 2px solid #ffd700;
  border-radius: 6px;
}

.seat.folded {
  opacity: 0.45;
}

.seat.me .seat-name {
  color: #ffd700;
}

.seat-info {
  background: rgba(0, 0, 0, 0.55);
  padding: 0.35rem 0.5rem;
  border-radius: 6px;
  color: #fff;
  font-size: 0.75rem;
  margin-bottom: 0.25rem;
}

.seat-name {
  display: block;
  font-weight: 700;
}

.dealer-btn {
  display: inline-block;
  background: #fff;
  color: #000;
  border-radius: 50%;
  width: 1.1rem;
  height: 1.1rem;
  line-height: 1.1rem;
  font-size: 0.65rem;
  font-weight: 800;
  margin-left: 0.25rem;
}

.hole-cards {
  display: flex;
  gap: 0.2rem;
  justify-content: center;
}

.hand-desc {
  font-size: 0.65rem;
  color: #f0e6c8;
  margin: 0.2rem 0 0;
}

.action-bar,
.waiting,
.winners,
.game-over,
.next-hand {
  padding: 1rem;
}

.action-buttons {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
  margin: 0.75rem 0;
}

.raise-row {
  display: flex;
  align-items: center;
  gap: 1rem;
  flex-wrap: wrap;
}

.raise-row label {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  flex: 1;
}

.turn-hint {
  font-weight: 600;
  margin: 0;
}

.winners ul {
  margin: 0.5rem 0 0;
  padding-left: 1.25rem;
}

.game-over {
  text-align: center;
}
</style>
