<script setup lang="ts">
import { computed, ref } from 'vue'
import type { Room } from '@/types'
import PowerupEncyclopedia from './PowerupEncyclopedia.vue'
import { ARENA_THEMES } from './themes'
import { getDailyChallenge } from './dailyChallenge'
import { POWERUP_LABELS } from './duelRenderer'
import { DUEL_LOBBY_PRESETS } from './lobbyPresets'
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
const tickMs = defineModel<number>('tickMs', { required: true })
const matchFormat = defineModel<string>('matchFormat', { required: true })
const mutator = defineModel<string>('mutator', { required: true })
const mutatorSecondary = defineModel<string>('mutatorSecondary', { required: true })
const aiDifficulty = defineModel<string>('aiDifficulty', { required: true })
const aiPersonality = defineModel<string>('aiPersonality', { required: true })
const obstacleCount = defineModel<number>('obstacleCount', { required: true })
const quickDuelLoadout = defineModel<string>('quickDuelLoadout', { required: true })
const arenaTheme = defineModel<string>('arenaTheme', { required: true })
const trainingDrill = defineModel<string>('trainingDrill', { required: true })
const obstacleRotation = defineModel<boolean>('obstacleRotation', { required: true })
const tutorialMode = defineModel<boolean>('tutorialMode', { required: true })
const powerupDraftEnabled = defineModel<boolean>('powerupDraftEnabled', { required: true })

const emit = defineEmits<{
  addAi: []
  remove: [id: string]
  applyDaily: []
  applyPreset: [settings: Record<string, unknown>]
}>()

const daily = computed(() => getDailyChallenge())
const showDailyConfirm = ref(false)
const guestSummary = computed(() => formatDuelLobbySummary(props.room))

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
  { label: 'Best of 7 (marathon)', value: 'best_of_7' },
]

const mutatorOptions = [
  { label: 'Classic', value: 'classic', hint: 'Cover, HP, power-ups' },
  { label: 'Chaos', value: 'chaos', hint: 'Fast bullets, rapid fire' },
  { label: 'Sniper', value: 'sniper', hint: 'One shot, long cooldown' },
  { label: 'Bounce House', value: 'bounce_house', hint: 'Ricochet + obstacles' },
  { label: 'Fog', value: 'fog', hint: 'Imprecise enemy position' },
]

const secondaryOptions = [
  { label: 'None', value: 'none' },
  { label: 'Fog overlay', value: 'fog' },
  { label: 'Chaos boost', value: 'chaos' },
]

const difficultyOptions = [
  { label: 'Easy', value: 'easy', hint: 'Slower reactions, more mistakes' },
  { label: 'Medium', value: 'medium', hint: 'Balanced opponent' },
  { label: 'Hard', value: 'hard', hint: 'Fast dodges and charge shots' },
  { label: 'Pro', value: 'pro', hint: 'Combos, center-row focus, prediction' },
]

const personalityOptions = [
  { label: 'Balanced', value: 'balanced' },
  { label: 'Aggressive', value: 'aggressive' },
  { label: 'Turtle', value: 'turtle' },
  { label: 'Trickster', value: 'trickster' },
]

const drillOptions = [
  { label: 'None', value: 'none' },
  { label: 'Dodge only', value: 'dodge_only' },
  { label: 'Aim trainer', value: 'aim_trainer' },
  { label: 'Power-up sandbox', value: 'powerup_sandbox' },
]

const loadoutOptions = [
  { label: 'None', value: 'none' },
  ...Object.entries(POWERUP_LABELS).map(([value, label]) => ({ label, value })),
]

const obstacleOptions = [0, 1, 2, 3, 4, 5, 6]
const themeOptions = Object.values(ARENA_THEMES)
const selectedTheme = computed(() => ARENA_THEMES[arenaTheme.value as keyof typeof ARENA_THEMES] ?? ARENA_THEMES.classic)

const showObstacleSetting = computed(
  () => matchFormat.value !== 'quick_duel' && mutator.value !== 'bounce_house',
)

const showPowerupDraftSetting = computed(() => matchFormat.value !== 'quick_duel')

function applyPreset(presetId: string) {
  const preset = DUEL_LOBBY_PRESETS.find((p) => p.id === presetId)
  if (!preset) return
  emit('applyPreset', preset.settings)
}

function confirmDaily() {
  showDailyConfirm.value = false
  emit('applyDaily')
}
</script>

<template>
  <div class="duel-lobby">
    <div v-if="!isHost" class="guest-summary card">
      <h3>Match setup</h3>
      <p class="guest-lead">The host chose these settings. You’ll see the same rules in-game.</p>
      <ul>
        <li v-for="line in guestSummary" :key="line">{{ line }}</li>
      </ul>
    </div>

    <div v-if="isHost" class="daily-banner card">
      <div>
        <strong>{{ daily.label }}</strong>
        <p class="daily-meta">
          {{ daily.dateKey }} · {{ daily.matchFormat.replace(/_/g, ' ') }} · {{ daily.obstacleCount }} cover
        </p>
      </div>
      <button type="button" class="btn-secondary" @click="showDailyConfirm = true">Use daily</button>
    </div>

    <div v-if="isHost && showDailyConfirm" class="daily-confirm card">
      <h4>Apply daily challenge?</h4>
      <ul>
        <li>Format: {{ daily.matchFormat.replace(/_/g, ' ') }}</li>
        <li>Mutator: {{ daily.mutator.replace(/_/g, ' ') }}</li>
        <li>Secondary: {{ daily.mutatorSecondary === 'none' ? 'None' : daily.mutatorSecondary }}</li>
        <li>Cover blocks: {{ daily.obstacleCount }}</li>
        <li>Layout seed: {{ daily.layoutSeed }}</li>
      </ul>
      <div class="daily-confirm-actions">
        <button type="button" class="btn-primary" @click="confirmDaily">Apply</button>
        <button type="button" class="btn-secondary" @click="showDailyConfirm = false">Cancel</button>
      </div>
    </div>

    <div v-if="isHost" class="presets card">
      <span class="section-label">Quick presets</span>
      <div class="preset-row">
        <button
          v-for="preset in DUEL_LOBBY_PRESETS"
          :key="preset.id"
          type="button"
          class="btn-secondary preset-btn"
          @click="applyPreset(preset.id)"
        >
          <strong>{{ preset.label }}</strong>
          <span>{{ preset.description }}</span>
        </button>
      </div>
    </div>

    <div v-if="isHost" class="settings-block card">
      <details open class="settings-group">
        <summary>Match</summary>
        <label class="checkbox-label">
          <input v-model="soloPractice" type="checkbox" />
          Solo practice (play against AI)
        </label>
        <label class="checkbox-label">
          <input v-model="tutorialMode" type="checkbox" />
          Opening tips (phase coaching)
        </label>
        <label v-if="showPowerupDraftSetting" class="checkbox-label">
          <input v-model="powerupDraftEnabled" type="checkbox" />
          Power-up ban phase (each player removes one orb type between rounds)
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
          <span class="setting-label">Secondary mutator</span>
          <select v-model="mutatorSecondary" class="setting-select">
            <option v-for="opt in secondaryOptions" :key="opt.value" :value="opt.value">
              {{ opt.label }}
            </option>
          </select>
        </div>
        <div v-if="matchFormat === 'quick_duel'" class="setting-row">
          <span class="setting-label">Quick duel loadout</span>
          <select v-model="quickDuelLoadout" class="setting-select">
            <option v-for="opt in loadoutOptions" :key="opt.value" :value="opt.value">
              {{ opt.label }}
            </option>
          </select>
        </div>
        <div class="setting-row">
          <span class="setting-label">Training drill</span>
          <select v-model="trainingDrill" class="setting-select">
            <option v-for="opt in drillOptions" :key="opt.value" :value="opt.value">
              {{ opt.label }}
            </option>
          </select>
        </div>
      </details>

      <details open class="settings-group">
        <summary>Arena</summary>
        <div class="setting-row">
          <span class="setting-label">Arena theme</span>
          <div class="theme-picker">
            <button
              v-for="opt in themeOptions"
              :key="opt.id"
              type="button"
              class="theme-swatch"
              :class="{ active: arenaTheme === opt.id }"
              :title="opt.label"
              @click="arenaTheme = opt.id"
            >
              <span
                class="swatch-colors"
                :style="{
                  background: `linear-gradient(135deg, ${opt.backdrop[0]}, ${opt.backdrop[1]})`,
                  '--swatch-grid': opt.grid,
                  '--swatch-midline': opt.midline,
                }"
              />
              <span class="swatch-label">{{ opt.label }}</span>
            </button>
          </div>
        </div>
        <div class="theme-preview card" :style="{ background: selectedTheme.canvasCss }">
          <div
            class="theme-preview-arena"
            :style="{
              background: `linear-gradient(180deg, ${selectedTheme.backdrop[0]}, ${selectedTheme.backdrop[1]})`,
              '--preview-grid': selectedTheme.grid,
              '--preview-midline': selectedTheme.midline,
              '--preview-hazard': selectedTheme.hazard,
            }"
          >
            <span class="preview-ship left" />
            <span class="preview-midline" />
            <span class="preview-ship right" />
            <span class="preview-hazard top" />
            <span class="preview-hazard bottom" />
          </div>
          <span class="theme-preview-label">{{ selectedTheme.label }}</span>
        </div>
        <div class="setting-row">
          <span class="setting-label">Game speed</span>
          <select v-model.number="tickMs" class="setting-select">
            <option v-for="opt in speedOptions" :key="opt.value" :value="opt.value">
              {{ opt.label }} ({{ opt.value }}ms)
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
        <label v-if="showObstacleSetting" class="checkbox-label">
          <input v-model="obstacleRotation" type="checkbox" />
          Drifting cover (slow obstacle rotation)
        </label>
        <p v-if="!showObstacleSetting && mutator === 'bounce_house'" class="setting-hint">
          Cover: {{ obstacleCount }} blocks (fixed for Bounce House)
        </p>
      </details>

      <details v-if="soloPractice || room.players.some((p) => p.is_ai)" class="settings-group">
        <summary>AI opponent</summary>
        <div class="setting-row">
          <span class="setting-label">AI difficulty</span>
          <select v-model="aiDifficulty" class="setting-select">
            <option v-for="opt in difficultyOptions" :key="opt.value" :value="opt.value">
              {{ opt.label }} — {{ opt.hint }}
            </option>
          </select>
        </div>
        <div class="setting-row">
          <span class="setting-label">AI personality</span>
          <select v-model="aiPersonality" class="setting-select">
            <option v-for="opt in personalityOptions" :key="opt.value" :value="opt.value">
              {{ opt.label }}
            </option>
          </select>
        </div>
      </details>
    </div>

    <PowerupEncyclopedia />

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

.guest-summary h3 {
  margin: 0 0 0.35rem;
  font-size: 1rem;
}

.guest-lead {
  margin: 0 0 0.5rem;
  font-size: 0.85rem;
  color: var(--text-muted);
}

.guest-summary ul {
  margin: 0;
  padding-left: 1.1rem;
  font-size: 0.9rem;
}

.daily-banner,
.daily-confirm {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 1rem;
}

.daily-confirm {
  flex-direction: column;
}

.daily-confirm h4 {
  margin: 0;
}

.daily-confirm ul {
  margin: 0.5rem 0;
  padding-left: 1.1rem;
  font-size: 0.9rem;
}

.daily-confirm-actions {
  display: flex;
  gap: 0.5rem;
}

.daily-meta {
  margin: 0.25rem 0 0;
  font-size: 0.85rem;
  color: var(--text-muted);
}

.presets .section-label {
  display: block;
  font-size: 0.85rem;
  color: var(--text-muted);
  margin-bottom: 0.5rem;
}

.preset-row {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
}

.preset-btn {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 0.15rem;
  min-width: 9rem;
}

.preset-btn span {
  font-size: 0.75rem;
  opacity: 0.8;
  font-weight: 400;
}

.settings-block {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

.settings-group {
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 0.65rem 0.75rem;
}

.settings-group summary {
  cursor: pointer;
  font-weight: 600;
  margin-bottom: 0.5rem;
}

.setting-row {
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
  margin-top: 0.5rem;
}

.setting-label {
  font-size: 0.85rem;
  color: var(--text-muted);
}

.setting-hint {
  font-size: 0.8rem;
  color: var(--text-muted);
  margin: 0.35rem 0 0;
}

.setting-select {
  max-width: 100%;
  padding: 0.4rem 0.6rem;
  border-radius: 6px;
  border: 1px solid var(--border);
  background: var(--surface);
  color: var(--text);
}

.theme-picker {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
}

.theme-swatch {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 0.25rem;
  padding: 0.35rem;
  border: 2px solid transparent;
  border-radius: 8px;
  background: transparent;
  cursor: pointer;
}

.theme-swatch.active {
  border-color: var(--accent);
}

.swatch-colors {
  position: relative;
  width: 3rem;
  height: 1.75rem;
  border-radius: 6px;
  border: 1px solid rgba(255, 255, 255, 0.15);
  overflow: hidden;
}

.swatch-colors::before,
.swatch-colors::after {
  content: '';
  position: absolute;
  inset: 0;
}

.swatch-colors::before {
  background-image:
    linear-gradient(var(--swatch-grid, rgba(255, 255, 255, 0.12)) 1px, transparent 1px),
    linear-gradient(90deg, var(--swatch-grid, rgba(255, 255, 255, 0.12)) 1px, transparent 1px);
  background-size: 8px 8px;
}

.swatch-colors::after {
  background: linear-gradient(90deg, transparent 48%, var(--swatch-midline, rgba(255, 255, 255, 0.3)) 50%, transparent 52%);
}

.theme-preview {
  margin-top: 0.5rem;
  padding: 0.65rem;
  border-radius: 8px;
  display: flex;
  flex-direction: column;
  gap: 0.45rem;
}

.theme-preview-arena {
  position: relative;
  height: 4.5rem;
  border-radius: 8px;
  overflow: hidden;
  border: 1px solid rgba(255, 255, 255, 0.1);
  background-image:
    linear-gradient(var(--preview-grid) 1px, transparent 1px),
    linear-gradient(90deg, var(--preview-grid) 1px, transparent 1px);
  background-size: 14px 14px;
}

.preview-midline {
  position: absolute;
  top: 0;
  bottom: 0;
  left: 50%;
  width: 2px;
  transform: translateX(-50%);
  background: var(--preview-midline);
}

.preview-ship {
  position: absolute;
  top: 50%;
  width: 1.1rem;
  height: 0.55rem;
  border-radius: 2px;
  transform: translateY(-50%);
}

.preview-ship.left {
  left: 18%;
  background: #5b9cff;
  box-shadow: 0 0 8px rgba(91, 156, 255, 0.5);
}

.preview-ship.right {
  right: 18%;
  background: #f87171;
  box-shadow: 0 0 8px rgba(248, 113, 113, 0.5);
}

.preview-hazard {
  position: absolute;
  left: 0;
  right: 0;
  height: 0.65rem;
  background: var(--preview-hazard);
}

.preview-hazard.top {
  top: 0;
}

.preview-hazard.bottom {
  bottom: 0;
}

.swatch-label {
  font-size: 0.7rem;
  color: var(--text-muted);
}

.theme-preview-label {
  font-size: 0.82rem;
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
  margin-top: 0.5rem;
}
</style>
