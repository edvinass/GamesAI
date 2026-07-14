<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import type { Room, DuelGameState } from '@/types'

const props = defineProps<{
  gameState: DuelGameState
  room: Room
  playerId: string
}>()

const emit = defineEmits<{
  action: [data: Record<string, unknown>]
}>()

const canvasRef = ref<HTMLCanvasElement | null>(null)
const canvasWrapRef = ref<HTMLElement | null>(null)

const myFighter = computed(() => props.gameState.fighters[props.playerId])
const isAlive = computed(() => myFighter.value?.alive ?? false)
const isHost = computed(() => props.room.host_player_id === props.playerId)
const isFinished = computed(() => props.gameState.phase === 'finished')
const isRoundOver = computed(() => props.gameState.phase === 'round_over')
const canControl = computed(
  () => props.gameState.phase === 'playing' && isAlive.value,
)
const chargeEnabled = computed(() => props.gameState.match_format !== 'quick_duel')

const roundsToWin = computed(() => Math.ceil(props.gameState.best_of / 2))

const countdownRemaining = computed(() => {
  if (
    props.gameState.phase !== 'countdown' &&
    props.gameState.phase !== 'round_over'
  ) {
    return null
  }
  if (!props.gameState.countdown_ends_at) return null
  const end = new Date(props.gameState.countdown_ends_at).getTime()
  return Math.max(0, Math.ceil((end - Date.now()) / 1000))
})

const winnerName = computed(() => {
  const winnerId = props.gameState.winner
  if (!winnerId) return 'Draw'
  const player = props.gameState.players.find((p) => p.id === winnerId)
  return player?.nickname ?? 'Unknown'
})

const roundWinnerName = computed(() => {
  const winnerId = props.gameState.round_winner
  if (!winnerId) return null
  const player = props.gameState.players.find((p) => p.id === winnerId)
  return player?.nickname ?? 'Unknown'
})

const playerRows = computed(() =>
  props.gameState.players.map((p) => ({
    ...p,
    fighter: props.gameState.fighters[p.id],
    roundWins: props.gameState.round_scores[p.id] ?? 0,
  })),
)

const heldMove = ref<'up' | 'down' | null>(null)
const charging = ref(false)
const chargeTicks = ref(0)
const localChargeInterval = ref<ReturnType<typeof setInterval> | null>(null)
const hitFlashUntil = ref(0)
const shakeUntil = ref(0)

const dangerRows = computed(() => {
  const rows = new Set<number>()
  if (!myFighter.value?.alive) return rows
  const myX = myFighter.value.x
  for (const bullet of props.gameState.bullets) {
    if (bullet.owner_id === props.playerId) continue
    const headingToward =
      (myFighter.value.side === 'left' && bullet.vx < 0 && bullet.x >= myX) ||
      (myFighter.value.side === 'right' && bullet.vx > 0 && bullet.x <= myX)
    if (!headingToward) continue
    const speed = Math.abs(bullet.vx) || 1
    const ticks = Math.abs(bullet.x - myX) / speed
    if (ticks <= 6) rows.add(bullet.y)
  }
  return rows
})

watch(
  () => props.gameState.last_hit,
  (hit) => {
    if (!hit) return
    if (hit.player_id === props.playerId) {
      hitFlashUntil.value = Date.now() + 250
      shakeUntil.value = Date.now() + 200
    } else if (hit.damage > 0) {
      shakeUntil.value = Date.now() + 120
    }
  },
)

function startNewGame() {
  emit('action', { type: 'start_game' })
}

function sendMove(direction: 'up' | 'down' | 'stop') {
  emit('action', { type: 'set_move', direction })
}

function startCharge() {
  if (!canControl.value || !chargeEnabled.value) return
  charging.value = true
  chargeTicks.value = 0
  emit('action', { type: 'charge_start' })
  if (localChargeInterval.value) clearInterval(localChargeInterval.value)
  localChargeInterval.value = setInterval(() => {
    if (charging.value) chargeTicks.value = Math.min(15, chargeTicks.value + 1)
  }, 75)
}

function releaseCharge() {
  if (!charging.value) return
  charging.value = false
  if (localChargeInterval.value) {
    clearInterval(localChargeInterval.value)
    localChargeInterval.value = null
  }
  emit('action', { type: 'release_charge', charge_ticks: chargeTicks.value })
  chargeTicks.value = 0
}

function quickShoot() {
  emit('action', { type: 'shoot' })
}

function onKeyDown(e: KeyboardEvent) {
  if (!canControl.value) return

  if (e.key === 'ArrowUp' || e.key === 'w' || e.key === 'W') {
    e.preventDefault()
    if (heldMove.value !== 'up') {
      heldMove.value = 'up'
      sendMove('up')
    }
    return
  }

  if (e.key === 'ArrowDown' || e.key === 's' || e.key === 'S') {
    e.preventDefault()
    if (heldMove.value !== 'down') {
      heldMove.value = 'down'
      sendMove('down')
    }
    return
  }

  if (e.key === ' ') {
    e.preventDefault()
    if (chargeEnabled.value) {
      if (!charging.value) startCharge()
    } else {
      quickShoot()
    }
  }
}

function onKeyUp(e: KeyboardEvent) {
  if (!canControl.value) return

  if (
    (e.key === 'ArrowUp' || e.key === 'w' || e.key === 'W') &&
    heldMove.value === 'up'
  ) {
    heldMove.value = null
    sendMove('stop')
    return
  }

  if (
    (e.key === 'ArrowDown' || e.key === 's' || e.key === 'S') &&
    heldMove.value === 'down'
  ) {
    heldMove.value = null
    sendMove('stop')
    return
  }

  if (e.key === ' ') {
    e.preventDefault()
    if (charging.value) releaseCharge()
  }
}

const POWERUP_COLORS: Record<string, string> = {
  rapid_fire: '#f97316',
  shield: '#38bdf8',
  wide_shot: '#a855f7',
  ghost: '#94a3b8',
}

const MUTATOR_LABELS: Record<string, string> = {
  classic: 'Classic',
  chaos: 'Chaos',
  sniper: 'Sniper',
  bounce_house: 'Bounce House',
  fog: 'Fog',
}

function fighterDisplayY(pid: string, fighter: (typeof props.gameState.fighters)[string]) {
  if (pid === props.playerId || fighter.display_y == null) return fighter.y
  return fighter.display_y
}

function draw() {
  const canvas = canvasRef.value
  const wrap = canvasWrapRef.value
  if (!canvas || !wrap) return
  const ctx = canvas.getContext('2d')
  if (!ctx) return

  const {
    grid_width,
    grid_height,
    fighter_height,
    fighters,
    bullets,
    obstacles,
    powerup,
    playable_y_min,
    playable_y_max,
  } = props.gameState
  const barCount = fighter_height ?? 3
  const displayW = wrap.clientWidth
  const displayH = wrap.clientHeight
  if (displayW <= 0 || displayH <= 0) return

  const shakeX =
    Date.now() < shakeUntil.value ? (Math.random() - 0.5) * 6 : 0
  const shakeY =
    Date.now() < shakeUntil.value ? (Math.random() - 0.5) * 4 : 0

  const dpr = window.devicePixelRatio || 1
  canvas.width = Math.floor(displayW * dpr)
  canvas.height = Math.floor(displayH * dpr)
  canvas.style.width = `${displayW}px`
  canvas.style.height = `${displayH}px`
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0)

  const cell = Math.min(displayW / grid_width, displayH / grid_height)
  const boardW = cell * grid_width
  const boardH = cell * grid_height
  const offsetX = (displayW - boardW) / 2 + shakeX
  const offsetY = (displayH - boardH) / 2 + shakeY

  ctx.fillStyle = '#0f1419'
  ctx.fillRect(0, 0, displayW, displayH)

  if (Date.now() < hitFlashUntil.value) {
    ctx.fillStyle = 'rgba(239, 68, 68, 0.18)'
    ctx.fillRect(0, 0, displayW, displayH)
  }

  ctx.fillRect(offsetX, offsetY, boardW, boardH)

  if (playable_y_min > 0) {
    ctx.fillStyle = 'rgba(239, 68, 68, 0.22)'
    ctx.fillRect(offsetX, offsetY, boardW, playable_y_min * cell)
  }
  if (playable_y_max < grid_height - 1) {
    const deadH = (grid_height - 1 - playable_y_max) * cell
    ctx.fillStyle = 'rgba(239, 68, 68, 0.22)'
    ctx.fillRect(offsetX, offsetY + (playable_y_max + 1) * cell, boardW, deadH)
  }

  ctx.strokeStyle = '#1e293b'
  ctx.lineWidth = 1
  for (let x = 0; x <= grid_width; x++) {
    ctx.beginPath()
    ctx.moveTo(offsetX + x * cell, offsetY)
    ctx.lineTo(offsetX + x * cell, offsetY + boardH)
    ctx.stroke()
  }
  for (let y = 0; y <= grid_height; y++) {
    ctx.beginPath()
    ctx.moveTo(offsetX, offsetY + y * cell)
    ctx.lineTo(offsetX + boardW, offsetY + y * cell)
    ctx.stroke()
  }

  ctx.fillStyle = 'rgba(91, 156, 255, 0.08)'
  ctx.fillRect(offsetX, offsetY, cell * 2, boardH)
  ctx.fillRect(offsetX + boardW - cell * 2, offsetY, cell * 2, boardH)

  for (const obstacle of obstacles) {
    ctx.fillStyle = '#334155'
    ctx.fillRect(
      offsetX + obstacle.x * cell,
      offsetY + obstacle.y * cell,
      obstacle.w * cell,
      obstacle.h * cell,
    )
    ctx.strokeStyle = '#64748b'
    ctx.lineWidth = Math.max(1, cell * 0.06)
    ctx.strokeRect(
      offsetX + obstacle.x * cell + 1,
      offsetY + obstacle.y * cell + 1,
      obstacle.w * cell - 2,
      obstacle.h * cell - 2,
    )
  }

  if (powerup) {
    const color = POWERUP_COLORS[powerup.type] ?? '#fbbf24'
    const cx = offsetX + powerup.x * cell + cell / 2
    const cy = offsetY + powerup.y * cell + cell / 2
    const pulse = 0.85 + Math.sin(Date.now() / 180) * 0.15
    ctx.fillStyle = color
    ctx.globalAlpha = 0.35
    ctx.beginPath()
    ctx.arc(cx, cy, cell * 0.55 * pulse, 0, Math.PI * 2)
    ctx.fill()
    ctx.globalAlpha = 1
    ctx.beginPath()
    ctx.arc(cx, cy, cell * 0.28, 0, Math.PI * 2)
    ctx.fill()
  }

  for (const bullet of bullets) {
    const trailAlpha = 0.35
    ctx.fillStyle = `rgba(251, 191, 36, ${trailAlpha})`
    const trailX = offsetX + (bullet.x - bullet.vx * 0.4) * cell + cell / 2
    const trailY = offsetY + (bullet.y - (bullet.vy ?? 0) * 0.4) * cell + cell / 2
    ctx.beginPath()
    ctx.arc(trailX, trailY, cell * 0.22, 0, Math.PI * 2)
    ctx.fill()

    ctx.fillStyle = bullet.damage && bullet.damage >= 2 ? '#fb7185' : '#fbbf24'
    const pad = Math.max(2, cell * 0.2)
    ctx.beginPath()
    ctx.arc(
      offsetX + bullet.x * cell + cell / 2,
      offsetY + bullet.y * cell + cell / 2,
      cell / 2 - pad,
      0,
      Math.PI * 2,
    )
    ctx.fill()
  }

  for (const [pid, fighter] of Object.entries(fighters)) {
    const isMe = pid === props.playerId
    const displayY = fighterDisplayY(pid, fighter)
    const ghosted = fighter.effects?.ghost_active && !isMe
    const alpha = fighter.alive ? (ghosted ? 0.45 : 1) : 0.35
    ctx.globalAlpha = alpha
    const inset = Math.max(1, cell * 0.1)
    const barGap = Math.max(1, cell * 0.06)
    const barH = (cell * barCount - barGap * (barCount - 1)) / barCount

    for (let i = 0; i < barCount; i++) {
      ctx.fillStyle = fighter.color
      const barY = displayY + i
      if (dangerRows.value.has(barY) && isMe) {
        ctx.fillStyle = '#fca5a5'
      }
      ctx.fillRect(
        offsetX + fighter.x * cell + inset,
        offsetY + barY * cell + (cell - barH) / 2,
        cell - inset * 2,
        barH,
      )
    }

    if (fighter.effects?.shield) {
      ctx.strokeStyle = 'rgba(56, 189, 248, 0.9)'
      ctx.lineWidth = Math.max(2, cell * 0.1)
      ctx.strokeRect(
        offsetX + fighter.x * cell,
        offsetY + displayY * cell,
        cell,
        cell * barCount,
      )
    }

    if (isMe && fighter.alive) {
      ctx.strokeStyle = '#fff'
      ctx.lineWidth = Math.max(1, cell * 0.08)
      ctx.strokeRect(
        offsetX + fighter.x * cell + 1,
        offsetY + displayY * cell + 1,
        cell - 2,
        cell * barCount - 2,
      )

      const aimRow = displayY + Math.floor(barCount / 2)
      ctx.strokeStyle = 'rgba(255,255,255,0.25)'
      ctx.setLineDash([cell * 0.3, cell * 0.25])
      ctx.beginPath()
      ctx.moveTo(offsetX + fighter.x * cell + cell, offsetY + aimRow * cell + cell / 2)
      ctx.lineTo(offsetX + boardW, offsetY + aimRow * cell + cell / 2)
      ctx.stroke()
      ctx.setLineDash([])
    }
    ctx.globalAlpha = 1
  }
}

let resizeObserver: ResizeObserver | null = null
let animFrame = 0

function animationLoop() {
  draw()
  animFrame = requestAnimationFrame(animationLoop)
}

watch(() => props.gameState, draw, { deep: true })

onMounted(() => {
  window.addEventListener('keydown', onKeyDown)
  window.addEventListener('keyup', onKeyUp)
  if (canvasWrapRef.value) {
    resizeObserver = new ResizeObserver(() => draw())
    resizeObserver.observe(canvasWrapRef.value)
  }
  animFrame = requestAnimationFrame(animationLoop)
})

onUnmounted(() => {
  window.removeEventListener('keydown', onKeyDown)
  window.removeEventListener('keyup', onKeyUp)
  resizeObserver?.disconnect()
  cancelAnimationFrame(animFrame)
  if (localChargeInterval.value) clearInterval(localChargeInterval.value)
})
</script>

<template>
  <div class="duel-board">
    <div class="match-bar">
      <span class="match-format">Round {{ gameState.round }} · Best of {{ gameState.best_of }}</span>
      <span class="mutator-tag">{{ MUTATOR_LABELS[gameState.mutator] ?? gameState.mutator }}</span>
    </div>

    <div ref="canvasWrapRef" class="canvas-wrap">
      <canvas ref="canvasRef" class="game-canvas" />

      <div v-if="charging && canControl" class="charge-bar">
        <div class="charge-fill" :style="{ width: `${(chargeTicks / 15) * 100}%` }" />
        <span class="charge-label">Charging…</span>
      </div>

      <div v-if="gameState.phase === 'countdown'" class="overlay countdown">
        <span class="overlay-value">{{ countdownRemaining ?? '…' }}</span>
        <span class="overlay-label">Get ready!</span>
      </div>

      <div v-else-if="isRoundOver" class="overlay round-over">
        <span class="overlay-label">Round {{ gameState.round - 1 }} over</span>
        <span v-if="roundWinnerName" class="overlay-value">{{ roundWinnerName }} wins the round!</span>
        <span v-else class="overlay-value">Draw — rematch!</span>
        <span class="overlay-hint">Next round in {{ countdownRemaining ?? '…' }}</span>
      </div>

      <div v-else-if="isFinished" class="overlay finished">
        <span class="overlay-label">Match over</span>
        <span class="overlay-value">{{ winnerName }} wins!</span>
        <button v-if="isHost" type="button" class="btn-primary play-again-btn" @click="startNewGame">
          Play Again
        </button>
        <p v-else class="overlay-hint">Waiting for host to start a new match…</p>
      </div>

      <div v-else-if="!isAlive" class="overlay eliminated">
        <span class="overlay-label">You were eliminated!</span>
        <span class="overlay-hint">Watch the round continue…</span>
      </div>
    </div>

    <aside class="player-bar">
      <ul class="player-scores">
        <li
          v-for="row in playerRows"
          :key="row.id"
          class="player-score-row"
          :class="{ me: row.id === playerId, dead: !row.fighter?.alive }"
        >
          <span class="color-dot" :style="{ background: row.fighter?.color ?? '#666' }" />
          <span class="name">{{ row.nickname }}</span>
          <span class="round-wins">{{ row.roundWins }}/{{ roundsToWin }}</span>
          <span v-if="row.fighter" class="hp-bar">
            <span
              v-for="i in row.fighter.max_hp"
              :key="i"
              class="hp-pip"
              :class="{ spent: i > row.fighter.hp }"
            />
          </span>
          <span v-if="row.fighter?.effects?.shield" class="effect-badge">🛡</span>
          <span v-if="!row.fighter?.alive" class="status">out</span>
        </li>
      </ul>

      <div class="controls-hint">
        <p v-if="canControl && chargeEnabled">
          <strong>Controls:</strong> W/S or ↑/↓ to move · Hold Space to charge, release to fire
        </p>
        <p v-else-if="canControl">
          <strong>Controls:</strong> W/S or ↑/↓ to move · Space to shoot
        </p>
        <p v-else-if="gameState.phase === 'playing' && !isAlive" class="muted">Spectating</p>
        <p v-else class="muted">Waiting…</p>
      </div>
    </aside>
  </div>
</template>

<style scoped>
.duel-board {
  flex: 1;
  width: 100%;
  min-height: 0;
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
  padding: 0 0.5rem 0.5rem;
}

.match-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.75rem;
  padding: 0.4rem 0.75rem;
  font-size: 0.85rem;
  color: var(--text-muted);
}

.mutator-tag {
  padding: 0.15rem 0.5rem;
  border-radius: 999px;
  background: var(--surface-elevated);
  font-size: 0.75rem;
  font-weight: 600;
}

.canvas-wrap {
  position: relative;
  flex: 1;
  min-height: 0;
  width: 100%;
  overflow: hidden;
  border: 1px solid var(--border);
  border-radius: var(--radius);
  background: #0f1419;
}

.game-canvas {
  display: block;
  width: 100%;
  height: 100%;
}

.charge-bar {
  position: absolute;
  left: 50%;
  bottom: 0.75rem;
  transform: translateX(-50%);
  width: min(240px, 70%);
  height: 8px;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.15);
  overflow: hidden;
}

.charge-fill {
  height: 100%;
  background: linear-gradient(90deg, #fbbf24, #ef4444);
  transition: width 75ms linear;
}

.charge-label {
  position: absolute;
  top: -1.35rem;
  left: 50%;
  transform: translateX(-50%);
  font-size: 0.75rem;
  color: #fbbf24;
  white-space: nowrap;
}

.overlay {
  position: absolute;
  inset: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  background: rgba(0, 0, 0, 0.65);
  gap: 0.5rem;
  padding: 1rem;
  text-align: center;
}

.overlay-value {
  font-size: clamp(1.75rem, 4vw, 2.5rem);
  font-weight: 800;
}

.overlay-label {
  font-size: 1.1rem;
  font-weight: 600;
}

.overlay-hint {
  font-size: 0.9rem;
  color: var(--text-muted);
}

.play-again-btn {
  margin-top: 0.5rem;
}

.player-bar {
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1rem;
  padding: 0.65rem 1rem;
  border: 1px solid var(--border);
  border-radius: var(--radius);
  background: var(--surface);
}

.player-scores {
  list-style: none;
  display: flex;
  flex-wrap: wrap;
  gap: 0.75rem 1.25rem;
  flex: 1;
  min-width: 0;
}

.player-score-row {
  display: flex;
  align-items: center;
  gap: 0.45rem;
  font-size: 0.9rem;
}

.player-score-row.me {
  font-weight: 700;
}

.player-score-row.dead {
  opacity: 0.55;
}

.color-dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  flex-shrink: 0;
}

.name {
  max-width: 8rem;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.round-wins {
  font-size: 0.75rem;
  font-weight: 700;
  color: var(--accent);
}

.hp-bar {
  display: inline-flex;
  gap: 3px;
}

.hp-pip {
  width: 8px;
  height: 8px;
  border-radius: 2px;
  background: #22c55e;
}

.hp-pip.spent {
  background: #334155;
}

.effect-badge {
  font-size: 0.85rem;
}

.status {
  font-size: 0.7rem;
  text-transform: uppercase;
  color: var(--text-muted);
}

.controls-hint {
  flex-shrink: 0;
  font-size: 0.85rem;
  color: var(--text-muted);
  text-align: right;
}

@media (max-width: 640px) {
  .player-bar {
    flex-direction: column;
    align-items: flex-start;
  }

  .controls-hint {
    text-align: left;
  }
}

.muted {
  color: var(--text-muted);
}
</style>
