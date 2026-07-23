<script setup lang="ts">
import { computed, ref } from 'vue'
import type { Player, Room } from '@/types'
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

const showAdvanced = ref(false)

const speedOptions = [
  { label: 'Blitz', value: 90 },
  { label: 'Fast', value: 120 },
  { label: 'Normal', value: 150 },
  { label: 'Slow', value: 200 },
  { label: 'Relaxed', value: 260 },
]

const modeOptions = [
  { id: 'classic', label: 'Classic', hint: 'Last bomber standing', icon: '💣' },
  { id: 'team', label: 'Team Battle', hint: 'Red vs Blue', icon: '🧑‍🤝‍🧑' },
  { id: 'kill_race', label: 'Kill Race', hint: 'Respawns · race to kills', icon: '🏆' },
]

const livesOptions = [1, 2, 3, 4, 5]
const killTargetOptions = [3, 5, 7, 10]
const matchTimeOptions = [
  { label: 'No timer', value: 0 },
  { label: '2 min', value: 120 },
  { label: '3 min', value: 180 },
  { label: '5 min', value: 300 },
]
const suddenDeathOptions = [
  { label: 'Off', value: 0 },
  { label: 'After 90s', value: 90 },
  { label: 'After 2 min', value: 120 },
  { label: 'After 2.5 min', value: 150 },
  { label: 'After 3 min', value: 180 },
]

const FALLBACK_MAPS: MapOption[] = [
  {
    id: 'classic',
    name: 'Classic',
    description: 'Standard pillar grid — balanced and familiar.',
    difficulty: 'standard',
    width: 23,
    height: 19,
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

const activeMode = computed(
  () => modeOptions.find((m) => m.id === gameMode.value) ?? modeOptions[0]!,
)

const activePreset = computed(
  () => BOMBERMAN_LOBBY_PRESETS.find((p) => p.id === rulePreset.value) ?? null,
)

const speedLabel = computed(
  () => speedOptions.find((o) => o.value === tickMs.value)?.label ?? 'Custom',
)

const summaryChips = computed(() => {
  const chips: { label: string; tone?: string }[] = []
  chips.push({
    label: soloPractice.value ? 'Solo practice' : 'Multiplayer',
    tone: 'accent',
  })
  chips.push({ label: activeMode.value.label, tone: 'accent' })
  if (selectedMap.value) chips.push({ label: selectedMap.value.name })
  if (gameMode.value === 'kill_race') {
    chips.push({ label: `First to ${killTarget.value}` })
  } else if (lives.value > 1) {
    chips.push({ label: `${lives.value} lives` })
  }
  if (matchTimeSec.value > 0) {
    chips.push({ label: `${Math.round(matchTimeSec.value / 60)} min timer` })
  }
  if (suddenDeathSec.value > 0) {
    chips.push({ label: `Sudden death ${suddenDeathSec.value}s`, tone: 'warn' })
  }
  chips.push({ label: speedLabel.value })
  if (startingKick.value) chips.push({ label: 'Kick' })
  if (startingThrow.value) chips.push({ label: 'Throw' })
  if (!allowSkulls.value) chips.push({ label: 'No skulls' })
  return chips
})

const isTeamMode = computed(() => gameMode.value === 'team')
const showKillTarget = computed(() => gameMode.value === 'kill_race')
const showLives = computed(() => gameMode.value !== 'kill_race')

const redPlayers = computed(() => props.room.players.filter((p) => p.team === 'red'))
const bluePlayers = computed(() => props.room.players.filter((p) => p.team === 'blue'))
const unassignedPlayers = computed(() =>
  props.room.players.filter((p) => p.team !== 'red' && p.team !== 'blue'),
)

const maxPlayers = computed(() => Number(props.room.settings?.max_players ?? 8))
const canAddAi = computed(
  () => props.isHost && !soloPractice.value && props.room.players.length < maxPlayers.value,
)

const difficultyClass = (difficulty: string) => {
  if (difficulty === 'brutal') return 'diff-brutal'
  if (difficulty === 'hard') return 'diff-hard'
  return 'diff-standard'
}

function markCustom() {
  if (rulePreset.value !== 'custom') rulePreset.value = 'custom'
}

function applyPreset(id: string) {
  const preset = BOMBERMAN_LOBBY_PRESETS.find((p) => p.id === id)
  if (!preset) return
  emit('applySettings', { ...preset.settings })
  showAdvanced.value = false
  if (preset.settings.game_mode === 'team' && props.isHost) {
    balanceTeams()
  }
}

function onModeSelect(id: string) {
  gameMode.value = id
  markCustom()
  if (id === 'kill_race' && matchTimeSec.value <= 0) {
    matchTimeSec.value = 180
  }
  if (
    id === 'team' &&
    props.isHost &&
    unassignedPlayers.value.length === props.room.players.length
  ) {
    balanceTeams()
  }
}

function onSoloToggle(value: boolean) {
  soloPractice.value = value
}

function canMovePlayer(playerId: string) {
  return props.isHost || playerId === props.currentPlayerId
}

function setTeam(playerId: string, team: 'red' | 'blue') {
  if (!canMovePlayer(playerId)) return
  emit('assignTeam', playerId, team)
}

function balanceTeams() {
  if (!props.isHost) return
  ;[...props.room.players].forEach((player, i) => {
    emit('assignTeam', player.id, i % 2 === 0 ? 'red' : 'blue')
  })
}

function playerBadges(player: Player) {
  return {
    isYou: player.id === props.currentPlayerId,
    isHost: player.id === props.hostPlayerId,
    isAi: player.is_ai,
  }
}
</script>

<template>
  <div class="bomberman-lobby">
    <section class="match-summary card">
      <div class="summary-top">
        <div>
          <p class="summary-kicker">Match setup</p>
          <h2 class="summary-title">
            <span class="summary-icon" aria-hidden="true">{{ activeMode.icon }}</span>
            {{ activeMode.label }}
            <span v-if="soloPractice" class="summary-sub">· solo</span>
          </h2>
          <p class="summary-desc">
            <template v-if="soloPractice">You vs 2 AI · {{ activeMode.hint }}</template>
            <template v-else-if="isTeamMode">Pick Red / Blue seats below · {{ activeMode.hint }}</template>
            <template v-else>{{ activeMode.hint }}</template>
          </p>
        </div>
        <span v-if="activePreset" class="preset-pill">{{ activePreset.label }}</span>
        <span v-else-if="rulePreset === 'custom'" class="preset-pill custom">Custom</span>
      </div>
      <div class="chip-row" aria-label="Match settings">
        <span
          v-for="chip in summaryChips"
          :key="chip.label"
          class="chip"
          :class="chip.tone"
        >{{ chip.label }}</span>
      </div>
    </section>

    <template v-if="isHost">
      <section class="card section-block">
        <h3 class="section-title">Play style</h3>
        <div class="play-style" role="radiogroup" aria-label="Play style">
          <button
            type="button"
            class="style-option"
            :class="{ active: !soloPractice }"
            role="radio"
            :aria-checked="!soloPractice"
            @click="onSoloToggle(false)"
          >
            <span class="style-icon" aria-hidden="true">👥</span>
            <span class="style-copy">
              <span class="style-label">Multiplayer</span>
              <span class="style-desc">2–8 players · share link or add AI</span>
            </span>
          </button>
          <button
            type="button"
            class="style-option"
            :class="{ active: soloPractice }"
            role="radio"
            :aria-checked="soloPractice"
            @click="onSoloToggle(true)"
          >
            <span class="style-icon" aria-hidden="true">🤖</span>
            <span class="style-copy">
              <span class="style-label">Solo practice</span>
              <span class="style-desc">You vs 2 AI when the match starts</span>
            </span>
          </button>
        </div>
      </section>

      <section class="card section-block">
        <div class="section-heading">
          <h3 class="section-title">Quick start</h3>
          <span class="section-hint">Applies mode + rules in one tap</span>
        </div>
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
      </section>

      <section class="card section-block">
        <h3 class="section-title">Mode</h3>
        <div class="mode-row" role="radiogroup" aria-label="Game mode">
          <button
            v-for="mode in modeOptions"
            :key="mode.id"
            type="button"
            class="mode-chip"
            :class="{ selected: gameMode === mode.id }"
            role="radio"
            :aria-checked="gameMode === mode.id"
            @click="onModeSelect(mode.id)"
          >
            <span class="mode-icon" aria-hidden="true">{{ mode.icon }}</span>
            <span class="mode-label">{{ mode.label }}</span>
            <span class="mode-hint">{{ mode.hint }}</span>
          </button>
        </div>

        <div class="settings-grid primary-grid">
          <label v-if="showLives" class="field">
            <span class="setting-label">Lives</span>
            <select v-model.number="lives" class="speed-select" @change="markCustom">
              <option v-for="n in livesOptions" :key="n" :value="n">{{ n }}</option>
            </select>
          </label>
          <label v-if="showKillTarget" class="field">
            <span class="setting-label">Kill target</span>
            <select v-model.number="killTarget" class="speed-select" @change="markCustom">
              <option v-for="n in killTargetOptions" :key="n" :value="n">{{ n }} kills</option>
            </select>
          </label>
          <label class="field">
            <span class="setting-label">Speed</span>
            <select v-model.number="tickMs" class="speed-select" @change="markCustom">
              <option v-for="opt in speedOptions" :key="opt.value" :value="opt.value">
                {{ opt.label }}
              </option>
            </select>
          </label>
        </div>

        <button
          type="button"
          class="advanced-toggle"
          :aria-expanded="showAdvanced"
          @click="showAdvanced = !showAdvanced"
        >
          {{ showAdvanced ? 'Hide' : 'Show' }} advanced rules
          <span class="caret" :class="{ open: showAdvanced }" aria-hidden="true">▾</span>
        </button>

        <div v-if="showAdvanced" class="advanced-panel">
          <div class="settings-grid">
            <label class="field">
              <span class="setting-label">Match timer</span>
              <select v-model.number="matchTimeSec" class="speed-select" @change="markCustom">
                <option v-for="opt in matchTimeOptions" :key="opt.value" :value="opt.value">
                  {{ opt.label }}
                </option>
              </select>
            </label>
            <label class="field">
              <span class="setting-label">Sudden death</span>
              <select v-model.number="suddenDeathSec" class="speed-select" @change="markCustom">
                <option v-for="opt in suddenDeathOptions" :key="opt.value" :value="opt.value">
                  {{ opt.label }}
                </option>
              </select>
            </label>
          </div>
          <div class="rule-toggles">
            <label class="checkbox-label">
              <input v-model="allowSkulls" type="checkbox" @change="markCustom" />
              Skull diseases
            </label>
            <label class="checkbox-label">
              <input v-model="startingKick" type="checkbox" @change="markCustom" />
              Start with Kick
            </label>
            <label class="checkbox-label">
              <input v-model="startingThrow" type="checkbox" @change="markCustom" />
              Start with Throw
            </label>
          </div>
        </div>
      </section>
    </template>

    <section class="map-block card">
      <div class="map-header">
        <div>
          <h3 class="section-title">Arena</h3>
          <p v-if="selectedMap" class="section-hint">{{ selectedMap.description }}</p>
        </div>
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
        </button>
      </div>
    </section>

    <section v-if="soloPractice" class="solo-notice card">
      <span class="solo-icon" aria-hidden="true">🤖</span>
      <div>
        <p class="solo-title">Ready for solo practice</p>
        <p class="solo-copy">
          Starting adds 2 AI bombers automatically.
          <span v-if="isTeamMode"> You’ll be Red against 2 Blue AI.</span>
          <span v-else-if="gameMode === 'kill_race'"> Race them to {{ killTarget }} kills.</span>
          <span v-else> Be the last bomber standing.</span>
        </p>
      </div>
    </section>

    <template v-else>
      <section class="card section-block players-section">
        <div class="section-heading">
          <div>
            <h3 class="section-title">
              {{ isTeamMode ? 'Teams' : 'Players' }}
              <span class="count-pill">{{ room.players.length }}/{{ maxPlayers }}</span>
            </h3>
            <p class="section-hint">
              <template v-if="isTeamMode">
                Host can move anyone · you can switch your own seat
              </template>
              <template v-else>Share the room link or add AI to fill seats</template>
            </p>
          </div>
          <button
            v-if="isHost && isTeamMode"
            type="button"
            class="btn-secondary balance-btn"
            @click="balanceTeams"
          >
            Balance
          </button>
        </div>

        <div v-if="isTeamMode" class="team-boards">
          <section
            v-for="side in (['red', 'blue'] as const)"
            :key="side"
            class="team-board"
            :class="side"
          >
            <header class="team-header">
              <h4>{{ side === 'red' ? 'Red' : 'Blue' }}</h4>
              <span class="team-count">
                {{ side === 'red' ? redPlayers.length : bluePlayers.length }}
              </span>
            </header>
            <ul class="team-list">
              <li
                v-for="player in side === 'red' ? redPlayers : bluePlayers"
                :key="player.id"
                class="player-row"
                :class="{ me: player.id === currentPlayerId }"
              >
                <div class="player-info">
                  <span class="team-dot" :class="side" aria-hidden="true" />
                  <span class="nickname">{{ player.nickname }}</span>
                  <span v-if="playerBadges(player).isAi" class="badge ai">AI</span>
                  <span v-if="playerBadges(player).isYou" class="badge you">You</span>
                  <span v-if="playerBadges(player).isHost" class="badge host">Host</span>
                </div>
                <div class="team-actions">
                  <button
                    v-if="canMovePlayer(player.id)"
                    type="button"
                    class="btn-secondary team-btn"
                    @click="setTeam(player.id, side === 'red' ? 'blue' : 'red')"
                  >
                    → {{ side === 'red' ? 'Blue' : 'Red' }}
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
              <li
                v-if="(side === 'red' ? redPlayers : bluePlayers).length === 0"
                class="empty-team"
              >
                Empty — add players or AI
              </li>
            </ul>
            <button
              v-if="canAddAi"
              type="button"
              class="btn-secondary add-ai-btn"
              @click="emit('addAi', side)"
            >
              + AI
            </button>
          </section>
        </div>

        <div v-if="isTeamMode && unassignedPlayers.length" class="unassigned">
          <div class="unassigned-header">
            <span class="setting-label">Unassigned ({{ unassignedPlayers.length }})</span>
            <span class="section-hint">Auto-balanced at start if left empty</span>
          </div>
          <div
            v-for="player in unassignedPlayers"
            :key="player.id"
            class="player-row"
            :class="{ me: player.id === currentPlayerId }"
          >
            <div class="player-info">
              <span class="nickname">{{ player.nickname }}</span>
              <span v-if="playerBadges(player).isAi" class="badge ai">AI</span>
              <span v-if="playerBadges(player).isYou" class="badge you">You</span>
              <span v-if="playerBadges(player).isHost" class="badge host">Host</span>
            </div>
            <div class="team-actions">
              <button
                v-if="canMovePlayer(player.id)"
                type="button"
                class="btn-secondary team-btn red-btn"
                @click="setTeam(player.id, 'red')"
              >
                Red
              </button>
              <button
                v-if="canMovePlayer(player.id)"
                type="button"
                class="btn-secondary team-btn blue-btn"
                @click="setTeam(player.id, 'blue')"
              >
                Blue
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
          <div class="player-list">
            <div
              v-for="player in room.players"
              :key="player.id"
              class="player-row"
              :class="{ me: player.id === currentPlayerId }"
            >
              <div class="player-info">
                <span class="nickname">{{ player.nickname }}</span>
                <span v-if="playerBadges(player).isAi" class="badge ai">AI</span>
                <span v-if="playerBadges(player).isYou" class="badge you">You</span>
                <span v-if="playerBadges(player).isHost" class="badge host">Host</span>
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
            v-if="canAddAi"
            type="button"
            class="btn-secondary add-ai-btn"
            @click="emit('addAi')"
          >
            + Add AI player
          </button>
        </template>
      </section>

      <div
        class="validation-banner card"
        :class="{ valid: validationValid, invalid: !validationValid }"
      >
        <span class="validation-icon" aria-hidden="true">
          {{ validationValid ? '✓' : '!' }}
        </span>
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
  gap: 0.9rem;
}

.card {
  padding: 0.95rem 1rem;
}

.section-block {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

.section-title {
  margin: 0;
  font-size: 0.95rem;
  font-weight: 700;
  display: flex;
  align-items: center;
  gap: 0.45rem;
}

.section-heading {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 0.75rem;
}

.section-hint {
  margin: 0.2rem 0 0;
  font-size: 0.75rem;
  color: var(--text-muted);
}

.match-summary {
  display: flex;
  flex-direction: column;
  gap: 0.7rem;
  border-color: rgba(249, 115, 22, 0.28);
  background:
    linear-gradient(135deg, rgba(249, 115, 22, 0.1), transparent 42%),
    var(--surface);
}

.summary-top {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 0.75rem;
}

.summary-kicker {
  margin: 0;
  font-size: 0.7rem;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  color: var(--text-muted);
}

.summary-title {
  margin: 0.2rem 0 0;
  font-size: 1.15rem;
  display: flex;
  align-items: center;
  gap: 0.4rem;
  flex-wrap: wrap;
}

.summary-icon {
  font-size: 1.05rem;
}

.summary-sub {
  font-weight: 500;
  color: var(--text-muted);
  font-size: 0.95rem;
}

.summary-desc {
  margin: 0.25rem 0 0;
  font-size: 0.82rem;
  color: var(--text-muted);
}

.preset-pill {
  flex-shrink: 0;
  font-size: 0.7rem;
  font-weight: 700;
  letter-spacing: 0.04em;
  text-transform: uppercase;
  padding: 0.28rem 0.55rem;
  border-radius: 999px;
  color: #fdba74;
  background: rgba(249, 115, 22, 0.16);
  border: 1px solid rgba(249, 115, 22, 0.3);
}

.preset-pill.custom {
  color: var(--text-muted);
  background: rgba(148, 163, 184, 0.12);
  border-color: rgba(148, 163, 184, 0.25);
}

.chip-row {
  display: flex;
  flex-wrap: wrap;
  gap: 0.35rem;
}

.chip {
  font-size: 0.72rem;
  font-weight: 600;
  padding: 0.22rem 0.5rem;
  border-radius: 999px;
  color: var(--text-muted);
  background: rgba(148, 163, 184, 0.12);
  border: 1px solid rgba(148, 163, 184, 0.18);
}

.chip.accent {
  color: #fdba74;
  background: rgba(249, 115, 22, 0.14);
  border-color: rgba(249, 115, 22, 0.28);
}

.chip.warn {
  color: #fca5a5;
  background: rgba(239, 68, 68, 0.14);
  border-color: rgba(239, 68, 68, 0.28);
}

.play-style {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 0.5rem;
}

.style-option {
  display: flex;
  align-items: flex-start;
  gap: 0.55rem;
  text-align: left;
  padding: 0.7rem 0.75rem;
  border-radius: 10px;
  border: 1px solid var(--border);
  background: var(--surface);
  color: var(--text);
  cursor: pointer;
  transition: border-color 0.15s ease, background 0.15s ease;
}

.style-option.active {
  border-color: rgba(249, 115, 22, 0.75);
  background: rgba(249, 115, 22, 0.1);
}

.style-icon {
  font-size: 1.15rem;
  line-height: 1.2;
}

.style-copy {
  display: flex;
  flex-direction: column;
  gap: 0.15rem;
  min-width: 0;
}

.style-label {
  font-weight: 700;
  font-size: 0.88rem;
}

.style-desc {
  font-size: 0.72rem;
  color: var(--text-muted);
  line-height: 1.3;
}

.preset-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(148px, 1fr));
  gap: 0.5rem;
}

.preset-card {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
  text-align: left;
  padding: 0.7rem 0.75rem;
  border-radius: 10px;
  border: 1px solid var(--border);
  background: rgba(12, 14, 18, 0.35);
  color: var(--text);
  cursor: pointer;
  transition: border-color 0.15s ease, transform 0.15s ease, box-shadow 0.15s ease;
}

.preset-card:hover {
  border-color: rgba(249, 115, 22, 0.45);
  transform: translateY(-1px);
}

.preset-card.selected {
  border-color: rgba(249, 115, 22, 0.85);
  box-shadow: 0 0 0 1px rgba(249, 115, 22, 0.28);
  background: rgba(249, 115, 22, 0.1);
}

.preset-name {
  font-weight: 700;
  font-size: 0.88rem;
}

.preset-desc {
  font-size: 0.72rem;
  color: var(--text-muted);
  line-height: 1.35;
}

.mode-row {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 0.45rem;
}

.mode-chip {
  display: flex;
  flex-direction: column;
  gap: 0.12rem;
  text-align: left;
  padding: 0.65rem 0.7rem;
  border-radius: 10px;
  border: 1px solid var(--border);
  background: rgba(12, 14, 18, 0.35);
  color: var(--text);
  cursor: pointer;
}

.mode-chip.selected {
  border-color: rgba(249, 115, 22, 0.8);
  background: rgba(249, 115, 22, 0.1);
}

.mode-icon {
  font-size: 1rem;
}

.mode-label {
  font-weight: 700;
  font-size: 0.85rem;
}

.mode-hint {
  font-size: 0.7rem;
  color: var(--text-muted);
  line-height: 1.3;
}

.settings-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(140px, 1fr));
  gap: 0.65rem;
}

.primary-grid {
  margin-top: 0.15rem;
}

.field {
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
}

.setting-label {
  font-size: 0.8rem;
  color: var(--text-muted);
}

.speed-select {
  width: 100%;
  padding: 0.45rem 0.6rem;
  border-radius: 8px;
  border: 1px solid var(--border);
  background: var(--surface);
  color: var(--text);
}

.advanced-toggle {
  align-self: flex-start;
  display: inline-flex;
  align-items: center;
  gap: 0.35rem;
  margin-top: 0.15rem;
  padding: 0.35rem 0.15rem;
  border: none;
  background: transparent;
  color: #fdba74;
  font-size: 0.82rem;
  font-weight: 600;
  cursor: pointer;
}

.caret {
  display: inline-block;
  transition: transform 0.15s ease;
}

.caret.open {
  transform: rotate(180deg);
}

.advanced-panel {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
  padding: 0.75rem;
  border-radius: 10px;
  border: 1px dashed rgba(249, 115, 22, 0.28);
  background: rgba(249, 115, 22, 0.04);
}

.rule-toggles {
  display: flex;
  flex-wrap: wrap;
  gap: 0.65rem 1.1rem;
}

.checkbox-label {
  display: flex;
  align-items: center;
  gap: 0.45rem;
  font-size: 0.85rem;
  cursor: pointer;
}

.map-block {
  display: flex;
  flex-direction: column;
  gap: 0.7rem;
}

.map-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 0.75rem;
}

.map-size {
  font-size: 0.75rem;
  color: var(--text-muted);
  white-space: nowrap;
  padding-top: 0.15rem;
}

.map-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(132px, 1fr));
  gap: 0.5rem;
}

.map-card {
  text-align: left;
  padding: 0.65rem 0.7rem;
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
    transform 0.15s ease,
    box-shadow 0.15s ease;
}

.map-card:hover:not(:disabled) {
  border-color: rgba(var(--map-accent-rgb, 249, 115, 22), 0.5);
  transform: translateY(-1px);
}

.map-card.selected {
  border-color: rgba(var(--map-accent-rgb, 249, 115, 22), 0.85);
  box-shadow: 0 0 0 1px rgba(var(--map-accent-rgb, 249, 115, 22), 0.28);
}

.map-card.disabled {
  cursor: default;
}

.map-swatch {
  display: flex;
  gap: 4px;
  margin-bottom: 0.4rem;
}

.swatch-floor,
.swatch-hard,
.swatch-soft {
  width: 12px;
  height: 12px;
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
  gap: 0.35rem;
}

.map-name {
  font-weight: 700;
  font-size: 0.85rem;
}

.diff-badge {
  font-size: 0.62rem;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  padding: 0.1rem 0.32rem;
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

.solo-notice {
  display: flex;
  gap: 0.75rem;
  align-items: flex-start;
}

.solo-icon {
  font-size: 1.25rem;
  line-height: 1.2;
}

.solo-title {
  margin: 0;
  font-weight: 700;
  font-size: 0.92rem;
}

.solo-copy {
  margin: 0.25rem 0 0;
  font-size: 0.84rem;
  color: var(--text-muted);
  line-height: 1.4;
}

.count-pill {
  font-size: 0.72rem;
  font-weight: 700;
  padding: 0.12rem 0.4rem;
  border-radius: 999px;
  color: var(--text-muted);
  background: rgba(148, 163, 184, 0.14);
}

.balance-btn {
  font-size: 0.78rem;
  padding: 0.3rem 0.6rem;
}

.player-list {
  display: flex;
  flex-direction: column;
  gap: 0.45rem;
}

.player-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.65rem;
  padding: 0.45rem 0.55rem;
  border-radius: 8px;
  background: rgba(12, 14, 18, 0.28);
}

.player-row.me {
  outline: 1px solid rgba(249, 115, 22, 0.35);
  background: rgba(249, 115, 22, 0.08);
}

.player-info {
  display: flex;
  align-items: center;
  gap: 0.4rem;
  flex-wrap: wrap;
  min-width: 0;
}

.nickname {
  font-weight: 600;
  font-size: 0.9rem;
}

.badge {
  font-size: 0.68rem;
  padding: 0.08rem 0.38rem;
  border-radius: 999px;
  background: rgba(148, 163, 184, 0.18);
  color: var(--text-muted);
}

.badge.you {
  background: rgba(249, 115, 22, 0.2);
  color: #fb923c;
}

.badge.host {
  background: rgba(59, 130, 246, 0.2);
  color: #60a5fa;
}

.badge.ai {
  background: rgba(168, 85, 247, 0.18);
  color: #c084fc;
}

.team-boards {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 0.65rem;
}

.team-board {
  display: flex;
  flex-direction: column;
  gap: 0.55rem;
  padding: 0.75rem;
  border-radius: 10px;
  border: 1px solid var(--border);
}

.team-board.red {
  border-color: rgba(239, 68, 68, 0.35);
  background: linear-gradient(160deg, rgba(239, 68, 68, 0.12), transparent 60%);
}

.team-board.blue {
  border-color: rgba(59, 130, 246, 0.35);
  background: linear-gradient(160deg, rgba(59, 130, 246, 0.12), transparent 60%);
}

.team-header {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
}

.team-header h4 {
  margin: 0;
  font-size: 0.95rem;
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
  gap: 0.4rem;
  min-height: 2.75rem;
}

.team-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  flex-shrink: 0;
}

.team-dot.red {
  background: #ef4444;
  box-shadow: 0 0 8px rgba(239, 68, 68, 0.55);
}

.team-dot.blue {
  background: #3b82f6;
  box-shadow: 0 0 8px rgba(59, 130, 246, 0.55);
}

.team-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 0.3rem;
  justify-content: flex-end;
}

.team-btn,
.remove-btn {
  font-size: 0.72rem;
  padding: 0.22rem 0.48rem;
}

.team-btn.red-btn {
  border-color: rgba(239, 68, 68, 0.4);
  color: #fca5a5;
}

.team-btn.blue-btn {
  border-color: rgba(59, 130, 246, 0.4);
  color: #93c5fd;
}

.empty-team {
  font-size: 0.78rem;
  color: var(--text-muted);
  padding: 0.35rem 0.15rem;
}

.unassigned {
  display: flex;
  flex-direction: column;
  gap: 0.45rem;
  padding: 0.7rem;
  border-radius: 10px;
  border: 1px dashed rgba(148, 163, 184, 0.35);
}

.unassigned-header {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 0.75rem;
  flex-wrap: wrap;
}

.add-ai-btn {
  align-self: flex-start;
  font-size: 0.8rem;
}

.validation-banner {
  display: flex;
  gap: 0.75rem;
  align-items: flex-start;
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

@media (max-width: 720px) {
  .play-style,
  .team-boards,
  .mode-row {
    grid-template-columns: 1fr;
  }
}
</style>
