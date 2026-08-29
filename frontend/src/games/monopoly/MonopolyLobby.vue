<script setup lang="ts">
import { computed } from 'vue'
import type { Room } from '@/types'
import { COLOR_HEX } from './boardData'

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
const startingCash = defineModel<number>('startingCash', { required: true })
const aiDifficulty = defineModel<string>('aiDifficulty', { required: true })
const soloAiDifficulties = defineModel<string[]>('soloAiDifficulties', { required: true })

const emit = defineEmits<{
  addAi: []
  remove: [id: string]
  setAiDifficulty: [playerId: string, difficulty: string]
}>()

type GameMode = 'multiplayer' | 'solo_practice'

const TOKEN_COLORS = ['#e74c3c', '#3498db', '#2ecc71', '#f1c40f', '#9b59b6', '#e67e22']
const TOKEN_GLYPHS = ['🎩', '🚗', '🐕', '⚔', '🚢', '🐈']

const gameModes: { id: GameMode; label: string; description: string; icon: string }[] = [
  {
    id: 'multiplayer',
    label: 'Multiplayer',
    description: '2–6 players around the board',
    icon: '🏠',
  },
  {
    id: 'solo_practice',
    label: 'Solo practice',
    description: 'You vs 2 AI tycoons',
    icon: '🤖',
  },
]

const cashPresets = [
  { id: 'lean', label: 'Lean', cash: 1000, hint: 'Tighter money, faster bankruptcies' },
  { id: 'classic', label: 'Classic', cash: 1500, hint: 'Standard starting cash' },
  { id: 'rich', label: 'Rich', cash: 2000, hint: 'More building, longer games' },
] as const

const difficultyOptions = [
  {
    value: 'easy',
    label: 'Easy',
    detail: 'Loose buyer',
    hint: 'Buys often, soft auctions, rarely trades hard.',
  },
  {
    value: 'medium',
    label: 'Medium',
    detail: 'Balanced',
    hint: 'Solid buys, builds sets, sensible jail choices.',
  },
  {
    value: 'hard',
    label: 'Hard',
    detail: 'Aggressive',
    hint: 'Hunts monopolies, pushes auctions, sharper trades.',
  },
] as const

const colorRibbon = [
  'brown',
  'light_blue',
  'pink',
  'orange',
  'red',
  'yellow',
  'green',
  'dark_blue',
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

const activeMode = computed(
  () => gameModes.find((mode) => mode.id === gameMode.value) ?? gameModes[0],
)

const activeDifficulty = computed(
  () => difficultyOptions.find((opt) => opt.value === aiDifficulty.value) ?? difficultyOptions[1],
)

const activeCashPreset = computed(
  () => cashPresets.find((p) => p.cash === startingCash.value)?.id ?? 'custom',
)

const seatSlots = computed(() => {
  const total = soloPractice.value ? 3 : maxPlayers.value
  const players = props.room.players
  const humanIndex = Math.max(
    0,
    players.findIndex((p) => p.id === props.currentPlayerId || !p.is_ai),
  )
  return Array.from({ length: total }, (_, index) => {
    const player = players[index] ?? null
    const angle = (index / total) * 2 * Math.PI - Math.PI / 2
    let soloGhost: { nickname: string; difficulty: string } | null = null
    if (soloPractice.value && !player && index !== humanIndex) {
      const ghostOrder = Array.from({ length: total }, (_, i) => i).filter((i) => i !== humanIndex)
      const ghostIdx = ghostOrder.indexOf(index)
      soloGhost = {
        nickname: `Opponent ${ghostIdx + 1}`,
        difficulty: soloAiDifficulties.value[ghostIdx] ?? 'medium',
      }
    }
    return {
      index,
      player,
      soloGhost,
      style: {
        left: `${50 + 40 * Math.cos(angle)}%`,
        top: `${50 + 36 * Math.sin(angle)}%`,
      },
    }
  })
})

const seatCountLabel = computed(() => {
  if (soloPractice.value) return 'You + 2 AI'
  return `${playerCount.value} / ${maxPlayers.value} seats`
})

function playerAiDifficulty(player: { id: string; ai_difficulty?: string }): string {
  const map = (props.room.settings?.ai_difficulties ?? {}) as Record<string, string>
  return player.ai_difficulty ?? map[player.id] ?? aiDifficulty.value
}

function updateSoloAiDifficulty(index: number, difficulty: string) {
  const next = [...soloAiDifficulties.value]
  while (next.length < 2) next.push('medium')
  next[index] = difficulty
  soloAiDifficulties.value = next.slice(0, 2)
}

function seatInitial(nickname: string): string {
  return nickname.trim().charAt(0).toUpperCase() || '?'
}
</script>

<template>
  <div class="mono-lobby">
    <header class="hero">
      <div class="hero-ribbon" aria-hidden="true">
        <span v-for="c in colorRibbon" :key="c" :style="{ background: COLOR_HEX[c] }" />
      </div>
      <div class="hero-copy">
        <p class="eyebrow">Property trading</p>
        <h1 class="title">MONOPOLY</h1>
        <p class="subtitle">
          {{ activeMode.description }} · start with
          <strong>${{ startingCash.toLocaleString() }}</strong>
        </p>
      </div>
    </header>

    <div class="lobby-grid">
      <section v-if="isHost" class="card settings-card">
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

        <h2 class="section-title">Starting cash</h2>
        <div class="preset-row" role="radiogroup" aria-label="Starting cash">
          <button
            v-for="preset in cashPresets"
            :key="preset.id"
            type="button"
            class="preset-chip"
            :class="{ active: activeCashPreset === preset.id }"
            role="radio"
            :aria-checked="activeCashPreset === preset.id"
            @click="startingCash = preset.cash"
          >
            <span class="preset-label">{{ preset.label }}</span>
            <span class="preset-detail">${{ preset.cash.toLocaleString() }}</span>
          </button>
        </div>
        <p class="hint">
          {{ cashPresets.find((p) => p.id === activeCashPreset)?.hint ?? 'Custom starting cash' }}
        </p>

        <template v-if="soloPractice">
          <div class="difficulty-header">
            <h2 class="section-title">AI opponents</h2>
            <span class="difficulty-hint">Set strength for each bot.</span>
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
        </template>
        <template v-else>
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
          <p class="hint">New AI seats start at this level. Override per seat on the board.</p>
        </template>
      </section>

      <section class="card table-card">
        <div class="table-header">
          <h2 class="section-title">The board</h2>
          <span class="count">{{ seatCountLabel }}</span>
        </div>

        <div class="table-stage">
          <div class="felt" :class="{ solo: soloPractice }">
            <div class="felt-brand">MONOPOLY</div>
            <div class="felt-sub">{{ soloPractice ? 'Solo practice' : 'Multiplayer' }}</div>
            <div
              v-for="slot in seatSlots"
              :key="slot.index"
              class="seat"
              :class="{
                empty: !slot.player && !slot.soloGhost,
                filled: Boolean(slot.player),
                ghost: Boolean(slot.soloGhost),
              }"
              :style="slot.style"
            >
              <template v-if="slot.player">
                <span
                  class="seat-token"
                  :style="{ background: TOKEN_COLORS[slot.index % TOKEN_COLORS.length] }"
                >
                  {{ TOKEN_GLYPHS[slot.index % TOKEN_GLYPHS.length] }}
                </span>
                <span class="seat-name">{{ slot.player.nickname }}</span>
                <span v-if="slot.player.id === hostPlayerId" class="seat-tag">Host</span>
                <span v-else-if="slot.player.is_ai" class="seat-tag ai">AI</span>
                <select
                  v-if="isHost && slot.player.is_ai && !soloPractice"
                  class="seat-diff"
                  :value="playerAiDifficulty(slot.player)"
                  @change="
                    emit(
                      'setAiDifficulty',
                      slot.player!.id,
                      ($event.target as HTMLSelectElement).value,
                    )
                  "
                >
                  <option v-for="opt in difficultyOptions" :key="opt.value" :value="opt.value">
                    {{ opt.label }}
                  </option>
                </select>
                <button
                  v-if="isHost && (slot.player.is_ai || slot.player.id !== currentPlayerId)"
                  type="button"
                  class="seat-remove"
                  @click="emit('remove', slot.player!.id)"
                >
                  ×
                </button>
              </template>
              <template v-else-if="slot.soloGhost">
                <span
                  class="seat-token ghost-tok"
                  :style="{ background: TOKEN_COLORS[slot.index % TOKEN_COLORS.length] }"
                >
                  {{ TOKEN_GLYPHS[slot.index % TOKEN_GLYPHS.length] }}
                </span>
                <span class="seat-name">{{ slot.soloGhost.nickname }}</span>
                <span class="seat-tag ai">AI · {{ slot.soloGhost.difficulty }}</span>
              </template>
              <template v-else>
                <span class="seat-empty-ring">{{ slot.index + 1 }}</span>
                <span class="seat-empty-label">Open</span>
              </template>
            </div>
          </div>
        </div>

        <ul class="roster">
          <li v-for="(player, index) in room.players" :key="player.id" class="roster-row">
            <span
              class="roster-tok"
              :style="{ background: TOKEN_COLORS[index % TOKEN_COLORS.length] }"
            >
              {{ seatInitial(player.nickname) }}
            </span>
            <div class="roster-info">
              <strong>{{ player.nickname }}</strong>
              <span v-if="player.id === hostPlayerId" class="tag">Host</span>
              <span v-if="player.is_ai" class="tag ai">AI · {{ playerAiDifficulty(player) }}</span>
            </div>
          </li>
        </ul>

        <button
          v-if="canAddAi"
          type="button"
          class="btn-add-ai"
          @click="emit('addAi')"
        >
          Add AI player
        </button>

        <p class="validation" :class="{ ok: validationValid }">{{ validationMessage }}</p>
        <ul v-if="validationIssues.length" class="issues">
          <li v-for="issue in validationIssues" :key="issue">{{ issue }}</li>
        </ul>
      </section>
    </div>
  </div>
</template>

<style scoped>
@import url('https://fonts.googleapis.com/css2?family=Libre+Baskerville:wght@700&family=Source+Sans+3:wght@500;600;700&display=swap');

.mono-lobby {
  --felt: #0f5c3a;
  --cream: #f3e6c8;
  --accent: #c41e3a;
  --ink: #1c1812;
  max-width: 980px;
  margin: 0 auto;
  display: flex;
  flex-direction: column;
  gap: 1.25rem;
  font-family: 'Source Sans 3', system-ui, sans-serif;
  color: #f2ebe0;
}

.hero {
  position: relative;
  overflow: hidden;
  border-radius: 16px;
  background:
    radial-gradient(ellipse at 80% 20%, rgba(196, 30, 58, 0.35), transparent 45%),
    linear-gradient(135deg, #0a3d28 0%, #123828 45%, #1a221c 100%);
  border: 1px solid rgba(243, 230, 200, 0.14);
  padding: 1.4rem 1.5rem 1.5rem;
}
.hero-ribbon {
  display: flex;
  height: 8px;
  border-radius: 4px;
  overflow: hidden;
  margin-bottom: 1rem;
  box-shadow: inset 0 0 0 1px #0003;
}
.hero-ribbon span {
  flex: 1;
}
.eyebrow {
  margin: 0;
  font-size: 0.72rem;
  letter-spacing: 0.2em;
  text-transform: uppercase;
  color: #9bb89a;
}
.title {
  margin: 0.25rem 0 0.35rem;
  font-family: 'Libre Baskerville', Georgia, serif;
  font-size: clamp(1.8rem, 4vw, 2.6rem);
  letter-spacing: 0.1em;
  color: var(--accent);
  text-shadow: 1px 1px 0 rgba(255, 255, 255, 0.2);
}
.subtitle {
  margin: 0;
  color: #c8d5c0;
  font-size: 0.95rem;
}
.subtitle strong {
  color: var(--cream);
}

.lobby-grid {
  display: grid;
  grid-template-columns: 1fr 1.15fr;
  gap: 1.1rem;
  align-items: start;
}

.card {
  background: linear-gradient(180deg, #1a221c 0%, #14181f 100%);
  border: 1px solid rgba(243, 230, 200, 0.1);
  border-radius: 14px;
  padding: 1.2rem 1.3rem;
}

.section-title {
  margin: 0 0 0.7rem;
  font-size: 0.72rem;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  color: #9bb89a;
}

.mode-selector {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 0.55rem;
  margin-bottom: 1.35rem;
}
.mode-option {
  display: flex;
  gap: 0.65rem;
  align-items: flex-start;
  text-align: left;
  padding: 0.75rem;
  border-radius: 12px;
  border: 1px solid rgba(255, 255, 255, 0.1);
  background: rgba(255, 255, 255, 0.03);
  color: inherit;
  cursor: pointer;
}
.mode-option.active {
  border-color: rgba(196, 30, 58, 0.55);
  background: rgba(15, 92, 58, 0.35);
  box-shadow: inset 0 0 0 1px rgba(243, 230, 200, 0.12);
}
.mode-icon {
  font-size: 1.35rem;
  line-height: 1;
}
.mode-label {
  display: block;
  font-weight: 700;
  font-size: 0.95rem;
}
.mode-desc {
  display: block;
  font-size: 0.78rem;
  color: #9a958c;
  margin-top: 0.15rem;
}

.preset-row,
.difficulty-row {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 0.5rem;
}
.preset-chip,
.difficulty-chip {
  display: flex;
  flex-direction: column;
  gap: 0.15rem;
  align-items: flex-start;
  text-align: left;
  padding: 0.65rem 0.7rem;
  border-radius: 10px;
  border: 1px solid rgba(255, 255, 255, 0.1);
  background: rgba(255, 255, 255, 0.03);
  color: inherit;
  cursor: pointer;
}
.preset-chip.active,
.difficulty-chip.active {
  border-color: #e8c97a;
  background: rgba(232, 201, 122, 0.12);
}
.preset-label,
.diff-label {
  font-weight: 700;
  font-size: 0.9rem;
}
.preset-detail,
.diff-detail {
  font-size: 0.75rem;
  color: #9a958c;
}
.hint,
.difficulty-hint {
  margin: 0.55rem 0 1.1rem;
  font-size: 0.8rem;
  color: #8f9a88;
}
.difficulty-header {
  display: flex;
  flex-wrap: wrap;
  align-items: baseline;
  justify-content: space-between;
  gap: 0.35rem;
}
.difficulty-header .section-title {
  margin-bottom: 0;
}
.difficulty-header + .difficulty-row,
.difficulty-header + .solo-ai-grid {
  margin-top: 0.65rem;
}

.solo-ai-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 0.65rem;
}
.solo-ai-field,
.field-label {
  display: flex;
  flex-direction: column;
  gap: 0.3rem;
  font-size: 0.8rem;
  color: #b0aaa0;
}
.difficulty-select {
  background: #12161a;
  color: #eee;
  border: 1px solid rgba(255, 255, 255, 0.15);
  border-radius: 8px;
  padding: 0.45rem 0.55rem;
  font-family: inherit;
}

.table-header {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
}
.count {
  font-size: 0.85rem;
  color: #9a958c;
}

.table-stage {
  position: relative;
  width: 100%;
  aspect-ratio: 1.15;
  margin: 0.4rem 0 1rem;
}
.felt {
  position: absolute;
  inset: 8%;
  border-radius: 50%;
  background:
    radial-gradient(circle at 50% 45%, rgba(255, 255, 255, 0.08), transparent 55%),
    radial-gradient(circle at 50% 50%, #147a4a, var(--felt) 70%);
  border: 10px solid #5c3a1e;
  box-shadow:
    inset 0 0 40px rgba(0, 0, 0, 0.35),
    0 10px 28px rgba(0, 0, 0, 0.4);
  display: grid;
  place-items: center;
}
.felt-brand {
  font-family: 'Libre Baskerville', Georgia, serif;
  font-size: clamp(1.1rem, 3vw, 1.6rem);
  letter-spacing: 0.12em;
  color: var(--accent);
  text-shadow: 1px 1px 0 rgba(255, 255, 255, 0.25);
  transform: rotate(-18deg);
}
.felt-sub {
  position: absolute;
  bottom: 22%;
  font-size: 0.7rem;
  letter-spacing: 0.16em;
  text-transform: uppercase;
  color: rgba(243, 230, 200, 0.65);
}

.seat {
  position: absolute;
  transform: translate(-50%, -50%);
  width: 5.6rem;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 0.15rem;
  z-index: 2;
}
.seat-token {
  width: 2.4rem;
  height: 2.4rem;
  border-radius: 50%;
  display: grid;
  place-items: center;
  font-size: 1.05rem;
  border: 2px solid #fff;
  box-shadow: 0 3px 8px #0006;
  background: #444;
}
.seat-name {
  max-width: 5.4rem;
  font-size: 0.72rem;
  font-weight: 700;
  text-align: center;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  background: rgba(0, 0, 0, 0.45);
  padding: 0.1rem 0.35rem;
  border-radius: 4px;
}
.seat-tag {
  font-size: 0.58rem;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  padding: 0.05rem 0.3rem;
  border-radius: 3px;
  background: rgba(232, 201, 122, 0.25);
  color: #e8c97a;
}
.seat-tag.ai {
  background: rgba(91, 141, 239, 0.3);
  color: #9ec5f0;
}
.seat-diff {
  font-size: 0.65rem;
  background: #12161a;
  color: #eee;
  border: 1px solid rgba(255, 255, 255, 0.2);
  border-radius: 4px;
  padding: 0.1rem;
  max-width: 4.5rem;
}
.seat-remove {
  position: absolute;
  top: -0.2rem;
  right: 0.4rem;
  width: 1.2rem;
  height: 1.2rem;
  border-radius: 50%;
  border: none;
  background: #a82020;
  color: #fff;
  cursor: pointer;
  font-size: 0.85rem;
  line-height: 1;
}
.seat-empty-ring {
  width: 2.2rem;
  height: 2.2rem;
  border-radius: 50%;
  border: 2px dashed rgba(243, 230, 200, 0.35);
  display: grid;
  place-items: center;
  color: rgba(243, 230, 200, 0.45);
  font-size: 0.8rem;
  font-weight: 700;
}
.seat-empty-label {
  font-size: 0.65rem;
  color: rgba(243, 230, 200, 0.4);
  text-transform: uppercase;
  letter-spacing: 0.08em;
}
.seat.ghost .seat-name {
  opacity: 0.95;
}
.ghost-tok {
  outline: 2px dashed rgba(255, 255, 255, 0.4);
  outline-offset: 2px;
}

.roster {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 0.4rem;
}
.roster-row {
  display: flex;
  align-items: center;
  gap: 0.6rem;
  padding: 0.4rem 0.5rem;
  border-radius: 8px;
  background: rgba(255, 255, 255, 0.03);
}
.roster-tok {
  width: 1.7rem;
  height: 1.7rem;
  border-radius: 50%;
  display: grid;
  place-items: center;
  font-size: 0.75rem;
  font-weight: 700;
  color: #fff;
  border: 1px solid #fff6;
}
.roster-info {
  display: flex;
  align-items: center;
  gap: 0.4rem;
  flex-wrap: wrap;
  font-size: 0.88rem;
}
.tag {
  font-size: 0.65rem;
  padding: 0.1rem 0.35rem;
  border-radius: 4px;
  background: rgba(232, 201, 122, 0.2);
  color: #e8c97a;
  text-transform: capitalize;
}
.tag.ai {
  background: rgba(91, 141, 239, 0.25);
  color: #9ec5f0;
}

.btn-add-ai {
  margin-top: 0.85rem;
  width: 100%;
  padding: 0.7rem;
  border-radius: 10px;
  border: 1px dashed rgba(243, 230, 200, 0.35);
  background: rgba(15, 92, 58, 0.25);
  color: var(--cream);
  font-weight: 700;
  cursor: pointer;
  font-family: inherit;
}
.btn-add-ai:hover {
  background: rgba(15, 92, 58, 0.4);
}

.validation {
  margin: 0.85rem 0 0;
  font-size: 0.9rem;
  color: #d09070;
}
.validation.ok {
  color: #7dba8a;
}
.issues {
  margin: 0.35rem 0 0;
  padding-left: 1.1rem;
  color: #b09080;
  font-size: 0.8rem;
}

@media (max-width: 820px) {
  .lobby-grid {
    grid-template-columns: 1fr;
  }
  .mode-selector,
  .preset-row,
  .difficulty-row,
  .solo-ai-grid {
    grid-template-columns: 1fr;
  }
  .table-stage {
    aspect-ratio: 1;
  }
}
</style>
