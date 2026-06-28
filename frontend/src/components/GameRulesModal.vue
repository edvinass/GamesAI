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
        <div>
          <h2>📖 {{ rules?.title ?? 'Rules' }}</h2>
          <p v-if="rules?.subtitle" class="modal-subtitle">{{ rules.subtitle }}</p>
        </div>
        <button type="button" class="close-btn" aria-label="Close" @click="emit('close')">×</button>
      </header>

      <div v-if="rules" class="modal-body stagger-in">
        <section v-if="rules.quickStart?.length" class="quick-start">
          <h3>Quick start</h3>
          <ol>
            <li v-for="(step, i) in rules.quickStart" :key="i">{{ step }}</li>
          </ol>
        </section>

        <section v-for="(section, i) in rules.sections" :key="i" class="rules-section">
          <h3>{{ section.heading }}</h3>
          <p>{{ section.body }}</p>
          <ul v-if="section.bullets?.length" class="rules-bullets">
            <li v-for="(bullet, j) in section.bullets" :key="j">{{ bullet }}</li>
          </ul>
        </section>

        <section v-if="rules.tips?.length" class="rules-tips">
          <h3>💡 Tips</h3>
          <ul>
            <li v-for="(tip, i) in rules.tips" :key="i">{{ tip }}</li>
          </ul>
        </section>
      </div>

      <div v-else class="modal-body">
        <p class="muted">No rules available for this game yet.</p>
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
  max-height: min(88vh, 680px);
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

.quick-start {
  margin-bottom: 1.5rem;
  padding: 1rem 1.15rem;
  border-radius: var(--radius);
  background: rgba(91, 156, 255, 0.08);
  border: 1px solid rgba(91, 156, 255, 0.2);
}

.quick-start h3 {
  font-size: 0.8rem;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  color: var(--accent);
  margin-bottom: 0.6rem;
}

.quick-start ol {
  margin: 0;
  padding-left: 1.25rem;
  font-size: 0.9rem;
  color: var(--text-muted);
  line-height: 1.55;
}

.quick-start li + li {
  margin-top: 0.35rem;
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
  margin-bottom: 0.35rem;
}

.rules-bullets {
  margin: 0.35rem 0 0;
  padding-left: 1.25rem;
  font-size: 0.88rem;
  color: var(--text-muted);
  line-height: 1.55;
}

.rules-bullets li + li {
  margin-top: 0.25rem;
}

.rules-tips {
  margin-top: 1.5rem;
  padding: 1rem 1.15rem;
  border-radius: var(--radius);
  background: var(--surface-elevated);
  border: 1px solid var(--border);
}

.rules-tips h3 {
  font-size: 0.9rem;
  margin-bottom: 0.5rem;
}

.rules-tips ul {
  margin: 0;
  padding-left: 1.25rem;
  font-size: 0.88rem;
  color: var(--text-muted);
  line-height: 1.55;
}

.rules-tips li + li {
  margin-top: 0.3rem;
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
