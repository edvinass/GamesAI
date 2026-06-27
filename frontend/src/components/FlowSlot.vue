<script setup lang="ts">
withDefaults(
  defineProps<{
    open: boolean
    horizontal?: boolean
    spaced?: false | true | 'before' | 'after'
  }>(),
  {
    horizontal: false,
    spaced: false,
  },
)
</script>

<template>
  <div
    class="flow-slot"
    :class="{
      'flow-slot--open': open,
      'flow-slot--horizontal': horizontal,
      'flow-slot--spaced-after': spaced === true || spaced === 'after',
      'flow-slot--spaced-before': spaced === 'before',
    }"
  >
    <div class="flow-slot-inner">
      <slot />
    </div>
  </div>
</template>

<style scoped>
.flow-slot {
  display: grid;
  grid-template-rows: 0fr;
  transition:
    grid-template-rows var(--flow-duration, 0.35s) var(--ease-smooth),
    margin var(--flow-duration, 0.35s) var(--ease-smooth);
}

.flow-slot--open {
  grid-template-rows: 1fr;
}

.flow-slot--horizontal {
  grid-template-rows: unset;
  grid-template-columns: 0fr;
  transition:
    grid-template-columns var(--flow-duration, 0.35s) var(--ease-smooth),
    margin var(--flow-duration, 0.35s) var(--ease-smooth);
}

.flow-slot--horizontal.flow-slot--open {
  grid-template-columns: 1fr;
}

.flow-slot-inner {
  overflow: hidden;
  min-height: 0;
  min-width: 0;
}

.flow-slot--horizontal .flow-slot-inner {
  min-height: auto;
}

.flow-slot :deep(.flow-slot-inner > *) {
  transition: opacity 0.25s var(--ease-smooth);
}

.flow-slot:not(.flow-slot--open) :deep(.flow-slot-inner > *) {
  opacity: 0;
}

.flow-slot--spaced-after.flow-slot--open {
  margin-bottom: 0.75rem;
}

.flow-slot--spaced-before.flow-slot--open {
  margin-top: 0.75rem;
}
</style>
