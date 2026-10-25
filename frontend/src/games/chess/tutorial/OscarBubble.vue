<script setup lang="ts">
defineProps<{
  mood: 'idle' | 'happy' | 'sad' | 'think'
  text: string
}>()
</script>

<template>
  <div class="oscar" :class="mood">
    <svg class="face" viewBox="0 0 72 72" aria-hidden="true">
      <circle cx="36" cy="36" r="34" fill="#1c6b4a" />
      <circle cx="36" cy="40" r="22" fill="#f3c7a1" />
      <path d="M16 34c4-14 36-14 40 0" fill="#5c4030" />
      <circle cx="28" cy="40" r="2.2" fill="#2a2118" />
      <circle cx="44" cy="40" r="2.2" fill="#2a2118" />
      <path
        v-if="mood === 'sad'"
        d="M28 52c4-4 12-4 16 0"
        fill="none"
        stroke="#2a2118"
        stroke-width="2"
        stroke-linecap="round"
      />
      <path
        v-else-if="mood === 'think'"
        d="M30 51h12"
        fill="none"
        stroke="#2a2118"
        stroke-width="2"
        stroke-linecap="round"
      />
      <path
        v-else
        d="M29 49c3 5 11 5 14 0"
        fill="none"
        stroke="#2a2118"
        stroke-width="2"
        stroke-linecap="round"
      />
      <path d="M24 46c4 3 8 3 12 0" fill="none" stroke="#3a2a22" stroke-width="2.4" stroke-linecap="round" />
      <path d="M36 46c4 3 8 3 12 0" fill="none" stroke="#3a2a22" stroke-width="2.4" stroke-linecap="round" />
    </svg>
    <p class="bubble">{{ text }}</p>
  </div>
</template>

<style scoped>
.oscar {
  display: flex;
  align-items: flex-end;
  gap: 0.75rem;
}

.face {
  width: 64px;
  height: 64px;
  flex-shrink: 0;
  filter: drop-shadow(0 6px 10px rgba(0, 0, 0, 0.28));
}

.sad .face {
  transform: translateY(2px);
}

.think .face {
  transform: rotate(-4deg);
}

.bubble {
  margin: 0;
  padding: 0.8rem 0.95rem;
  border-radius: 16px 16px 16px 6px;
  background: var(--surface);
  border: 1px solid var(--border);
  line-height: 1.45;
  flex: 1;
}
</style>
