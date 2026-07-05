<script setup lang="ts">
import { onMounted, onUnmounted, ref, watch } from 'vue'
import { pieceCells } from './pieces'
import { computeBoardMetrics, drawBlock } from './render'

const props = defineProps<{
  pieceType: string | null | undefined
  color: string | null | undefined
  compact?: boolean
}>()

const canvasRef = ref<HTMLCanvasElement | null>(null)
const PREVIEW_CELLS = 4

function draw() {
  const canvas = canvasRef.value
  if (!canvas) return
  const ctx = canvas.getContext('2d')
  if (!ctx) return

  const displayW = canvas.clientWidth
  const displayH = canvas.clientHeight
  if (displayW <= 0 || displayH <= 0) return

  const dpr = window.devicePixelRatio || 1
  canvas.width = Math.floor(displayW * dpr)
  canvas.height = Math.floor(displayH * dpr)
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0)

  const metrics = computeBoardMetrics(displayW, displayH, PREVIEW_CELLS, PREVIEW_CELLS)

  ctx.fillStyle = '#0a0e14'
  ctx.fillRect(0, 0, displayW, displayH)
  ctx.fillRect(metrics.offsetX, metrics.offsetY, metrics.boardW, metrics.boardH)

  ctx.strokeStyle = '#1e293b'
  ctx.lineWidth = 1
  for (let x = 0; x <= PREVIEW_CELLS; x++) {
    ctx.beginPath()
    ctx.moveTo(metrics.offsetX + x * metrics.cell, metrics.offsetY)
    ctx.lineTo(metrics.offsetX + x * metrics.cell, metrics.offsetY + metrics.boardH)
    ctx.stroke()
  }
  for (let y = 0; y <= PREVIEW_CELLS; y++) {
    ctx.beginPath()
    ctx.moveTo(metrics.offsetX, metrics.offsetY + y * metrics.cell)
    ctx.lineTo(metrics.offsetX + metrics.boardW, metrics.offsetY + y * metrics.cell)
    ctx.stroke()
  }

  if (props.pieceType && props.color) {
    const cells = pieceCells(props.pieceType, 0, 0, 0)
    for (const [x, y] of cells) {
      if (x < 0 || y < 0 || x >= PREVIEW_CELLS || y >= PREVIEW_CELLS) continue
      drawBlock(ctx, metrics, x, y, props.color)
    }
  }
}

let resizeObserver: ResizeObserver | null = null

watch(() => [props.pieceType, props.color], draw)

onMounted(() => {
  if (canvasRef.value) {
    resizeObserver = new ResizeObserver(() => draw())
    resizeObserver.observe(canvasRef.value)
  }
  draw()
})

onUnmounted(() => {
  resizeObserver?.disconnect()
})
</script>

<template>
  <div class="next-piece-preview" :class="{ compact }">
    <span class="next-label">Next</span>
    <canvas ref="canvasRef" class="next-canvas" />
  </div>
</template>

<style scoped>
.next-piece-preview {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 0.25rem;
  width: 3.75rem;
}

.next-piece-preview.compact {
  width: 2.75rem;
  gap: 0.15rem;
}

.next-label {
  font-size: 0.6rem;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--text-muted);
}

.next-piece-preview.compact .next-label {
  font-size: 0.5rem;
}

.next-canvas {
  width: 100%;
  aspect-ratio: 1;
  display: block;
  border: 1px solid rgba(255, 255, 255, 0.06);
  border-radius: 4px;
  background: #0a0e14;
}
</style>
