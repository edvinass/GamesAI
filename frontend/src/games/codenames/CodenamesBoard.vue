<script setup lang="ts">
import { computed } from 'vue'
import type { GameState, Room } from '@/types'
import TeamPanel from './TeamPanel.vue'
import ClueInput from './ClueInput.vue'

const props = defineProps<{
  gameState: GameState
  room: Room
  playerId: string
}>()

const emit = defineEmits<{
  action: [data: Record<string, unknown>]
}>()

const me = computed(() => props.room.players.find((p) => p.id === props.playerId))

const isMyTurn = computed(() => {
  if (!me.value) return false
  return (
    me.value.team === props.gameState.current_team &&
    ((props.gameState.phase === 'clue' && me.value.role === 'spymaster') ||
      (props.gameState.phase === 'guess' && me.value.role === 'operative'))
  )
})

const redPlayers = computed(() => props.room.players.filter((p) => p.team === 'red'))
const bluePlayers = computed(() => props.room.players.filter((p) => p.team === 'blue'))

function guessCard(index: number) {
  if (!isMyTurn.value || props.gameState.phase !== 'guess') return
  emit('action', { type: 'guess_word', card_index: index })
}

function submitClue(word: string, number: number) {
  emit('action', { type: 'submit_clue', clue_word: word, clue_number: number })
}

function endTurn() {
  emit('action', { type: 'end_turn' })
}

function cardClass(card: { revealed: boolean; color?: string }) {
  if (!card.revealed) return 'hidden'
  return card.color ?? 'hidden'
}
</script>

<template>
  <div class="board-container container">
    <div v-if="gameState.winner" class="game-over card">
      <h2>{{ gameState.winner.toUpperCase() }} team wins!</h2>
      <p v-if="gameState.win_reason === 'assassin'">Assassin card was revealed.</p>
      <p v-else>All team words revealed.</p>
    </div>

    <div class="status-bar">
      <span :class="['turn-indicator', gameState.current_team]">
        {{ gameState.current_team.toUpperCase() }} team's turn
        · {{ gameState.phase === 'clue' ? 'Give a clue' : 'Guess words' }}
      </span>
      <span v-if="gameState.current_clue" class="current-clue">
        Clue: <strong>{{ gameState.current_clue.word }}</strong> {{ gameState.current_clue.number }}
        <span v-if="gameState.phase === 'guess'"> · {{ gameState.guesses_remaining }} guesses left</span>
      </span>
    </div>

    <div class="layout">
      <TeamPanel team="red" :players="redPlayers" :remaining="gameState.red_remaining" />

      <div class="center">
        <ClueInput
          v-if="isMyTurn && gameState.phase === 'clue'"
          @submit="submitClue"
        />

        <div class="grid">
          <button
            v-for="card in gameState.cards"
            :key="card.index"
            :class="['card-btn', cardClass(card)]"
            :disabled="!isMyTurn || gameState.phase !== 'guess' || card.revealed"
            @click="guessCard(card.index)"
          >
            {{ card.word }}
          </button>
        </div>

        <button
          v-if="isMyTurn && gameState.phase === 'guess'"
          class="btn-secondary end-turn-btn"
          @click="endTurn"
        >
          End Turn
        </button>
      </div>

      <TeamPanel team="blue" :players="bluePlayers" :remaining="gameState.blue_remaining" />
    </div>
  </div>
</template>

<style scoped>
.board-container {
  padding-bottom: 2rem;
}

.game-over {
  text-align: center;
  margin-bottom: 1.5rem;
  padding: 1.5rem;
}

.game-over h2 {
  font-size: 1.5rem;
  margin-bottom: 0.5rem;
}

.status-bar {
  display: flex;
  flex-wrap: wrap;
  gap: 1rem;
  justify-content: center;
  margin-bottom: 1.25rem;
  font-size: 0.9rem;
}

.turn-indicator.red { color: var(--red-team); }
.turn-indicator.blue { color: var(--blue-team); }

.current-clue {
  color: var(--text-muted);
}

.layout {
  display: grid;
  grid-template-columns: 160px 1fr 160px;
  gap: 1rem;
  align-items: start;
}

@media (max-width: 900px) {
  .layout {
    grid-template-columns: 1fr;
  }
}

.center {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 1rem;
}

.grid {
  display: grid;
  grid-template-columns: repeat(5, 1fr);
  gap: 0.5rem;
  width: 100%;
  max-width: 700px;
}

@media (max-width: 600px) {
  .grid {
    grid-template-columns: repeat(3, 1fr);
  }
}

.card-btn {
  aspect-ratio: 1.6;
  padding: 0.5rem;
  font-size: 0.75rem;
  font-weight: 600;
  text-transform: uppercase;
  border-radius: 8px;
  border: 2px solid var(--border);
  background: #c4a35a;
  color: #1a1a1a;
  word-break: break-word;
  line-height: 1.2;
}

.card-btn.hidden {
  background: #c4a35a;
  color: #1a1a1a;
}

.card-btn.red {
  background: var(--red-team);
  color: white;
  border-color: var(--red-team);
}

.card-btn.blue {
  background: var(--blue-team);
  color: white;
  border-color: var(--blue-team);
}

.card-btn.neutral {
  background: #c4a35a;
  color: #1a1a1a;
  border-color: #a08040;
}

.card-btn.assassin {
  background: var(--assassin);
  color: white;
  border-color: #333;
}

.card-btn:disabled:not(.red):not(.blue):not(.neutral):not(.assassin) {
  cursor: default;
}

.card-btn:not(:disabled):hover {
  transform: scale(1.03);
  box-shadow: var(--shadow);
}

.end-turn-btn {
  margin-top: 0.5rem;
}
</style>
