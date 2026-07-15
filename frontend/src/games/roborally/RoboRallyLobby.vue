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
const mapId = defineModel<string>('mapId', { required: true })
const registerSize = defineModel<number>('registerSize', { required: true })
const aiDifficulty = defineModel<string>('aiDifficulty', { required: true })

const emit = defineEmits<{
  addAi: []
  remove: [id: string]
}>()

const mapOptions = [
  { id: 'factory_floor', label: 'Factory Floor', detail: 'Winding course with obstacles' },
  { id: 'open_grid', label: 'Open Grid', detail: 'Simpler layout for quick races' },
]

const registerOptions = [
  { value: 3, label: '3 cards' },
  { value: 4, label: '4 cards' },
  { value: 5, label: '5 cards' },
]

const difficultyOptions = [
  { value: 'easy', label: 'Easy' },
  { value: 'medium', label: 'Medium' },
  { value: 'hard', label: 'Hard' },
]

const maxPlayers = 4
</script>

<template>
  <div class="roborally-lobby">
    <div v-if="isHost" class="settings-block card">
      <label class="checkbox-label">
        <input v-model="soloPractice" type="checkbox" />
        Solo practice (race against AI)
      </label>

      <div class="setting-row">
        <span class="setting-label">Map</span>
        <select v-model="mapId" class="setting-select">
          <option v-for="opt in mapOptions" :key="opt.id" :value="opt.id">
            {{ opt.label }} — {{ opt.detail }}
          </option>
        </select>
      </div>

      <div class="setting-row">
        <span class="setting-label">Register size</span>
        <select v-model.number="registerSize" class="setting-select">
          <option v-for="opt in registerOptions" :key="opt.value" :value="opt.value">
            {{ opt.label }}
          </option>
        </select>
      </div>

      <div v-if="soloPractice" class="setting-row">
        <span class="setting-label">AI difficulty</span>
        <select v-model="aiDifficulty" class="setting-select">
          <option v-for="opt in difficultyOptions" :key="opt.value" :value="opt.value">
            {{ opt.label }}
          </option>
        </select>
      </div>
    </div>

    <div v-if="soloPractice" class="solo-notice card">
      <p>Solo practice adds one AI racer when you start. You'll program your robot each round until someone hits all checkpoints.</p>
    </div>

    <template v-else>
      <p v-if="isHost" class="arrange-hint">
        Need 2–{{ maxPlayers }} players. Add AI to fill empty seats, or share the room link.
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
        v-if="isHost && room.players.length < maxPlayers"
        type="button"
        class="btn-secondary add-ai-btn"
        @click="emit('addAi')"
      >
        + Add AI racer
      </button>
    </template>

    <div
      class="validation-banner card"
      :class="{ valid: validationValid, invalid: !validationValid }"
    >
      <p>{{ validationMessage }}</p>
      <ul v-if="validationIssues.length">
        <li v-for="issue in validationIssues" :key="issue">{{ issue }}</li>
      </ul>
    </div>
  </div>
</template>

<style scoped>
.roborally-lobby {
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
  padding: 0.5rem 0.65rem;
  border-radius: 8px;
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

.solo-notice p {
  margin: 0;
  color: var(--text-muted);
  font-size: 0.9rem;
}

.arrange-hint {
  margin: 0;
  color: var(--text-muted);
  font-size: 0.9rem;
}

.player-list {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.player-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.75rem;
}

.player-info {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  flex-wrap: wrap;
}

.nickname {
  font-weight: 600;
}

.ai-badge,
.you-badge,
.host-badge {
  font-size: 0.75rem;
  padding: 0.15rem 0.45rem;
  border-radius: 999px;
  background: var(--surface-elevated);
}

.add-ai-btn {
  align-self: flex-start;
}

.validation-banner.valid {
  border-color: rgba(34, 197, 94, 0.4);
}

.validation-banner.invalid {
  border-color: rgba(239, 68, 68, 0.4);
}

.validation-banner p {
  margin: 0;
}

.validation-banner ul {
  margin: 0.5rem 0 0;
  padding-left: 1.2rem;
}
</style>
