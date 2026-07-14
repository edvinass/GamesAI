<script setup lang="ts">
import { computed } from 'vue'
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
const tickMs = defineModel<number>('tickMs', { required: true })
const matchFormat = defineModel<string>('matchFormat', { required: true })
const mutator = defineModel<string>('mutator', { required: true })
const aiDifficulty = defineModel<string>('aiDifficulty', { required: true })
const obstacleCount = defineModel<number>('obstacleCount', { required: true })

const emit = defineEmits<{
  addAi: []
  remove: [id: string]
}>()

const speedOptions = [
  { label: 'Fast', value: 50 },
  { label: 'Normal', value: 75 },
  { label: 'Slow', value: 100 },
  { label: 'Relaxed', value: 150 },
]

const matchFormatOptions = [
  { label: 'Quick duel (1 hit)', value: 'quick_duel' },
  { label: 'Best of 3', value: 'best_of_3' },
  { label: 'Best of 5', value: 'best_of_5' },
]

const mutatorOptions = [
  { label: 'Classic', value: 'classic', hint: 'Cover, HP, power-ups' },
  { label: 'Chaos', value: 'chaos', hint: 'Fast bullets, rapid fire' },
  { label: 'Sniper', value: 'sniper', hint: 'One shot, long cooldown' },
  { label: 'Bounce House', value: 'bounce_house', hint: 'Ricochet + obstacles' },
  { label: 'Fog', value: 'fog', hint: 'Imprecise enemy position' },
]

const difficultyOptions = [
  { label: 'Easy', value: 'easy', hint: 'Slower reactions, more mistakes' },
  { label: 'Medium', value: 'medium', hint: 'Balanced opponent' },
  { label: 'Hard', value: 'hard', hint: 'Fast dodges and charge shots' },
]

const obstacleOptions = [0, 1, 2, 3, 4, 5, 6]

const showObstacleSetting = computed(
  () => matchFormat.value !== 'quick_duel' && mutator.value !== 'bounce_house',
)
</script>

<template>
  <div class="duel-lobby">
    <div v-if="isHost" class="settings-block card">
      <label class="checkbox-label">
        <input v-model="soloPractice" type="checkbox" />
        Solo practice (play against AI)
      </label>

      <div class="setting-row">
        <span class="setting-label">Match format</span>
        <select v-model="matchFormat" class="setting-select">
          <option v-for="opt in matchFormatOptions" :key="opt.value" :value="opt.value">
            {{ opt.label }}
          </option>
        </select>
      </div>

      <div class="setting-row">
        <span class="setting-label">Mutator</span>
        <select v-model="mutator" class="setting-select">
          <option v-for="opt in mutatorOptions" :key="opt.value" :value="opt.value">
            {{ opt.label }} — {{ opt.hint }}
          </option>
        </select>
      </div>

      <div class="setting-row">
        <span class="setting-label">Game speed</span>
        <select v-model.number="tickMs" class="setting-select">
          <option v-for="opt in speedOptions" :key="opt.value" :value="opt.value">
            {{ opt.label }} ({{ opt.value }}ms)
          </option>
        </select>
      </div>

      <div v-if="soloPractice || room.players.some((p) => p.is_ai)" class="setting-row">
        <span class="setting-label">AI difficulty</span>
        <select v-model="aiDifficulty" class="setting-select">
          <option v-for="opt in difficultyOptions" :key="opt.value" :value="opt.value">
            {{ opt.label }} — {{ opt.hint }}
          </option>
        </select>
      </div>

      <div v-if="showObstacleSetting" class="setting-row">
        <span class="setting-label">Cover blocks</span>
        <select v-model.number="obstacleCount" class="setting-select">
          <option v-for="count in obstacleOptions" :key="count" :value="count">
            {{ count === 0 ? 'None' : count }}
          </option>
        </select>
      </div>
    </div>

    <div v-if="soloPractice" class="solo-notice card">
      <p>
        Solo practice adds one AI opponent. Duel across rounds with HP, cover, power-ups,
        shrinking arena, and charge shots (in match modes).
      </p>
    </div>

    <template v-else>
      <p v-if="isHost" class="arrange-hint">
        Need exactly 2 players. Share the room link or add one AI opponent.
      </p>

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

.ai-badge,
.you-badge,
.host-badge {
  font-size: 0.7rem;
  padding: 0.15rem 0.4rem;
  border-radius: 4px;
  background: var(--surface-elevated);
}

.you-badge {
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

.checkbox-label {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  cursor: pointer;
}
</style>
