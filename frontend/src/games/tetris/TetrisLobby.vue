<script setup lang="ts">
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
const singlePlayer = defineModel<boolean>('singlePlayer', { required: true })
const baseDropTicks = defineModel<number>('baseDropTicks', { required: true })
const soloAiDifficulties = defineModel<string[]>('soloAiDifficulties', { required: true })

const emit = defineEmits<{
  addAi: []
  remove: [id: string]
  setAiDifficulty: [playerId: string, difficulty: string]
}>()

const speedOptions = [
  { label: 'Fast', value: 14 },
  { label: 'Normal', value: 20 },
  { label: 'Slow', value: 28 },
  { label: 'Relaxed', value: 36 },
]

const difficultyOptions = [
  { label: 'Easy', value: 'easy' },
  { label: 'Normal', value: 'normal' },
  { label: 'Hard', value: 'hard' },
]

function onSinglePlayerChange(e: Event) {
  const checked = (e.target as HTMLInputElement).checked
  if (checked) soloPractice.value = false
  singlePlayer.value = checked
}

function onSoloPracticeChange(e: Event) {
  const checked = (e.target as HTMLInputElement).checked
  if (checked) singlePlayer.value = false
  soloPractice.value = checked
}

function playerAiDifficulty(player: { id: string; ai_difficulty?: string }): string {
  const map = (props.room.settings?.ai_difficulties ?? {}) as Record<string, string>
  return player.ai_difficulty ?? map[player.id] ?? 'normal'
}

function updateSoloAiDifficulty(index: number, difficulty: string) {
  const next = [...soloAiDifficulties.value]
  while (next.length < 2) next.push('normal')
  next[index] = difficulty
  soloAiDifficulties.value = next.slice(0, 2)
}
</script>

<template>
  <div class="tetris-lobby">
    <div v-if="isHost" class="settings-block card">
      <label class="checkbox-label">
        <input
          :checked="singlePlayer"
          type="checkbox"
          @change="onSinglePlayerChange"
        />
        Single player (high score)
      </label>
      <label class="checkbox-label">
        <input
          :checked="soloPractice"
          type="checkbox"
          @change="onSoloPracticeChange"
        />
        Solo practice (play against 2 AI)
      </label>
      <div class="speed-setting">
        <span class="setting-label">Starting gravity</span>
        <select v-model.number="baseDropTicks" class="speed-select">
          <option v-for="opt in speedOptions" :key="opt.value" :value="opt.value">
            {{ opt.label }}
          </option>
        </select>
      </div>
    </div>

    <div v-if="singlePlayer" class="solo-notice card">
      <p>Play alone and clear as many lines as you can. The game ends when you top out.</p>
    </div>

    <div v-else-if="soloPractice" class="solo-notice card">
      <p>Solo practice auto-adds 2 AI opponents when you start.</p>
      <div v-if="isHost" class="solo-ai-settings">
        <label v-for="slot in 2" :key="slot" class="difficulty-label">
          <span>AI {{ slot }} difficulty</span>
          <select
            class="difficulty-select"
            :value="soloAiDifficulties[slot - 1] ?? 'normal'"
            @change="updateSoloAiDifficulty(slot - 1, ($event.target as HTMLSelectElement).value)"
          >
            <option v-for="opt in difficultyOptions" :key="opt.value" :value="opt.value">
              {{ opt.label }}
            </option>
          </select>
        </label>
      </div>
    </div>

    <template v-else>
      <p v-if="isHost" class="arrange-hint">
        Need 2–4 players. Add AI to fill empty seats, or share the room link.
      </p>
    </template>

    <div
      v-if="!singlePlayer && room.players.length > 0"
      class="player-list card"
    >
      <div v-for="player in room.players" :key="player.id" class="player-row">
        <div class="player-info">
          <span class="nickname">{{ player.nickname }}</span>
          <span v-if="player.is_ai" class="ai-badge">AI</span>
          <span v-if="player.id === currentPlayerId" class="you-badge">You</span>
          <span v-if="player.id === hostPlayerId" class="host-badge">Host</span>
        </div>
        <div class="player-actions">
          <label v-if="isHost && player.is_ai" class="difficulty-label">
            <span>Difficulty</span>
            <select
              class="difficulty-select"
              :value="playerAiDifficulty(player)"
              @change="emit('setAiDifficulty', player.id, ($event.target as HTMLSelectElement).value)"
            >
              <option v-for="opt in difficultyOptions" :key="opt.value" :value="opt.value">
                {{ opt.label }}
              </option>
            </select>
          </label>
          <span v-else-if="player.is_ai" class="difficulty-readonly">
            {{ playerAiDifficulty(player) }}
          </span>
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
    </div>

    <button
      v-if="isHost && !singlePlayer"
      type="button"
      class="btn-secondary add-ai-btn"
      @click="emit('addAi')"
    >
      + Add AI player
    </button>

    <div
      v-if="!singlePlayer && !soloPractice"
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
  </div>
</template>

<style scoped>
.tetris-lobby {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.settings-block {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

.speed-setting {
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
}

.setting-label {
  font-size: 0.85rem;
  color: var(--text-muted);
}

.speed-select,
.difficulty-select {
  padding: 0.4rem 0.6rem;
  border-radius: 6px;
  border: 1px solid var(--border);
  background: var(--surface);
  color: var(--text);
}

.speed-select {
  max-width: 220px;
}

.difficulty-select {
  min-width: 6.5rem;
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
  gap: 0.75rem;
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
  min-width: 0;
}

.player-actions {
  display: flex;
  align-items: center;
  gap: 0.65rem;
  flex-shrink: 0;
}

.difficulty-label {
  display: flex;
  flex-direction: column;
  gap: 0.2rem;
  font-size: 0.75rem;
  color: var(--text-muted);
}

.difficulty-readonly {
  font-size: 0.8rem;
  text-transform: capitalize;
  color: var(--text-muted);
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

.solo-ai-settings {
  display: flex;
  flex-wrap: wrap;
  gap: 1rem;
  margin-top: 0.75rem;
}

.checkbox-label {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  cursor: pointer;
}

@media (max-width: 640px) {
  .player-row {
    flex-direction: column;
    align-items: flex-start;
  }

  .player-actions {
    width: 100%;
    justify-content: space-between;
  }
}
</style>
