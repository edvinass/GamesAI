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
const singlePlayer = defineModel<boolean>('singlePlayer', { required: true })
const baseDropTicks = defineModel<number>('baseDropTicks', { required: true })
const soloAiDifficulties = defineModel<string[]>('soloAiDifficulties', { required: true })

const emit = defineEmits<{
  addAi: []
  remove: [id: string]
  setAiDifficulty: [playerId: string, difficulty: string]
}>()

type GameMode = 'multiplayer' | 'solo_practice' | 'single_player'

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

const gameModes: { id: GameMode; label: string; description: string; icon: string }[] = [
  {
    id: 'multiplayer',
    label: 'Multiplayer',
    description: '2–4 players, last board standing wins',
    icon: '👥',
  },
  {
    id: 'solo_practice',
    label: 'Solo practice',
    description: 'You vs 3 AI opponents',
    icon: '🤖',
  },
  {
    id: 'single_player',
    label: 'Single player',
    description: 'High score — clear as many lines as you can',
    icon: '🏆',
  },
]

const gameMode = computed<GameMode>({
  get() {
    if (singlePlayer.value) return 'single_player'
    if (soloPractice.value) return 'solo_practice'
    return 'multiplayer'
  },
  set(mode) {
    singlePlayer.value = mode === 'single_player'
    soloPractice.value = mode === 'solo_practice'
  },
})

const activeMode = computed(() => gameModes.find((mode) => mode.id === gameMode.value) ?? gameModes[0])

function playerAiDifficulty(player: { id: string; ai_difficulty?: string }): string {
  const map = (props.room.settings?.ai_difficulties ?? {}) as Record<string, string>
  return player.ai_difficulty ?? map[player.id] ?? 'normal'
}

const maxPlayers = computed(() => Number(props.room.settings?.max_players ?? 4))
const maxAiOpponents = computed(() => Math.max(0, maxPlayers.value - 1))
const playerCount = computed(() => props.room.players.length)
const canAddAi = computed(
  () => props.isHost && gameMode.value === 'multiplayer' && playerCount.value < maxPlayers.value,
)

function updateSoloAiDifficulty(index: number, difficulty: string) {
  const next = [...soloAiDifficulties.value]
  while (next.length < maxAiOpponents.value) next.push('normal')
  next[index] = difficulty
  soloAiDifficulties.value = next.slice(0, maxAiOpponents.value)
}

function difficultyLabel(value: string): string {
  return difficultyOptions.find((opt) => opt.value === value)?.label ?? value
}
</script>

<template>
  <div class="tetris-lobby">
    <section v-if="isHost" class="settings-card card">
      <h2 class="section-title">Game mode</h2>
      <div class="mode-selector" role="radiogroup" aria-label="Game mode">
        <button
          v-for="mode in gameModes"
          :key="mode.id"
          type="button"
          class="mode-option"
          :class="{ active: gameMode === mode.id }"
          role="radio"
          :aria-checked="gameMode === mode.id"
          @click="gameMode = mode.id"
        >
          <span class="mode-icon" aria-hidden="true">{{ mode.icon }}</span>
          <span class="mode-copy">
            <span class="mode-label">{{ mode.label }}</span>
            <span class="mode-desc">{{ mode.description }}</span>
          </span>
        </button>
      </div>

      <div class="speed-setting">
        <label class="setting-label" for="tetris-gravity">Starting gravity</label>
        <select id="tetris-gravity" v-model.number="baseDropTicks" class="speed-select">
          <option v-for="opt in speedOptions" :key="opt.value" :value="opt.value">
            {{ opt.label }}
          </option>
        </select>
      </div>
    </section>

    <section v-else class="mode-summary card">
      <span class="mode-icon" aria-hidden="true">{{ activeMode.icon }}</span>
      <div>
        <p class="mode-summary-label">{{ activeMode.label }}</p>
        <p class="mode-summary-desc">{{ activeMode.description }}</p>
      </div>
    </section>

    <section v-if="gameMode === 'single_player'" class="solo-notice card">
      <p>Play alone and clear as many lines as you can. The game ends when you top out.</p>
    </section>

    <section v-else-if="gameMode === 'solo_practice'" class="solo-notice card">
      <p>Solo practice auto-adds 3 AI opponents when you start (4-player match).</p>
      <div v-if="isHost" class="solo-ai-settings">
        <label v-for="slot in maxAiOpponents" :key="slot" class="ai-slot">
          <span class="ai-slot-label">AI {{ slot }}</span>
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
    </section>

    <template v-else>
      <p v-if="isHost" class="arrange-hint">
        Need 2–4 players. Add AI to fill empty seats, or share the room link above.
      </p>

      <section class="players-card card">
        <div class="players-header">
          <h2 class="section-title">Players</h2>
          <span class="player-count">{{ playerCount }} / {{ maxPlayers }}</span>
        </div>

        <ul v-if="room.players.length > 0" class="player-list">
          <li v-for="player in room.players" :key="player.id" class="player-row">
            <div class="player-info">
              <span class="nickname">{{ player.nickname }}</span>
              <span v-if="player.is_ai" class="badge ai-badge">AI</span>
              <span v-if="player.id === currentPlayerId" class="badge you-badge">You</span>
              <span v-if="player.id === hostPlayerId" class="badge host-badge">Host</span>
            </div>
            <div class="player-actions">
              <label v-if="isHost && player.is_ai" class="inline-select">
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
                {{ difficultyLabel(playerAiDifficulty(player)) }}
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
          </li>
        </ul>
        <p v-else class="empty-players">Waiting for players to join…</p>

        <button
          v-if="canAddAi"
          type="button"
          class="btn-secondary add-ai-btn"
          @click="emit('addAi')"
        >
          + Add AI player
        </button>
        <p v-else-if="isHost && playerCount >= maxPlayers" class="room-full-hint">
          Room is full (max {{ maxPlayers }} players).
        </p>
      </section>

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
.tetris-lobby {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.section-title {
  font-size: 0.7rem;
  font-weight: 600;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  color: var(--text-muted);
  margin: 0;
}

.settings-card {
  display: flex;
  flex-direction: column;
  gap: 1.25rem;
}

.mode-selector {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 0.65rem;
}

.mode-option {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 0.5rem;
  padding: 0.85rem 0.9rem;
  border-radius: 10px;
  border: 1px solid var(--border);
  background: var(--surface-hover);
  color: var(--text);
  text-align: left;
  cursor: pointer;
  transition:
    border-color 0.2s,
    background 0.2s,
    transform 0.2s var(--ease-smooth),
    box-shadow 0.2s;
}

.mode-option:hover {
  border-color: rgba(91, 156, 255, 0.35);
  transform: translateY(-1px);
}

.mode-option.active {
  border-color: var(--accent);
  background: rgba(91, 156, 255, 0.1);
  box-shadow: 0 0 0 1px rgba(91, 156, 255, 0.15);
}

.mode-icon {
  font-size: 1.35rem;
  line-height: 1;
}

.mode-copy {
  display: flex;
  flex-direction: column;
  gap: 0.2rem;
  min-width: 0;
}

.mode-label {
  font-size: 0.9rem;
  font-weight: 600;
}

.mode-desc {
  font-size: 0.75rem;
  line-height: 1.35;
  color: var(--text-muted);
}

.mode-summary {
  display: flex;
  align-items: center;
  gap: 0.85rem;
}

.mode-summary-label {
  margin: 0;
  font-weight: 600;
}

.mode-summary-desc {
  margin: 0.15rem 0 0;
  font-size: 0.85rem;
  color: var(--text-muted);
}

.speed-setting {
  display: flex;
  flex-direction: column;
  gap: 0.4rem;
  padding-top: 0.25rem;
  border-top: 1px solid var(--border);
}

.setting-label {
  font-size: 0.7rem;
  font-weight: 600;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  color: var(--text-muted);
}

.speed-select,
.difficulty-select {
  padding: 0.45rem 0.65rem;
  border-radius: 8px;
  border: 1px solid var(--border);
  background: var(--surface);
  color: var(--text);
  font-size: 0.9rem;
}

.speed-select {
  max-width: 220px;
}

.difficulty-select {
  min-width: 6.5rem;
}

.solo-notice {
  font-size: 0.9rem;
  color: var(--text-muted);
  border-left: 3px solid var(--accent);
}

.solo-notice p {
  margin: 0;
  line-height: 1.5;
}

.solo-ai-settings {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
  gap: 0.75rem;
  margin-top: 1rem;
  padding-top: 1rem;
  border-top: 1px solid var(--border);
}

.ai-slot {
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
}

.ai-slot-label {
  font-size: 0.75rem;
  font-weight: 600;
  color: var(--text-muted);
}

.arrange-hint {
  margin: 0;
  font-size: 0.85rem;
  color: var(--text-muted);
  line-height: 1.5;
}

.players-card {
  display: flex;
  flex-direction: column;
  gap: 0.85rem;
}

.players-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.75rem;
}

.player-count {
  font-size: 0.8rem;
  font-variant-numeric: tabular-nums;
  color: var(--text-muted);
  padding: 0.15rem 0.55rem;
  border-radius: 999px;
  background: var(--surface-hover);
  border: 1px solid var(--border);
}

.player-list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
}

.player-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 0.75rem;
  padding: 0.65rem 0;
  border-bottom: 1px solid var(--border);
}

.player-row:last-child {
  border-bottom: none;
}

.player-info {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 0.45rem;
  min-width: 0;
}

.player-actions {
  display: flex;
  align-items: center;
  gap: 0.65rem;
  flex-shrink: 0;
}

.inline-select {
  display: flex;
  align-items: center;
  gap: 0.45rem;
  font-size: 0.8rem;
  color: var(--text-muted);
}

.difficulty-readonly {
  font-size: 0.8rem;
  color: var(--text-muted);
}

.nickname {
  font-weight: 600;
}

.badge {
  font-size: 0.68rem;
  padding: 0.12rem 0.4rem;
  border-radius: 999px;
  background: var(--surface-elevated);
  text-transform: uppercase;
  letter-spacing: 0.03em;
}

.you-badge {
  background: var(--accent-muted);
  color: var(--accent);
}

.empty-players,
.room-full-hint {
  margin: 0;
  font-size: 0.85rem;
  color: var(--text-muted);
}

.remove-btn {
  font-size: 0.8rem;
  padding: 0.35rem 0.65rem;
}

.add-ai-btn {
  align-self: flex-start;
}

.validation-banner {
  display: flex;
  gap: 0.75rem;
  align-items: flex-start;
  padding: 1rem 1.25rem;
  transition: border-color 0.3s, background 0.3s;
}

.validation-banner.valid {
  border-color: rgba(61, 214, 140, 0.4);
  background: rgba(61, 214, 140, 0.08);
}

.validation-banner.invalid {
  border-color: rgba(255, 92, 108, 0.35);
  background: rgba(255, 92, 108, 0.08);
}

.validation-icon {
  width: 1.75rem;
  height: 1.75rem;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: 700;
  font-size: 0.85rem;
  flex-shrink: 0;
}

.validation-banner.valid .validation-icon {
  background: rgba(61, 214, 140, 0.2);
  color: var(--success);
}

.validation-banner.invalid .validation-icon {
  background: rgba(255, 92, 108, 0.2);
  color: var(--error);
}

.validation-message {
  margin: 0;
  font-size: 0.9rem;
}

.validation-issues {
  margin: 0.5rem 0 0;
  padding-left: 1.1rem;
  font-size: 0.85rem;
  color: var(--text-muted);
}

.validation-issues li {
  margin-bottom: 0.2rem;
}

@media (max-width: 768px) {
  .mode-selector {
    grid-template-columns: 1fr;
  }
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
