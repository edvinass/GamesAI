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
const aiDifficulty = defineModel<string>('aiDifficulty', { required: true })
const soloAiDifficulties = defineModel<string[]>('soloAiDifficulties', { required: true })
const showCardsOnFold = defineModel<boolean>('showCardsOnFold', { required: true })

const emit = defineEmits<{
  addAi: []
  remove: [id: string]
  setAiDifficulty: [playerId: string, difficulty: string]
}>()

type GameMode = 'multiplayer' | 'solo_practice'

const gameModes: { id: GameMode; label: string; description: string; icon: string }[] = [
  {
    id: 'multiplayer',
    label: 'Multiplayer',
    description: '2–6 players at the table',
    icon: '👥',
  },
  {
    id: 'solo_practice',
    label: 'Solo practice',
    description: 'You vs 2 AI opponents',
    icon: '🤖',
  },
]

const stakePresets = [
  { id: 'casual', label: 'Casual', chips: 1000, sb: 5, bb: 10 },
  { id: 'standard', label: 'Standard', chips: 2000, sb: 10, bb: 20 },
  { id: 'high', label: 'High stakes', chips: 5000, sb: 25, bb: 50 },
] as const

const difficultyOptions = [
  {
    value: 'easy',
    label: 'Easy',
    detail: 'Loose & leaky',
    hint: 'Good for learning. Bots call too much, bluff often, and make frequent mistakes.',
  },
  {
    value: 'medium',
    label: 'Medium',
    detail: 'Solid & balanced',
    hint: 'A fair match. Bots bet good hands, fold weak ones, and use pot odds to decide.',
  },
  {
    value: 'hard',
    label: 'Hard',
    detail: 'Tight & adaptive',
    hint: 'Tough opponent. Bots pick strong lines, size bets well, and adjust to how you play.',
  },
] as const

const maxPlayers = computed(() => Number(props.room.settings?.max_players ?? 6))
const playerCount = computed(() => props.room.players.length)
const canAddAi = computed(
  () => props.isHost && !soloPractice.value && playerCount.value < maxPlayers.value,
)

const gameMode = computed<GameMode>({
  get: () => (soloPractice.value ? 'solo_practice' : 'multiplayer'),
  set: (mode) => {
    soloPractice.value = mode === 'solo_practice'
  },
})

const activeMode = computed(() => gameModes.find((mode) => mode.id === gameMode.value) ?? gameModes[0])

const activeDifficulty = computed(
  () => difficultyOptions.find((opt) => opt.value === aiDifficulty.value) ?? difficultyOptions[1],
)

function playerAiDifficulty(player: { id: string; ai_difficulty?: string }): string {
  const map = (props.room.settings?.ai_difficulties ?? {}) as Record<string, string>
  return player.ai_difficulty ?? map[player.id] ?? aiDifficulty.value
}

function difficultyLabel(value: string): string {
  return difficultyOptions.find((opt) => opt.value === value)?.label ?? value
}

function updateSoloAiDifficulty(index: number, difficulty: string) {
  const next = [...soloAiDifficulties.value]
  while (next.length < 2) next.push('medium')
  next[index] = difficulty
  soloAiDifficulties.value = next.slice(0, 2)
}

const activePresetId = computed(() => {
  const match = stakePresets.find(
    (preset) =>
      preset.chips === startingChips.value &&
      preset.sb === smallBlind.value &&
      preset.bb === bigBlind.value,
  )
  return match?.id ?? 'custom'
})

const bbDepth = computed(() => {
  if (!bigBlind.value) return 0
  return Math.round(startingChips.value / bigBlind.value)
})

const seatSlots = computed(() => {
  const total = maxPlayers.value
  const players = props.room.players
  return Array.from({ length: total }, (_, index) => {
    const player = players[index] ?? null
    const angle = (index / total) * 2 * Math.PI - Math.PI / 2
    return {
      index,
      player,
      style: {
        left: `${50 + 42 * Math.cos(angle)}%`,
        top: `${50 + 36 * Math.sin(angle)}%`,
      },
    }
  })
})

function applyPreset(preset: (typeof stakePresets)[number]) {
  startingChips.value = preset.chips
  smallBlind.value = preset.sb
  bigBlind.value = preset.bb
}

function seatInitial(nickname: string): string {
  return nickname.trim().charAt(0).toUpperCase() || '?'
}
</script>

<template>
  <div class="poker-lobby">
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

      <div class="stakes-section">
        <h2 class="section-title">Table stakes</h2>
        <div class="preset-row" role="radiogroup" aria-label="Stake preset">
          <button
            v-for="preset in stakePresets"
            :key="preset.id"
            type="button"
            class="preset-chip"
            :class="{ active: activePresetId === preset.id }"
            role="radio"
            :aria-checked="activePresetId === preset.id"
            @click="applyPreset(preset)"
          >
            <span class="preset-label">{{ preset.label }}</span>
            <span class="preset-detail">{{ preset.sb }}/{{ preset.bb }}</span>
          </button>
          <span class="preset-chip custom-indicator" :class="{ active: activePresetId === 'custom' }">
            Custom
          </span>
        </div>

        <div class="stakes-grid">
          <label class="field">
            <span class="field-label">Starting chips</span>
            <input v-model.number="startingChips" type="number" min="100" step="100" />
          </label>
          <label class="field">
            <span class="field-label">Small blind</span>
            <input v-model.number="smallBlind" type="number" min="1" />
          </label>
          <label class="field">
            <span class="field-label">Big blind</span>
            <input v-model.number="bigBlind" type="number" min="2" />
          </label>
        </div>

        <p class="stakes-summary">
          <span class="chip-icon" aria-hidden="true">🪙</span>
          {{ startingChips.toLocaleString() }} chips · blinds {{ smallBlind }}/{{ bigBlind }} ·
          {{ bbDepth }} BB deep
        </p>
      </div>

      <div v-if="soloPractice" class="difficulty-section">
        <div class="difficulty-header">
          <h2 class="section-title">AI opponents</h2>
          <span class="difficulty-hint">Set strength for each solo-practice bot.</span>
        </div>
        <div class="solo-ai-grid">
          <label v-for="index in 2" :key="index" class="solo-ai-field">
            <span class="field-label">Opponent {{ index }}</span>
            <select
              class="difficulty-select"
              :value="soloAiDifficulties[index - 1] ?? 'medium'"
              @change="
                updateSoloAiDifficulty(index - 1, ($event.target as HTMLSelectElement).value)
              "
            >
              <option v-for="opt in difficultyOptions" :key="opt.value" :value="opt.value">
                {{ opt.label }} · {{ opt.detail }}
              </option>
            </select>
          </label>
        </div>
      </div>

      <div v-else class="difficulty-section">
        <div class="difficulty-header">
          <h2 class="section-title">Default AI strength</h2>
          <span class="difficulty-hint">{{ activeDifficulty.hint }}</span>
        </div>
        <div class="difficulty-row" role="radiogroup" aria-label="Default AI difficulty">
          <button
            v-for="opt in difficultyOptions"
            :key="opt.value"
            type="button"
            class="difficulty-chip"
            :class="{ active: aiDifficulty === opt.value }"
            role="radio"
            :aria-checked="aiDifficulty === opt.value"
            @click="aiDifficulty = opt.value"
          >
            <span class="diff-label">{{ opt.label }}</span>
            <span class="diff-detail">{{ opt.detail }}</span>
          </button>
        </div>
        <p class="default-ai-note">New AI players start at this level. Override per seat below.</p>
      </div>

      <div class="rules-section">
        <h2 class="section-title">Table rules</h2>
        <label class="toggle-row">
          <span class="toggle-label">
            <span class="toggle-title">Show cards on fold</span>
            <span class="toggle-desc">Reveal winner's cards when everyone folds</span>
          </span>
          <button
            type="button"
            role="switch"
            class="toggle-switch"
            :class="{ active: showCardsOnFold }"
            :aria-checked="showCardsOnFold"
            @click="showCardsOnFold = !showCardsOnFold"
          >
            <span class="toggle-knob" />
          </button>
        </label>
      </div>
    </section>

    <section v-else class="mode-summary card">
      <span class="mode-icon" aria-hidden="true">{{ activeMode.icon }}</span>
      <div>
        <p class="mode-summary-label">{{ activeMode.label }}</p>
        <p class="mode-summary-desc">{{ activeMode.description }}</p>
        <p class="mode-summary-stakes">
          {{ startingChips.toLocaleString() }} chips · blinds {{ smallBlind }}/{{ bigBlind }}
          <template v-if="soloPractice">
            · solo opponents
            {{ soloAiDifficulties.map((level) => difficultyLabel(level)).join(' & ') }}
          </template>
          <template v-else> · default AI {{ activeDifficulty.label }}</template>
        </p>
        <p v-if="!soloPractice" class="mode-summary-ai-hint">{{ activeDifficulty.hint }}</p>
      </div>
    </section>

    <section v-if="soloPractice" class="solo-notice card">
      <p>
        Solo practice auto-adds 2 AI players when you start. You'll play 3-handed Texas Hold'em
        against
        {{ soloAiDifficulties.map((level) => difficultyLabel(level).toLowerCase()).join(' and ') }}
        bots.
      </p>
    </section>

    <template v-else>
      <p v-if="isHost" class="arrange-hint">
        Need 2–{{ maxPlayers }} players. Add AI to fill seats, or share the room link above.
      </p>

      <div class="table-layout">
        <section class="table-preview card" aria-label="Table preview">
          <div class="preview-header">
            <h2 class="section-title">The table</h2>
            <span class="seat-count">{{ playerCount }} / {{ maxPlayers }} seated</span>
          </div>
          <div class="felt-preview">
            <div class="felt-oval" aria-hidden="true">
              <div class="felt-center">
                <span class="felt-label">Texas Hold'em</span>
                <span class="felt-blinds">{{ smallBlind }}/{{ bigBlind }}</span>
              </div>
              <div
                v-for="slot in seatSlots"
                :key="slot.index"
                class="seat-marker"
                :class="{
                  filled: Boolean(slot.player),
                  empty: !slot.player,
                  me: slot.player?.id === currentPlayerId,
                  ai: slot.player?.is_ai,
                }"
                :style="slot.style"
                :title="slot.player?.nickname ?? `Seat ${slot.index + 1}`"
              >
                <span v-if="slot.player" class="seat-initial">
                  {{ seatInitial(slot.player.nickname) }}
                </span>
                <span v-else class="seat-empty-dot" />
              </div>
            </div>
          </div>
        </section>

        <section class="players-card card">
          <div class="players-header">
            <h2 class="section-title">Players</h2>
            <span class="player-count">{{ playerCount }} / {{ maxPlayers }}</span>
          </div>

          <ul v-if="room.players.length > 0" class="player-list">
            <li v-for="(player, index) in room.players" :key="player.id" class="player-row">
              <div class="player-info">
                <span class="seat-num">#{{ index + 1 }}</span>
                <span class="nickname">{{ player.nickname }}</span>
                <span v-if="player.is_ai" class="badge ai-badge">AI</span>
                <span v-if="player.id === currentPlayerId" class="badge you-badge">You</span>
                <span v-if="player.id === hostPlayerId" class="badge host-badge">Host</span>
              </div>
              <div class="player-actions">
                <label v-if="isHost && player.is_ai" class="inline-select">
                  <span>Strength</span>
                  <select
                    class="difficulty-select"
                    :value="playerAiDifficulty(player)"
                    @change="
                      emit('setAiDifficulty', player.id, ($event.target as HTMLSelectElement).value)
                    "
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

          <button v-if="canAddAi" type="button" class="btn-secondary add-ai-btn" @click="emit('addAi')">
            + Add AI player
          </button>
          <p v-else-if="isHost && playerCount >= maxPlayers" class="room-full-hint">
            Table is full (max {{ maxPlayers }} players).
          </p>
        </section>
      </div>

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
  color: var(--text);
  animation: fadeInUp 0.4s var(--ease-smooth) 0.08s backwards;
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
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 0.65rem;
}

.mode-option {
  display: flex;
  align-items: flex-start;
  gap: 0.65rem;
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
  border-color: rgba(42, 143, 78, 0.45);
  transform: translateY(-1px);
}

.mode-option.active {
  border-color: #2a8f4e;
  background: rgba(42, 143, 78, 0.12);
  box-shadow: 0 0 0 1px rgba(42, 143, 78, 0.2);
}

.mode-icon {
  font-size: 1.35rem;
  line-height: 1;
  flex-shrink: 0;
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
  color: var(--text);
}

.mode-summary-desc,
.mode-summary-stakes {
  margin: 0.15rem 0 0;
  font-size: 0.85rem;
  color: var(--text-muted);
}

.mode-summary-ai-hint {
  margin: 0.35rem 0 0;
  font-size: 0.82rem;
  line-height: 1.45;
  color: var(--text-muted);
}

.stakes-section {
  display: flex;
  flex-direction: column;
  gap: 0.85rem;
  padding-top: 0.25rem;
  border-top: 1px solid var(--border);
}

.difficulty-section {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
  padding-top: 0.25rem;
  border-top: 1px solid var(--border);
}

.difficulty-header {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 0.75rem;
}

.difficulty-hint {
  font-size: 0.82rem;
  line-height: 1.45;
  color: var(--text-muted);
  text-align: right;
  max-width: 22rem;
}

.difficulty-row {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 0.5rem;
}

.difficulty-chip {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 0.15rem;
  padding: 0.65rem 0.75rem;
  border: 1px solid var(--border);
  border-radius: 10px;
  background: var(--surface-elevated, rgba(255, 255, 255, 0.03));
  color: var(--text);
  cursor: pointer;
  text-align: left;
}

.difficulty-chip:hover {
  border-color: var(--accent);
}

.difficulty-chip.active {
  border-color: var(--accent);
  background: color-mix(in srgb, var(--accent) 12%, transparent);
}

.diff-label {
  font-weight: 600;
}

.diff-detail {
  font-size: 0.78rem;
  line-height: 1.35;
  color: var(--text-muted);
}

.preset-row {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
}

.preset-chip {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 0.1rem;
  padding: 0.45rem 0.75rem;
  border-radius: 999px;
  border: 1px solid var(--border);
  background: var(--surface-hover);
  color: var(--text);
  cursor: pointer;
  transition:
    border-color 0.2s,
    background 0.2s,
    transform 0.15s;
}

.preset-chip:hover:not(.custom-indicator) {
  border-color: rgba(255, 200, 80, 0.45);
  transform: translateY(-1px);
}

.preset-chip.active {
  border-color: rgba(255, 200, 80, 0.65);
  background: rgba(255, 200, 80, 0.12);
  box-shadow: 0 0 0 1px rgba(255, 200, 80, 0.15);
}

.custom-indicator {
  cursor: default;
  opacity: 0.85;
}

.preset-label {
  font-size: 0.78rem;
  font-weight: 600;
}

.preset-detail {
  font-size: 0.68rem;
  color: var(--text-muted);
  font-variant-numeric: tabular-nums;
}

.stakes-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 0.75rem;
}

.field {
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
}

.field-label {
  font-size: 0.7rem;
  font-weight: 600;
  letter-spacing: 0.04em;
  text-transform: uppercase;
  color: var(--text-muted);
}

.field input {
  padding: 0.45rem 0.65rem;
  border-radius: 8px;
  border: 1px solid var(--border);
  background: var(--surface-hover);
  color: var(--text);
  font-size: 0.9rem;
  font-variant-numeric: tabular-nums;
}

.field input::placeholder {
  color: var(--text-muted);
}

.stakes-summary {
  display: flex;
  align-items: center;
  gap: 0.4rem;
  margin: 0;
  font-size: 0.82rem;
  color: var(--text-muted);
  padding: 0.55rem 0.75rem;
  border-radius: 8px;
  background: rgba(42, 143, 78, 0.08);
  border: 1px solid rgba(42, 143, 78, 0.2);
}

.chip-icon {
  font-size: 0.9rem;
}

.solo-notice {
  font-size: 0.9rem;
  color: var(--text-muted);
  border-left: 3px solid #2a8f4e;
}

.solo-notice p {
  margin: 0;
  line-height: 1.5;
}

.arrange-hint {
  margin: 0;
  font-size: 0.85rem;
  color: var(--text-muted);
  line-height: 1.5;
}

.table-layout {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 1rem;
  align-items: start;
}

.table-preview {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
  min-height: 100%;
}

.preview-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.75rem;
}

.seat-count,
.player-count {
  font-size: 0.8rem;
  font-variant-numeric: tabular-nums;
  color: var(--text-muted);
  padding: 0.15rem 0.55rem;
  border-radius: 999px;
  background: var(--surface-hover);
  border: 1px solid var(--border);
}

.felt-preview {
  position: relative;
  aspect-ratio: 4 / 3;
  min-height: 200px;
  border-radius: 16px;
  background:
    radial-gradient(ellipse at center, rgba(40, 28, 12, 0.45) 0%, rgba(10, 14, 23, 0.85) 72%);
  padding: 1rem;
}

.felt-oval {
  position: relative;
  width: 100%;
  height: 100%;
  border-radius: 50% / 42%;
  background:
    radial-gradient(ellipse 85% 65% at 50% 42%, rgba(255, 255, 255, 0.06) 0%, transparent 55%),
    radial-gradient(ellipse at center, #2a8f4e 0%, #1a6b38 38%, #0d4a26 72%, #082e18 100%);
  box-shadow:
    inset 0 0 0 6px #4a2f18,
    inset 0 0 0 8px #6b4423,
    inset 0 0 30px rgba(0, 0, 0, 0.4);
}

.felt-oval::before {
  content: '';
  position: absolute;
  inset: 10% 12%;
  border: 1px solid rgba(255, 215, 0, 0.12);
  border-radius: 50% / 40%;
  pointer-events: none;
}

.felt-center {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 0.15rem;
  text-align: center;
  pointer-events: none;
}

.felt-label {
  font-size: 0.65rem;
  font-weight: 600;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: rgba(255, 255, 255, 0.55);
}

.felt-blinds {
  font-size: 0.85rem;
  font-weight: 700;
  color: rgba(255, 215, 80, 0.9);
  font-variant-numeric: tabular-nums;
}

.seat-marker {
  position: absolute;
  transform: translate(-50%, -50%);
  width: 2rem;
  height: 2rem;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 0.75rem;
  font-weight: 700;
  transition:
    transform 0.25s var(--ease-bounce),
    box-shadow 0.25s;
  z-index: 1;
}

.seat-marker.empty {
  border: 2px dashed rgba(255, 255, 255, 0.2);
  background: rgba(0, 0, 0, 0.2);
}

.seat-empty-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: rgba(255, 255, 255, 0.25);
}

.seat-marker.filled {
  border: 2px solid rgba(255, 255, 255, 0.35);
  background: rgba(20, 40, 28, 0.85);
  color: rgba(255, 255, 255, 0.9);
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.35);
}

.seat-marker.filled.ai {
  border-color: rgba(91, 156, 255, 0.55);
  background: rgba(30, 50, 80, 0.85);
}

.seat-marker.filled.me {
  border-color: rgba(255, 215, 80, 0.75);
  background: rgba(60, 45, 10, 0.9);
  box-shadow:
    0 0 0 2px rgba(255, 215, 80, 0.25),
    0 2px 10px rgba(0, 0, 0, 0.4);
  transform: translate(-50%, -50%) scale(1.08);
}

.players-card {
  display: flex;
  flex-direction: column;
  gap: 0.85rem;
  min-height: 100%;
}

.players-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.75rem;
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
  font-size: 0.78rem;
  color: var(--text-muted);
}

.difficulty-select {
  padding: 0.35rem 0.55rem;
  border-radius: 8px;
  border: 1px solid var(--border);
  background: var(--surface-hover);
  color: var(--text);
  font-size: 0.82rem;
}

.difficulty-readonly {
  font-size: 0.78rem;
  color: var(--text-muted);
  padding: 0.2rem 0.45rem;
  border-radius: 999px;
  background: var(--surface-hover);
}

.default-ai-note,
.solo-ai-grid {
  margin: 0;
}

.default-ai-note {
  font-size: 0.78rem;
  color: var(--text-muted);
}

.rules-section {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
  padding-top: 0.25rem;
  border-top: 1px solid var(--border);
}

.toggle-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1rem;
  padding: 0.65rem 0.75rem;
  border-radius: 10px;
  background: var(--surface-hover);
  border: 1px solid var(--border);
  cursor: pointer;
  transition: border-color 0.2s;
}

.toggle-row:hover {
  border-color: rgba(255, 255, 255, 0.15);
}

.toggle-label {
  display: flex;
  flex-direction: column;
  gap: 0.15rem;
  min-width: 0;
}

.toggle-title {
  font-size: 0.9rem;
  font-weight: 600;
  color: var(--text);
}

.toggle-desc {
  font-size: 0.78rem;
  color: var(--text-muted);
  line-height: 1.35;
}

.toggle-switch {
  position: relative;
  width: 2.75rem;
  height: 1.5rem;
  border-radius: 999px;
  border: 1px solid var(--border);
  background: rgba(255, 255, 255, 0.08);
  cursor: pointer;
  flex-shrink: 0;
  transition: background 0.2s, border-color 0.2s;
}

.toggle-switch.active {
  background: #2a8f4e;
  border-color: #2a8f4e;
}

.toggle-knob {
  position: absolute;
  top: 2px;
  left: 2px;
  width: 1.15rem;
  height: 1.15rem;
  border-radius: 50%;
  background: #fff;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.3);
  transition: transform 0.2s var(--ease-smooth);
}

.toggle-switch.active .toggle-knob {
  transform: translateX(1.25rem);
}

.solo-ai-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 0.75rem;
}

.solo-ai-field {
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
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

.seat-num {
  font-size: 0.72rem;
  font-weight: 600;
  color: var(--text-muted);
  font-variant-numeric: tabular-nums;
  min-width: 1.5rem;
}

.nickname {
  font-weight: 600;
  color: var(--text);
}

.badge {
  font-size: 0.68rem;
  padding: 0.12rem 0.4rem;
  border-radius: 999px;
  background: var(--surface-elevated);
  color: var(--text-muted);
  text-transform: uppercase;
  letter-spacing: 0.03em;
}

.ai-badge {
  background: rgba(91, 156, 255, 0.15);
  color: #8ec5ff;
}

.host-badge {
  background: rgba(61, 214, 140, 0.15);
  color: var(--success);
}

.you-badge {
  background: rgba(255, 215, 80, 0.15);
  color: #ffd666;
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
  flex-shrink: 0;
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
  color: var(--text);
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

@media (max-width: 900px) {
  .table-layout {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 640px) {
  .mode-selector {
    grid-template-columns: 1fr;
  }

  .stakes-grid {
    grid-template-columns: 1fr;
  }

  .player-row {
    flex-direction: column;
    align-items: flex-start;
  }

  .player-actions {
    width: 100%;
    justify-content: space-between;
  }

  .solo-ai-grid {
    grid-template-columns: 1fr;
  }

  .difficulty-row {
    grid-template-columns: 1fr;
  }

  .difficulty-header {
    flex-direction: column;
    align-items: flex-start;
  }

  .difficulty-hint {
    text-align: left;
    max-width: none;
  }
}
</style>
