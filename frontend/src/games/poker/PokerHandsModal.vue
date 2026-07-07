<script setup lang="ts">
import { onMounted, onUnmounted } from 'vue'
import { pokerHandRankings } from './handRankings'

const emit = defineEmits<{
  close: []
}>()

function onKeydown(e: KeyboardEvent) {
  if (e.key === 'Escape') emit('close')
}

onMounted(() => window.addEventListener('keydown', onKeydown))
onUnmounted(() => window.removeEventListener('keydown', onKeydown))
</script>

<template>
  <div class="modal-backdrop" @click.self="emit('close')">
    <div class="modal card" role="dialog" aria-modal="true" aria-label="Poker hand rankings">
      <header class="modal-header">
        <div>
          <h2>🃏 Hand Rankings</h2>
          <p class="modal-subtitle">Best hand wins at showdown — highest rank on top</p>
        </div>
        <button type="button" class="close-btn" aria-label="Close" @click="emit('close')">×</button>
      </header>

      <div class="modal-body stagger-in">
        <p class="intro">
          Your best five-card hand can use any mix of your two hole cards and the five community cards.
        </p>

        <ol class="hand-list">
          <li v-for="(hand, index) in pokerHandRankings" :key="hand.name" class="hand-item">
            <div class="hand-item__header">
              <span class="hand-rank">{{ index + 1 }}</span>
              <h3>{{ hand.name }}</h3>
            </div>
            <p class="hand-desc">{{ hand.description }}</p>
            <p class="hand-example"><span>Example:</span> {{ hand.example }}</p>
          </li>
        </ol>
      </div>

      <footer class="modal-footer">
        <button type="button" class="btn-primary" @click="emit('close')">Got it</button>
      </footer>
    </div>
  </div>
</template>

<style scoped>
.modal-backdrop {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.7);
  backdrop-filter: blur(4px);
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 1.5rem;
  z-index: 1000;
  animation: fadeIn 0.25s ease;
}

.modal {
  width: 100%;
  max-width: 560px;
  max-height: min(88vh, 720px);
  display: flex;
  flex-direction: column;
  padding: 0;
  overflow: hidden;
  animation: modalIn 0.4s var(--ease-bounce);
}

.modal-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 1rem;
  padding: 1.25rem 1.5rem;
  border-bottom: 1px solid var(--border);
  flex-shrink: 0;
}

.modal-header h2 {
  font-size: 1.25rem;
  margin-bottom: 0.15rem;
}

.modal-subtitle {
  font-size: 0.85rem;
  color: var(--text-muted);
  margin: 0;
}

.close-btn {
  width: 2.25rem;
  height: 2.25rem;
  display: flex;
  align-items: center;
  justify-content: center;
  background: transparent;
  color: var(--text-muted);
  font-size: 1.5rem;
  line-height: 1;
  border-radius: 8px;
  flex-shrink: 0;
  transition: transform 0.2s, background 0.2s, color 0.2s;
}

.close-btn:hover {
  background: var(--surface-hover);
  color: var(--text);
  transform: rotate(90deg);
}

.modal-body {
  padding: 1.25rem 1.5rem;
  overflow-y: auto;
  flex: 1;
}

.modal-footer {
  padding: 1rem 1.5rem;
  border-top: 1px solid var(--border);
  flex-shrink: 0;
}

.modal-footer .btn-primary {
  width: 100%;
}

.intro {
  margin: 0 0 1rem;
  font-size: 0.9rem;
  color: var(--text-muted);
  line-height: 1.55;
}

.hand-list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

.hand-item {
  padding: 0.85rem 1rem;
  border-radius: var(--radius);
  background: var(--surface-elevated);
  border: 1px solid var(--border);
}

.hand-item__header {
  display: flex;
  align-items: center;
  gap: 0.6rem;
  margin-bottom: 0.35rem;
}

.hand-rank {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 1.5rem;
  height: 1.5rem;
  border-radius: 50%;
  background: rgba(91, 156, 255, 0.15);
  color: var(--accent);
  font-size: 0.75rem;
  font-weight: 800;
  flex-shrink: 0;
}

.hand-item h3 {
  margin: 0;
  font-size: 0.95rem;
  color: var(--text);
}

.hand-desc {
  margin: 0;
  font-size: 0.88rem;
  color: var(--text-muted);
  line-height: 1.5;
}

.hand-example {
  margin: 0.4rem 0 0;
  font-size: 0.85rem;
  color: var(--text);
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
  letter-spacing: 0.02em;
}

.hand-example span {
  color: var(--text-muted);
  font-family: inherit;
  font-weight: 600;
}

@keyframes fadeIn {
  from { opacity: 0; }
  to { opacity: 1; }
}

@keyframes modalIn {
  from {
    transform: translateY(24px) scale(0.95);
    opacity: 0;
  }
  to {
    transform: translateY(0) scale(1);
    opacity: 1;
  }
}
</style>
