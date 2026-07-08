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
    glyph: '⚫',
  },
  {
    id: 'solo_practice',
    label: 'Vs AI',
    description: 'You play Black against the bot',
    glyph: '🤖',
  },
]

const difficultyOptions = [
  { value: 'easy', label: 'Easy', detail: 'Heuristic', depth: 'Smart hints' },
  { value: 'medium', label: 'Medium', detail: 'Guided MCTS', depth: '~400 sims' },
  { value: 'hard', label: 'Hard', detail: 'Deep MCTS', depth: '~1500 sims' },
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
      { color: 'B' as const, label: 'Black', player: human, pending: 'You' },
      { color: 'W' as const, label: 'White', player: null, pending: 'AI Opponent' },
    ]
  }
  return [
    {
      color: 'B' as const,
      label: 'Black',
      player: players[0] ?? null,
      pending: 'Waiting…',
    },
    {
      color: 'W' as const,
      label: 'White',
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
  <div class="go-lobby">
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
        <h2 class="section-title">9×9 board</h2>
        <span class="seat-count">
          <template v-if="soloPractice">Vs AI · {{ activeDifficulty.label }}</template>
          <template v-else>{{ playerCount }} / 2 seated</template>
        </span>
      </div>

      <div class="board-stage">
        <div class="mini-board" aria-hidden="true">
          <div class="mini-grid">
            <div v-for="i in 81" :key="i" class="mini-point" />
          </div>
          <span class="mini-stone stone-b" />
          <span class="mini-stone stone-w" />
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
              ai: seat.player?.is_ai || (soloPractice && seat.color === 'W'),
              'seat-white': seat.color === 'W',
              'seat-black': seat.color === 'B',
            }"
          >
            <div class="seat-color" :class="seat.color === 'B' ? 'stone-b' : 'stone-w'">
              <span class="seat-stone" aria-hidden="true" />
            </div>
            <div class="seat-body">
              <p class="seat-side">{{ seat.label }} · moves {{ seat.color === 'B' ? 'first' : 'second' }}</p>
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
                <p v-if="soloPractice && seat.color === 'W'" class="seat-pending-sub">
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
        <p v-else-if="isHost" class="arrange-hint">Share the room link or add an AI to fill a seat.</p>
      </div>

      <p v-else class="solo-blurb">
        Starting adds an AI on White. You sit as <strong>Black</strong> at
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
.go-lobby {
  --wood-light: #d9b896;
  --wood-dark: #8b5e3c;
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.section-title {
  margin: 0;
  font-size: 0.95rem;
  font-weight: 600;
}

.settings-card,
.mode-summary,
.matchup-card,
.validation-banner {
  padding: 1rem 1.1rem;
}

.mode-selector {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 0.6rem;
  margin-top: 0.75rem;
}

.mode-option {
  display: flex;
  align-items: flex-start;
  gap: 0.65rem;
  padding: 0.75rem;
  border: 1px solid var(--border);
  border-radius: 12px;
  background: rgba(21, 28, 44, 0.85);
  color: var(--text);
  text-align: left;
  cursor: pointer;
}

.mode-option.active {
  border-color: var(--accent);
  background: color-mix(in srgb, var(--accent) 14%, rgba(21, 28, 44, 0.95));
  color: var(--text);
}

.mode-glyph {
  font-size: 1.4rem;
  line-height: 1;
}

.mode-label {
  display: block;
  font-weight: 600;
}

.mode-desc {
  display: block;
  font-size: 0.82rem;
  color: var(--text-muted);
  margin-top: 0.15rem;
}

.difficulty-section {
  margin-top: 1rem;
}

.difficulty-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.difficulty-hint {
  font-size: 0.78rem;
  color: var(--text-muted);
}

.difficulty-row {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 0.5rem;
  margin-top: 0.65rem;
}

.difficulty-chip {
  padding: 0.55rem 0.5rem;
  border: 1px solid var(--border);
  border-radius: 10px;
  background: rgba(21, 28, 44, 0.85);
  color: var(--text);
  cursor: pointer;
}

.difficulty-chip.active {
  border-color: var(--accent);
  background: color-mix(in srgb, var(--accent) 14%, rgba(21, 28, 44, 0.95));
  color: var(--text);
}

.diff-label {
  display: block;
  font-weight: 600;
  font-size: 0.88rem;
}

.diff-detail {
  display: block;
  font-size: 0.75rem;
  color: var(--text-muted);
}

.mode-summary {
  display: flex;
  gap: 0.75rem;
  align-items: center;
  color: var(--text);
}

.mode-summary-label {
  margin: 0;
  font-weight: 600;
}

.mode-summary-desc,
.mode-summary-diff {
  margin: 0.15rem 0 0;
  font-size: 0.85rem;
  color: var(--text-muted);
}

.matchup-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.seat-count {
  font-size: 0.82rem;
  color: var(--text-muted);
}

.board-stage {
  display: grid;
  grid-template-columns: auto 1fr;
  gap: 1rem;
  margin-top: 0.85rem;
  align-items: center;
}

.mini-board {
  position: relative;
  width: 88px;
  height: 88px;
  background: linear-gradient(145deg, var(--wood-light), var(--wood-dark));
  border-radius: 8px;
  border: 2px solid #5c3d28;
}

.mini-grid {
  display: grid;
  grid-template-columns: repeat(9, 1fr);
  gap: 0;
  width: 100%;
  height: 100%;
  padding: 6px;
}

.mini-point {
  width: 3px;
  height: 3px;
  background: rgba(0, 0, 0, 0.35);
  border-radius: 50%;
  margin: auto;
}

.mini-stone {
  position: absolute;
  width: 14px;
  height: 14px;
  border-radius: 50%;
}

.mini-stone.stone-b {
  background: #1a1a1a;
  top: 28%;
  left: 28%;
}

.mini-stone.stone-w {
  background: #f5f5f0;
  border: 1px solid #999;
  bottom: 28%;
  right: 28%;
}

.vs-column {
  display: flex;
  flex-direction: column;
  gap: 0.55rem;
}

.seat-card {
  display: flex;
  align-items: center;
  gap: 0.65rem;
  padding: 0.55rem 0.65rem;
  border-radius: 10px;
  border: 1px solid var(--border);
  background: rgba(21, 28, 44, 0.85);
  color: var(--text);
}

.seat-card.filled {
  background: rgba(21, 28, 44, 0.95);
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
  opacity: 0.92;
}

.seat-card.seat-black {
  border-color: rgba(180, 175, 168, 0.35);
}

.seat-card.seat-white {
  border-color: rgba(240, 236, 228, 0.2);
}

.seat-color {
  width: 34px;
  height: 34px;
  border-radius: 50%;
  display: grid;
  place-items: center;
  flex-shrink: 0;
  border: 1px solid rgba(255, 255, 255, 0.12);
}

.seat-color.stone-b {
  background: linear-gradient(145deg, #4a4540, #1a1816);
}

.seat-color.stone-w {
  background: linear-gradient(145deg, #f3ebe0, #d6c4a8);
  border-color: rgba(255, 255, 255, 0.25);
}

.seat-stone {
  width: 18px;
  height: 18px;
  border-radius: 50%;
}

.seat-color.stone-b .seat-stone {
  background: radial-gradient(circle at 32% 28%, #555, #0a0a0a);
  box-shadow: 0 1px 2px rgba(0, 0, 0, 0.5);
}

.seat-color.stone-w .seat-stone {
  background: radial-gradient(circle at 32% 28%, #fff, #ccc);
  border: 1px solid #999;
}

.seat-side {
  margin: 0;
  font-size: 0.72rem;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  color: var(--text-muted);
  font-weight: 600;
}

.seat-card.seat-black .seat-side {
  color: #c4bfb8;
}

.seat-card.seat-white .seat-side {
  color: #d8dce4;
}

.seat-name {
  margin: 0.1rem 0 0;
  font-weight: 600;
  font-size: 0.9rem;
  color: var(--text);
}

.seat-initial {
  display: inline-grid;
  place-items: center;
  width: 1.25rem;
  height: 1.25rem;
  border-radius: 50%;
  background: rgba(255, 255, 255, 0.08);
  color: var(--text);
  font-size: 0.72rem;
  margin-right: 0.25rem;
}

.seat-badges {
  display: flex;
  gap: 0.3rem;
  margin-top: 0.2rem;
}

.badge {
  font-size: 0.65rem;
  padding: 0.1rem 0.35rem;
  border-radius: 999px;
  font-weight: 600;
}

.ai-badge {
  background: color-mix(in srgb, var(--accent) 20%, transparent);
  color: var(--accent);
}

.you-badge {
  background: color-mix(in srgb, #4ade80 20%, transparent);
  color: #4ade80;
}

.host-badge {
  background: color-mix(in srgb, #fbbf24 20%, transparent);
  color: #fbbf24;
}

.seat-pending {
  margin: 0.15rem 0 0;
  font-size: 0.85rem;
  color: var(--text-muted);
}

.seat-pending-sub {
  margin: 0.1rem 0 0;
  font-size: 0.75rem;
  color: var(--text-muted);
}

.remove-btn {
  margin-left: auto;
  font-size: 0.75rem;
  padding: 0.25rem 0.5rem;
}

.matchup-actions,
.solo-blurb {
  margin-top: 0.75rem;
  font-size: 0.85rem;
  color: var(--text-muted);
}

.solo-blurb strong {
  color: #e8e2d8;
  font-weight: 650;
}

.validation-banner {
  display: flex;
  gap: 0.65rem;
  align-items: flex-start;
}

.validation-banner.valid {
  border-color: color-mix(in srgb, #4ade80 40%, var(--border));
}

.validation-banner.invalid {
  border-color: color-mix(in srgb, #f87171 40%, var(--border));
}

.validation-message {
  margin: 0;
  font-size: 0.88rem;
  color: var(--text);
}

.validation-issues {
  margin: 0.35rem 0 0;
  padding-left: 1.1rem;
  font-size: 0.82rem;
  color: var(--text-muted);
}
</style>
