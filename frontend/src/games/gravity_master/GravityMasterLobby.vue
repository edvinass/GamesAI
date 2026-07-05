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
</script>

<template>
  <section class="gravity-lobby card">
    <div class="lobby-icon">🪐</div>
    <h2>Solo puzzle</h2>
    <p class="desc">
      Draw shapes that fall and become physical walls. Guide the ball into the green target across
      five levels.
    </p>

    <ul class="feature-list">
      <li>Draw ramps and platforms with limited ink</li>
      <li>Press Go! to release physics</li>
      <li>5 levels — increasing difficulty</li>
    </ul>

    <div v-if="validationIssues.length" class="issues">
      <p v-for="issue in validationIssues" :key="issue">{{ issue }}</p>
    </div>
    <p v-else class="ready-msg">{{ validationMessage }}</p>
  </section>
</template>

<style scoped>
.gravity-lobby {
  padding: 1.5rem;
  text-align: center;
  max-width: 480px;
  margin: 0 auto 1rem;
}

.lobby-icon {
  font-size: 2.5rem;
  margin-bottom: 0.5rem;
}

.gravity-lobby h2 {
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

.issues p {
  color: var(--error);
  font-size: 0.85rem;
  margin: 0.25rem 0;
}

.ready-msg {
  color: var(--success);
  font-size: 0.9rem;
  font-weight: 600;
  margin: 0;
}
</style>
