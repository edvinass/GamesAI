<script setup lang="ts">
import { computed } from 'vue'
import type { Room } from '@/types'

interface MapPreview {
  id: string
  name: string
  description?: string
  difficulty?: string
  width: number
  height: number
  checkpoint_count?: number
  walls: Array<number[] | { x: number; y: number; dir: string }>
  checkpoints: number[][]
  antenna: number[]
  pits?: number[][]
  conveyors?: Array<{ x: number; y: number }>
  lasers?: Array<{ x: number; y: number }>
  repairs?: number[][]
  upgrades?: number[][]
  starts?: Array<{ x: number; y: number; facing: string }>
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
const mapId = defineModel<string>('mapId', { required: true })
const registerSize = defineModel<number>('registerSize', { required: true })
const aiDifficulty = defineModel<string>('aiDifficulty', { required: true })

const emit = defineEmits<{
  addAi: []
  remove: [id: string]
}>()

const FALLBACK_MAPS: MapPreview[] = [
  {
    id: 'factory_floor',
    name: 'Factory Floor',
    description: 'Winding halls with mid-board chokepoints — classic race.',
    difficulty: 'standard',
    width: 13,
    height: 11,
    checkpoint_count: 3,
    walls: [],
    checkpoints: [],
    antenna: [6, 5],
  },
]

const mapOptions = computed<MapPreview[]>(() => {
  const raw = props.room.settings?.available_maps
  if (!Array.isArray(raw) || raw.length === 0) return FALLBACK_MAPS
  return raw
    .filter((m): m is Record<string, unknown> => !!m && typeof m === 'object')
    .map((m) => ({
      id: String(m.id ?? ''),
      name: String(m.name ?? m.id ?? 'Map'),
      description: String(m.description ?? ''),
      difficulty: String(m.difficulty ?? 'standard'),
      width: Number(m.width ?? 10),
      height: Number(m.height ?? 10),
      checkpoint_count: Number(
        m.checkpoint_count ?? (Array.isArray(m.checkpoints) ? m.checkpoints.length : 0),
      ),
      walls: Array.isArray(m.walls) ? (m.walls as MapPreview['walls']) : [],
      checkpoints: Array.isArray(m.checkpoints) ? (m.checkpoints as number[][]) : [],
      antenna: Array.isArray(m.antenna) ? (m.antenna as number[]) : [0, 0],
      pits: Array.isArray(m.pits) ? (m.pits as number[][]) : [],
      conveyors: Array.isArray(m.conveyors) ? (m.conveyors as Array<{ x: number; y: number }>) : [],
      lasers: Array.isArray(m.lasers) ? (m.lasers as Array<{ x: number; y: number }>) : [],
      repairs: Array.isArray(m.repairs) ? (m.repairs as number[][]) : [],
      upgrades: Array.isArray(m.upgrades) ? (m.upgrades as number[][]) : [],
      starts: Array.isArray(m.starts)
        ? (m.starts as Array<{ x: number; y: number; facing: string }>)
        : [],
    }))
    .filter((m) => m.id)
})

const selectedMap = computed(
  () => mapOptions.value.find((m) => m.id === mapId.value) ?? mapOptions.value[0],
)

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

const DIFFICULTY_LABEL: Record<string, string> = {
  easy: 'Easy',
  standard: 'Standard',
  hard: 'Hard',
  long: 'Long',
}

function cellKind(map: MapPreview, x: number, y: number): string {
  if (map.pits?.some(([px, py]) => px === x && py === y)) return 'pit'
  if (map.checkpoints.some(([cx, cy]) => cx === x && cy === y)) return 'checkpoint'
  if (map.antenna[0] === x && map.antenna[1] === y) return 'antenna'
  if (map.lasers?.some((l) => l.x === x && l.y === y)) return 'laser'
  if (map.conveyors?.some((c) => c.x === x && c.y === y)) return 'conveyor'
  if (map.repairs?.some(([rx, ry]) => rx === x && ry === y)) return 'repair'
  if (map.upgrades?.some(([ux, uy]) => ux === x && uy === y)) return 'upgrade'
  if (map.starts?.some((s) => s.x === x && s.y === y)) return 'start'
  return 'floor'
}

function selectMap(id: string) {
  if (!props.isHost) return
  mapId.value = id
}
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
        <div class="map-grid" role="listbox" :aria-label="'Select map'">
          <button
            v-for="opt in mapOptions"
            :key="opt.id"
            type="button"
            class="map-card"
            :class="{ selected: mapId === opt.id }"
            role="option"
            :aria-selected="mapId === opt.id"
            @click="selectMap(opt.id)"
          >
            <div
              class="map-preview"
              :style="{
                gridTemplateColumns: `repeat(${opt.width}, 1fr)`,
                gridTemplateRows: `repeat(${opt.height}, 1fr)`,
                aspectRatio: `${opt.width} / ${opt.height}`,
              }"
            >
              <template v-for="y in opt.height" :key="'py-' + y">
                <span
                  v-for="x in opt.width"
                  :key="`${opt.id}-${x - 1}-${y - 1}`"
                  class="preview-cell"
                  :class="cellKind(opt, x - 1, y - 1)"
                />
              </template>
            </div>
            <div class="map-meta">
              <span class="map-name">{{ opt.name }}</span>
              <span class="map-tags">
                <span class="map-tag">{{ DIFFICULTY_LABEL[opt.difficulty || 'standard'] || opt.difficulty }}</span>
                <span class="map-tag">{{ opt.width }}×{{ opt.height }}</span>
                <span class="map-tag">{{ opt.checkpoint_count ?? opt.checkpoints.length }} CP</span>
              </span>
              <span class="map-desc">{{ opt.description }}</span>
            </div>
          </button>
        </div>
        <p v-if="selectedMap" class="map-selected-hint">
          Selected: <strong>{{ selectedMap.name }}</strong>
        </p>
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

    <div v-else-if="selectedMap" class="guest-map card">
      <span class="setting-label">Race map</span>
      <p class="guest-map-name">{{ selectedMap.name }}</p>
      <p class="map-desc">{{ selectedMap.description }}</p>
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

.map-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(11.5rem, 1fr));
  gap: 0.65rem;
}

.map-card {
  display: flex;
  flex-direction: column;
  gap: 0.55rem;
  padding: 0.65rem;
  border-radius: 10px;
  border: 1px solid var(--border);
  background: var(--surface-elevated, var(--surface));
  color: inherit;
  text-align: left;
  cursor: pointer;
  transition: border-color 0.15s ease, box-shadow 0.15s ease, transform 0.15s ease;
}

.map-card:hover {
  border-color: color-mix(in srgb, var(--accent, #3b82f6) 55%, var(--border));
  transform: translateY(-1px);
}

.map-card.selected {
  border-color: var(--accent, #3b82f6);
  box-shadow: 0 0 0 1px color-mix(in srgb, var(--accent, #3b82f6) 40%, transparent);
}

.map-preview {
  display: grid;
  width: 100%;
  gap: 1px;
  background: #3a424e;
  border-radius: 3px;
  overflow: hidden;
  border: 2px solid #1c1f24;
}

.preview-cell {
  min-height: 0;
  min-width: 0;
  aspect-ratio: 1;
}

.preview-cell.floor {
  background: #9aa3af;
}

.preview-cell.pit {
  background:
    repeating-conic-gradient(#f5c518 0% 25%, #1a1a1a 0% 50%) 0 0 / 6px 6px;
}

.preview-cell.checkpoint {
  background: #dc2626;
}

.preview-cell.antenna {
  background: #c9a24a;
}

.preview-cell.conveyor {
  background:
    repeating-linear-gradient(
      90deg,
      #111418 0 2px,
      #4b5563 2px 4px
    );
}

.preview-cell.laser {
  background: #ef4444;
}

.preview-cell.repair {
  background: #f5c518;
}

.preview-cell.upgrade {
  background: #3b82f6;
}

.preview-cell.start {
  background: #22c55e;
}

.map-meta {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
}

.map-name {
  font-weight: 650;
  font-size: 0.95rem;
}

.map-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 0.3rem;
}

.map-tag {
  font-size: 0.7rem;
  padding: 0.1rem 0.4rem;
  border-radius: 999px;
  background: var(--surface);
  color: var(--text-muted);
  border: 1px solid var(--border);
}

.map-desc {
  margin: 0;
  font-size: 0.78rem;
  color: var(--text-muted);
  line-height: 1.35;
}

.map-selected-hint {
  margin: 0.15rem 0 0;
  font-size: 0.85rem;
  color: var(--text-muted);
}

.guest-map-name {
  margin: 0.2rem 0;
  font-weight: 650;
  font-size: 1.05rem;
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
