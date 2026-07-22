<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import type { PacmanGameState, Room } from '@/types'
import {
  renderFrame,
  smoothEntities,
  smoothGhostList,
  snapshotEntities,
  spawnChompParticles,
  updateParticles,
  type Particle,
  type SmoothEntity,
} from './pacmanRender'
import {
  isSoundMuted,
  playDeath,
  playGhostEat,
  playLose,
  playPellet,
  playPower,
  playWin,
  setSoundMuted,
  unlockAudio,
} from './sounds'

const props = defineProps<{
  gameState: PacmanGameState
  room: Room
  playerId: string
}>()

const emit = defineEmits<{
  action: [data: Record<string, unknown>]
}>()

const canvasRef = ref<HTMLCanvasElement | null>(null)
const canvasWrapRef = ref<HTMLElement | null>(null)
const soundMuted = ref(isSoundMuted())

const myPac = computed(() => props.gameState.pacmen[props.playerId])
const isAlive = computed(() => myPac.value?.alive ?? false)
const isHost = computed(() => props.room.host_player_id === props.playerId)
const isFinished = computed(() => props.gameState.phase === 'finished')
const canControl = computed(
  () =>
    props.gameState.phase === 'playing' &&
    isAlive.value &&
    (myPac.value?.respawn_ticks ?? 0) <= 0,
)

const countdownRemaining = computed(() => {
  if (props.gameState.phase !== 'countdown' || !props.gameState.countdown_ends_at) return null
  const end = new Date(props.gameState.countdown_ends_at).getTime()
  return Math.max(0, Math.ceil((end - Date.now()) / 1000))
})

const winnerName = computed(() => {
  const winnerId = props.gameState.winner
  if (!winnerId) return null
  return props.gameState.players.find((p) => p.id === winnerId)?.nickname ?? 'Unknown'
})

const winReasonLabel = computed(() => {
  const reason = props.gameState.win_reason
  if (reason === 'last_standing') return 'Last Pac-Man standing'
  if (reason === 'maze_clear') return 'Maze cleared — highest score'
  if (reason === 'highest_score') return 'Highest score'
  return null
})

const playerRows = computed(() =>
  props.gameState.players.map((p) => ({
    ...p,
    pac: props.gameState.pacmen[p.id],
  })),
)

function toggleSoundMute() {
  const next = !soundMuted.value
  setSoundMuted(next)
  soundMuted.value = next
  if (!next) void unlockAudio()
}

const codeToDirection: Record<string, string> = {
  ArrowUp: 'up',
  ArrowDown: 'down',
  ArrowLeft: 'left',
  ArrowRight: 'right',
  KeyW: 'up',
  KeyS: 'down',
  KeyA: 'left',
  KeyD: 'right',
}

const directionStack: string[] = []
let currentDirection = 'left'

function desiredDirection(): string {
  return directionStack.length ? directionStack[directionStack.length - 1]! : currentDirection
}

function emitDirection(force = false) {
  const next = desiredDirection()
  if (!force && next === currentDirection) return
  currentDirection = next
  void unlockAudio()
  emit('action', { type: 'set_direction', direction: next })
}

function startNewGame() {
  void unlockAudio()
  emit('action', { type: 'start_game' })
}

function onKeyDown(e: KeyboardEvent) {
  if (!canControl.value) return
  const direction = codeToDirection[e.code]
  if (!direction) return
  e.preventDefault()
  if (e.repeat) return
  const idx = directionStack.indexOf(direction)
  if (idx >= 0) directionStack.splice(idx, 1)
  directionStack.push(direction)
  emitDirection()
}

function onKeyUp(e: KeyboardEvent) {
  const direction = codeToDirection[e.code]
  if (!direction) return
  e.preventDefault()
  const idx = directionStack.indexOf(direction)
  if (idx >= 0) directionStack.splice(idx, 1)
  if (!canControl.value) {
    directionStack.length = 0
    return
  }
  if (directionStack.length) emitDirection()
}

let rafId = 0
let resizeObserver: ResizeObserver | null = null
let lastFrameTime = performance.now()
let lastTick = -1
let smoothPac: Record<string, SmoothEntity> = {}
let smoothGhosts: SmoothEntity[] = []
let particles: Particle[] = []
let lastPelletCount = -1
let lastScores: Record<string, number> = {}
let lastLives: Record<string, number> = {}
let lastGhostEaten = 0
let finishedSoundPlayed = false

function onStateSync() {
  const gs = props.gameState
  const snap = snapshotEntities(gs.pacmen, gs.ghosts)
  if (gs.tick !== lastTick || !Object.keys(smoothPac).length) {
    smoothPac = smoothEntities(smoothPac, snap.pacmen, 1, 40)
    smoothGhosts = smoothGhostList(smoothGhosts, snap.ghosts, 1, 40)
    lastTick = gs.tick
  }

  const remaining = gs.pellets_remaining ?? 0
  if (lastPelletCount >= 0 && remaining < lastPelletCount) {
    const me = gs.pacmen[props.playerId]
    if (me && (me.powered_ticks ?? 0) > 0 && remaining === lastPelletCount - 1) {
      /* power vs pellet distinguished below via score jumps */
    }
    const scoreDelta = (me?.score ?? 0) - (lastScores[props.playerId] ?? me?.score ?? 0)
    if (scoreDelta >= 50) {
      playPower()
      if (me) particles.push(...spawnChompParticles(me.x, me.y, '#fde047'))
    } else if (scoreDelta > 0) {
      playPellet()
    }
  }
  lastPelletCount = remaining

  for (const [pid, pac] of Object.entries(gs.pacmen)) {
    const prevScore = lastScores[pid] ?? pac.score
    const delta = pac.score - prevScore
    if (delta >= 200 && pid === props.playerId) {
      playGhostEat()
      lastGhostEaten = gs.tick
      particles.push(...spawnChompParticles(pac.x, pac.y, '#94a3b8'))
    }
    const prevLives = lastLives[pid]
    if (prevLives !== undefined && pac.lives < prevLives) {
      if (pid === props.playerId) playDeath()
    }
    lastScores[pid] = pac.score
    lastLives[pid] = pac.lives
  }

  if (gs.phase === 'finished' && !finishedSoundPlayed) {
    finishedSoundPlayed = true
    if (gs.winner === props.playerId) playWin()
    else playLose()
  }
  if (gs.phase !== 'finished') finishedSoundPlayed = false

  void lastGhostEaten
}

watch(() => props.gameState, onStateSync, { deep: true, immediate: true })

function paint(now: number) {
  const canvas = canvasRef.value
  const wrap = canvasWrapRef.value
  if (!canvas || !wrap) return
  const ctx = canvas.getContext('2d')
  if (!ctx) return

  const dt = Math.min(0.05, (now - lastFrameTime) / 1000)
  lastFrameTime = now
  particles = updateParticles(particles, dt)

  const displayW = wrap.clientWidth
  const displayH = wrap.clientHeight
  if (displayW <= 0 || displayH <= 0) return

  const dpr = window.devicePixelRatio || 1
  const needW = Math.floor(displayW * dpr)
  const needH = Math.floor(displayH * dpr)
  if (canvas.width !== needW || canvas.height !== needH) {
    canvas.width = needW
    canvas.height = needH
    canvas.style.width = `${displayW}px`
    canvas.style.height = `${displayH}px`
  }
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0)

  const snap = snapshotEntities(props.gameState.pacmen, props.gameState.ghosts)
  smoothPac = smoothEntities(smoothPac, snap.pacmen, dt)
  smoothGhosts = smoothGhostList(smoothGhosts, snap.ghosts, dt)

  renderFrame(ctx, displayW, displayH, {
    gridW: props.gameState.grid_width,
    gridH: props.gameState.grid_height,
    grid: props.gameState.grid,
    pellets: props.gameState.pellets,
    powerPellets: props.gameState.power_pellets,
    pacmen: smoothPac,
    ghosts: smoothGhosts,
    playerId: props.playerId,
    time: now,
    particles,
    mode: props.gameState.mode,
  })
}

function loop(now: number) {
  paint(now)
  rafId = requestAnimationFrame(loop)
}

onMounted(() => {
  window.addEventListener('keydown', onKeyDown)
  window.addEventListener('keyup', onKeyUp)
  if (canvasWrapRef.value) {
    resizeObserver = new ResizeObserver(() => {
      /* next rAF paints at new size */
    })
    resizeObserver.observe(canvasWrapRef.value)
  }
  lastFrameTime = performance.now()
  rafId = requestAnimationFrame(loop)
})

onUnmounted(() => {
  window.removeEventListener('keydown', onKeyDown)
  window.removeEventListener('keyup', onKeyUp)
  resizeObserver?.disconnect()
  cancelAnimationFrame(rafId)
})
</script>

<template>
  <div class="pacman-board">
    <div ref="canvasWrapRef" class="canvas-wrap">
      <canvas ref="canvasRef" class="game-canvas" />

      <button type="button" class="mute-btn" :title="soundMuted ? 'Unmute' : 'Mute'" @click="toggleSoundMute">
        {{ soundMuted ? '🔇' : '🔊' }}
      </button>

      <div v-if="gameState.phase === 'countdown'" class="overlay countdown">
        <span class="overlay-value pulse">{{ countdownRemaining ?? '…' }}</span>
        <span class="overlay-label">Get ready!</span>
      </div>

      <div v-else-if="isFinished" class="overlay finished">
        <span class="overlay-label">{{ winReasonLabel ?? 'Game over' }}</span>
        <span class="overlay-value win-pop">{{ winnerName }} wins!</span>
        <button v-if="isHost" type="button" class="btn-primary play-again-btn" @click="startNewGame">
          Play Again
        </button>
        <p v-else class="overlay-hint">Waiting for host to start a new game…</p>
      </div>

      <div v-else-if="!isAlive" class="overlay eliminated">
        <span class="overlay-label">Out of lives</span>
        <span class="overlay-hint">Spectating the maze…</span>
      </div>

      <div
        v-else-if="(myPac?.respawn_ticks ?? 0) > 0"
        class="overlay respawn"
      >
        <span class="overlay-label">Respawning…</span>
      </div>
    </div>

    <aside class="player-bar">
      <ul class="player-scores">
        <li
          v-for="row in playerRows"
          :key="row.id"
          class="player-score-row"
          :class="{ me: row.id === playerId, dead: !row.pac?.alive }"
        >
          <span class="color-dot" :style="{ background: row.pac?.color ?? '#666' }" />
          <span class="name">{{ row.nickname }}</span>
          <span class="score">{{ row.pac?.score ?? 0 }}</span>
          <span class="lives" title="Lives">♥{{ row.pac?.lives ?? 0 }}</span>
          <span v-if="(row.pac?.powered_ticks ?? 0) > 0" class="powered">PWR</span>
          <span v-if="!row.pac?.alive" class="status">out</span>
        </li>
      </ul>

      <div class="controls-hint">
        <p v-if="canControl">
          <strong>Controls:</strong> Arrow keys / WASD · pellets left
          {{ gameState.pellets_remaining ?? 0 }}
        </p>
        <p v-else-if="gameState.phase === 'playing' && !isAlive" class="muted">Spectating</p>
        <p v-else class="muted">Waiting to start…</p>
        <p class="mode-line muted">
          Mode: {{ gameState.mode ?? '—' }}
          <span v-if="gameState.map_name"> · {{ gameState.map_name }}</span>
        </p>
      </div>
    </aside>
  </div>
</template>

<style scoped>
.pacman-board {
  flex: 1;
  width: 100%;
  min-height: 0;
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
  padding: 0 0.5rem 0.5rem;
}

.canvas-wrap {
  position: relative;
  flex: 1;
  min-height: 0;
  width: 100%;
  overflow: hidden;
  border: 1px solid rgba(96, 165, 250, 0.28);
  border-radius: var(--radius);
  background:
    radial-gradient(ellipse at 50% 30%, rgba(30, 64, 175, 0.35), transparent 55%),
    #050914;
  box-shadow:
    inset 0 0 40px rgba(0, 0, 0, 0.35),
    0 0 24px rgba(37, 99, 235, 0.12);
}

.game-canvas {
  display: block;
  width: 100%;
  height: 100%;
}

.mute-btn {
  position: absolute;
  top: 0.5rem;
  right: 0.5rem;
  z-index: 2;
  border: 1px solid rgba(148, 163, 184, 0.3);
  background: rgba(15, 23, 42, 0.75);
  color: #e2e8f0;
  border-radius: 8px;
  padding: 0.25rem 0.45rem;
  cursor: pointer;
}

.overlay {
  position: absolute;
  inset: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  background: rgba(5, 9, 20, 0.72);
  backdrop-filter: blur(4px);
  gap: 0.5rem;
  padding: 1rem;
  text-align: center;
}

.overlay.respawn {
  background: rgba(5, 9, 20, 0.35);
}

.overlay-value {
  font-family: 'Outfit', 'DM Sans', system-ui, sans-serif;
  font-size: clamp(1.75rem, 4vw, 2.75rem);
  font-weight: 800;
  letter-spacing: -0.02em;
  text-shadow: 0 0 28px rgba(250, 204, 21, 0.35);
}

.overlay-value.pulse {
  animation: count-pulse 1s ease-in-out infinite;
}

@keyframes count-pulse {
  0%,
  100% {
    transform: scale(1);
  }
  50% {
    transform: scale(1.12);
  }
}

.overlay-label {
  font-size: 1.1rem;
  font-weight: 600;
  color: #c7d2fe;
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
  border: 1px solid rgba(96, 165, 250, 0.22);
  border-radius: var(--radius);
  background: linear-gradient(180deg, rgba(15, 23, 48, 0.95), rgba(8, 12, 28, 0.98));
}

.player-scores {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-wrap: wrap;
  gap: 0.65rem 1rem;
}

.player-score-row {
  display: flex;
  align-items: center;
  gap: 0.35rem;
  font-size: 0.85rem;
}

.player-score-row.me {
  font-weight: 700;
}

.player-score-row.dead {
  opacity: 0.45;
}

.color-dot {
  width: 0.65rem;
  height: 0.65rem;
  border-radius: 50%;
}

.score {
  font-variant-numeric: tabular-nums;
  color: #fde047;
}

.lives {
  color: #f87171;
  font-size: 0.8rem;
}

.powered {
  font-size: 0.65rem;
  font-weight: 800;
  color: #fef08a;
  background: rgba(250, 204, 21, 0.15);
  padding: 0.05rem 0.3rem;
  border-radius: 4px;
}

.status {
  font-size: 0.7rem;
  color: var(--text-muted);
  text-transform: uppercase;
}

.controls-hint {
  font-size: 0.8rem;
  color: #cbd5e1;
  text-align: right;
}

.controls-hint p {
  margin: 0;
}

.muted {
  color: var(--text-muted);
}

.mode-line {
  margin-top: 0.2rem !important;
  font-size: 0.75rem;
}

@media (max-width: 720px) {
  .player-bar {
    flex-direction: column;
    align-items: stretch;
  }

  .controls-hint {
    text-align: left;
  }
}
</style>
