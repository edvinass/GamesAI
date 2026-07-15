<script setup lang="ts">
import { computed } from 'vue'
import type { Room } from '@/types'
import { formatDuelLobbySummary } from './lobbySummary'

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
const matchFormat = defineModel<string>('matchFormat', { required: true })
const aiDifficulty = defineModel<string>('aiDifficulty', { required: true })

const emit = defineEmits<{
  addAi: []
  remove: [id: string]
}>()

const guestSummary = computed(() => formatDuelLobbySummary(props.room))

const matchFormatOptions = [
  { label: 'Best of 3', value: 'best_of_3' },
  { label: 'Best of 5', value: 'best_of_5' },
]

const difficultyOptions = [
  { label: 'Easy', value: 'easy' },
  { label: 'Medium', value: 'medium' },
  { label: 'Hard', value: 'hard' },
]

const showAiSettings = computed(
  () => soloPractice.value || props.room.players.some((p) => p.is_ai),
)
</script>

<template>
  <div class="duel-lobby">
    <div v-if="!isHost" class="guest-summary card">
      <h3>Match setup</h3>
      <ul>
        <li v-for="line in guestSummary" :key="line">{{ line }}</li>
      </ul>
    </div>

    <div v-if="isHost" class="settings-block card">
      <label class="checkbox-label">
        <input v-model="soloPractice" type="checkbox" />
        Solo practice (vs AI)
      </label>

      <div class="setting-row">
        <span class="setting-label">Match length</span>
        <select v-model="matchFormat" class="setting-select">
          <option v-for="opt in matchFormatOptions" :key="opt.value" :value="opt.value">
            {{ opt.label }}
          </option>
        </select>
      </div>

      <div v-if="showAiSettings" class="setting-row">
        <span class="setting-label">AI difficulty</span>
        <select v-model="aiDifficulty" class="setting-select">
          <option v-for="opt in difficultyOptions" :key="opt.value" :value="opt.value">
            {{ opt.label }}
          </option>
        </select>
      </div>
    </div>

    <div v-if="soloPractice" class="solo-notice card">
      <p>Practice against one AI opponent. Classic rules — HP, cover, power-ups, charge shots.</p>
    </div>

    <template v-else>
      <p v-if="isHost" class="arrange-hint">
        Need 2 players. Share the room link or add an AI opponent.
      </p>

      <div class="player-list card">
        <div v-for="player in room.players" :key="player.id" class="player-row">
          <div class="player-info">
            <span class="nickname">{{ player.nickname }}</span>
            <span v-if="player.is_ai" class="badge">AI</span>
            <span v-if="player.id === currentPlayerId" class="badge you">You</span>
            <span v-if="player.id === hostPlayerId" class="badge">Host</span>
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
        v-if="isHost && room.players.length < 2"
        type="button"
        class="btn-secondary add-ai-btn"
        @click="emit('addAi')"
      >
        + Add AI opponent
      </button>

      <div
        class="validation-banner card"
        :class="{ valid: validationValid, invalid: !validationValid }"
      >
        <span class="validation-icon">{{ validationValid ? '✓' : '!' }}</span>
        <div>
          <p class="validation-message">{{ validationMessage }}</p>
          <ul v-if="!validationValid && validationIssues.length > 1" class="validation-issues">
            <li v-for="issue in validationIssues" :key="issue">{{ issue }}</li>
          </ul>
        </div>
      </div>
    </template>
  </div>
</template>

<style scoped>
.duel-lobby {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.guest-summary h3 {
  margin: 0 0 0.35rem;
  font-size: 1rem;
}

.guest-summary ul {
  margin: 0;
  padding-left: 1.1rem;
  font-size: 0.9rem;
}

.settings-block {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

.setting-row {
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
}

.setting-label {
  font-size: 0.85rem;
  color: var(--text-muted);
}

.setting-select {
  max-width: 100%;
  padding: 0.4rem 0.6rem;
  border-radius: 6px;
  border: 1px solid var(--border);
  background: var(--surface);
  color: var(--text);
}

.checkbox-label {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  cursor: pointer;
}

.arrange-hint {
  font-size: 0.9rem;
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
  padding: 0.5rem 0;
  border-bottom: 1px solid var(--border);
}

.player-row:last-child {
  border-bottom: none;
}

.player-info {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.nickname {
  font-weight: 600;
}

.badge {
  font-size: 0.7rem;
  padding: 0.15rem 0.4rem;
  border-radius: 4px;
  background: var(--surface-elevated);
}

.badge.you {
  background: var(--accent-muted);
  color: var(--accent);
}

.remove-btn {
  font-size: 0.8rem;
  padding: 0.3rem 0.6rem;
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
  border-color: var(--success);
}

.validation-banner.invalid {
  border-color: var(--warning, #e6a700);
}

.validation-icon {
  font-size: 1.25rem;
  font-weight: 700;
}

.validation-issues {
  margin-top: 0.35rem;
  padding-left: 1.25rem;
  font-size: 0.85rem;
  color: var(--text-muted);
}

.solo-notice {
  font-size: 0.9rem;
  color: var(--text-muted);
}
</style>
