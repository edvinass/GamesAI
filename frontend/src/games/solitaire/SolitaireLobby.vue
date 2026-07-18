<script setup lang="ts">
import type { Room } from '@/types'

defineProps<{
  room: Room
  isHost: boolean
  currentPlayerId: string
  hostPlayerId: string | null
  validationMessage: string
  validationValid: boolean
  validationIssues: string[]
}>()

const drawCount = defineModel<number>('drawCount', { default: 1 })

const drawModes = [
  { value: 1, label: 'Draw 1', description: 'Easier — see every card', icon: '🃏' },
  { value: 3, label: 'Draw 3', description: 'Classic — more strategy', icon: '🃏🃏🃏' },
]

const rules = [
  { icon: '🎯', title: 'Goal', desc: 'Move all 52 cards to the four foundation piles' },
  { icon: '📚', title: 'Foundations', desc: 'Build up by suit: A → 2 → 3 … → K' },
  { icon: '🔄', title: 'Tableau', desc: 'Stack in alternating colors, descending order' },
  { icon: '👑', title: 'Empty columns', desc: 'Only Kings can fill empty tableau spots' },
]
</script>

<template>
  <div class="solitaire-lobby">
    <section class="hero-card card">
      <div class="card-preview" aria-hidden="true">
        <div class="preview-card preview-card--1">
          <span class="preview-suit">♠</span>
        </div>
        <div class="preview-card preview-card--2">
          <span class="preview-suit red">♥</span>
        </div>
        <div class="preview-card preview-card--3">
          <span class="preview-suit">♣</span>
        </div>
        <div class="preview-card preview-card--4">
          <span class="preview-suit red">♦</span>
        </div>
      </div>

      <div class="hero-content">
        <p class="hero-eyebrow">Single player</p>
        <h2 class="hero-title">Klondike Solitaire</h2>
        <p class="hero-desc">
          Build four foundation piles from Ace to King, stack the tableau in
          alternating colors, and clear the board.
        </p>
      </div>
    </section>

    <div class="lobby-grid">
      <section v-if="isHost" class="settings-card card">
        <h3 class="section-title">Game settings</h3>

        <div class="mode-selector" role="radiogroup" aria-label="Draw mode">
          <button
            v-for="mode in drawModes"
            :key="mode.value"
            type="button"
            class="mode-option"
            :class="{ active: drawCount === mode.value }"
            role="radio"
            :aria-checked="drawCount === mode.value"
            @click="drawCount = mode.value"
          >
            <span class="mode-icon" aria-hidden="true">{{ mode.icon }}</span>
            <span class="mode-copy">
              <span class="mode-label">{{ mode.label }}</span>
              <span class="mode-desc">{{ mode.description }}</span>
            </span>
          </button>
        </div>
      </section>

      <section v-else class="settings-summary card">
        <span class="summary-icon">🃏</span>
        <div class="summary-content">
          <p class="summary-label">{{ drawCount === 1 ? 'Draw 1' : 'Draw 3' }} mode</p>
          <p class="summary-desc">
            {{ drawCount === 1 ? 'Easier — see every card' : 'Classic — more strategy required' }}
          </p>
        </div>
      </section>

      <section class="rules-card card">
        <h3 class="section-title">How to play</h3>
        <div class="rules-grid">
          <div v-for="rule in rules" :key="rule.title" class="rule-item">
            <span class="rule-icon">{{ rule.icon }}</span>
            <div class="rule-content">
              <span class="rule-title">{{ rule.title }}</span>
              <span class="rule-desc">{{ rule.desc }}</span>
            </div>
          </div>
        </div>
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
  </div>
</template>

<style scoped>
.solitaire-lobby {
  display: flex;
  flex-direction: column;
  gap: 1.1rem;
  width: 100%;
  animation: fadeInUp 0.4s var(--ease-smooth) 0.08s backwards;
}

.hero-card {
  display: grid;
  grid-template-columns: minmax(200px, 280px) minmax(0, 1fr);
  align-items: center;
  gap: 1.75rem 2.5rem;
  padding: 1.75rem 2rem;
  background:
    radial-gradient(ellipse 70% 80% at 12% 40%, rgba(34, 139, 34, 0.16) 0%, transparent 55%),
    linear-gradient(135deg, rgba(21, 28, 44, 0.98) 0%, rgba(16, 22, 36, 0.98) 100%);
  border-color: rgba(42, 143, 78, 0.3);
  min-height: 200px;
}

.card-preview {
  position: relative;
  width: 100%;
  max-width: 260px;
  height: 140px;
  margin: 0 auto;
  display: flex;
  align-items: center;
  justify-content: center;
}

.preview-card {
  position: absolute;
  width: 72px;
  height: 100px;
  border-radius: 10px;
  background: linear-gradient(160deg, #fffef9 0%, #f4f0e6 100%);
  border: 1px solid rgba(0, 0, 0, 0.12);
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow:
    0 2px 8px rgba(0, 0, 0, 0.2),
    0 8px 24px rgba(0, 0, 0, 0.2);
  transition: transform 0.3s var(--ease-smooth);
}

.preview-card--1 {
  transform: rotate(-16deg) translateX(-52px);
  z-index: 1;
}

.preview-card--2 {
  transform: rotate(-6deg) translateX(-18px);
  z-index: 2;
}

.preview-card--3 {
  transform: rotate(6deg) translateX(18px);
  z-index: 3;
}

.preview-card--4 {
  transform: rotate(16deg) translateX(52px);
  z-index: 4;
}

.hero-card:hover .preview-card--1 {
  transform: rotate(-22deg) translateX(-64px) translateY(-6px);
}

.hero-card:hover .preview-card--2 {
  transform: rotate(-9deg) translateX(-22px) translateY(-4px);
}

.hero-card:hover .preview-card--3 {
  transform: rotate(9deg) translateX(22px) translateY(-4px);
}

.hero-card:hover .preview-card--4 {
  transform: rotate(22deg) translateX(64px) translateY(-6px);
}

.preview-suit {
  font-size: 2.2rem;
  color: #1a1a1a;
}

.preview-suit.red {
  color: #c62828;
}

.hero-content {
  text-align: left;
  min-width: 0;
}

.hero-eyebrow {
  margin: 0 0 0.35rem;
  font-size: 0.72rem;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: #7dffb0;
}

.hero-title {
  margin: 0 0 0.55rem;
  font-size: clamp(1.6rem, 2.5vw, 2.1rem);
  font-weight: 800;
  color: #fff;
  line-height: 1.15;
}

.hero-desc {
  margin: 0;
  font-size: 1rem;
  line-height: 1.55;
  color: var(--text-muted);
  max-width: 42ch;
}

.lobby-grid {
  display: grid;
  grid-template-columns: minmax(280px, 1fr) minmax(0, 1.35fr);
  gap: 1.1rem;
  align-items: stretch;
}

.section-title {
  font-size: 0.7rem;
  font-weight: 600;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  color: var(--text-muted);
  margin: 0 0 0.9rem;
}

.settings-card {
  display: flex;
  flex-direction: column;
  min-height: 100%;
}

.mode-selector {
  display: grid;
  grid-template-columns: 1fr;
  gap: 0.75rem;
  flex: 1;
}

.mode-option {
  display: flex;
  align-items: center;
  gap: 0.85rem;
  padding: 1.15rem 1.2rem;
  border-radius: 12px;
  border: 2px solid var(--border);
  background: var(--surface-hover);
  color: var(--text);
  text-align: left;
  cursor: pointer;
  transition:
    border-color 0.2s,
    background 0.2s,
    transform 0.2s var(--ease-smooth),
    box-shadow 0.2s;
  flex: 1;
}

.mode-option:hover {
  border-color: rgba(42, 143, 78, 0.45);
  transform: translateY(-2px);
}

.mode-option.active {
  border-color: #2a8f4e;
  background: rgba(42, 143, 78, 0.12);
  box-shadow:
    0 0 0 1px rgba(42, 143, 78, 0.2),
    0 4px 12px rgba(42, 143, 78, 0.15);
}

.mode-icon {
  font-size: 1.35rem;
  line-height: 1;
  flex-shrink: 0;
  filter: grayscale(0.3);
}

.mode-option.active .mode-icon {
  filter: none;
}

.mode-copy {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
  min-width: 0;
}

.mode-label {
  font-size: 1rem;
  font-weight: 700;
}

.mode-desc {
  font-size: 0.82rem;
  line-height: 1.4;
  color: var(--text-muted);
}

.settings-summary {
  display: flex;
  align-items: center;
  gap: 0.9rem;
  min-height: 100%;
}

.summary-icon {
  font-size: 1.6rem;
}

.summary-content {
  display: flex;
  flex-direction: column;
  gap: 0.15rem;
}

.summary-label {
  margin: 0;
  font-weight: 600;
  color: var(--text);
}

.summary-desc {
  margin: 0;
  font-size: 0.85rem;
  color: var(--text-muted);
}

.rules-card {
  background: linear-gradient(135deg, rgba(21, 28, 44, 0.98) 0%, rgba(16, 22, 36, 0.98) 100%);
  min-height: 100%;
}

.rules-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 0.75rem;
  height: calc(100% - 1.6rem);
}

.rule-item {
  display: flex;
  align-items: flex-start;
  gap: 0.7rem;
  padding: 1rem 1.05rem;
  border-radius: 10px;
  background: rgba(255, 255, 255, 0.03);
  border: 1px solid rgba(255, 255, 255, 0.06);
  min-height: 0;
}

.rule-icon {
  font-size: 1.3rem;
  line-height: 1;
  flex-shrink: 0;
}

.rule-content {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
  min-width: 0;
}

.rule-title {
  font-size: 0.88rem;
  font-weight: 600;
  color: var(--text);
}

.rule-desc {
  font-size: 0.8rem;
  line-height: 1.45;
  color: var(--text-muted);
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
  .lobby-grid {
    grid-template-columns: 1fr;
  }

  .mode-selector {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 640px) {
  .hero-card {
    grid-template-columns: 1fr;
    justify-items: center;
    text-align: center;
    padding: 1.5rem 1.25rem;
    min-height: 0;
    gap: 1.25rem;
  }

  .hero-content {
    text-align: center;
  }

  .hero-desc {
    max-width: none;
  }

  .card-preview {
    height: 120px;
  }

  .preview-card {
    width: 60px;
    height: 84px;
  }

  .preview-suit {
    font-size: 1.8rem;
  }

  .mode-selector {
    grid-template-columns: 1fr;
  }

  .rules-grid {
    grid-template-columns: 1fr;
    height: auto;
  }
}
</style>
