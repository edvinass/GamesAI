<script setup lang="ts">
import { computed } from 'vue'
import type { Room } from '@/types'

interface MapOption {
  id: string
  name: string
  description: string
  difficulty: string
  width: number
  height: number
}

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
const tickMs = defineModel<number>('tickMs', { required: true })
const mapId = defineModel<string>('mapId', { required: true })

const emit = defineEmits<{
  addAi: []
  remove: [id: string]
}>()

const speedOptions = [
  { label: 'Blitz', value: 90 },
  { label: 'Fast', value: 120 },
  { label: 'Normal', value: 150 },
  { label: 'Slow', value: 200 },
  { label: 'Relaxed', value: 260 },
]

const FALLBACK_MAPS: MapOption[] = [
  {
    id: 'classic',
    name: 'Classic',
    description: 'Standard pillar grid — balanced and familiar.',
    difficulty: 'standard',
    width: 15,
    height: 13,
  },
]

const mapOptions = computed<MapOption[]>(() => {
  const raw = props.room.settings?.available_maps
  if (!Array.isArray(raw) || raw.length === 0) return FALLBACK_MAPS
  return raw
    .filter((m): m is Record<string, unknown> => !!m && typeof m === 'object')
    .map((m) => ({
      id: String(m.id ?? ''),
      name: String(m.name ?? m.id ?? 'Map'),
      description: String(m.description ?? ''),
      difficulty: String(m.difficulty ?? 'standard'),
      width: Number(m.width ?? 15),
      height: Number(m.height ?? 13),
    }))
    .filter((m) => m.id)
})

const selectedMap = computed(
  () => mapOptions.value.find((m) => m.id === mapId.value) ?? mapOptions.value[0] ?? null,
)

const difficultyClass = (difficulty: string) => {
  if (difficulty === 'brutal') return 'diff-brutal'
  if (difficulty === 'hard') return 'diff-hard'
  return 'diff-standard'
}
</script>

<template>
  <div class="bomberman-lobby">
    <div v-if="isHost" class="settings-block card">
      <label class="checkbox-label">
        <input v-model="soloPractice" type="checkbox" />
        Solo practice (play against 2 AI)
      </label>
      <div class="speed-setting">
        <span class="setting-label">Game speed</span>
        <select v-model.number="tickMs" class="speed-select">
          <option v-for="opt in speedOptions" :key="opt.value" :value="opt.value">
            {{ opt.label }} ({{ opt.value }}ms)
          </option>
        </select>
      </div>
    </div>

    <div class="map-block card">
      <div class="map-header">
        <span class="setting-label">Arena</span>
        <span v-if="selectedMap" class="map-size">
          {{ selectedMap.width }}×{{ selectedMap.height }}
        </span>
      </div>

      <div class="map-grid">
        <button
          v-for="m in mapOptions"
          :key="m.id"
          type="button"
          class="map-card"
          :class="{ selected: m.id === mapId, disabled: !isHost }"
          :disabled="!isHost"
          @click="mapId = m.id"
        >
          <div class="map-card-top">
            <span class="map-name">{{ m.name }}</span>
            <span class="diff-badge" :class="difficultyClass(m.difficulty)">
              {{ m.difficulty }}
            </span>
          </div>
          <p class="map-desc">{{ m.description }}</p>
        </button>
      </div>
    </div>

    <div v-if="soloPractice" class="solo-notice card">
      <p>Solo practice auto-adds 2 AI bombers when you start. Clear the arena and be the last one standing.</p>
    </div>

    <template v-else>
      <p v-if="isHost" class="arrange-hint">
        Need 2–8 players. Add AI to fill empty seats, or share the room link.
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

      <button v-if="isHost" type="button" class="btn-secondary add-ai-btn" @click="emit('addAi')">
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
.bomberman-lobby {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.settings-block,
.map-block {
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

.speed-select {
  max-width: 220px;
  padding: 0.4rem 0.6rem;
  border-radius: 6px;
  border: 1px solid var(--border);
  background: var(--surface);
  color: var(--text);
}

.map-header {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 0.75rem;
}

.map-size {
  font-size: 0.75rem;
  color: var(--text-muted);
}

.map-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(160px, 1fr));
  gap: 0.55rem;
}

.map-card {
  text-align: left;
  padding: 0.7rem 0.75rem;
  border-radius: 10px;
  border: 1px solid rgba(249, 115, 22, 0.18);
  background: rgba(20, 16, 12, 0.55);
  color: var(--text);
  cursor: pointer;
  transition:
    border-color 0.15s ease,
    background 0.15s ease,
    transform 0.15s ease;
}

.map-card:hover:not(:disabled) {
  border-color: rgba(249, 115, 22, 0.45);
  transform: translateY(-1px);
}

.map-card.selected {
  border-color: rgba(249, 115, 22, 0.75);
  background: rgba(249, 115, 22, 0.12);
  box-shadow: 0 0 0 1px rgba(249, 115, 22, 0.25);
}

.map-card.disabled {
  cursor: default;
  opacity: 0.9;
}

.map-card-top {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.4rem;
  margin-bottom: 0.35rem;
}

.map-name {
  font-weight: 700;
  font-size: 0.9rem;
}

.diff-badge {
  font-size: 0.65rem;
  font-weight: 700;
  letter-spacing: 0.04em;
  text-transform: uppercase;
  padding: 0.12rem 0.35rem;
  border-radius: 999px;
}

.diff-standard {
  background: rgba(56, 189, 248, 0.15);
  color: #7dd3fc;
}

.diff-hard {
  background: rgba(249, 115, 22, 0.18);
  color: #fdba74;
}

.diff-brutal {
  background: rgba(239, 68, 68, 0.18);
  color: #fca5a5;
}

.map-desc {
  margin: 0;
  font-size: 0.75rem;
  line-height: 1.35;
  color: var(--text-muted);
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
