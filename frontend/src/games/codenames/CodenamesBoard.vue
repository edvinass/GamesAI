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
    return `${team} AI ${role} is thinking…`
  }
  if (isMyTurn.value) {
    return props.gameState.phase === 'clue'
      ? `Your clue — ${team} team`
      : `Your guess — ${team} team`
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

const confettiPieces = Array.from({ length: 24 }, (_, i) => i)
</script>

<template>
  <div class="board-container container-wide">
    <Transition name="win">
      <div v-if="gameState.winner" class="game-over card">
        <div class="confetti" aria-hidden="true">
          <span
            v-for="piece in confettiPieces"
            :key="piece"
            class="confetti-piece"
            :style="{ '--i': piece }"
          />
        </div>
        <div class="winner-badge" :class="gameState.winner">
          🏆 {{ gameState.winner.toUpperCase() }} WINS!
        </div>
        <p class="win-reason">
          {{ gameState.win_reason === 'assassin' ? 'The assassin was revealed.' : 'All team words found!' }}
        </p>
        <button v-if="isHost" class="btn-primary new-game-btn" @click="startNewGame">
          Play Again
        </button>
        <p v-else class="waiting-host">Waiting for host to start a new game…</p>
      </div>
    </Transition>

    <div v-if="!isGameOver" class="status-bar">
      <div
        class="turn-pill"
        :class="[gameState.current_team, { 'my-turn': isMyTurn, 'ai-thinking': isAiTurn }]"
      >
        <span v-if="isAiTurn" class="ai-icon">🤖</span>
        <span class="turn-text">{{ statusMessage }}</span>
      </div>
      <Transition name="clue-reveal">
        <div v-if="gameState.current_clue" class="current-clue">
          <span class="clue-label">Clue</span>
          <strong>{{ gameState.current_clue.word }}</strong>
          <span class="clue-number">{{ gameState.current_clue.number }}</span>
          <span v-if="gameState.phase === 'guess'" class="guesses-left">
            {{ gameState.guesses_remaining }} left
          </span>
        </div>
      </Transition>
    </div>

    <div class="layout">
      <TeamPanel
        team="red"
        :players="redPlayers"
        :remaining="gameState.red_remaining"
        :active="!isGameOver && gameState.current_team === 'red'"
      />

      <div class="center">
        <Transition name="slide-down">
          <ClueInput
            v-if="isMyTurn && gameState.phase === 'clue'"
            :board-words="gameState.cards.map((c) => c.word)"
            @submit="submitClue"
          />
        </Transition>

        <div class="grid">
          <button
            v-for="(card, idx) in gameState.cards"
            :key="card.index"
            :class="[
              'card-btn',
              ...cardClasses(card),
              { pop: isPopping(card.index), 'can-guess': isMyTurn && gameState.phase === 'guess' && !card.revealed && !gameState.winner },
            ]"
            :style="{ '--delay': `${idx * 0.03}s` }"
            :disabled="!!gameState.winner || !isMyTurn || gameState.phase !== 'guess' || card.revealed"
            @click="guessCard(card.index)"
          >
            {{ card.word }}
          </button>
        </div>

        <Transition name="slide-down">
          <button
            v-if="isMyTurn && gameState.phase === 'guess'"
            class="btn-secondary end-turn-btn"
            @click="endTurn"
          >
            End Turn
          </button>
        </Transition>
      </div>

      <TeamPanel
        team="blue"
        :players="bluePlayers"
        :remaining="gameState.blue_remaining"
        :active="!isGameOver && gameState.current_team === 'blue'"
      />
    </div>
  </div>
</template>

<style scoped>
.board-container {
  padding-bottom: 1.5rem;
}

.game-over {
  position: relative;
  text-align: center;
  margin-bottom: 1.25rem;
  padding: 2rem 1.5rem;
  overflow: hidden;
}

.confetti {
  position: absolute;
  inset: 0;
  pointer-events: none;
  overflow: hidden;
}

.confetti-piece {
  position: absolute;
  width: 8px;
  height: 8px;
  top: -10px;
  left: calc(var(--i) * 4.2%);
  background: hsl(calc(var(--i) * 15), 80%, 60%);
  border-radius: 2px;
  animation: confetti-fall 2.5s ease-in forwards;
  animation-delay: calc(var(--i) * 0.05s);
}

@keyframes confetti-fall {
  0% {
    transform: translateY(0) rotate(0deg);
    opacity: 1;
  }
  100% {
    transform: translateY(180px) rotate(720deg);
    opacity: 0;
  }
}

.winner-badge {
  font-size: 1.75rem;
  font-weight: 800;
  margin-bottom: 0.5rem;
  animation: celebrate 0.6s var(--ease-bounce);
}

.winner-badge.red { color: var(--red-team); }
.winner-badge.blue { color: var(--blue-team); }

.win-reason {
  color: var(--text-muted);
  margin-bottom: 1rem;
}

.new-game-btn {
  animation: fadeInUp 0.5s var(--ease-smooth) 0.3s backwards;
}

.waiting-host {
  margin-top: 1rem;
  font-size: 0.9rem;
  color: var(--text-muted);
}

.win-enter-active {
  animation: celebrate 0.6s var(--ease-bounce);
}

.status-bar {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: center;
  gap: 0.75rem 1.25rem;
  margin-bottom: 1rem;
  animation: fadeInUp 0.4s var(--ease-smooth);
}

.turn-pill {
  display: inline-flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.5rem 1.25rem;
  border-radius: 999px;
  font-size: 0.95rem;
  font-weight: 700;
  border: 2px solid var(--border);
  background: var(--surface);
  transition: border-color 0.3s, box-shadow 0.3s, transform 0.3s;
}

.turn-pill.red {
  border-color: rgba(255, 92, 108, 0.4);
  color: var(--red-team);
}

.turn-pill.blue {
  border-color: rgba(91, 156, 255, 0.4);
  color: var(--blue-team);
}

.turn-pill.my-turn {
  animation: glowPulse 2s ease-in-out infinite;
}

.turn-pill.ai-thinking {
  animation: pulse 1.5s ease-in-out infinite;
}

.ai-icon {
  animation: float 2s ease-in-out infinite;
}

@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.6; }
}

.current-clue {
  display: flex;
  align-items: baseline;
  gap: 0.5rem;
  padding: 0.4rem 1rem;
  border-radius: 999px;
  background: var(--surface);
  border: 1px solid var(--border);
}

.clue-label {
  font-size: 0.7rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  color: var(--text-muted);
}

.current-clue strong {
  font-size: 1.35rem;
  color: var(--text);
}

.clue-number {
  font-size: 1.1rem;
  font-weight: 700;
  color: var(--accent);
}

.guesses-left {
  font-size: 0.8rem;
  color: var(--text-muted);
  padding-left: 0.5rem;
  border-left: 1px solid var(--border);
}

.clue-reveal-enter-active {
  animation: fadeInUp 0.35s var(--ease-bounce);
}

.layout {
  display: grid;
  grid-template-columns: minmax(140px, 200px) minmax(0, 1fr) minmax(140px, 200px);
  gap: 1rem;
  align-items: start;
}

@media (max-width: 1000px) {
  .layout {
    grid-template-columns: 1fr;
  }
}

.center {
  display: flex;
  flex-direction: column;
  align-items: stretch;
  gap: 0.75rem;
}

.grid {
  display: grid;
  grid-template-columns: repeat(5, 1fr);
  gap: 0.45rem;
  width: 100%;
}

@media (max-width: 600px) {
  .grid {
    grid-template-columns: repeat(3, 1fr);
  }
}

.card-btn {
  aspect-ratio: 1.55;
  padding: 0.4rem 0.35rem;
  font-size: clamp(0.65rem, 1.2vw, 0.8rem);
  font-weight: 700;
  text-transform: uppercase;
  border-radius: 10px;
  border: 2px solid var(--border);
  background: #d4b06a;
  color: #1a1a1a;
  word-break: break-word;
  line-height: 1.15;
  position: relative;
  transition:
    transform 0.2s var(--ease-bounce),
    box-shadow 0.2s,
    border-color 0.2s;
  animation: cardDeal 0.4s var(--ease-smooth) backwards;
  animation-delay: var(--delay);
}

@keyframes cardDeal {
  from {
    opacity: 0;
    transform: scale(0.85) translateY(8px);
  }
  to {
    opacity: 1;
    transform: scale(1) translateY(0);
  }
}

.card-btn.hidden {
  background: linear-gradient(145deg, #dcc078 0%, #c4a35a 100%);
  color: #1a1a1a;
}

.card-btn.unguessed {
  background: #c4a35a;
  color: #1a1a1a;
  border-style: dashed;
  cursor: default;
}

.card-btn.unguessed.red { border-color: var(--red-team); }
.card-btn.unguessed.blue { border-color: var(--blue-team); }
.card-btn.unguessed.neutral { border-color: #8a7040; }
.card-btn.unguessed.assassin { border-color: #555; }

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

.card-btn.revealed {
  opacity: 1;
  cursor: default;
  box-shadow: inset 0 0 0 2px rgba(255, 255, 255, 0.2);
}

.card-btn.revealed::after {
  content: '✓';
  position: absolute;
  top: 3px;
  right: 5px;
  font-size: 0.6rem;
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
  animation: card-pop 0.45s var(--ease-bounce);
  z-index: 1;
}

@keyframes card-pop {
  0% { transform: scale(1); }
  45% { transform: scale(1.12); }
  100% { transform: scale(1); }
}

.card-btn.can-guess:hover {
  transform: translateY(-3px) scale(1.04);
  box-shadow: 0 8px 20px rgba(0, 0, 0, 0.35), 0 0 0 2px rgba(91, 156, 255, 0.3);
  z-index: 1;
}

.end-turn-btn {
  align-self: center;
}

.slide-down-enter-active {
  animation: fadeInUp 0.35s var(--ease-bounce);
}

.slide-down-leave-active {
  animation: fadeInUp 0.2s reverse;
}
</style>
