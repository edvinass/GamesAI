<script setup lang="ts">
import type { Player } from '@/types'

defineProps<{
  team: 'red' | 'blue'
  players: Player[]
  remaining: number
}>()
</script>

<template>
  <div :class="['team-panel', team]">
    <h3>{{ team.toUpperCase() }}</h3>
    <div class="remaining">{{ remaining }} left</div>
    <ul>
      <li v-for="p in players" :key="p.id" :class="{ active: p.role === 'spymaster' }">
        {{ p.nickname }}
        <span v-if="p.is_ai" class="badge badge-ai">AI</span>
        <span v-if="!p.is_connected" class="badge badge-disconnected">Off</span>
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
}

.team-panel.red {
  border-top: 3px solid var(--red-team);
}

.team-panel.blue {
  border-top: 3px solid var(--blue-team);
}

.team-panel h3 {
  font-size: 0.85rem;
  margin-bottom: 0.25rem;
}

.team-panel.red h3 { color: var(--red-team); }
.team-panel.blue h3 { color: var(--blue-team); }

.remaining {
  font-size: 1.5rem;
  font-weight: 700;
  margin-bottom: 0.75rem;
}

ul {
  list-style: none;
  font-size: 0.8rem;
}

li {
  padding: 0.25rem 0;
  color: var(--text-muted);
}

li.active {
  color: var(--text);
  font-weight: 600;
}
</style>
