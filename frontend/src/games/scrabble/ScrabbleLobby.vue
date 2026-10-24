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

const emit = defineEmits<{
  addAi: []
  remove: [id: string]
}>()

const difficultyOptions = [
  { value: 'easy', label: 'Easy', detail: 'Short words' },
  { value: 'medium', label: 'Medium', detail: 'Solid scores' },
  { value: 'hard', label: 'Hard', detail: 'Best score' },
]
</script>

<template>
  <div class="scrabble-lobby">
    <section class="hero card">
      <div class="tiles" aria-hidden="true">
        <span>S</span>
        <span>C</span>
        <span>R</span>
        <span>A</span>
      </div>
      <div>
        <p class="eyebrow">Classic</p>
        <h2>Build across the star.</h2>
        <p class="lede">
          Draw seven tiles, lay down a word, and chase the colored squares. Two to four players can share a board, or you can play the AI.
        </p>
      </div>
    </section>

    <section v-if="isHost" class="settings card">
      <label class="check">
        <input v-model="soloPractice" type="checkbox" />
        Solo play against the AI
      </label>
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
      Solo play adds an AI opponent when you start. You go first.
    </p>

    <template v-else>
      <p v-if="isHost" class="hint">Need 2 to 4 players. Add an AI seat or share the room link.</p>
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
        v-if="isHost && room.players.length < 4"
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
.scrabble-lobby {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.hero {
  display: grid;
  grid-template-columns: 148px 1fr;
  gap: 1.25rem;
  align-items: center;
  background:
    radial-gradient(circle at 12% 20%, rgba(212, 162, 74, 0.18), transparent 42%),
    var(--surface);
}

.tiles {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 0.4rem;
  justify-self: center;
}

.tiles span {
  width: 58px;
  height: 58px;
  display: grid;
  place-items: center;
  border-radius: 6px;
  background: linear-gradient(180deg, #fff8e8, #f0d7a2);
  color: #3a2a16;
  font-family: Georgia, 'Iowan Old Style', serif;
  font-size: 1.7rem;
  font-weight: 700;
  box-shadow: 0 8px 16px rgba(0, 0, 0, 0.25);
}

.tiles span:nth-child(2) {
  transform: translateY(8px);
}

.tiles span:nth-child(3) {
  transform: translateY(-6px);
}

.eyebrow {
  color: #d4a24a;
  font-size: 0.75rem;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  margin-bottom: 0.35rem;
}

.lede {
  color: var(--text-muted);
  margin-top: 0.4rem;
  max-width: 42rem;
}

.settings {
  display: flex;
  flex-direction: column;
  gap: 0.9rem;
}

.check {
  display: flex;
  align-items: center;
  gap: 0.55rem;
}

.difficulty {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 0.5rem;
}

.difficulty button {
  text-align: left;
  border: 1px solid var(--border);
  background: transparent;
  color: var(--text);
  border-radius: 10px;
  padding: 0.65rem 0.75rem;
  cursor: pointer;
}

.difficulty button span {
  display: block;
  color: var(--text-muted);
  font-size: 0.8rem;
  margin-top: 0.15rem;
}

.difficulty button.active {
  border-color: #d4a24a;
  background: rgba(212, 162, 74, 0.12);
}

.note,
.hint {
  color: var(--text-muted);
}

.player-list {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
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
  background: var(--surface-hover);
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
  border-color: rgba(255, 92, 108, 0.45);
}

.validation-issues {
  margin: 0.35rem 0 0;
  padding-left: 1.1rem;
  color: var(--text-muted);
}

@media (max-width: 640px) {
  .hero {
    grid-template-columns: 1fr;
  }

  .difficulty {
    grid-template-columns: 1fr;
  }
}
</style>
