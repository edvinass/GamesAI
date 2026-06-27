<script setup lang="ts">
import { computed, ref, watch } from 'vue'
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

const currentActor = computed(() => {
  const role = props.gameState.phase === 'clue' ? 'spymaster' : 'operative'
  return props.room.players.find(
    (p) => p.team === props.gameState.current_team && p.role === role
  )
})

const isGameOver = computed(() => Boolean(props.gameState.winner))

const isAiTurn = computed(
  () => !isGameOver.value && Boolean(currentActor.value?.is_ai),
)

const isMyTurn = computed(() => {
  if (!me.value) return false
  return (
    me.value.team === props.gameState.current_team &&
    ((props.gameState.phase === 'clue' && me.value.role === 'spymaster') ||
      (props.gameState.phase === 'guess' && me.value.role === 'operative'))
  )
})

const statusMessage = computed(() => {
  const team = props.gameState.current_team.toUpperCase()
  if (isAiTurn.value) {
    const role = props.gameState.phase === 'clue' ? 'spymaster' : 'operative'
    return `${team} team's AI ${role} is thinking...`
  }
  if (isMyTurn.value) {
    return props.gameState.phase === 'clue'
      ? `${team} team — your clue`
      : `${team} team — your guess`
  }
  const role = props.gameState.phase === 'clue' ? 'spymaster' : 'operative'
  return `${team} team — waiting for ${role}`
})

const redPlayers = computed(() => props.room.players.filter((p) => p.team === 'red'))
const bluePlayers = computed(() => props.room.players.filter((p) => p.team === 'blue'))

const isHost = computed(() => props.room.host_player_id === props.playerId)

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

function startNewGame() {
  emit('action', { type: 'start_game' })
}

function cardClasses(card: { revealed: boolean; color?: string }) {
  if (card.revealed) {
    return ['revealed', card.color ?? 'hidden']
  }
  if (props.gameState.winner && card.color) {
    if (me.value?.role === 'spymaster') {
      return ['key', card.color]
    }
    return ['unguessed', card.color]
  }
  if (card.color) {
    return ['key', card.color]
  }
  return ['hidden']
}

const poppingCards = ref<Set<number>>(new Set())

watch(
  () => props.gameState.cards.map((c) => ({ index: c.index, revealed: c.revealed })),
  (cards, prev) => {
    if (!prev) return
    for (const card of cards) {
      const wasRevealed = prev.find((c) => c.index === card.index)?.revealed
      if (card.revealed && !wasRevealed) {
        poppingCards.value = new Set(poppingCards.value).add(card.index)
        setTimeout(() => {
          const next = new Set(poppingCards.value)
          next.delete(card.index)
          poppingCards.value = next
        }, 500)
      }
    }
  },
)

function isPopping(index: number) {
  return poppingCards.value.has(index)
}
</script>

<template>
  <div class="board-container container">
    <div v-if="gameState.winner" class="game-over card">
      <h2>{{ gameState.winner.toUpperCase() }} team wins!</h2>
      <p v-if="gameState.win_reason === 'assassin'">Assassin card was revealed.</p>
      <p v-else>All team words revealed.</p>
      <button v-if="isHost" class="btn-primary new-game-btn" @click="startNewGame">
        New Game
      </button>
      <p v-else class="waiting-host">Waiting for host to start a new game...</p>
    </div>

    <div v-if="!isGameOver" class="status-bar">
      <span :class="['turn-indicator', gameState.current_team, { 'ai-thinking': isAiTurn }]">
        {{ statusMessage }}
      </span>
      <span v-if="gameState.current_clue" class="current-clue">
        Clue: <strong>{{ gameState.current_clue.word }}</strong> {{ gameState.current_clue.number }}
        <span v-if="gameState.phase === 'guess'"> · {{ gameState.guesses_remaining }} guesses left</span>
      </span>
    </div>

    <div v-if="isAiTurn" class="ai-thinking-banner card">
      🤖 AI is playing — hang tight...
    </div>

    <div class="layout">
      <TeamPanel team="red" :players="redPlayers" :remaining="gameState.red_remaining" />

      <div class="center">
        <ClueInput
          v-if="isMyTurn && gameState.phase === 'clue'"
          :board-words="gameState.cards.map((c) => c.word)"
          @submit="submitClue"
        />

        <div class="grid">
          <button
            v-for="card in gameState.cards"
            :key="card.index"
            :class="['card-btn', ...cardClasses(card), { pop: isPopping(card.index) }]"
            :disabled="!!gameState.winner || !isMyTurn || gameState.phase !== 'guess' || card.revealed"
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

.new-game-btn {
  margin-top: 1rem;
}

.waiting-host {
  margin-top: 1rem;
  font-size: 0.9rem;
  color: var(--text-muted);
}

.status-bar {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 0.5rem;
  justify-content: center;
  margin-bottom: 1.5rem;
  text-align: center;
}

.turn-indicator {
  font-size: 2rem;
  font-weight: 700;
  letter-spacing: 0.02em;
}

.turn-indicator.red { color: var(--red-team); }
.turn-indicator.blue { color: var(--blue-team); }

.turn-indicator.ai-thinking {
  animation: pulse 1.5s ease-in-out infinite;
}

@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.55; }
}

.ai-thinking-banner {
  text-align: center;
  margin-bottom: 1rem;
  padding: 0.75rem 1rem;
  color: var(--text-muted);
  font-size: 0.9rem;
  border-left: 3px solid #bb86fc;
}

.current-clue {
  font-size: 1.5rem;
  color: var(--text-muted);
}

.current-clue strong {
  font-size: 2rem;
  color: var(--text);
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
  position: relative;
}

.card-btn.hidden {
  background: #c4a35a;
  color: #1a1a1a;
}

/* Post-game unrevealed — same tan face operatives see during play, color via border */
.card-btn.unguessed {
  background: #c4a35a;
  color: #1a1a1a;
  border-style: dashed;
  cursor: default;
}

.card-btn.unguessed.red {
  border-color: var(--red-team);
}

.card-btn.unguessed.blue {
  border-color: var(--blue-team);
}

.card-btn.unguessed.neutral {
  border-color: #8a7040;
}

.card-btn.unguessed.assassin {
  border-color: #555;
}

/* Spymaster key view — unrevealed cards show a muted color hint */
.card-btn.key {
  opacity: 1;
  border-style: dashed;
}

.card-btn.key.red {
  background: color-mix(in srgb, var(--red-team) 35%, #c4a35a);
  color: #1a1a1a;
  border-color: var(--red-team);
}

.card-btn.key.blue {
  background: color-mix(in srgb, var(--blue-team) 35%, #c4a35a);
  color: #1a1a1a;
  border-color: var(--blue-team);
}

.card-btn.key.neutral {
  background: #b8956a;
  color: #1a1a1a;
  border-color: #8a7040;
}

.card-btn.key.assassin {
  background: color-mix(in srgb, var(--assassin) 40%, #c4a35a);
  color: #1a1a1a;
  border-color: #555;
}

/* Revealed cards — solid color, full opacity even when disabled */
.card-btn.revealed {
  opacity: 1;
  cursor: default;
  box-shadow: inset 0 0 0 2px rgba(255, 255, 255, 0.25);
}

.card-btn.revealed::after {
  content: '✓';
  position: absolute;
  top: 3px;
  right: 5px;
  font-size: 0.65rem;
  line-height: 1;
  opacity: 0.85;
}

.card-btn.revealed.red {
  background: var(--red-team);
  color: white;
  border-color: var(--red-team);
  border-style: solid;
}

.card-btn.revealed.blue {
  background: var(--blue-team);
  color: white;
  border-color: var(--blue-team);
  border-style: solid;
}

.card-btn.revealed.neutral {
  background: #9a8455;
  color: #f5f0e6;
  border-color: #7a6840;
  border-style: solid;
}

.card-btn.revealed.assassin {
  background: var(--assassin);
  color: white;
  border-color: #555;
  border-style: solid;
}

.card-btn.revealed.hidden {
  background: #9a8455;
  color: #f5f0e6;
  border-color: #7a6840;
  border-style: solid;
}

.card-btn.pop {
  animation: card-pop 0.45s cubic-bezier(0.34, 1.56, 0.64, 1);
  z-index: 1;
}

@keyframes card-pop {
  0% { transform: scale(1); }
  45% { transform: scale(1.14); }
  100% { transform: scale(1); }
}

.card-btn:not(:disabled):not(.revealed):hover {
  transform: scale(1.03);
  box-shadow: var(--shadow);
}

.end-turn-btn {
  margin-top: 0.5rem;
}
</style>
