<script setup lang="ts">
import { computed } from 'vue'
import type { Player } from '@/types'
import FlowSlot from '@/components/FlowSlot.vue'

const props = defineProps<{
  team: 'red' | 'blue'
  players: Player[]
  remaining: number
  active?: boolean
}>()

const totalWords = computed(() => {
  return props.team === 'red' ? 9 : 8
})

const dots = computed(() => {
  const total = totalWords.value
  const hidden = props.remaining
  return Array.from({ length: total }, (_, i) => i < hidden)
})
</script>

<template>
  <div :class="['team-panel', team, { active }]">
    <div class="panel-header">
      <h3>{{ team.toUpperCase() }}</h3>
      <FlowSlot horizontal :open="Boolean(active)">
        <span v-show="active" class="turn-badge">Turn</span>
      </FlowSlot>
    </div>

    <div class="remaining-block">
      <span class="remaining-num">{{ remaining }}</span>
      <span class="remaining-label">words left</span>
    </div>

    <div class="word-dots" aria-hidden="true">
      <span
        v-for="(visible, i) in dots"
        :key="i"
        class="dot"
        :class="{ hidden: !visible }"
      />
    </div>

    <ul class="player-list">
      <li
        v-for="p in players"
        :key="p.id"
        :class="{ spymaster: p.role === 'spymaster' }"
      >
        <span class="player-name">{{ p.nickname }}</span>
        <span class="badges">
          <span v-if="p.is_ai" class="badge badge-ai">AI</span>
          <span v-if="!p.is_connected" class="badge badge-disconnected">Off</span>
        </span>
      </li>
    </ul>
  </div>
</template>

<style scoped>
.team-panel {
  padding: 1rem;
  border-radius: var(--radius);
  border: 1px solid var(--border);
  background: var(--surface);
  transition: transform 0.3s var(--ease-smooth), box-shadow 0.3s, border-color 0.3s;
  position: sticky;
  top: 1rem;
}

.team-panel.red {
  border-top: 3px solid var(--red-team);
}

.team-panel.blue {
  border-top: 3px solid var(--blue-team);
}

.team-panel.active {
  transform: scale(1.02);
  box-shadow: var(--shadow);
}

.team-panel.active.red {
  border-color: rgba(255, 92, 108, 0.5);
  box-shadow: 0 0 24px rgba(255, 92, 108, 0.15);
  animation: teamGlowRed 2s ease-in-out infinite;
}

.team-panel.active.blue {
  border-color: rgba(91, 156, 255, 0.5);
  box-shadow: 0 0 24px rgba(91, 156, 255, 0.15);
  animation: teamGlowBlue 2s ease-in-out infinite;
}

@keyframes teamGlowRed {
  0%, 100% { box-shadow: 0 0 16px rgba(255, 92, 108, 0.12); }
  50% { box-shadow: 0 0 28px rgba(255, 92, 108, 0.25); }
}

@keyframes teamGlowBlue {
  0%, 100% { box-shadow: 0 0 16px rgba(91, 156, 255, 0.12); }
  50% { box-shadow: 0 0 28px rgba(91, 156, 255, 0.25); }
}

.panel-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 0.5rem;
}

.team-panel h3 {
  font-size: 0.9rem;
  font-weight: 700;
  letter-spacing: 0.04em;
}

.team-panel.red h3 { color: var(--red-team); }
.team-panel.blue h3 { color: var(--blue-team); }

.turn-badge {
  font-size: 0.65rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  padding: 0.15rem 0.45rem;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.1);
  animation: badgePulse 1.5s ease-in-out infinite;
}

.team-panel.red .turn-badge { color: var(--red-team); }
.team-panel.blue .turn-badge { color: var(--blue-team); }

.remaining-block {
  display: flex;
  align-items: baseline;
  gap: 0.35rem;
  margin-bottom: 0.65rem;
}

.remaining-num {
  font-size: 2rem;
  font-weight: 800;
  line-height: 1;
  transition: transform 0.3s var(--ease-bounce);
}

.team-panel.red .remaining-num { color: var(--red-team); }
.team-panel.blue .remaining-num { color: var(--blue-team); }

.remaining-label {
  font-size: 0.75rem;
  color: var(--text-muted);
}

.word-dots {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
  margin-bottom: 0.85rem;
}

.dot {
  width: 10px;
  height: 10px;
  border-radius: 3px;
  transition: opacity 0.4s, transform 0.3s var(--ease-bounce);
}

.team-panel.red .dot:not(.hidden) {
  background: var(--red-team);
}

.team-panel.blue .dot:not(.hidden) {
  background: var(--blue-team);
}

.dot.hidden {
  opacity: 0.2;
  transform: scale(0.7);
  background: var(--border);
}

.player-list {
  list-style: none;
  font-size: 0.78rem;
}

.player-list li {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.35rem;
  padding: 0.3rem 0;
  color: var(--text-muted);
  border-bottom: 1px solid rgba(255, 255, 255, 0.04);
  transition: color 0.2s;
}

.player-list li:last-child {
  border-bottom: none;
}

.player-list li.spymaster {
  color: var(--text);
  font-weight: 600;
}

.player-list li.spymaster .player-name::before {
  content: '👁 ';
  font-size: 0.7rem;
}

.player-name {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.badges {
  display: flex;
  gap: 0.25rem;
  flex-shrink: 0;
}
</style>
