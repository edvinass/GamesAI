<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import type { PacmanGameState, Room } from '@/types'
import {
  lerpEntities,
  lerpGhostList,
  renderFrame,
  snapshotEntities,
  spawnChompParticles,
  updateParticles,
  type EntitySnapshot,
  type Particle,
  type SmoothEntity,
} from './pacmanRender'
import {
  isSoundMuted,
  playCountdownGo,
  playCountdownTick,
  playDeath,
  playGhostEat,
  playLose,
  playPacEat,
  playPellet,
  playPower,
  playWin,
  setSirenMode,
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
  if (reason === 'out_of_lives') return 'Out of lives'
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
  if (!next) {
    void unlockAudio()
    syncSiren()
  }
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
let tickReceivedAt = performance.now()
let prevPac: Record<string, EntitySnapshot> = {}
let targetPac: Record<string, EntitySnapshot> = {}
let prevGhosts: EntitySnapshot[] = []
let targetGhosts: EntitySnapshot[] = []
let particles: Particle[] = []
let lastPelletCount = -1
let lastScores: Record<string, number> = {}
let lastLives: Record<string, number> = {}
let finishedSoundPlayed = false
let lastCountdownSec: number | null = null
let wasCountdown = false

function syncSiren() {
  const gs = props.gameState
  if (soundMuted.value || gs.phase !== 'playing') {
    setSirenMode('off')
    return
  }
  const fright = (gs.ghosts ?? []).some(
    (g) => !g.eaten && ((g.frightened_ticks ?? 0) > 0 || g.mode === 'frightened'),
  )
  setSirenMode(fright ? 'fright' : 'normal')
}

function onStateSync() {
  const gs = props.gameState
  const snap = snapshotEntities(gs.pacmen, gs.ghosts)

  if (gs.tick !== lastTick) {
    // Use last rendered targets as origin so motion never snaps backward.
    prevPac = Object.keys(targetPac).length ? { ...targetPac } : snap.pacmen
    prevGhosts = targetGhosts.length ? targetGhosts.map((g) => ({ ...g })) : snap.ghosts
    targetPac = snap.pacmen
    targetGhosts = snap.ghosts
    lastTick = gs.tick
    tickReceivedAt = performance.now()
  } else {
    targetPac = snap.pacmen
    targetGhosts = snap.ghosts
    if (!Object.keys(prevPac).length) prevPac = snap.pacmen
    if (!prevGhosts.length) prevGhosts = snap.ghosts
  }

  // Countdown SFX
  if (gs.phase === 'countdown') {
    wasCountdown = true
    const sec = countdownRemaining.value
    if (sec != null && sec !== lastCountdownSec) {
      lastCountdownSec = sec
      if (sec > 0) playCountdownTick()
    }
  } else if (wasCountdown && gs.phase === 'playing') {
    wasCountdown = false
    playCountdownGo()
  }

  const remaining = gs.pellets_remaining ?? 0
  if (lastPelletCount >= 0 && remaining < lastPelletCount) {
    const me = gs.pacmen[props.playerId]
    const scoreDelta = (me?.score ?? 0) - (lastScores[props.playerId] ?? me?.score ?? 0)
    if (scoreDelta >= 50) {
      playPower()
      if (me) particles.push(...spawnChompParticles(me.x, me.y, '#ffb897'))
    } else if (scoreDelta > 0) {
      playPellet()
    }
  }
  lastPelletCount = remaining

  for (const [pid, pac] of Object.entries(gs.pacmen)) {
    const prevScore = lastScores[pid] ?? pac.score
    const delta = pac.score - prevScore
    if (pid === props.playerId) {
      if (delta >= 500) {
        playPacEat()
        particles.push(...spawnChompParticles(pac.x, pac.y, '#f472b6'))
      } else if (delta >= 200) {
        playGhostEat()
        particles.push(...spawnChompParticles(pac.x, pac.y, '#94a3b8'))
      }
    }
    const prevLives = lastLives[pid]
    if (prevLives !== undefined && pac.lives < prevLives && pid === props.playerId) {
      playDeath()
    }
    lastScores[pid] = pac.score
    lastLives[pid] = pac.lives
  }

  if (gs.phase === 'finished' && !finishedSoundPlayed) {
    finishedSoundPlayed = true
    setSirenMode('off')
    if (gs.winner === props.playerId) playWin()
    else playLose()
  }
  if (gs.phase !== 'finished') finishedSoundPlayed = false

  syncSiren()
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

  const tickMs =
    props.gameState.tick_ms ?? Number(props.room.settings?.tick_ms ?? 90)
  const rawT =
    props.gameState.phase === 'playing'
      ? (now - tickReceivedAt) / Math.max(16, tickMs)
      : 1

  const gridW = props.gameState.grid_width
  const smoothPac: Record<string, SmoothEntity> = lerpEntities(
    prevPac,
    targetPac,
    rawT,
    gridW,
  )
  const smoothGhosts = lerpGhostList(prevGhosts, targetGhosts, rawT, gridW)

  renderFrame(ctx, displayW, displayH, {
    gridW,
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
    gate: props.gameState.gate,
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
  setSirenMode('off')
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
        <span class="overlay-label">READY!</span>
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
        <span class="overlay-label">GAME OVER</span>
        <span class="overlay-hint">Spectating the maze…</span>
      </div>

      <div v-else-if="(myPac?.respawn_ticks ?? 0) > 0" class="overlay respawn">
        <span class="overlay-label">READY!</span>
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
          <span class="score">{{ String(row.pac?.score ?? 0).padStart(4, '0') }}</span>
          <span class="lives" title="Lives">
            <span v-for="n in row.pac?.lives ?? 0" :key="n" class="life-icon">ᗧ</span>
          </span>
          <span v-if="(row.pac?.powered_ticks ?? 0) > 0" class="powered">PWR</span>
          <span v-if="!row.pac?.alive" class="status">out</span>
        </li>
      </ul>

      <div class="controls-hint">
        <p v-if="canControl">
          <strong>↑↓←→ / WASD</strong>
          · {{ gameState.pellets_remaining ?? 0 }} dots
        </p>
        <p v-else-if="gameState.phase === 'playing' && !isAlive" class="muted">Spectating</p>
        <p v-else class="muted">Waiting…</p>
        <p class="mode-line muted">
          {{ (gameState.mode ?? 'chase').toUpperCase() }}
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
  font-family: 'Outfit', 'DM Sans', system-ui, sans-serif;
}

.canvas-wrap {
  position: relative;
  flex: 1;
  min-height: 0;
  width: 100%;
  overflow: hidden;
  border: 2px solid #2121de;
  border-radius: 4px;
  background: #000;
  box-shadow: 0 0 0 1px #3b5bff, inset 0 0 40px rgba(0, 0, 0, 0.8);
}

.game-canvas {
  display: block;
  width: 100%;
  height: 100%;
}

.mute-btn {
  position: absolute;
  top: 0.45rem;
  right: 0.45rem;
  z-index: 2;
  border: 1px solid #2121de;
  background: rgba(0, 0, 0, 0.75);
  color: #ffb897;
  border-radius: 4px;
  padding: 0.25rem 0.45rem;
  cursor: pointer;
  font-size: 0.85rem;
}

.overlay {
  position: absolute;
  inset: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  background: rgba(0, 0, 0, 0.72);
  gap: 0.55rem;
  padding: 1rem;
  text-align: center;
}

.overlay.respawn {
  background: rgba(0, 0, 0, 0.28);
}

.overlay-value {
  font-size: clamp(1.4rem, 3.5vw, 2.4rem);
  font-weight: 700;
  color: #ffff00;
  text-shadow: 0 0 20px rgba(255, 255, 0, 0.35);
  letter-spacing: 0.04em;
}

.overlay-value.pulse {
  animation: count-pulse 1s steps(2, end) infinite;
}

@keyframes count-pulse {
  0%,
  100% {
    opacity: 1;
  }
  50% {
    opacity: 0.55;
  }
}

.overlay-label {
  font-size: 0.85rem;
  font-weight: 700;
  color: #ffb8ff;
  letter-spacing: 0.08em;
}

.overlay-hint {
  font-size: 0.65rem;
  color: #ffb897;
  font-family: 'DM Sans', system-ui, sans-serif;
}

.play-again-btn {
  margin-top: 0.5rem;
  font-family: 'DM Sans', system-ui, sans-serif;
}

.player-bar {
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1rem;
  padding: 0.7rem 1rem;
  border: 2px solid #2121de;
  border-radius: 4px;
  background: #000;
}

.player-scores {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-wrap: wrap;
  gap: 0.7rem 1.1rem;
  font-family: 'DM Sans', system-ui, sans-serif;
}

.player-score-row {
  display: flex;
  align-items: center;
  gap: 0.35rem;
  font-size: 0.85rem;
  color: #ffb897;
}

.player-score-row.me {
  font-weight: 700;
  color: #ffff00;
}

.player-score-row.dead {
  opacity: 0.4;
}

.color-dot {
  width: 0.65rem;
  height: 0.65rem;
  border-radius: 50%;
}

.score {
  font-variant-numeric: tabular-nums;
  color: #ffffff;
  min-width: 2.8rem;
}

.lives {
  display: inline-flex;
  gap: 0.1rem;
  color: #ffff00;
  font-size: 0.85rem;
  letter-spacing: -0.05em;
}

.life-icon {
  display: inline-block;
  transform: scaleX(-1);
}

.powered {
  font-size: 0.6rem;
  font-weight: 800;
  color: #2121de;
  background: #ffb8ff;
  padding: 0.05rem 0.3rem;
  border-radius: 2px;
}

.status {
  font-size: 0.65rem;
  color: #ff0000;
  text-transform: uppercase;
}

.controls-hint {
  font-size: 0.72rem;
  color: #ffb897;
  text-align: right;
  font-family: 'DM Sans', system-ui, sans-serif;
}

.controls-hint p {
  margin: 0;
}

.muted {
  color: #888;
}

.mode-line {
  margin-top: 0.2rem !important;
  font-size: 0.7rem;
  color: #5b8cff;
  letter-spacing: 0.06em;
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
