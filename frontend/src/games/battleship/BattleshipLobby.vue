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
const aiDifficulty = defineModel<string>('aiDifficulty', { required: true })

const emit = defineEmits<{
  addAi: []
  remove: [id: string]
}>()

type GameMode = 'multiplayer' | 'solo_practice'

const gameModes: { id: GameMode; label: string; description: string }[] = [
  {
    id: 'multiplayer',
    label: 'Match',
    description: 'You vs a friend or AI seat',
  },
  {
    id: 'solo_practice',
    label: 'Vs AI',
    description: 'You captain against the bot',
  },
]

const difficultyOptions = [
  { value: 'easy', label: 'Easy', detail: 'Random shots' },
  { value: 'medium', label: 'Medium', detail: 'Hunts hits' },
  { value: 'hard', label: 'Hard', detail: 'Sharp targeting' },
] as const

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
  () =>
    difficultyOptions.find((opt) => opt.value === aiDifficulty.value) ?? difficultyOptions[1],
)

const playerCount = computed(() => props.room.players.length)
const canAddAi = computed(
  () => props.isHost && !soloPractice.value && playerCount.value < 2,
)

const seats = computed(() => {
  const players = props.room.players
  if (soloPractice.value) {
    const human = players.find((p) => !p.is_ai) ?? null
    return [
      { key: 'you', label: 'Your fleet', player: human, pending: 'You' },
      { key: 'ai', label: 'Enemy fleet', player: null, pending: 'AI Opponent' },
    ]
  }
  return [
    {
      key: 'a',
      label: 'Captain A',
      player: players[0] ?? null,
      pending: 'Waiting…',
    },
    {
      key: 'b',
      label: 'Captain B',
      player: players[1] ?? null,
      pending: 'Open seat',
    },
  ]
})

function seatInitial(nickname: string): string {
  const cleaned = nickname.replace(/^[🤖\s]+/, '').trim()
  return cleaned.charAt(0).toUpperCase() || '?'
}
</script>

<template>
  <div class="battleship-lobby">
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
          <span class="mode-glyph" aria-hidden="true">{{ mode.id === 'multiplayer' ? '⚓' : '🛰️' }}</span>
          <span class="mode-copy">
            <span class="mode-label">{{ mode.label }}</span>
            <span class="mode-desc">{{ mode.description }}</span>
          </span>
        </button>
      </div>

      <div class="difficulty-section">
        <div class="difficulty-header">
          <h2 class="section-title">AI strength</h2>
          <span class="difficulty-hint">{{ activeDifficulty.detail }}</span>
        </div>
        <div class="difficulty-row" role="radiogroup" aria-label="AI difficulty">
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
      </div>
    </section>

    <section v-else class="mode-summary card">
      <span class="mode-glyph" aria-hidden="true">{{ activeMode.id === 'multiplayer' ? '⚓' : '🛰️' }}</span>
      <div>
        <p class="mode-summary-label">{{ activeMode.label }}</p>
        <p class="mode-summary-desc">{{ activeMode.description }}</p>
        <p class="mode-summary-diff">AI · {{ activeDifficulty.label }}</p>
      </div>
    </section>

    <section class="matchup-card card" aria-label="Matchup preview">
      <div class="matchup-header">
        <h2 class="section-title">The theater</h2>
        <span class="seat-count">
          <template v-if="soloPractice">Vs AI · {{ activeDifficulty.label }}</template>
          <template v-else>{{ playerCount }} / 2 captains</template>
        </span>
      </div>

      <div class="board-stage">
        <div class="mini-sea" aria-hidden="true">
          <div class="mini-grid">
            <span v-for="i in 100" :key="i" class="mini-cell" />
          </div>
          <div class="mini-ships">
            <span class="ship long" aria-hidden="true">
              <i class="stern" /><i class="mid" /><i class="mid bridge" /><i class="mid" /><i class="bow" />
            </span>
            <span class="ship mid-ship" aria-hidden="true">
              <i class="stern" /><i class="mid bridge" /><i class="bow" />
            </span>
            <span class="ship short" aria-hidden="true">
              <i class="stern" /><i class="bow" />
            </span>
          </div>
        </div>

        <div class="vs-column">
          <div
            v-for="seat in seats"
            :key="seat.key"
            class="seat-card"
            :class="{
              filled: Boolean(seat.player),
              empty: !seat.player,
              me: seat.player?.id === currentPlayerId,
              ai: seat.player?.is_ai || (soloPractice && seat.key === 'ai'),
            }"
          >
            <div class="seat-mark" aria-hidden="true">{{ seat.key === 'ai' || seat.player?.is_ai ? '🤖' : '🚢' }}</div>
            <div class="seat-body">
              <p class="seat-side">{{ seat.label }}</p>
              <template v-if="seat.player">
                <p class="seat-name">
                  <span class="seat-initial">{{ seatInitial(seat.player.nickname) }}</span>
                  {{ seat.player.nickname }}
                </p>
                <div class="seat-badges">
                  <span v-if="seat.player.is_ai" class="badge ai-badge">AI</span>
                  <span v-if="seat.player.id === currentPlayerId" class="badge you-badge">You</span>
                  <span v-if="seat.player.id === hostPlayerId" class="badge host-badge">Host</span>
                </div>
              </template>
              <template v-else>
                <p class="seat-pending">{{ seat.pending }}</p>
                <p v-if="soloPractice && seat.key === 'ai'" class="seat-pending-sub">
                  {{ activeDifficulty.label }} difficulty
                </p>
              </template>
            </div>
            <button
              v-if="isHost && seat.player?.is_ai && !soloPractice"
              type="button"
              class="btn-secondary remove-btn"
              @click="emit('remove', seat.player.id)"
            >
              Remove
            </button>
          </div>
        </div>
      </div>

      <div v-if="!soloPractice" class="matchup-actions">
        <button v-if="canAddAi" type="button" class="btn-secondary add-ai-btn" @click="emit('addAi')">
          + Add AI opponent
        </button>
        <p v-else-if="isHost && playerCount >= 2" class="room-full-hint">Both captains are seated.</p>
        <p v-else-if="isHost" class="arrange-hint">Share the room link or add an AI opponent.</p>
      </div>

      <p v-else class="solo-blurb">
        Starting adds one AI opponent. You place first with
        <strong>{{ activeDifficulty.label }}</strong> AI strength.
      </p>
    </section>

    <div
      v-if="!soloPractice"
      class="validation-banner card"
      :class="{ valid: validationValid, invalid: !validationValid }"
    >
      <span class="validation-icon" aria-hidden="true">{{ validationValid ? '✓' : '!' }}</span>
      <div>
        <p class="validation-message">{{ validationMessage }}</p>
        <ul v-if="!validationValid && validationIssues.length > 1" class="validation-issues">
          <li v-for="issue in validationIssues" :key="issue">{{ issue }}</li>
        </ul>
      </div>
    </div>

    <div v-else class="validation-banner card valid">
      <span class="validation-icon" aria-hidden="true">✓</span>
      <div>
        <p class="validation-message">Ready for solo practice against AI</p>
      </div>
    </div>
  </div>
</template>

<style scoped>
.battleship-lobby {
  --sea: #1a6b7a;
  --sea-deep: #0d3d4a;
  --sea-glow: rgba(45, 156, 170, 0.22);
  --hull: #c4a574;
  display: flex;
  flex-direction: column;
  gap: 1rem;
  animation: battleshipLobbyIn 0.45s var(--ease-smooth) 0.06s backwards;
}

@keyframes battleshipLobbyIn {
  from {
    opacity: 0;
    transform: translateY(10px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
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
  gap: 0.7rem;
  padding: 0.9rem 0.95rem;
  border-radius: 12px;
  border: 1px solid var(--border);
  background: var(--surface-hover);
  color: var(--text);
  text-align: left;
  cursor: pointer;
  transition:
    border-color 0.2s,
    background 0.2s,
    transform 0.2s var(--ease-smooth);
}

.mode-option:hover {
  border-color: rgba(45, 156, 170, 0.45);
  transform: translateY(-1px);
}

.mode-option.active {
  border-color: var(--sea);
  background: linear-gradient(145deg, rgba(45, 156, 170, 0.16), rgba(13, 61, 74, 0.2));
  box-shadow: 0 0 0 1px rgba(45, 156, 170, 0.18);
}

.mode-glyph {
  width: 2.4rem;
  height: 2.4rem;
  border-radius: 10px;
  display: grid;
  place-items: center;
  flex-shrink: 0;
  background: rgba(10, 14, 23, 0.45);
  border: 1px solid rgba(255, 255, 255, 0.06);
  font-size: 1.1rem;
}

.mode-copy {
  display: flex;
  flex-direction: column;
  gap: 0.2rem;
  min-width: 0;
}

.mode-label {
  font-weight: 650;
  font-size: 0.95rem;
}

.mode-desc {
  font-size: 0.8rem;
  color: var(--text-muted);
  line-height: 1.35;
}

.difficulty-section {
  display: flex;
  flex-direction: column;
  gap: 0.65rem;
}

.difficulty-header {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 0.75rem;
}

.difficulty-hint {
  font-size: 0.75rem;
  color: var(--text-muted);
}

.difficulty-row {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 0.55rem;
}

.difficulty-chip {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 0.15rem;
  padding: 0.7rem 0.75rem;
  border-radius: 10px;
  border: 1px solid var(--border);
  background: var(--bg);
  color: var(--text);
  text-align: left;
  cursor: pointer;
  transition:
    border-color 0.2s,
    background 0.2s,
    transform 0.15s var(--ease-smooth);
}

.difficulty-chip:hover {
  border-color: rgba(45, 156, 170, 0.4);
  transform: translateY(-1px);
}

.difficulty-chip.active {
  border-color: var(--sea);
  background: rgba(45, 156, 170, 0.12);
  box-shadow: inset 0 -2px 0 rgba(45, 156, 170, 0.45);
}

.diff-label {
  font-weight: 650;
  font-size: 0.9rem;
}

.diff-detail {
  font-size: 0.72rem;
  color: var(--text-muted);
}

.mode-summary {
  display: flex;
  align-items: center;
  gap: 0.85rem;
  padding: 1rem 1.1rem;
}

.mode-summary-label {
  margin: 0;
  font-weight: 650;
}

.mode-summary-desc,
.mode-summary-diff {
  margin: 0.15rem 0 0;
  font-size: 0.85rem;
  color: var(--text-muted);
}

.mode-summary-diff {
  color: #7ec8d4;
}

.matchup-card {
  display: flex;
  flex-direction: column;
  gap: 1rem;
  padding: 1.1rem;
  position: relative;
  overflow: hidden;
}

.matchup-card::before {
  content: '';
  position: absolute;
  inset: 0;
  background:
    radial-gradient(ellipse 70% 50% at 15% 20%, var(--sea-glow), transparent 60%),
    radial-gradient(ellipse 50% 40% at 90% 80%, rgba(196, 165, 116, 0.08), transparent 55%);
  pointer-events: none;
}

.matchup-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.75rem;
  position: relative;
}

.seat-count {
  font-size: 0.8rem;
  color: var(--text-muted);
  font-weight: 500;
}

.board-stage {
  display: grid;
  grid-template-columns: minmax(120px, 150px) minmax(0, 1fr);
  gap: 1.1rem;
  align-items: center;
  position: relative;
}

.mini-sea {
  position: relative;
  aspect-ratio: 1;
  border-radius: 12px;
  overflow: hidden;
  border: 2px solid var(--sea-deep);
  background: linear-gradient(165deg, #248a9c 0%, var(--sea) 40%, var(--sea-deep) 100%);
  box-shadow: 0 12px 28px rgba(0, 0, 0, 0.4);
  animation: seaPulse 4.5s ease-in-out infinite;
}

.mini-grid {
  display: grid;
  grid-template-columns: repeat(10, 1fr);
  inset: 8%;
  position: absolute;
  gap: 1px;
  opacity: 0.35;
}

.mini-cell {
  background: rgba(7, 20, 28, 0.55);
  aspect-ratio: 1;
}

.mini-ships {
  position: absolute;
  inset: 0;
  pointer-events: none;
}

.ship {
  position: absolute;
  height: 9%;
  display: flex;
  align-items: stretch;
  filter: drop-shadow(0 1px 3px rgba(0, 0, 0, 0.4));
  animation: shipIn 0.55s var(--ease-bounce) backwards;
}

.ship i {
  display: block;
  height: 100%;
  background: linear-gradient(180deg, #e8d2a8, var(--hull) 50%, #8a6f45);
  position: relative;
}

.ship .stern {
  width: 18%;
  clip-path: polygon(18% 22%, 100% 14%, 100% 86%, 18% 78%, 0% 50%);
}

.ship .mid {
  flex: 1;
  clip-path: polygon(0% 14%, 100% 14%, 100% 86%, 0% 86%);
  margin: 0 -1px;
}

.ship .bow {
  width: 22%;
  clip-path: polygon(0% 14%, 55% 8%, 100% 50%, 55% 92%, 0% 86%);
}

.ship .mid.bridge::after {
  content: '';
  position: absolute;
  left: 22%;
  right: 22%;
  top: 6%;
  height: 40%;
  border-radius: 1px;
  background: #4a3b28;
}

.ship.long {
  width: 46%;
  left: 10%;
  top: 26%;
  animation-delay: 0.15s;
}

.ship.mid-ship {
  width: 30%;
  left: 52%;
  top: 54%;
  animation-delay: 0.3s;
}

.ship.short {
  width: 18%;
  left: 22%;
  top: 72%;
  animation-delay: 0.45s;
}

@keyframes seaPulse {
  0%,
  100% {
    filter: drop-shadow(0 10px 20px rgba(0, 0, 0, 0.35));
  }
  50% {
    filter: drop-shadow(0 12px 26px rgba(45, 156, 170, 0.35));
  }
}

@keyframes shipIn {
  from {
    opacity: 0;
    transform: translateY(-6px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

.vs-column {
  display: flex;
  flex-direction: column;
  gap: 0.65rem;
  min-width: 0;
}

.seat-card {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  padding: 0.7rem 0.8rem;
  border-radius: 12px;
  border: 1px solid var(--border);
  background: rgba(10, 14, 23, 0.45);
  position: relative;
  overflow: hidden;
}

.seat-card::before {
  content: '';
  position: absolute;
  left: 0;
  top: 0;
  bottom: 0;
  width: 3px;
  background: var(--sea);
  opacity: 0.5;
}

.seat-card.filled::before {
  opacity: 1;
}

.seat-card.me {
  border-color: rgba(91, 156, 255, 0.55);
  box-shadow: 0 0 0 1px rgba(91, 156, 255, 0.15);
}

.seat-card.ai {
  border-color: rgba(45, 156, 170, 0.35);
}

.seat-card.empty {
  border-style: dashed;
}

.seat-mark {
  width: 42px;
  height: 42px;
  border-radius: 10px;
  display: grid;
  place-items: center;
  flex-shrink: 0;
  background: rgba(13, 61, 74, 0.55);
  border: 1px solid rgba(45, 156, 170, 0.25);
  font-size: 1.2rem;
}

.seat-body {
  flex: 1;
  min-width: 0;
}

.seat-side {
  margin: 0;
  font-size: 0.68rem;
  letter-spacing: 0.05em;
  text-transform: uppercase;
  color: var(--text-muted);
  font-weight: 600;
}

.seat-name {
  margin: 0.1rem 0 0;
  font-weight: 650;
  font-size: 0.95rem;
  display: flex;
  align-items: center;
  gap: 0.45rem;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.seat-initial {
  display: inline-grid;
  place-items: center;
  width: 1.35rem;
  height: 1.35rem;
  border-radius: 6px;
  font-size: 0.7rem;
  font-weight: 700;
  background: var(--surface-hover);
  flex-shrink: 0;
}

.seat-pending {
  margin: 0.15rem 0 0;
  font-weight: 600;
  color: var(--text-muted);
}

.seat-pending-sub {
  margin: 0.1rem 0 0;
  font-size: 0.78rem;
  color: #7ec8d4;
}

.seat-badges {
  display: flex;
  flex-wrap: wrap;
  gap: 0.3rem;
  margin-top: 0.3rem;
}

.badge {
  font-size: 0.65rem;
  padding: 0.12rem 0.4rem;
  border-radius: 4px;
  background: var(--surface-hover);
  font-weight: 600;
}

.you-badge {
  background: rgba(91, 156, 255, 0.18);
  color: var(--accent);
}

.ai-badge {
  background: rgba(45, 156, 170, 0.18);
  color: #7ec8d4;
}

.host-badge {
  color: var(--text-muted);
}

.remove-btn {
  font-size: 0.75rem;
  padding: 0.3rem 0.55rem;
  flex-shrink: 0;
}

.matchup-actions {
  display: flex;
  flex-direction: column;
  gap: 0.45rem;
  position: relative;
}

.add-ai-btn {
  align-self: flex-start;
}

.arrange-hint,
.room-full-hint,
.solo-blurb {
  margin: 0;
  font-size: 0.85rem;
  color: var(--text-muted);
  position: relative;
}

.solo-blurb strong {
  color: #7ec8d4;
  font-weight: 650;
}

.validation-banner {
  display: flex;
  gap: 0.75rem;
  align-items: flex-start;
  padding: 0.85rem 1rem;
}

.validation-banner.valid {
  border-color: rgba(61, 214, 140, 0.45);
  background: rgba(61, 214, 140, 0.06);
}

.validation-banner.invalid {
  border-color: rgba(230, 167, 0, 0.5);
  background: rgba(230, 167, 0, 0.06);
}

.validation-icon {
  font-size: 1.15rem;
  font-weight: 700;
  line-height: 1.2;
}

.validation-message {
  margin: 0;
  font-weight: 600;
}

.validation-issues {
  margin-top: 0.35rem;
  padding-left: 1.1rem;
  font-size: 0.85rem;
  color: var(--text-muted);
}

@media (max-width: 560px) {
  .mode-selector,
  .difficulty-row {
    grid-template-columns: 1fr;
  }

  .board-stage {
    grid-template-columns: 1fr;
  }

  .mini-sea {
    width: min(170px, 46vw);
    margin: 0 auto;
  }
}

@media (prefers-reduced-motion: reduce) {
  .battleship-lobby,
  .mini-sea,
  .ship {
    animation: none !important;
  }
}
</style>
