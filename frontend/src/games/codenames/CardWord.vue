<script setup lang="ts">
import { nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'

const props = defineProps<{
  text: string
}>()

const root = ref<HTMLElement | null>(null)
let observer: ResizeObserver | null = null
let frame = 0
const MIN_PX = 8

function fits(node: HTMLElement, maxHeight: number) {
  return node.scrollWidth <= node.clientWidth + 1 && node.scrollHeight <= maxHeight + 1
}

function fit() {
  const node = root.value
  const parent = node?.parentElement
  if (!node || !parent) return

  const style = getComputedStyle(parent)
  const maxHeight = parent.clientHeight - parseFloat(style.paddingTop) - parseFloat(style.paddingBottom)
  if (maxHeight <= 0 || parent.clientWidth <= 0) return

  node.style.fontSize = ''
  const maxSize = parseFloat(getComputedStyle(node).fontSize)
  if (!Number.isFinite(maxSize) || maxSize <= MIN_PX) return
  if (fits(node, maxHeight)) return

  let lo = MIN_PX
  let hi = maxSize
  let best = MIN_PX
  for (let i = 0; i < 12; i++) {
    const mid = (lo + hi) / 2
    node.style.fontSize = `${mid}px`
    if (fits(node, maxHeight)) {
      best = mid
      lo = mid
    } else {
      hi = mid
    }
  }
  node.style.fontSize = `${best}px`
}

function schedule() {
  cancelAnimationFrame(frame)
  frame = requestAnimationFrame(() => fit())
}

onMounted(() => {
  fit()
  const parent = root.value?.parentElement
  if (parent) {
    observer = new ResizeObserver(schedule)
    observer.observe(parent)
  }
  document.fonts?.ready.then(schedule).catch(() => {})
})

watch(
  () => props.text,
  async () => {
    await nextTick()
    schedule()
  },
)

onBeforeUnmount(() => {
  cancelAnimationFrame(frame)
  observer?.disconnect()
})
</script>

<template>
  <span ref="root" class="card-word">{{ text }}</span>
</template>

<style scoped>
.card-word {
  display: block;
  width: 100%;
  min-width: 0;
  max-height: 100%;
  font-size: var(--card-word-size, 1.5rem);
  line-height: 1.05;
  text-align: center;
  white-space: normal;
  overflow-wrap: normal;
  word-break: keep-all;
}
</style>
