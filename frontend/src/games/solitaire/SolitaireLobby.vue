<script setup lang="ts">
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

const emit = defineEmits<{
  'update:drawCount': [value: number]
}>()

const drawCount = defineModel<number>('drawCount', { default: 1 })
</script>

<template>
  <section class="solitaire-lobby card">
    <div class="lobby-icon">🃏</div>
    <h2>Solo card game</h2>
    <p class="desc">
      Classic Klondike Solitaire. Build four foundation piles from Ace to King by suit.
      Stack cards in alternating colors on the tableau.
    </p>

    <ul class="feature-list">
      <li>7 tableau columns to organize cards</li>
      <li>Build foundations by suit: A → K</li>
      <li>Draw from stock when stuck</li>
      <li>Win by clearing all cards to foundations</li>
    </ul>

    <div v-if="isHost" class="settings-section">
      <label class="setting-row">
        <span class="setting-label">Draw count</span>
        <select v-model.number="drawCount" class="draw-select">
          <option :value="1">Draw 1 (easier)</option>
          <option :value="3">Draw 3 (harder)</option>
        </select>
      </label>
    </div>

    <div v-if="validationIssues.length" class="issues">
      <p v-for="issue in validationIssues" :key="issue">{{ issue }}</p>
    </div>
    <p v-else class="ready-msg">{{ validationMessage }}</p>
  </section>
</template>

<style scoped>
.solitaire-lobby {
  padding: 1.5rem;
  text-align: center;
  max-width: 480px;
  margin: 0 auto 1rem;
}

.lobby-icon {
  font-size: 2.5rem;
  margin-bottom: 0.5rem;
}

.solitaire-lobby h2 {
  margin: 0 0 0.5rem;
}

.desc {
  color: var(--text-muted);
  font-size: 0.9rem;
  line-height: 1.5;
  margin: 0 0 1rem;
}

.feature-list {
  text-align: left;
  margin: 0 0 1rem;
  padding-left: 1.25rem;
  font-size: 0.85rem;
  color: var(--text-muted);
  line-height: 1.6;
}

.settings-section {
  margin: 1rem 0;
  padding: 1rem;
  background: var(--surface-hover);
  border-radius: 8px;
}

.setting-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1rem;
}

.setting-label {
  font-size: 0.9rem;
  font-weight: 600;
}

.draw-select {
  padding: 0.4rem 0.6rem;
  border-radius: 6px;
  border: 1px solid var(--border);
  background: var(--surface);
  color: var(--text);
  font-size: 0.85rem;
}

.issues p {
  color: #737373;
  font-size: 0.85rem;
  margin: 0.25rem 0;
}

.ready-msg {
  color: #e5e5e5;
  font-size: 0.9rem;
  font-weight: 600;
  margin: 0;
}
</style>
