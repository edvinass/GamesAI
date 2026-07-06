<script setup lang="ts">
import { computed } from 'vue'
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
const startingChips = defineModel<number>('startingChips', { required: true })
const smallBlind = defineModel<number>('smallBlind', { required: true })
const bigBlind = defineModel<number>('bigBlind', { required: true })

const emit = defineEmits<{
  addAi: []
  remove: [id: string]
}>()

const maxPlayers = computed(() => Number(props.room.settings?.max_players ?? 6))
</script>

<template>
  <div class="poker-lobby">
    <div v-if="isHost" class="settings-block card">
      <h3>Table settings</h3>
      <label class="field">
        Starting chips
        <input v-model.number="startingChips" type="number" min="100" step="100" />
      </label>
      <label class="field">
        Small blind
        <input v-model.number="smallBlind" type="number" min="1" />
      </label>
      <label class="field">
        Big blind
        <input v-model.number="bigBlind" type="number" min="2" />
      </label>
      <label class="checkbox-label">
        <input v-model="soloPractice" type="checkbox" />
        Solo practice (play against 2 AI)
      </label>
    </div>

    <div v-if="soloPractice" class="solo-notice card">
      <p>Solo practice auto-adds 2 AI players when you start. You'll play a 3-handed game.</p>
    </div>

    <template v-else>
      <p v-if="isHost" class="arrange-hint">
        Need 2–{{ maxPlayers }} players. Add AI to fill seats, or share the room link.
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
        + Add AI player
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
.poker-lobby {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.settings-block h3 {
  margin: 0 0 0.75rem;
  font-size: 1rem;
}

.field {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
  margin-bottom: 0.75rem;
  font-size: 0.9rem;
}

.field input {
  padding: 0.4rem 0.6rem;
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
