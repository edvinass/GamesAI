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

const rules = [
  { icon: '🎯', title: 'Objective', desc: 'Keep the ball in play and score as many points as possible' },
  { icon: '🔴', title: 'Bumpers', desc: 'Hit bumpers for 75-150 points each bounce' },
  { icon: '🎪', title: 'Targets', desc: 'Hit targets for 250-1000 bonus points (one-time each)' },
  { icon: '⚡', title: 'Combos', desc: 'Quick successive hits multiply your score up to 5x' },
]

const controls = [
  { key: 'A / ← / Z', action: 'Left flipper' },
  { key: 'D / → / M', action: 'Right flipper' },
  { key: 'Space / Enter', action: 'Launch ball' },
]
</script>

<template>
  <div class="pinball-lobby">
    <section class="hero-card card">
      <div class="card-preview" aria-hidden="true">
        <div class="preview-table">
          <div class="preview-bumper bumper-1" />
          <div class="preview-bumper bumper-2" />
          <div class="preview-bumper bumper-3" />
          <div class="preview-ball" />
          <div class="preview-flipper flipper-left" />
          <div class="preview-flipper flipper-right" />
        </div>
      </div>

      <div class="hero-content">
        <p class="hero-eyebrow">Single player</p>
        <h2 class="hero-title">Pinball</h2>
        <p class="hero-desc">
          Classic arcade pinball action! Use the flippers to keep the ball in play,
          hit bumpers and targets to rack up points, and try to beat your high score.
        </p>
      </div>
    </section>

    <div class="lobby-grid">
      <section class="controls-card card">
        <h3 class="section-title">Controls</h3>
        <div class="controls-list">
          <div v-for="ctrl in controls" :key="ctrl.key" class="control-item">
            <kbd class="control-key">{{ ctrl.key }}</kbd>
            <span class="control-action">{{ ctrl.action }}</span>
          </div>
        </div>
        <p class="touch-note">On mobile, tap the left/right buttons to control flippers</p>
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
.pinball-lobby {
  display: flex;
  flex-direction: column;
  gap: 1.1rem;
  width: 100%;
  animation: fadeInUp 0.4s var(--ease-smooth) 0.08s backwards;
}

.hero-card {
  display: grid;
  grid-template-columns: minmax(180px, 260px) minmax(0, 1fr);
  align-items: center;
  gap: 1.75rem 2.5rem;
  padding: 1.75rem 2rem;
  background:
    radial-gradient(ellipse 70% 80% at 12% 40%, rgba(83, 82, 237, 0.2) 0%, transparent 55%),
    linear-gradient(135deg, rgba(21, 28, 44, 0.98) 0%, rgba(16, 22, 36, 0.98) 100%);
  border-color: rgba(83, 82, 237, 0.3);
  min-height: 200px;
}

.card-preview {
  position: relative;
  width: 100%;
  max-width: 220px;
  height: 160px;
  margin: 0 auto;
  display: flex;
  align-items: center;
  justify-content: center;
}

.preview-table {
  position: relative;
  width: 140px;
  height: 140px;
  background: linear-gradient(180deg, #1a1a2e 0%, #0f0f23 100%);
  border-radius: 12px 12px 0 0;
  border: 3px solid #4a4a6a;
  overflow: hidden;
}

.preview-bumper {
  position: absolute;
  border-radius: 50%;
  box-shadow: 0 0 10px currentColor;
}

.preview-bumper.bumper-1 {
  width: 24px;
  height: 24px;
  top: 20px;
  left: 30px;
  background: radial-gradient(circle at 30% 30%, #ff6b6b, #ff4757);
}

.preview-bumper.bumper-2 {
  width: 24px;
  height: 24px;
  top: 20px;
  right: 30px;
  background: radial-gradient(circle at 30% 30%, #ff6b6b, #ff4757);
}

.preview-bumper.bumper-3 {
  width: 28px;
  height: 28px;
  top: 45px;
  left: 50%;
  transform: translateX(-50%);
  background: radial-gradient(circle at 30% 30%, #ffd700, #ffa502);
}

.preview-ball {
  position: absolute;
  width: 14px;
  height: 14px;
  border-radius: 50%;
  background: radial-gradient(circle at 30% 30%, #fff, #888);
  bottom: 40px;
  left: 50%;
  transform: translateX(-50%);
  box-shadow: 0 0 8px rgba(255, 255, 255, 0.5);
  animation: ballBounce 2s ease-in-out infinite;
}

@keyframes ballBounce {
  0%, 100% { transform: translateX(-50%) translateY(0); }
  50% { transform: translateX(-50%) translateY(-30px); }
}

.preview-flipper {
  position: absolute;
  bottom: 15px;
  width: 35px;
  height: 8px;
  border-radius: 4px;
}

.preview-flipper.flipper-left {
  left: 15px;
  background: linear-gradient(90deg, #ff6b6b, #ee5a5a);
  transform-origin: left center;
  animation: flipperLeft 1s ease-in-out infinite;
}

.preview-flipper.flipper-right {
  right: 15px;
  background: linear-gradient(90deg, #4ecdc4, #3dbdb5);
  transform-origin: right center;
  animation: flipperRight 1s ease-in-out infinite;
}

@keyframes flipperLeft {
  0%, 100% { transform: rotate(20deg); }
  50% { transform: rotate(-15deg); }
}

@keyframes flipperRight {
  0%, 100% { transform: rotate(-20deg); }
  50% { transform: rotate(15deg); }
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
  color: #a78bfa;
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
  grid-template-columns: minmax(260px, 1fr) minmax(0, 1.5fr);
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

.controls-card {
  display: flex;
  flex-direction: column;
}

.controls-list {
  display: flex;
  flex-direction: column;
  gap: 0.6rem;
  flex: 1;
}

.control-item {
  display: flex;
  align-items: center;
  gap: 0.8rem;
  padding: 0.6rem 0.8rem;
  background: rgba(255, 255, 255, 0.03);
  border-radius: 8px;
}

.control-key {
  font-family: 'SF Mono', 'Consolas', monospace;
  font-size: 0.8rem;
  font-weight: 600;
  padding: 0.3rem 0.6rem;
  background: rgba(255, 255, 255, 0.1);
  border: 1px solid rgba(255, 255, 255, 0.15);
  border-radius: 6px;
  color: #fff;
  min-width: 90px;
  text-align: center;
}

.control-action {
  font-size: 0.9rem;
  color: var(--text-muted);
}

.touch-note {
  margin: 0.8rem 0 0;
  font-size: 0.78rem;
  color: var(--text-muted);
  font-style: italic;
}

.rules-card {
  background: linear-gradient(135deg, rgba(21, 28, 44, 0.98) 0%, rgba(16, 22, 36, 0.98) 100%);
  min-height: 100%;
}

.rules-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 0.75rem;
}

.rule-item {
  display: flex;
  align-items: flex-start;
  gap: 0.7rem;
  padding: 1rem 1.05rem;
  border-radius: 10px;
  background: rgba(255, 255, 255, 0.03);
  border: 1px solid rgba(255, 255, 255, 0.06);
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

  .rules-grid {
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
    height: 130px;
  }

  .preview-table {
    width: 120px;
    height: 120px;
  }

  .rules-grid {
    grid-template-columns: 1fr;
  }
}
</style>
