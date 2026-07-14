<script setup lang="ts">
import { computed, ref } from 'vue'
import { POWERUP_COLORS, POWERUP_ICONS, POWERUP_LABELS } from './duelRenderer'
import {
  POWERUP_HINTS,
  POWERUP_TIER_LABELS,
  powerupTier,
  powerupUseHint,
} from './powerupMeta'

const query = ref('')

const entries = computed(() =>
  Object.keys(POWERUP_LABELS)
    .map((id) => ({
      id,
      label: POWERUP_LABELS[id],
      icon: POWERUP_ICONS[id],
      color: POWERUP_COLORS[id],
      tier: POWERUP_TIER_LABELS[powerupTier(id)],
      hint: POWERUP_HINTS[id] ?? '',
      use: powerupUseHint(id),
    }))
    .filter((entry) => {
      const q = query.value.trim().toLowerCase()
      if (!q) return true
      return (
        entry.id.includes(q) ||
        entry.label.toLowerCase().includes(q) ||
        entry.tier.toLowerCase().includes(q)
      )
    }),
)
</script>

<template>
  <details class="encyclopedia card">
    <summary>Power-up encyclopedia</summary>
    <input v-model="query" class="search" type="search" placeholder="Search power-ups…" />
    <div class="grid">
      <article v-for="entry in entries" :key="entry.id" class="entry">
        <header>
          <span class="icon" :style="{ color: entry.color }">{{ entry.icon }}</span>
          <strong>{{ entry.label }}</strong>
          <span class="tier">{{ entry.tier }}</span>
        </header>
        <p>{{ entry.hint }}</p>
        <p class="use">{{ entry.use }}</p>
      </article>
    </div>
  </details>
</template>

<style scoped>
.encyclopedia {
  margin-top: 0.75rem;
  padding: 0.75rem 1rem;
}

summary {
  cursor: pointer;
  font-weight: 600;
}

.search {
  width: 100%;
  margin: 0.75rem 0;
  padding: 0.45rem 0.6rem;
  border-radius: 8px;
  border: 1px solid rgba(148, 163, 184, 0.25);
  background: rgba(15, 23, 42, 0.6);
  color: inherit;
}

.grid {
  display: grid;
  gap: 0.6rem;
  max-height: 280px;
  overflow: auto;
}

.entry {
  padding: 0.55rem 0.65rem;
  border-radius: 10px;
  background: rgba(15, 23, 42, 0.45);
}

.entry header {
  display: flex;
  align-items: center;
  gap: 0.45rem;
}

.icon {
  font-size: 1.1rem;
}

.tier {
  margin-left: auto;
  font-size: 0.75rem;
  opacity: 0.75;
}

.entry p {
  margin: 0.35rem 0 0;
  font-size: 0.85rem;
  opacity: 0.9;
}

.use {
  opacity: 0.75;
  font-size: 0.8rem !important;
}
</style>
