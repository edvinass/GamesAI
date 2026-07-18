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
        <h2 class="hero-title">Klondike Solitaire</h2>
        <p class="hero-desc">
          The classic card game. Build four foundation piles from Ace to King, 
          stack cards in alternating colors, and clear the tableau to win.
        </p>
      </div>
    </section>

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
        <div class="rule-item">
          <span class="rule-icon">🎯</span>
          <div class="rule-content">
            <span class="rule-title">Goal</span>
            <span class="rule-desc">Move all 52 cards to the four foundation piles</span>
          </div>
        </div>
        <div class="rule-item">
          <span class="rule-icon">📚</span>
          <div class="rule-content">
            <span class="rule-title">Foundations</span>
            <span class="rule-desc">Build up by suit: A → 2 → 3 ... → K</span>
          </div>
        </div>
        <div class="rule-item">
          <span class="rule-icon">🔄</span>
          <div class="rule-content">
            <span class="rule-title">Tableau</span>
            <span class="rule-desc">Stack in alternating colors, descending order</span>
          </div>
        </div>
        <div class="rule-item">
          <span class="rule-icon">👑</span>
          <div class="rule-content">
            <span class="rule-title">Empty columns</span>
            <span class="rule-desc">Only Kings can fill empty tableau spots</span>
          </div>
        </div>
      </div>
    </section>

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
  gap: 1rem;
  max-width: 600px;
  margin: 0 auto;
  animation: fadeInUp 0.4s var(--ease-smooth) 0.08s backwards;
}

.hero-card {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 1.5rem;
  padding: 2rem 1.5rem;
  background: 
    radial-gradient(ellipse 80% 60% at 50% 0%, rgba(34, 139, 34, 0.12) 0%, transparent 50%),
    linear-gradient(135deg, rgba(21, 28, 44, 0.98) 0%, rgba(16, 22, 36, 0.98) 100%);
  border-color: rgba(42, 143, 78, 0.3);
}

.card-preview {
  position: relative;
  width: 200px;
  height: 100px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.preview-card {
  position: absolute;
  width: 56px;
  height: 78px;
  border-radius: 8px;
  background: linear-gradient(160deg, #fffef9 0%, #f4f0e6 100%);
  border: 1px solid rgba(0, 0, 0, 0.12);
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow:
    0 2px 8px rgba(0, 0, 0, 0.2),
    0 4px 16px rgba(0, 0, 0, 0.15);
  transition: transform 0.3s var(--ease-smooth);
}

.preview-card--1 {
  transform: rotate(-15deg) translateX(-45px);
  z-index: 1;
}

.preview-card--2 {
  transform: rotate(-5deg) translateX(-15px);
  z-index: 2;
}

.preview-card--3 {
  transform: rotate(5deg) translateX(15px);
  z-index: 3;
}

.preview-card--4 {
  transform: rotate(15deg) translateX(45px);
  z-index: 4;
}

.hero-card:hover .preview-card--1 {
  transform: rotate(-20deg) translateX(-55px) translateY(-5px);
}

.hero-card:hover .preview-card--2 {
  transform: rotate(-8deg) translateX(-18px) translateY(-3px);
}

.hero-card:hover .preview-card--3 {
  transform: rotate(8deg) translateX(18px) translateY(-3px);
}

.hero-card:hover .preview-card--4 {
  transform: rotate(20deg) translateX(55px) translateY(-5px);
}

.preview-suit {
  font-size: 1.8rem;
  color: #1a1a1a;
}

.preview-suit.red {
  color: #c62828;
}

.hero-content {
  text-align: center;
}

.hero-title {
  margin: 0 0 0.5rem;
  font-size: 1.5rem;
  font-weight: 800;
  color: #fff;
}

.hero-desc {
  margin: 0;
  font-size: 0.9rem;
  line-height: 1.6;
  color: var(--text-muted);
  max-width: 400px;
}

.section-title {
  font-size: 0.7rem;
  font-weight: 600;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  color: var(--text-muted);
  margin: 0 0 0.85rem;
}

.settings-card {
  display: flex;
  flex-direction: column;
}

.mode-selector {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 0.65rem;
}

.mode-option {
  display: flex;
  align-items: flex-start;
  gap: 0.75rem;
  padding: 1rem;
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
  font-size: 1.25rem;
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
  font-size: 0.95rem;
  font-weight: 700;
}

.mode-desc {
  font-size: 0.78rem;
  line-height: 1.4;
  color: var(--text-muted);
}

.settings-summary {
  display: flex;
  align-items: center;
  gap: 0.85rem;
}

.summary-icon {
  font-size: 1.5rem;
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
}

.rules-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 0.75rem;
}

.rule-item {
  display: flex;
  align-items: flex-start;
  gap: 0.65rem;
  padding: 0.75rem;
  border-radius: 10px;
  background: rgba(255, 255, 255, 0.03);
  border: 1px solid rgba(255, 255, 255, 0.06);
}

.rule-icon {
  font-size: 1.25rem;
  line-height: 1;
  flex-shrink: 0;
}

.rule-content {
  display: flex;
  flex-direction: column;
  gap: 0.2rem;
  min-width: 0;
}

.rule-title {
  font-size: 0.82rem;
  font-weight: 600;
  color: var(--text);
}

.rule-desc {
  font-size: 0.75rem;
  line-height: 1.4;
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

@media (max-width: 480px) {
  .mode-selector {
    grid-template-columns: 1fr;
  }

  .rules-grid {
    grid-template-columns: 1fr;
  }

  .card-preview {
    transform: scale(0.85);
  }
}
</style>
