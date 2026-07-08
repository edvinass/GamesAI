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

const gameModes: { id: GameMode; label: string; description: string; glyph: string }[] = [
  {
    id: 'multiplayer',
    label: 'Match',
    description: 'You vs a friend or AI seat',
    glyph: '♞',
  },
  {
    id: 'solo_practice',
    label: 'Vs AI',
    description: 'You play White against the bot',
    glyph: '♚',
  },
]

const difficultyOptions = [
  {
    value: 'easy',
    label: 'Easy',
    detail: 'Casual play',
    depth: 'Depth 1',
  },
  {
    value: 'medium',
    label: 'Medium',
    detail: 'Solid play',
    depth: 'Depth 2',
  },
  {
    value: 'hard',
    label: 'Hard',
    detail: 'Tough to crack',
    depth: 'Depth 3',
  },
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

/** Preview seats: White first when solo; otherwise seating order. */
const seats = computed(() => {
  const players = props.room.players
  if (soloPractice.value) {
    const human = players.find((p) => !p.is_ai) ?? null
    return [
      { color: 'w' as const, label: 'White', player: human, pending: 'You' },
      { color: 'b' as const, label: 'Black', player: null, pending: 'AI Opponent' },
    ]
  }
  return [
    {
      color: 'w' as const,
      label: 'White',
      player: players[0] ?? null,
      pending: 'Waiting…',
    },
    {
      color: 'b' as const,
      label: 'Black',
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
  <div class="chess-lobby">
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
          <span class="mode-glyph" aria-hidden="true">{{ mode.glyph }}</span>
          <span class="mode-copy">
            <span class="mode-label">{{ mode.label }}</span>
            <span class="mode-desc">{{ mode.description }}</span>
          </span>
        </button>
      </div>

      <div class="difficulty-section">
        <div class="difficulty-header">
          <h2 class="section-title">AI strength</h2>
          <span class="difficulty-hint">{{ activeDifficulty.depth }}</span>
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
      <span class="mode-glyph" aria-hidden="true">{{ activeMode.glyph }}</span>
      <div>
        <p class="mode-summary-label">{{ activeMode.label }}</p>
        <p class="mode-summary-desc">{{ activeMode.description }}</p>
        <p class="mode-summary-diff">AI · {{ activeDifficulty.label }}</p>
      </div>
    </section>

    <section class="matchup-card card" aria-label="Matchup preview">
      <div class="matchup-header">
        <h2 class="section-title">The board</h2>
        <span class="seat-count">
          <template v-if="soloPractice">Vs AI · {{ activeDifficulty.label }}</template>
          <template v-else>{{ playerCount }} / 2 seated</template>
        </span>
      </div>

      <div class="board-stage">
        <div class="mini-board" aria-hidden="true">
          <div
            v-for="i in 64"
            :key="i"
            class="mini-square"
            :class="(Math.floor((i - 1) / 8) + ((i - 1) % 8)) % 2 === 0 ? 'light' : 'dark'"
          />
          <div class="board-pieces">
            <span class="corner-piece tl">♜</span>
            <span class="corner-piece tr">♝</span>
            <span class="corner-piece bl">♙</span>
            <span class="corner-piece br">♘</span>
          </div>
        </div>

        <div class="vs-column">
          <div
            v-for="seat in seats"
            :key="seat.color"
            class="seat-card"
            :class="{
              filled: Boolean(seat.player),
              empty: !seat.player,
              me: seat.player?.id === currentPlayerId,
              ai: seat.player?.is_ai || (soloPractice && seat.color === 'b'),
              white: seat.color === 'w',
              black: seat.color === 'b',
            }"
          >
            <div class="seat-color" :class="seat.color">
              <span class="seat-king" aria-hidden="true">{{ seat.color === 'w' ? '♔' : '♚' }}</span>
            </div>
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
                <p v-if="soloPractice && seat.color === 'b'" class="seat-pending-sub">
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
        <p v-else-if="isHost && playerCount >= 2" class="room-full-hint">Both seats are filled.</p>
        <p v-else-if="isHost" class="arrange-hint">Share the room link or add an AI to fill Black.</p>
      </div>

      <p v-else class="solo-blurb">
        Starting adds one AI on Black. You sit as White with
        <strong>{{ activeDifficulty.label }}</strong> strength.
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
.chess-lobby {
  --wood-light: #d9b896;
  --wood-dark: #8b5e3c;
  --wood-glow: rgba(201, 154, 98, 0.22);
  display: flex;
  flex-direction: column;
  gap: 1rem;
  animation: chessLobbyIn 0.45s var(--ease-smooth) 0.06s backwards;
}

@keyframes chessLobbyIn {
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
    transform 0.2s var(--ease-smooth),
    box-shadow 0.2s;
}

.mode-option:hover {
  border-color: rgba(201, 154, 98, 0.45);
  transform: translateY(-1px);
}

.mode-option.active {
  border-color: var(--wood-light);
  background: linear-gradient(145deg, rgba(201, 154, 98, 0.16), rgba(139, 94, 60, 0.08));
  box-shadow: 0 0 0 1px rgba(201, 154, 98, 0.18);
}

.mode-glyph {
  font-size: 1.55rem;
  line-height: 1;
  flex-shrink: 0;
  color: var(--wood-light);
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
  border-color: rgba(201, 154, 98, 0.4);
  transform: translateY(-1px);
}

.difficulty-chip.active {
  border-color: var(--wood-light);
  background: rgba(201, 154, 98, 0.12);
  box-shadow: inset 0 -2px 0 rgba(201, 154, 98, 0.45);
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
  color: var(--wood-light);
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
    radial-gradient(ellipse 70% 50% at 15% 20%, var(--wood-glow), transparent 60%),
    radial-gradient(ellipse 50% 40% at 90% 80%, rgba(91, 156, 255, 0.08), transparent 55%);
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
  grid-template-columns: minmax(110px, 140px) minmax(0, 1fr);
  gap: 1rem;
  align-items: center;
  position: relative;
}

.mini-board {
  position: relative;
  display: grid;
  grid-template-columns: repeat(8, 1fr);
  aspect-ratio: 1;
  border-radius: 10px;
  overflow: hidden;
  border: 2px solid rgba(217, 184, 150, 0.35);
  box-shadow:
    0 10px 28px rgba(0, 0, 0, 0.4),
    inset 0 0 0 1px rgba(255, 255, 255, 0.06);
  animation: boardPulse 4.5s ease-in-out infinite;
}

@keyframes boardPulse {
  0%,
  100% {
    box-shadow:
      0 10px 28px rgba(0, 0, 0, 0.4),
      inset 0 0 0 1px rgba(255, 255, 255, 0.06);
  }
  50% {
    box-shadow:
      0 12px 32px rgba(0, 0, 0, 0.45),
      0 0 22px var(--wood-glow),
      inset 0 0 0 1px rgba(255, 255, 255, 0.08);
  }
}

.mini-square.light {
  background: #e8d5b5;
}

.mini-square.dark {
  background: #b58863;
}

.board-pieces {
  position: absolute;
  inset: 0;
  pointer-events: none;
}

.corner-piece {
  position: absolute;
  font-size: clamp(0.85rem, 2.5vw, 1.15rem);
  line-height: 1;
  opacity: 0.85;
  filter: drop-shadow(0 1px 1px rgba(0, 0, 0, 0.35));
}

.corner-piece.tl {
  top: 6%;
  left: 8%;
  color: #1a1a1a;
}

.corner-piece.tr {
  top: 6%;
  right: 8%;
  color: #1a1a1a;
}

.corner-piece.bl {
  bottom: 6%;
  left: 8%;
  color: #f8f5f0;
  -webkit-text-stroke: 0.5px #222;
}

.corner-piece.br {
  bottom: 6%;
  right: 10%;
  color: #f8f5f0;
  -webkit-text-stroke: 0.5px #222;
  animation: knightIdle 2.8s var(--ease-smooth) infinite;
}

@keyframes knightIdle {
  0%,
  100% {
    transform: translateY(0);
  }
  50% {
    transform: translateY(-3px);
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
  transition:
    border-color 0.2s,
    background 0.2s,
    transform 0.2s var(--ease-smooth);
}

.seat-card.filled {
  background: rgba(21, 28, 44, 0.85);
}

.seat-card.me {
  border-color: rgba(91, 156, 255, 0.55);
  box-shadow: 0 0 0 1px rgba(91, 156, 255, 0.15);
}

.seat-card.ai {
  border-color: rgba(201, 154, 98, 0.35);
}

.seat-card.empty {
  border-style: dashed;
  opacity: 0.9;
}

.seat-color {
  width: 42px;
  height: 42px;
  border-radius: 10px;
  display: grid;
  place-items: center;
  flex-shrink: 0;
  border: 1px solid rgba(255, 255, 255, 0.1);
}

.seat-color.w {
  background: linear-gradient(145deg, #f3ebe0, #d6c4a8);
  color: #2a2118;
}

.seat-color.b {
  background: linear-gradient(145deg, #3a3230, #1a1614);
  color: #f0e6d8;
}

.seat-king {
  font-size: 1.35rem;
  line-height: 1;
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
  color: var(--wood-light);
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
  background: rgba(201, 154, 98, 0.18);
  color: var(--wood-light);
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
  color: var(--wood-light);
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

  .mini-board {
    width: min(160px, 42vw);
    margin: 0 auto;
  }
}
</style>
