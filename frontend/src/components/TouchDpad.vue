<script setup lang="ts">
import { ref, computed, onUnmounted } from 'vue'

export type Direction = 'up' | 'down' | 'left' | 'right'

const props = withDefaults(
  defineProps<{
    /** Whether to emit 'stop' when touch ends (for hold-to-move games) */
    emitStop?: boolean
    /** Accent color for the control */
    accentColor?: string
    /** Minimum drag distance from center to register a direction (0-1, relative to radius) */
    deadZone?: number
    /** Size of the control in rem */
    size?: number
  }>(),
  {
    emitStop: false,
    accentColor: '#a7f3d0',
    deadZone: 0.15,
    size: 9,
  },
)

const emit = defineEmits<{
  direction: [direction: Direction]
  stop: []
}>()

const padRef = ref<HTMLElement | null>(null)
const activeDirection = ref<Direction | null>(null)
const isActive = ref(false)

const accentRgb = computed(() => {
  const hex = props.accentColor.replace('#', '')
  const r = parseInt(hex.slice(0, 2), 16)
  const g = parseInt(hex.slice(2, 4), 16)
  const b = parseInt(hex.slice(4, 6), 16)
  return `${r}, ${g}, ${b}`
})

function getDirectionFromAngle(angle: number): Direction {
  const normalized = ((angle % 360) + 360) % 360
  if (normalized >= 315 || normalized < 45) return 'right'
  if (normalized >= 45 && normalized < 135) return 'down'
  if (normalized >= 135 && normalized < 225) return 'left'
  return 'up'
}

function handleTouch(clientX: number, clientY: number) {
  const pad = padRef.value
  if (!pad) return

  const rect = pad.getBoundingClientRect()
  const centerX = rect.left + rect.width / 2
  const centerY = rect.top + rect.height / 2
  const radius = rect.width / 2

  const dx = clientX - centerX
  const dy = clientY - centerY
  const distance = Math.sqrt(dx * dx + dy * dy)
  const normalizedDistance = distance / radius

  if (normalizedDistance < props.deadZone) {
    return
  }

  const angle = Math.atan2(dy, dx) * (180 / Math.PI)
  const direction = getDirectionFromAngle(angle)

  if (direction !== activeDirection.value) {
    activeDirection.value = direction
    emit('direction', direction)
  }
}

function onTouchStart(e: TouchEvent) {
  e.preventDefault()
  isActive.value = true
  const touch = e.touches[0]
  if (touch) {
    handleTouch(touch.clientX, touch.clientY)
  }
}

function onTouchMove(e: TouchEvent) {
  e.preventDefault()
  const touch = e.touches[0]
  if (touch) {
    handleTouch(touch.clientX, touch.clientY)
  }
}

function onTouchEnd(e: TouchEvent) {
  e.preventDefault()
  isActive.value = false
  activeDirection.value = null
  if (props.emitStop) {
    emit('stop')
  }
}

function onMouseDown(e: MouseEvent) {
  e.preventDefault()
  isActive.value = true
  handleTouch(e.clientX, e.clientY)
  window.addEventListener('mousemove', onMouseMove)
  window.addEventListener('mouseup', onMouseUp)
}

function onMouseMove(e: MouseEvent) {
  handleTouch(e.clientX, e.clientY)
}

function onMouseUp() {
  isActive.value = false
  activeDirection.value = null
  if (props.emitStop) {
    emit('stop')
  }
  window.removeEventListener('mousemove', onMouseMove)
  window.removeEventListener('mouseup', onMouseUp)
}

onUnmounted(() => {
  window.removeEventListener('mousemove', onMouseMove)
  window.removeEventListener('mouseup', onMouseUp)
})
</script>

<template>
  <div
    ref="padRef"
    class="touch-dpad-circle"
    :class="{ active: isActive }"
    :style="{
      '--accent': accentColor,
      '--accent-rgb': accentRgb,
      '--size': `${size}rem`,
    }"
    @touchstart="onTouchStart"
    @touchmove="onTouchMove"
    @touchend="onTouchEnd"
    @touchcancel="onTouchEnd"
    @mousedown="onMouseDown"
  >
    <div class="dpad-inner">
      <div class="direction-indicator" :class="activeDirection ?? ''">
        <span class="arrow up" :class="{ active: activeDirection === 'up' }">▲</span>
        <span class="arrow left" :class="{ active: activeDirection === 'left' }">◀</span>
        <span class="arrow right" :class="{ active: activeDirection === 'right' }">▶</span>
        <span class="arrow down" :class="{ active: activeDirection === 'down' }">▼</span>
        <div class="center-dot" />
      </div>
    </div>
  </div>
</template>

<style scoped>
.touch-dpad-circle {
  width: var(--size);
  height: var(--size);
  border-radius: 50%;
  background: radial-gradient(
    circle at 50% 50%,
    rgba(var(--accent-rgb), 0.12) 0%,
    rgba(var(--accent-rgb), 0.06) 50%,
    rgba(10, 18, 16, 0.92) 100%
  );
  border: 2px solid rgba(var(--accent-rgb), 0.35);
  backdrop-filter: blur(8px);
  box-shadow:
    0 4px 20px rgba(0, 0, 0, 0.4),
    inset 0 0 30px rgba(var(--accent-rgb), 0.08);
  touch-action: none;
  user-select: none;
  cursor: pointer;
  transition: transform 0.15s ease, box-shadow 0.15s ease;
  pointer-events: auto;
}

.touch-dpad-circle.active {
  transform: scale(0.98);
  box-shadow:
    0 2px 12px rgba(0, 0, 0, 0.5),
    inset 0 0 40px rgba(var(--accent-rgb), 0.15);
  border-color: rgba(var(--accent-rgb), 0.55);
}

.dpad-inner {
  width: 100%;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
}

.direction-indicator {
  position: relative;
  width: 70%;
  height: 70%;
}

.arrow {
  position: absolute;
  font-size: 1.25rem;
  color: rgba(var(--accent-rgb), 0.45);
  transition: color 0.1s ease, transform 0.1s ease, text-shadow 0.1s ease;
}

.arrow.active {
  color: var(--accent);
  text-shadow: 0 0 12px rgba(var(--accent-rgb), 0.6);
  transform: scale(1.15);
}

.arrow.up {
  top: 0;
  left: 50%;
  transform: translateX(-50%);
}

.arrow.up.active {
  transform: translateX(-50%) scale(1.15);
}

.arrow.down {
  bottom: 0;
  left: 50%;
  transform: translateX(-50%);
}

.arrow.down.active {
  transform: translateX(-50%) scale(1.15);
}

.arrow.left {
  left: 0;
  top: 50%;
  transform: translateY(-50%);
}

.arrow.left.active {
  transform: translateY(-50%) scale(1.15);
}

.arrow.right {
  right: 0;
  top: 50%;
  transform: translateY(-50%);
}

.arrow.right.active {
  transform: translateY(-50%) scale(1.15);
}

.center-dot {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  width: 12px;
  height: 12px;
  border-radius: 50%;
  background: rgba(var(--accent-rgb), 0.25);
  border: 1px solid rgba(var(--accent-rgb), 0.4);
}

.touch-dpad-circle.active .center-dot {
  background: rgba(var(--accent-rgb), 0.4);
  box-shadow: 0 0 8px rgba(var(--accent-rgb), 0.5);
}
</style>
