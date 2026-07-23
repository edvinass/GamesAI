<script setup lang="ts">
import { computed } from 'vue'
import type { Room } from '@/types'
import { getMapTheme } from './bombermanRender'
import { BOMBERMAN_LOBBY_PRESETS } from './lobbyPresets'

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
const gameMode = defineModel<string>('gameMode', { required: true })
const lives = defineModel<number>('lives', { required: true })
const killTarget = defineModel<number>('killTarget', { required: true })
const matchTimeSec = defineModel<number>('matchTimeSec', { required: true })
const suddenDeathSec = defineModel<number>('suddenDeathSec', { required: true })
const allowSkulls = defineModel<boolean>('allowSkulls', { required: true })
const startingKick = defineModel<boolean>('startingKick', { required: true })
const startingThrow = defineModel<boolean>('startingThrow', { required: true })
const rulePreset = defineModel<string>('rulePreset', { required: true })

const emit = defineEmits<{
  addAi: [team?: 'red' | 'blue']
  remove: [id: string]
  assignTeam: [playerId: string, team: 'red' | 'blue']
  applySettings: [settings: Record<string, unknown>]
}>()

const speedOptions = [
  { label: 'Blitz', value: 90 },
  { label: 'Fast', value: 120 },
  { label: 'Normal', value: 150 },
  { label: 'Slow', value: 200 },
  { label: 'Relaxed', value: 260 },
]

const modeOptions = [
  { id: 'classic', label: 'Classic', hint: 'Last bomber standing' },
  { id: 'team', label: 'Team', hint: 'Red vs Blue' },
  { id: 'kill_race', label: 'Kill Race', hint: 'Respawns · race to kills' },
]

const livesOptions = [1, 2, 3, 4, 5]
const killTargetOptions = [3, 5, 7, 10]
const matchTimeOptions = [
  { label: 'None', value: 0 },
  { label: '2 min', value: 120 },
  { label: '3 min', value: 180 },
  { label: '5 min', value: 300 },
]
const suddenDeathOptions = [
  { label: 'Off', value: 0 },
  { label: '90s', value: 90 },
  { label: '2 min', value: 120 },
  { label: '2.5 min', value: 150 },
  { label: '3 min', value: 180 },
]

const FALLBACK_MAPS: MapOption[] = [
  {
    id: 'classic',
    name: 'Classic',
    description: 'Standard pillar grid — balanced and familiar.',
    difficulty: 'standard',
    width: 25,
    height: 21,
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
      width: Number(m.width ?? 25),
      height: Number(m.height ?? 21),
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

function applyPreset(id: string) {
  const preset = BOMBERMAN_LOBBY_PRESETS.find((p) => p.id === id)
  if (!preset) return
  emit('applySettings', { ...preset.settings })
  if (preset.settings.game_mode === 'team' && props.isHost) {
    balanceTeams()
  }
}

function onModeSelect(id: string) {
  gameMode.value = id
  rulePreset.value = 'custom'
  if (id === 'kill_race' && matchTimeSec.value <= 0) {
    matchTimeSec.value = 180
  }
  if (id === 'team' && props.isHost && unassignedPlayers.value.length === props.room.players.length) {
    // First time entering team mode with everyone unassigned — split seats.
    balanceTeams()
  }
}

const showKillTarget = computed(() => gameMode.value === 'kill_race')
const showLives = computed(() => gameMode.value !== 'kill_race')
const isTeamMode = computed(() => gameMode.value === 'team')

const redPlayers = computed(() =>
  props.room.players.filter((p) => p.team === 'red'),
)
const bluePlayers = computed(() =>
  props.room.players.filter((p) => p.team === 'blue'),
)
const unassignedPlayers = computed(() =>
  props.room.players.filter((p) => p.team !== 'red' && p.team !== 'blue'),
)

function canMovePlayer(playerId: string) {
  return props.isHost || playerId === props.currentPlayerId
}

function setTeam(playerId: string, team: 'red' | 'blue') {
  if (!canMovePlayer(playerId)) return
  emit('assignTeam', playerId, team)
}

function balanceTeams() {
  if (!props.isHost) return
  const ordered = [...props.room.players]
  ordered.forEach((player, i) => {
    emit('assignTeam', player.id, i % 2 === 0 ? 'red' : 'blue')
  })
}
</script>

<template>
  <div class="bomberman-lobby">
    <div v-if="isHost" class="presets-block card">
      <span class="setting-label">Rule presets</span>
      <div class="preset-grid">
        <button
          v-for="preset in BOMBERMAN_LOBBY_PRESETS"
          :key="preset.id"
          type="button"
          class="preset-card"
          :class="{ selected: rulePreset === preset.id }"
          @click="applyPreset(preset.id)"
        >
          <span class="preset-name">{{ preset.label }}</span>
          <span class="preset-desc">{{ preset.description }}</span>
        </button>
      </div>
    </div>

    <div v-if="isHost" class="settings-block card">
      <label class="checkbox-label">
        <input v-model="soloPractice" type="checkbox" />
        Solo practice (play against 2 AI)
      </label>

      <div class="mode-setting">
        <span class="setting-label">Game mode</span>
        <div class="mode-row">
          <button
            v-for="mode in modeOptions"
            :key="mode.id"
            type="button"
            class="mode-chip"
            :class="{ selected: gameMode === mode.id }"
            @click="onModeSelect(mode.id)"
          >
            <span class="mode-label">{{ mode.label }}</span>
            <span class="mode-hint">{{ mode.hint }}</span>
          </button>
        </div>
      </div>

      <div class="settings-grid">
        <div v-if="showLives" class="speed-setting">
          <span class="setting-label">Lives (stock)</span>
          <select v-model.number="lives" class="speed-select">
            <option v-for="n in livesOptions" :key="n" :value="n">{{ n }}</option>
          </select>
        </div>
        <div v-if="showKillTarget" class="speed-setting">
          <span class="setting-label">Kill target</span>
          <select v-model.number="killTarget" class="speed-select">
            <option v-for="n in killTargetOptions" :key="n" :value="n">{{ n }} kills</option>
          </select>
        </div>
        <div class="speed-setting">
          <span class="setting-label">Match timer</span>
          <select v-model.number="matchTimeSec" class="speed-select">
            <option v-for="opt in matchTimeOptions" :key="opt.value" :value="opt.value">
              {{ opt.label }}
            </option>
          </select>
        </div>
        <div class="speed-setting">
          <span class="setting-label">Sudden death</span>
          <select v-model.number="suddenDeathSec" class="speed-select">
            <option v-for="opt in suddenDeathOptions" :key="opt.value" :value="opt.value">
              {{ opt.label }}
            </option>
          </select>
        </div>
        <div class="speed-setting">
          <span class="setting-label">Game speed</span>
          <select v-model.number="tickMs" class="speed-select">
            <option v-for="opt in speedOptions" :key="opt.value" :value="opt.value">
              {{ opt.label }} ({{ opt.value }}ms)
            </option>
          </select>
        </div>
      </div>

      <div class="rule-toggles">
        <label class="checkbox-label">
          <input v-model="allowSkulls" type="checkbox" />
          Skull diseases
        </label>
        <label class="checkbox-label">
          <input v-model="startingKick" type="checkbox" />
          Start with Kick
        </label>
        <label class="checkbox-label">
          <input v-model="startingThrow" type="checkbox" />
          Start with Throw
        </label>
      </div>
    </div>

    <div v-else class="settings-block card guest-summary">
      <p>
        <strong>{{ modeOptions.find((m) => m.id === gameMode)?.label ?? 'Classic' }}</strong>
        <span v-if="lives > 1 && gameMode !== 'kill_race'"> · {{ lives }} lives</span>
        <span v-if="gameMode === 'kill_race'"> · first to {{ killTarget }}</span>
        <span v-if="matchTimeSec > 0"> · {{ Math.round(matchTimeSec / 60) }} min</span>
        <span v-if="suddenDeathSec > 0"> · sudden death {{ suddenDeathSec }}s</span>
      </p>
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
          :style="{
            '--map-accent': getMapTheme(m.id).accent,
            '--map-accent-rgb': getMapTheme(m.id).accentRgb,
            '--map-floor': getMapTheme(m.id).floorTop,
            '--map-hard': getMapTheme(m.id).hard[1],
            '--map-soft': getMapTheme(m.id).soft[1],
          }"
          @click="mapId = m.id"
        >
          <div class="map-swatch" aria-hidden="true">
            <span class="swatch-floor" />
            <span class="swatch-hard" />
            <span class="swatch-soft" />
          </div>
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
      <p>
        Solo practice auto-adds 2 AI bombers when you start.
        <span v-if="gameMode === 'team'"> You’ll be Red vs 2 Blue AI.</span>
        <span v-else-if="gameMode === 'kill_race'"> Race them to {{ killTarget }} kills.</span>
        <span v-else> Clear the arena and be the last one standing.</span>
      </p>
    </div>

    <template v-else>
      <p v-if="isHost" class="arrange-hint">
        Need 2–8 players. Add AI to fill empty seats, or share the room link.
        <span v-if="isTeamMode"> Assign players to Red / Blue below.</span>
      </p>

      <div v-if="isTeamMode" class="team-boards">
        <section class="team-board red">
          <header class="team-header">
            <h3>Red</h3>
            <span class="team-count">{{ redPlayers.length }}</span>
          </header>
          <ul class="team-list">
            <li v-for="player in redPlayers" :key="player.id" class="team-player">
              <div class="player-info">
                <span class="nickname">{{ player.nickname }}</span>
                <span v-if="player.is_ai" class="ai-badge">AI</span>
                <span v-if="player.id === currentPlayerId" class="you-badge">You</span>
                <span v-if="player.id === hostPlayerId" class="host-badge">Host</span>
              </div>
              <div class="team-actions">
                <button
                  v-if="canMovePlayer(player.id)"
                  type="button"
                  class="btn-secondary team-btn"
                  @click="setTeam(player.id, 'blue')"
                >
                  To Blue
                </button>
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
            <li v-if="redPlayers.length === 0" class="empty-team">No players yet</li>
          </ul>
          <button
            v-if="isHost"
            type="button"
            class="btn-secondary add-ai-btn"
            @click="emit('addAi', 'red')"
          >
            + AI on Red
          </button>
        </section>

        <section class="team-board blue">
          <header class="team-header">
            <h3>Blue</h3>
            <span class="team-count">{{ bluePlayers.length }}</span>
          </header>
          <ul class="team-list">
            <li v-for="player in bluePlayers" :key="player.id" class="team-player">
              <div class="player-info">
                <span class="nickname">{{ player.nickname }}</span>
                <span v-if="player.is_ai" class="ai-badge">AI</span>
                <span v-if="player.id === currentPlayerId" class="you-badge">You</span>
                <span v-if="player.id === hostPlayerId" class="host-badge">Host</span>
              </div>
              <div class="team-actions">
                <button
                  v-if="canMovePlayer(player.id)"
                  type="button"
                  class="btn-secondary team-btn"
                  @click="setTeam(player.id, 'red')"
                >
                  To Red
                </button>
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
            <li v-if="bluePlayers.length === 0" class="empty-team">No players yet</li>
          </ul>
          <button
            v-if="isHost"
            type="button"
            class="btn-secondary add-ai-btn"
            @click="emit('addAi', 'blue')"
          >
            + AI on Blue
          </button>
        </section>
      </div>

      <div v-if="isTeamMode && unassignedPlayers.length" class="unassigned card">
        <div class="unassigned-header">
          <span class="setting-label">Unassigned</span>
          <button
            v-if="isHost"
            type="button"
            class="btn-secondary team-btn"
            @click="balanceTeams"
          >
            Balance teams
          </button>
        </div>
        <div v-for="player in unassignedPlayers" :key="player.id" class="player-row">
          <div class="player-info">
            <span class="nickname">{{ player.nickname }}</span>
            <span v-if="player.is_ai" class="ai-badge">AI</span>
            <span v-if="player.id === currentPlayerId" class="you-badge">You</span>
            <span v-if="player.id === hostPlayerId" class="host-badge">Host</span>
          </div>
          <div class="team-actions">
            <button
              v-if="canMovePlayer(player.id)"
              type="button"
              class="btn-secondary team-btn red-btn"
              @click="setTeam(player.id, 'red')"
            >
              Join Red
            </button>
            <button
              v-if="canMovePlayer(player.id)"
              type="button"
              class="btn-secondary team-btn blue-btn"
              @click="setTeam(player.id, 'blue')"
            >
              Join Blue
            </button>
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

      <template v-if="!isTeamMode">
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
      </template>

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
.map-block,
.presets-block {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

.preset-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(140px, 1fr));
  gap: 0.5rem;
}

.preset-card {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
  text-align: left;
  padding: 0.65rem 0.7rem;
  border-radius: 8px;
  border: 1px solid var(--border);
  background: var(--surface);
  color: var(--text);
  cursor: pointer;
}

.preset-card.selected {
  border-color: #f97316;
  box-shadow: 0 0 0 1px rgba(249, 115, 22, 0.35);
}

.preset-name {
  font-weight: 600;
  font-size: 0.9rem;
}

.preset-desc {
  font-size: 0.72rem;
  color: var(--text-muted);
  line-height: 1.3;
}

.mode-row {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 0.45rem;
}

.mode-chip {
  display: flex;
  flex-direction: column;
  gap: 0.15rem;
  text-align: left;
  padding: 0.55rem 0.6rem;
  border-radius: 8px;
  border: 1px solid var(--border);
  background: var(--surface);
  color: var(--text);
  cursor: pointer;
}

.mode-chip.selected {
  border-color: #f97316;
}

.mode-label {
  font-weight: 600;
  font-size: 0.85rem;
}

.mode-hint {
  font-size: 0.7rem;
  color: var(--text-muted);
}

.settings-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(140px, 1fr));
  gap: 0.65rem;
}

.rule-toggles {
  display: flex;
  flex-wrap: wrap;
  gap: 0.75rem 1.1rem;
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
  width: 100%;
  padding: 0.4rem 0.6rem;
  border-radius: 6px;
  border: 1px solid var(--border);
  background: var(--surface);
  color: var(--text);
}

.guest-summary {
  font-size: 0.9rem;
  color: var(--text-muted);
}

.guest-summary strong {
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
  border: 1px solid rgba(var(--map-accent-rgb, 249, 115, 22), 0.22);
  background:
    linear-gradient(
      145deg,
      color-mix(in srgb, var(--map-floor, #1c2838) 55%, transparent),
      rgba(12, 14, 18, 0.7)
    );
  color: var(--text);
  cursor: pointer;
  transition:
    border-color 0.15s ease,
    background 0.15s ease,
    transform 0.15s ease,
    box-shadow 0.15s ease;
}

.map-card:hover:not(:disabled) {
  border-color: rgba(var(--map-accent-rgb, 249, 115, 22), 0.5);
  transform: translateY(-1px);
}

.map-card.selected {
  border-color: rgba(var(--map-accent-rgb, 249, 115, 22), 0.8);
  background:
    linear-gradient(
      145deg,
      color-mix(in srgb, var(--map-accent, #f97316) 18%, transparent),
      color-mix(in srgb, var(--map-floor, #1c2838) 45%, transparent)
    );
  box-shadow: 0 0 0 1px rgba(var(--map-accent-rgb, 249, 115, 22), 0.28);
}

.map-card.disabled {
  cursor: default;
  opacity: 0.9;
}

.map-swatch {
  display: flex;
  gap: 4px;
  margin-bottom: 0.45rem;
}

.swatch-floor,
.swatch-hard,
.swatch-soft {
  width: 14px;
  height: 14px;
  border-radius: 3px;
}

.swatch-floor {
  background: var(--map-floor, #1c2838);
}
.swatch-hard {
  background: var(--map-hard, #64748b);
}
.swatch-soft {
  background: var(--map-soft, #b45309);
}

.map-card-top {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.4rem;
  margin-bottom: 0.25rem;
}

.map-name {
  font-weight: 600;
  font-size: 0.9rem;
}

.diff-badge {
  font-size: 0.65rem;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  padding: 0.12rem 0.35rem;
  border-radius: 999px;
}

.diff-standard {
  background: rgba(34, 197, 94, 0.15);
  color: #4ade80;
}
.diff-hard {
  background: rgba(249, 115, 22, 0.15);
  color: #fb923c;
}
.diff-brutal {
  background: rgba(239, 68, 68, 0.15);
  color: #f87171;
}

.map-desc {
  margin: 0;
  font-size: 0.75rem;
  color: var(--text-muted);
  line-height: 1.35;
}

.checkbox-label {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  font-size: 0.9rem;
  cursor: pointer;
}

.solo-notice {
  padding: 0.85rem 1rem;
  font-size: 0.9rem;
  color: var(--text-muted);
}

.solo-notice p {
  margin: 0;
}

.arrange-hint {
  margin: 0;
  font-size: 0.85rem;
  color: var(--text-muted);
}

.player-list {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
  padding: 0.75rem;
}

.team-boards {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 0.75rem;
}

.team-board {
  display: flex;
  flex-direction: column;
  gap: 0.65rem;
  padding: 0.85rem;
  border-radius: 10px;
  border: 1px solid var(--border);
  background: var(--surface);
}

.team-board.red {
  border-color: rgba(239, 68, 68, 0.35);
  background: linear-gradient(160deg, rgba(239, 68, 68, 0.1), transparent 55%);
}

.team-board.blue {
  border-color: rgba(59, 130, 246, 0.35);
  background: linear-gradient(160deg, rgba(59, 130, 246, 0.1), transparent 55%);
}

.team-header {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 0.5rem;
}

.team-header h3 {
  margin: 0;
  font-size: 1rem;
}

.team-count {
  font-size: 0.75rem;
  color: var(--text-muted);
}

.team-list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 0.45rem;
  min-height: 2.5rem;
}

.team-player,
.player-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.75rem;
}

.team-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 0.35rem;
  justify-content: flex-end;
}

.team-btn {
  font-size: 0.75rem;
  padding: 0.2rem 0.5rem;
}

.empty-team {
  font-size: 0.8rem;
  color: var(--text-muted);
}

.unassigned {
  display: flex;
  flex-direction: column;
  gap: 0.55rem;
  padding: 0.85rem;
}

.unassigned-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.75rem;
}

@media (max-width: 640px) {
  .team-boards {
    grid-template-columns: 1fr;
  }
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
  gap: 0.4rem;
  flex-wrap: wrap;
}

.nickname {
  font-weight: 500;
}

.ai-badge,
.you-badge,
.host-badge {
  font-size: 0.7rem;
  padding: 0.1rem 0.4rem;
  border-radius: 999px;
  background: rgba(148, 163, 184, 0.2);
  color: var(--text-muted);
}

.you-badge {
  background: rgba(249, 115, 22, 0.2);
  color: #fb923c;
}

.host-badge {
  background: rgba(59, 130, 246, 0.2);
  color: #60a5fa;
}

.remove-btn {
  font-size: 0.8rem;
  padding: 0.25rem 0.55rem;
}

.add-ai-btn {
  align-self: flex-start;
}

.validation-banner {
  display: flex;
  gap: 0.75rem;
  align-items: flex-start;
  padding: 0.85rem 1rem;
}

.validation-banner.valid {
  border-color: rgba(34, 197, 94, 0.35);
}

.validation-banner.invalid {
  border-color: rgba(239, 68, 68, 0.35);
}

.validation-icon {
  font-weight: 700;
}

.validation-message {
  margin: 0;
  font-size: 0.9rem;
}

.validation-issues {
  margin: 0.35rem 0 0;
  padding-left: 1.1rem;
  font-size: 0.8rem;
  color: var(--text-muted);
}

@media (max-width: 640px) {
  .mode-row {
    grid-template-columns: 1fr;
  }
}
</style>
