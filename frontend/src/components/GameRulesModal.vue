<script setup lang="ts">
import { computed, onMounted, onUnmounted } from 'vue'
import { getGameRules } from '@/games/rules'

const props = defineProps<{
  gameType: string
}>()

const emit = defineEmits<{
  close: []
}>()

const rules = computed(() => getGameRules(props.gameType))

function onKeydown(e: KeyboardEvent) {
  if (e.key === 'Escape') emit('close')
}

onMounted(() => window.addEventListener('keydown', onKeydown))
onUnmounted(() => window.removeEventListener('keydown', onKeydown))
</script>

<template>
  <div class="modal-backdrop" @click.self="emit('close')">
    <div class="modal card" role="dialog" aria-modal="true" :aria-label="rules?.title ?? 'Game rules'">
      <header class="modal-header">
        <h2>📖 {{ rules?.title ?? 'Rules' }}</h2>
        <button type="button" class="close-btn" aria-label="Close" @click="emit('close')">×</button>
      </header>

      <div v-if="rules" class="modal-body stagger-in">
        <section v-for="(section, i) in rules.sections" :key="i" class="rules-section">
          <h3>{{ section.heading }}</h3>
          <p>{{ section.body }}</p>
        </section>
      </div>

      <div v-else class="modal-body">
        <p class="muted">No rules available for this game yet.</p>
      </div>
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
  max-width: 540px;
  max-height: min(85vh, 640px);
  display: flex;
  flex-direction: column;
  padding: 0;
  overflow: hidden;
  animation: modalIn 0.4s var(--ease-bounce);
}

.modal-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 1.25rem 1.5rem;
  border-bottom: 1px solid var(--border);
  flex-shrink: 0;
}

.modal-header h2 {
  font-size: 1.25rem;
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
  transition: transform 0.2s, background 0.2s, color 0.2s;
}

.close-btn:hover {
  background: var(--surface-hover);
  color: var(--text);
  transform: rotate(90deg);
}

.modal-body {
  padding: 1.25rem 1.5rem 1.5rem;
  overflow-y: auto;
}

.rules-section + .rules-section {
  margin-top: 1.25rem;
}

.rules-section h3 {
  font-size: 0.95rem;
  margin-bottom: 0.35rem;
  color: var(--accent);
}

.rules-section p {
  color: var(--text-muted);
  font-size: 0.9rem;
  line-height: 1.6;
}

.muted {
  color: var(--text-muted);
  font-size: 0.9rem;
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
