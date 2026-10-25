<script setup lang="ts">
import { computed } from 'vue'
import { RouterLink } from 'vue-router'
import type { Room } from '@/types'

const props = defineProps<{
  room: Room
  isHost: boolean
  currentPlayerId: string
  hostPlayerId: string | null
  validationMessage: string
  validationValid: boolean
  validationIssues: string[]
}>()

const soloPractice = defineModel<boolean>('soloPractice', { required: true })
const aiDifficulty = defineModel<string>('aiDifficulty', { required: true })

const emit = defineEmits<{
  addAi: []
  remove: [id: string]
}>()

const difficultyOptions = [
  { value: 'easy', label: 'Easy' },
  { value: 'medium', label: 'Medium' },
  { value: 'hard', label: 'Hard' },
] as const

const hasAi = computed(() => props.room.players.some((player) => player.is_ai))
const showStrength = computed(() => soloPractice.value || hasAi.value)

const activeDifficulty = computed(
  () => difficultyOptions.find((opt) => opt.value === aiDifficulty.value) ?? difficultyOptions[1],
)

const playerCount = computed(() => props.room.players.length)
const canAddAi = computed(
  () => props.isHost && !soloPractice.value && playerCount.value < 2,
)

const seats = computed(() => {
  const players = props.room.players
  if (soloPractice.value) {
    const human = players.find((player) => !player.is_ai) ?? null
    return [
      { color: 'w' as const, label: 'White', player: human, pending: 'You' },
      { color: 'b' as const, label: 'Black', player: null, pending: 'AI' },
    ]
  }
  return [
    {
      color: 'w' as const,
      label: 'White',
      player: players[0] ?? null,
      pending: 'Waiting',
    },
    {
      color: 'b' as const,
      label: 'Black',
      player: players[1] ?? null,
      pending: 'Open',
    },
  ]
})
</script>

<template>
  <div class="chess-lobby">
    <RouterLink to="/chess/learn" class="card learn-card">
      <span class="learn-mark" aria-hidden="true">★</span>
      <span>
        <strong>Learn chess</strong>
        <small>Guided lessons, puzzles, a capture drill, and a match with Oscar.</small>
      </span>
    </RouterLink>

    <section v-if="isHost" class="card setup">
      <div class="segment" role="radiogroup" aria-label="Game mode">
        <button
          type="button"
          role="radio"
          :aria-checked="soloPractice"
          :class="{ active: soloPractice }"
          @click="soloPractice = true"
        >
          Vs AI
        </button>
        <button
          type="button"
          role="radio"
          :aria-checked="!soloPractice"
          :class="{ active: !soloPractice }"
          @click="soloPractice = false"
        >
          Match
        </button>
      </div>

      <div v-if="showStrength" class="strength">
        <span class="strength-label">AI</span>
        <div class="segment" role="radiogroup" aria-label="AI strength">
          <button
            v-for="opt in difficultyOptions"
            :key="opt.value"
            type="button"
            role="radio"
            :aria-checked="aiDifficulty === opt.value"
            :class="{ active: aiDifficulty === opt.value }"
            @click="aiDifficulty = opt.value"
          >
            {{ opt.label }}
          </button>
        </div>
      </div>
    </section>

    <p v-else class="card guest">
      {{ soloPractice ? 'Vs AI' : 'Match' }}
      <template v-if="showStrength"> · {{ activeDifficulty.label }}</template>
    </p>

    <section class="card seats" aria-label="Players">
      <div
        v-for="seat in seats"
        :key="seat.color"
        class="seat"
        :class="{
          filled: Boolean(seat.player),
          empty: !seat.player,
          me: seat.player?.id === currentPlayerId,
          ai: seat.player?.is_ai || (soloPractice && seat.color === 'b'),
        }"
      >
        <span class="king" :class="seat.color" aria-hidden="true">
          {{ seat.color === 'w' ? '♔' : '♚' }}
        </span>
        <div class="seat-body">
          <p class="seat-side">{{ seat.label }}</p>
          <p v-if="seat.player" class="seat-name">{{ seat.player.nickname }}</p>
          <p v-else class="seat-name pending">{{ seat.pending }}</p>
        </div>
        <div v-if="seat.player" class="badges">
          <span v-if="seat.player.is_ai" class="badge">AI</span>
          <span v-if="seat.player.id === currentPlayerId" class="badge you">You</span>
          <span v-if="seat.player.id === hostPlayerId" class="badge">Host</span>
        </div>
        <button
          v-if="isHost && seat.player?.is_ai && !soloPractice"
          type="button"
          class="btn-secondary remove"
          @click="emit('remove', seat.player.id)"
        >
          Remove
        </button>
      </div>

      <button v-if="canAddAi" type="button" class="btn-secondary add-ai" @click="emit('addAi')">
        Add AI
      </button>
    </section>

    <p v-if="!validationValid" class="card problem">
      {{ validationMessage }}
    </p>
    <ul v-if="!validationValid && validationIssues.length > 1" class="issues">
      <li v-for="issue in validationIssues" :key="issue">{{ issue }}</li>
    </ul>
  </div>
</template>

<style scoped>
.chess-lobby {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

.learn-card {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  padding: 0.9rem 1rem;
  text-decoration: none;
  color: inherit;
}

.learn-card strong,
.learn-card small {
  display: block;
}

.learn-card small {
  color: var(--text-muted);
}

.learn-mark {
  width: 2.2rem;
  height: 2.2rem;
  border-radius: 50%;
  display: grid;
  place-items: center;
  background: #1c6b4a;
  color: white;
  flex-shrink: 0;
}

.setup {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

.segment {
  display: grid;
  grid-auto-flow: column;
  grid-auto-columns: 1fr;
  gap: 0.35rem;
  padding: 0.25rem;
  border-radius: 12px;
  background: rgba(10, 14, 23, 0.45);
}

.segment button {
  border-radius: 9px;
  padding: 0.55rem 0.7rem;
  background: transparent;
  color: var(--text-muted);
  font-size: 0.9rem;
}

.segment button.active {
  background: rgba(201, 154, 98, 0.18);
  color: var(--text);
  box-shadow: inset 0 0 0 1px rgba(201, 154, 98, 0.45);
}

.strength {
  display: flex;
  align-items: center;
  gap: 0.65rem;
}

.strength-label {
  flex-shrink: 0;
  font-size: 0.75rem;
  font-weight: 700;
  letter-spacing: 0.04em;
  text-transform: uppercase;
  color: var(--text-muted);
}

.strength .segment {
  flex: 1;
}

.guest {
  margin: 0;
  font-weight: 650;
}

.seats {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.seat {
  display: flex;
  align-items: center;
  gap: 0.7rem;
  padding: 0.55rem 0.65rem;
  border-radius: 10px;
  border: 1px solid var(--border);
  background: rgba(10, 14, 23, 0.35);
}

.seat.me {
  border-color: rgba(91, 156, 255, 0.5);
}

.seat.empty {
  border-style: dashed;
}

.king {
  width: 2.1rem;
  height: 2.1rem;
  border-radius: 8px;
  display: grid;
  place-items: center;
  flex-shrink: 0;
  font-size: 1.2rem;
}

.king.w {
  background: #efe4d4;
  color: #2a2118;
}

.king.b {
  background: #2a2422;
  color: #f0e6d8;
}

.seat-body {
  min-width: 0;
  flex: 1;
}

.seat-side {
  margin: 0;
  font-size: 0.68rem;
  font-weight: 700;
  letter-spacing: 0.04em;
  text-transform: uppercase;
  color: var(--text-muted);
}

.seat-name {
  margin: 0.05rem 0 0;
  font-weight: 650;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.seat-name.pending {
  color: var(--text-muted);
  font-weight: 600;
}

.badges {
  display: flex;
  gap: 0.3rem;
  flex-shrink: 0;
}

.badge {
  font-size: 0.65rem;
  font-weight: 700;
  padding: 0.12rem 0.35rem;
  border-radius: 4px;
  background: rgba(255, 255, 255, 0.06);
  color: var(--text-muted);
}

.badge.you {
  background: rgba(91, 156, 255, 0.18);
  color: var(--accent);
}

.remove {
  font-size: 0.75rem;
  padding: 0.3rem 0.5rem;
}

.add-ai {
  align-self: flex-start;
}

.problem {
  margin: 0;
  border-color: rgba(230, 167, 0, 0.5);
  color: var(--text);
  font-weight: 600;
}

.issues {
  margin: -0.35rem 0 0;
  padding-left: 1.2rem;
  color: var(--text-muted);
  font-size: 0.85rem;
}
</style>
