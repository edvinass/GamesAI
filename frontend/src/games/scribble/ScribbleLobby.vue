<script setup lang="ts">
import type { Room } from '@/types'

defineProps<{
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
const rounds = defineModel<number>('rounds', { required: true })
const drawSeconds = defineModel<number>('drawSeconds', { required: true })

const emit = defineEmits<{
  addAi: []
  remove: [id: string]
}>()

const roundOptions = [
  { label: '1 round', value: 1 },
  { label: '2 rounds', value: 2 },
  { label: '3 rounds', value: 3 },
  { label: '5 rounds', value: 5 },
]

const timeOptions = [
  { label: '45 seconds', value: 45 },
  { label: '70 seconds', value: 70 },
  { label: '90 seconds', value: 90 },
  { label: '120 seconds', value: 120 },
]

const difficultyOptions = [
  { value: 'easy', label: 'Easy', detail: 'Slow guesses' },
  { value: 'medium', label: 'Medium', detail: 'Fair guesses' },
  { value: 'hard', label: 'Hard', detail: 'Quick guesses' },
]
</script>

<template>
  <div class="scribble-lobby">
    <section class="hero card">
      <div class="paper" aria-hidden="true">
        <svg viewBox="0 0 120 80">
          <path d="M18 58 C30 20, 48 18, 60 40 S90 62, 104 24" />
          <circle cx="78" cy="28" r="8" />
        </svg>
      </div>
      <div>
        <p class="eyebrow">Party</p>
        <h2>Draw it. Guess it.</h2>
        <p class="lede">
          One player sketches a secret word. Everyone else types guesses. Faster correct guesses score more, and the artist scores when the room figures it out.
        </p>
      </div>
    </section>

    <section v-if="isHost" class="settings card">
      <label class="check">
        <input v-model="soloPractice" type="checkbox" />
        Solo practice against 3 AI players
      </label>

      <div class="fields">
        <label>
          <span>Rounds</span>
          <select v-model.number="rounds">
            <option v-for="opt in roundOptions" :key="opt.value" :value="opt.value">{{ opt.label }}</option>
          </select>
        </label>
        <label>
          <span>Draw time</span>
          <select v-model.number="drawSeconds">
            <option v-for="opt in timeOptions" :key="opt.value" :value="opt.value">{{ opt.label }}</option>
          </select>
        </label>
      </div>

      <div class="difficulty" role="radiogroup" aria-label="AI difficulty">
        <button
          v-for="opt in difficultyOptions"
          :key="opt.value"
          type="button"
          :class="{ active: aiDifficulty === opt.value }"
          @click="aiDifficulty = opt.value"
        >
          <strong>{{ opt.label }}</strong>
          <span>{{ opt.detail }}</span>
        </button>
      </div>
    </section>

    <p v-if="soloPractice" class="note card">
      Solo practice adds three AI players when you start. You still draw on your turn, and you guess while they draw.
    </p>

    <template v-else>
      <p v-if="isHost" class="hint">Need 2 to 8 players. Add AI seats or share the room link.</p>
      <div class="player-list card">
        <div v-for="player in room.players" :key="player.id" class="player-row">
          <div class="player-info">
            <span class="nickname">{{ player.nickname }}</span>
            <span v-if="player.is_ai" class="ai-badge">AI</span>
            <span v-if="player.id === currentPlayerId" class="you-badge">You</span>
            <span v-if="player.id === hostPlayerId" class="host-badge">Host</span>
          </div>
          <button
            v-if="isHost && player.is_ai"
            type="button"
            class="btn-secondary remove-btn"
            @click="emit('remove', player.id)"
          >
            Remove
          </button>
        </div>
      </div>
      <button
        v-if="isHost && room.players.length < 8"
        type="button"
        class="btn-secondary add-ai-btn"
        @click="emit('addAi')"
      >
        + Add AI player
      </button>
    </template>

    <div class="validation-banner card" :class="{ valid: validationValid, invalid: !validationValid }">
      <span class="validation-icon">{{ validationValid ? '✓' : '!' }}</span>
      <div>
        <p class="validation-message">{{ validationMessage }}</p>
        <ul v-if="!validationValid && validationIssues.length > 1" class="validation-issues">
          <li v-for="issue in validationIssues" :key="issue">{{ issue }}</li>
        </ul>
      </div>
    </div>
  </div>
</template>

<style scoped>
.scribble-lobby {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.hero {
  display: grid;
  grid-template-columns: 140px 1fr;
  gap: 1.25rem;
  align-items: center;
  background:
    radial-gradient(circle at 10% 20%, rgba(244, 196, 48, 0.16), transparent 42%),
    var(--surface);
}

.paper {
  height: 96px;
  border-radius: 12px;
  background: #f6f1e7;
  border: 1px solid rgba(28, 25, 23, 0.12);
  display: grid;
  place-items: center;
}

.paper svg {
  width: 92px;
  height: 64px;
}

.paper path,
.paper circle {
  fill: none;
  stroke: #e11d48;
  stroke-width: 4;
  stroke-linecap: round;
  stroke-linejoin: round;
}

.eyebrow {
  margin: 0;
  color: var(--text-muted);
  font-size: 0.78rem;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.hero h2 {
  margin: 0.15rem 0 0.4rem;
}

.lede {
  margin: 0;
  color: var(--text-muted);
}

.settings {
  display: flex;
  flex-direction: column;
  gap: 0.9rem;
}

.check {
  display: flex;
  gap: 0.55rem;
  align-items: center;
}

.fields {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 0.75rem;
}

.fields label,
.difficulty {
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
}

.fields span,
.difficulty button span {
  color: var(--text-muted);
  font-size: 0.82rem;
}

.difficulty {
  flex-direction: row;
}

.difficulty button {
  flex: 1;
  text-align: left;
  border-radius: 12px;
  border: 1px solid var(--border);
  background: transparent;
  color: inherit;
  padding: 0.7rem 0.8rem;
}

.difficulty button.active {
  border-color: #e11d48;
  box-shadow: 0 0 0 3px rgba(225, 29, 72, 0.2);
}

.difficulty strong,
.difficulty span {
  display: block;
}

.note,
.hint {
  margin: 0;
  color: var(--text-muted);
}

.player-list {
  display: flex;
  flex-direction: column;
  gap: 0.65rem;
}

.player-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 0.75rem;
}

.player-info {
  display: flex;
  flex-wrap: wrap;
  gap: 0.4rem;
  align-items: center;
}

.ai-badge,
.you-badge,
.host-badge {
  font-size: 0.72rem;
  border-radius: 999px;
  padding: 0.1rem 0.45rem;
  background: rgba(255, 255, 255, 0.06);
}

.add-ai-btn {
  align-self: flex-start;
}

.validation-banner {
  display: flex;
  gap: 0.75rem;
  align-items: flex-start;
}

.validation-banner.valid {
  border-color: rgba(61, 214, 140, 0.45);
}

.validation-banner.invalid {
  border-color: rgba(225, 29, 72, 0.45);
}

.validation-message,
.validation-issues {
  margin: 0;
}

@media (max-width: 700px) {
  .hero,
  .fields,
  .difficulty {
    grid-template-columns: 1fr;
    flex-direction: column;
  }
}
</style>
