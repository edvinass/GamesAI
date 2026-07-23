<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import type { Room, BombermanGameState, BombermanBomb } from '@/types'
import {
  getMapTheme,
  interpolateBombers,
  interpolateBombs,
  renderFrame,
  snapshotBombers,
  spawnDebrisParticles,
  spawnDeathParticles,
  spawnExplosionParticles,
  spawnPowerupParticles,
  updateParticles,
  type BomberSnapshot,
  type Particle,
  type SmoothBomber,
} from './bombermanRender'
import {
  isSoundMuted,
  playBombKick,
  playBombPlace,
  playBombFuse,
  playBombStop,
  playBombThrow,
  playCountdownGo,
  playCountdownTick,
  playDeath,
  playExplosion,
  playLose,
  playPowerup,
  playSoftDestroy,
  playScreamVariant,
  playStep,
  playWin,
  SCREAM_VARIANTS,
  getSelectedScreamVariant,
  setSelectedScreamVariant,
  setSoundMuted,
  unlockAudio,
  type PowerupSoundKind,
} from './sounds'

const props = defineProps<{
  gameState: BombermanGameState
  room: Room
  playerId: string
}>()

const emit = defineEmits<{
  action: [data: Record<string, unknown>]
}>()

const canvasRef = ref<HTMLCanvasElement | null>(null)
const canvasWrapRef = ref<HTMLElement | null>(null)
const soundMuted = ref(isSoundMuted())
const showTouchControls = ref(false)
const touchDirection = ref<string | null>(null)
const selectedScream = ref(getSelectedScreamVariant())
const showScreamTester = ref(true)

async function previewScream(id: number) {
  selectedScream.value = id
  setSelectedScreamVariant(id)
  if (soundMuted.value) {
    setSoundMuted(false)
    soundMuted.value = false
  }
  await unlockAudio()
  playScreamVariant(id)
}

const myBomber = computed(() => props.gameState.bombers[props.playerId])
const isAlive = computed(() => myBomber.value?.alive ?? false)
const isHost = computed(() => props.room.host_player_id === props.playerId)
const isFinished = computed(() => props.gameState.phase === 'finished')
const canControl = computed(
  () => props.gameState.phase === 'playing' && isAlive.value,
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
  if (reason === 'last_standing') return 'Last bomber standing'
  if (reason === 'most_kills') return 'Most kills'
  return null
})

const playerRows = computed(() =>
  props.gameState.players.map((p) => ({
    ...p,
    bomber: props.gameState.bombers[p.id],
  })),
)

const myActiveBombs = computed(() =>
  (props.gameState.bombs ?? []).filter((b) => b.owner_id === props.playerId).length,
)

const mapTheme = computed(() => getMapTheme(props.gameState.map_id))

const themeStyle = computed(() => {
  const t = mapTheme.value
  return {
    '--bm-accent': t.accent,
    '--bm-accent-rgb': t.accentRgb,
    '--bm-glow': t.glow,
    '--bm-wrap-top': t.wrapTop,
    '--bm-wrap-bottom': t.wrapBottom,
  }
})

function toggleSoundMute() {
  const next = !soundMuted.value
  setSoundMuted(next)
  soundMuted.value = next
  if (!next) void unlockAudio()
}

function detectTouchControls() {
  showTouchControls.value =
    window.matchMedia('(pointer: coarse)').matches || window.innerWidth < 900
}

function onTouchDirectionStart(direction: string) {
  if (!canControl.value) return
  void unlockAudio()
  touchDirection.value = direction
  emit('action', { type: 'set_direction', direction })
}

function onTouchDirectionEnd(direction: string) {
  if (touchDirection.value !== direction) return
  touchDirection.value = null
  emit('action', { type: 'set_direction', direction: 'stop' })
}

function isGroundedBomb(b: BombermanBomb): boolean {
  return b.flight !== 'throw' && b.flight !== 'kick' && b.flight !== 'carried'
}

const DIR_DELTAS: Record<string, [number, number]> = {
  up: [0, -1],
  down: [0, 1],
  left: [-1, 0],
  right: [1, 0],
}

/** True when Space will pick up or throw rather than plant (skip plant SFX). */
function spaceIsGloveAction(): boolean {
  const me = myBomber.value
  if (!me?.can_throw) return false
  if (me.carrying_bomb_id) return true
  const bombs = props.gameState.bombs ?? []
  if (bombs.some((b) => b.x === me.x && b.y === me.y && isGroundedBomb(b))) {
    return true
  }
  const facing =
    (me.direction && DIR_DELTAS[me.direction] ? me.direction : null) ||
    (me.next_direction && DIR_DELTAS[me.next_direction] ? me.next_direction : null) ||
    me.facing ||
    'right'
  const delta = DIR_DELTAS[facing]
  if (!delta) return false
  const [dx, dy] = delta
  return bombs.some((b) => b.x === me.x + dx && b.y === me.y + dy && isGroundedBomb(b))
}

function onTouchBomb() {
  if (!canControl.value) return
  void unlockAudio()
  if (!spaceIsGloveAction()) {
    playBombPlace()
  }
  emit('action', { type: 'place_bomb' })
}

/** Physical key codes — stable across layouts; most-recent direction wins. */
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

/** Held directions, oldest → newest (last entry is active). */
const directionStack: string[] = []
let currentDirection = 'stop'

function desiredDirection(): string {
  return directionStack.length ? directionStack[directionStack.length - 1]! : 'stop'
}

function emitDirection(force = false) {
  const next = desiredDirection()
  if (!force && next === currentDirection) return
  currentDirection = next
  void unlockAudio()
  emit('action', { type: 'set_direction', direction: next })
}

function clearMovementInput() {
  directionStack.length = 0
  if (currentDirection !== 'stop') {
    currentDirection = 'stop'
    emit('action', { type: 'set_direction', direction: 'stop' })
  } else {
    currentDirection = 'stop'
  }
}

function startNewGame() {
  void unlockAudio()
  emit('action', { type: 'start_game' })
}

function onKeyDown(e: KeyboardEvent) {
  if (!canControl.value) return
  if (e.code === 'Space' || e.key === ' ') {
    e.preventDefault()
    if (!e.repeat) {
      void unlockAudio()
      // Place SFX only for planting; pick up / throw come from state sync.
      if (!spaceIsGloveAction()) {
        playBombPlace()
      }
      emit('action', { type: 'place_bomb' })
    }
    return
  }
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
    currentDirection = 'stop'
    return
  }
  emitDirection()
}

function onWindowBlur() {
  clearMovementInput()
}

let rafId = 0
let resizeObserver: ResizeObserver | null = null
let lastFrameTime = performance.now()
let lastTick = -1
let tickReceivedAt = performance.now()
/** Previous tick positions (lerp origin). */
let prevBombers: Record<string, BomberSnapshot> = {}
/** Latest server truth positions. */
let targetBombers: Record<string, BomberSnapshot> = {}
/** Previous / current bomb cells for kick/throw lerp. */
let prevBombPos: Record<string, { x: number; y: number }> = {}
let targetBombPos: Record<string, { x: number; y: number }> = {}
let particles: Particle[] = []
let shake = 0

const POWERUP_COLORS: Record<string, string> = {
  bomb: '#f97316',
  range: '#38bdf8',
  speed: '#a3e635',
  throw: '#fbbf24',
  kick: '#f472b6',
}

/** Snapshot used to detect gameplay events for SFX. */
let prevSoundSnap: {
  phase: string
  bombIds: Set<string>
  bombs: BombermanBomb[]
  explosionCount: number
  softCount: number
  alive: Record<string, boolean>
  countdownSec: number | null
  myStats: {
    maxBombs: number
    bombRange: number
    speedLevel: number
    canThrow: boolean
    canKick: boolean
  } | null
  myPos: { x: number; y: number } | null
  softCells: Set<string>
  explosionKeys: Set<string>
} | null = null
let soundBootstrapped = false

function countSoftBlocks(grid: number[][]): number {
  let n = 0
  for (const row of grid) {
    for (const cell of row) {
      if (cell === 2) n++
    }
  }
  return n
}

function softCellKeys(grid: number[][]): Set<string> {
  const keys = new Set<string>()
  for (let y = 0; y < grid.length; y++) {
    const row = grid[y] ?? []
    for (let x = 0; x < row.length; x++) {
      if (row[x] === 2) keys.add(`${x},${y}`)
    }
  }
  return keys
}

function explosionKeys(state: BombermanGameState): Set<string> {
  return new Set((state.explosions ?? []).map((e) => `${e.x},${e.y}`))
}

function playStateSounds(state: BombermanGameState) {
  const bombIds = new Set((state.bombs ?? []).map((b) => b.id))
  const explosionCount = (state.explosions ?? []).length
  const softCount = countSoftBlocks(state.grid)
  const softCells = softCellKeys(state.grid)
  const explKeys = explosionKeys(state)
  const alive: Record<string, boolean> = {}
  for (const [pid, b] of Object.entries(state.bombers)) {
    alive[pid] = Boolean(b.alive)
  }
  const me = state.bombers[props.playerId]
  const countdownSec =
    state.phase === 'countdown' && state.countdown_ends_at
      ? Math.max(0, Math.ceil((new Date(state.countdown_ends_at).getTime() - Date.now()) / 1000))
      : null

  if (!soundBootstrapped || !prevSoundSnap) {
    soundBootstrapped = true
    prevSoundSnap = {
      phase: state.phase,
      bombIds,
      bombs: (state.bombs ?? []).map((b) => ({ ...b })),
      explosionCount,
      softCount,
      alive: { ...alive },
      countdownSec,
      myStats: me
        ? {
            maxBombs: me.max_bombs,
            bombRange: me.bomb_range,
            speedLevel: me.speed_level,
            canThrow: Boolean(me.can_throw),
            canKick: Boolean(me.can_kick),
          }
        : null,
      myPos: me ? { x: me.x, y: me.y } : null,
      softCells,
      explosionKeys: explKeys,
    }
    return
  }

  const prev = prevSoundSnap

  // Countdown
  if (state.phase === 'countdown' && countdownSec != null && countdownSec !== prev.countdownSec) {
    if (countdownSec > 0) playCountdownTick()
  }
  if (prev.phase === 'countdown' && state.phase === 'playing') {
    playCountdownGo()
  }

  // New bombs (AI / remote — local place already played on keydown)
  for (const bomb of state.bombs ?? []) {
    if (!prev.bombIds.has(bomb.id) && bomb.owner_id !== props.playerId) {
      playBombPlace()
      break
    }
  }

  // Throw / kick / pick up / stop
  for (const bomb of state.bombs ?? []) {
    const prevBomb = prev.bombs.find((b) => b.id === bomb.id)
    if (!prevBomb) continue
    if (bomb.flight === 'carried' && prevBomb.flight !== 'carried') {
      playBombPlace()
      break
    }
    const wasMoving = prevBomb.flight === 'throw' || prevBomb.flight === 'kick' || prevBomb.sliding
    const isMoving = bomb.flight === 'throw' || bomb.flight === 'kick' || Boolean(bomb.sliding)
    if (!wasMoving && isMoving) {
      if (bomb.flight === 'kick') playBombKick()
      else playBombThrow()
      break
    }
  }
  for (const prevBomb of prev.bombs) {
    const bomb = (state.bombs ?? []).find((b) => b.id === prevBomb.id)
    if (!bomb) continue
    const wasMoving = Boolean(prevBomb.flight || prevBomb.sliding)
    const isMoving = Boolean(bomb.flight || bomb.sliding)
    if (wasMoving && !isMoving) {
      playBombStop()
      break
    }
  }

  // Fuse hiss while any bomb is close to detonating
  const liveBombs = state.bombs ?? []
  if (liveBombs.length > 0 && state.phase === 'playing') {
    const minFuse = Math.min(...liveBombs.map((b) => b.fuse))
    if (minFuse <= 5) playBombFuse(minFuse <= 3)
  }

  // Explosions + particles / shake
  const newBlasts: string[] = []
  for (const key of explKeys) {
    if (!prev.explosionKeys.has(key)) newBlasts.push(key)
  }
  const bombsLost = prev.bombs.length - (state.bombs ?? []).length
  if (newBlasts.length > 0 || (bombsLost > 0 && explosionCount > 0)) {
    const intensity = Math.min(1.35, 0.75 + newBlasts.length * 0.12)
    playExplosion(intensity)
    shake = Math.min(1, shake + 0.55 + newBlasts.length * 0.08)
    for (const key of newBlasts.length ? newBlasts : [...explKeys].slice(0, 6)) {
      const [sx, sy] = key.split(',').map(Number)
      particles.push(...spawnExplosionParticles(sx!, sy!, 10))
    }
  }

  // Soft walls destroyed
  if (softCount < prev.softCount) {
    playSoftDestroy()
    for (const key of prev.softCells) {
      if (!softCells.has(key)) {
        const [sx, sy] = key.split(',').map(Number)
        particles.push(...spawnDebrisParticles(sx!, sy!, 7, mapTheme.value.debris))
      }
    }
  }

  // Power-up pickup (detect via our bomber stats rising)
  const prevMeStats = prev.myStats
  if (
    me &&
    prevMeStats &&
    (me.max_bombs > prevMeStats.maxBombs ||
      me.bomb_range > prevMeStats.bombRange ||
      me.speed_level > prevMeStats.speedLevel ||
      (Boolean(me.can_throw) && !prevMeStats.canThrow) ||
      (Boolean(me.can_kick) && !prevMeStats.canKick))
  ) {
    const kind: PowerupSoundKind =
      me.max_bombs > prevMeStats.maxBombs
        ? 'bomb'
        : me.bomb_range > prevMeStats.bombRange
          ? 'range'
          : me.speed_level > prevMeStats.speedLevel
            ? 'speed'
            : Boolean(me.can_throw) && !prevMeStats.canThrow
              ? 'throw'
              : 'kick'
    playPowerup(kind)
    particles.push(
      ...spawnPowerupParticles(me.x, me.y, POWERUP_COLORS[kind] ?? '#fff'),
    )
  }

  // Local footsteps
  if (me && prev.myPos && (me.x !== prev.myPos.x || me.y !== prev.myPos.y) && me.alive) {
    playStep()
  }

  // Deaths — scream for every bomber that goes out
  for (const [pid, wasAlive] of Object.entries(prev.alive)) {
    if (wasAlive && !alive[pid]) {
      const dead = state.bombers[pid]
      playDeath()
      if (dead) {
        particles.push(...spawnDeathParticles(dead.x, dead.y, dead.color))
        shake = Math.min(1, shake + 0.35)
      }
    }
  }

  // Match end
  if (prev.phase !== 'finished' && state.phase === 'finished') {
    if (state.winner === props.playerId) playWin()
    else playLose()
  }

  prevSoundSnap = {
    phase: state.phase,
    bombIds,
    bombs: (state.bombs ?? []).map((b) => ({ ...b })),
    explosionCount,
    softCount,
    alive: { ...alive },
    countdownSec,
    myStats: me
      ? {
          maxBombs: me.max_bombs,
          bombRange: me.bomb_range,
          speedLevel: me.speed_level,
          canThrow: Boolean(me.can_throw),
          canKick: Boolean(me.can_kick),
        }
      : null,
    myPos: me ? { x: me.x, y: me.y } : null,
    softCells,
    explosionKeys: explKeys,
  }
}

function bombPosSnapshot(bombs: BombermanBomb[]): Record<string, { x: number; y: number }> {
  return Object.fromEntries(bombs.map((b) => [b.id, { x: b.x, y: b.y }]))
}

function onStateSync() {
  const tick = props.gameState.tick
  const snap = snapshotBombers(props.gameState.bombers)
  const bombSnap = bombPosSnapshot(props.gameState.bombs ?? [])

  if (tick !== lastTick) {
    // Use last rendered targets as origin so motion never snaps backward.
    prevBombers = Object.keys(targetBombers).length ? { ...targetBombers } : snap
    prevBombPos = Object.keys(targetBombPos).length ? { ...targetBombPos } : bombSnap
    targetBombers = snap
    targetBombPos = bombSnap
    lastTick = tick
    tickReceivedAt = performance.now()
    playStateSounds(props.gameState)
  } else {
    targetBombers = snap
    targetBombPos = bombSnap
    if (!Object.keys(prevBombers).length) prevBombers = snap
    if (!Object.keys(prevBombPos).length) prevBombPos = bombSnap
  }
}

watch(() => props.gameState, onStateSync, { deep: true, immediate: true })

watch(canControl, (ok) => {
  if (!ok) {
    directionStack.length = 0
    currentDirection = 'stop'
  } else if (desiredDirection() !== 'stop') {
    // Re-assert held direction after countdown / reconnect.
    emitDirection(true)
  }
})

watch(countdownRemaining, (sec, prev) => {
  if (sec == null || prev == null) return
  if (sec !== prev && sec > 0 && props.gameState.phase === 'countdown') {
    void unlockAudio()
  }
})

function paint(now: number) {
  const canvas = canvasRef.value
  const wrap = canvasWrapRef.value
  if (!canvas || !wrap) return
  const ctx = canvas.getContext('2d')
  if (!ctx) return

  const dt = Math.min(0.05, (now - lastFrameTime) / 1000)
  lastFrameTime = now
  particles = updateParticles(particles, dt)
  shake = Math.max(0, shake - dt * 2.8)

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
    props.gameState.tick_ms ?? Number(props.room.settings?.tick_ms ?? 150)
  const rawT =
    props.gameState.phase === 'playing'
      ? (now - tickReceivedAt) / Math.max(16, tickMs)
      : 1

  const displayBombers: Record<string, SmoothBomber> =
    props.gameState.phase === 'playing'
      ? interpolateBombers(prevBombers, targetBombers, rawT)
      : Object.fromEntries(
          Object.entries(targetBombers).map(([pid, b]) => [pid, { ...b, speed: 0 }]),
        )

  const renderedBombs =
    props.gameState.phase === 'playing'
      ? interpolateBombs(prevBombPos, props.gameState.bombs ?? [], rawT).map((bomb) => {
          if (bomb.flight !== 'carried') return bomb
          // Keep carried bombs locked to the smoothed bomber so they don't stutter on the grid.
          const carrier = Object.entries(props.gameState.bombers).find(
            ([, b]) => b.carrying_bomb_id === bomb.id,
          )
          if (!carrier) return bomb
          const smooth = displayBombers[carrier[0]]
          if (!smooth) return bomb
          return { ...bomb, x: smooth.x, y: smooth.y }
        })
      : (props.gameState.bombs ?? [])

  renderFrame(ctx, displayW, displayH, {
    gridW: props.gameState.grid_width,
    gridH: props.gameState.grid_height,
    grid: props.gameState.grid,
    bombers: displayBombers,
    bombs: renderedBombs,
    explosions: props.gameState.explosions ?? [],
    powerups: props.gameState.powerups ?? [],
    playerId: props.playerId,
    time: now,
    particles,
    shake,
    mapId: props.gameState.map_id,
  })
}

function loop(now: number) {
  paint(now)
  rafId = requestAnimationFrame(loop)
}

onMounted(() => {
  detectTouchControls()
  window.addEventListener('resize', detectTouchControls)
  window.addEventListener('keydown', onKeyDown)
  window.addEventListener('keyup', onKeyUp)
  window.addEventListener('blur', onWindowBlur)
  if (canvasWrapRef.value) {
    resizeObserver = new ResizeObserver(() => {})
    resizeObserver.observe(canvasWrapRef.value)
  }
  lastFrameTime = performance.now()
  rafId = requestAnimationFrame(loop)
})

onUnmounted(() => {
  window.removeEventListener('resize', detectTouchControls)
  window.removeEventListener('keydown', onKeyDown)
  window.removeEventListener('keyup', onKeyUp)
  window.removeEventListener('blur', onWindowBlur)
  resizeObserver?.disconnect()
  cancelAnimationFrame(rafId)
})
</script>

<template>
  <div class="bomberman-board" :style="themeStyle">
    <div ref="canvasWrapRef" class="canvas-wrap">
      <div class="arena-glow" aria-hidden="true" />
      <canvas ref="canvasRef" class="game-canvas" />

      <div v-if="gameState.phase === 'countdown'" class="overlay countdown">
        <span class="overlay-kicker">{{ gameState.map_name ?? 'Arena' }}</span>
        <span class="overlay-value pulse">{{ countdownRemaining ?? '…' }}</span>
        <span class="overlay-label">Get ready!</span>
      </div>

      <div v-else-if="isFinished" class="overlay finished">
        <span class="overlay-kicker">{{ winReasonLabel ?? 'Game over' }}</span>
        <span class="overlay-value win-pop">{{ winnerName }} wins!</span>
        <button v-if="isHost" type="button" class="btn-primary play-again-btn" @click="startNewGame">
          Play Again
        </button>
        <p v-else class="overlay-hint">Waiting for host to start a new game…</p>
      </div>

      <div
        v-else-if="!isAlive && gameState.phase === 'playing'"
        class="spectate-banner"
      >
        <span class="spectate-label">Eliminated — spectating</span>
      </div>

      <div
        v-if="showTouchControls && canControl"
        class="touch-controls"
        aria-label="Touch controls"
      >
        <div class="touch-dpad">
          <button
            type="button"
            class="touch-btn dpad-up"
            aria-label="Move up"
            @touchstart.prevent="onTouchDirectionStart('up')"
            @touchend.prevent="onTouchDirectionEnd('up')"
            @touchcancel.prevent="onTouchDirectionEnd('up')"
            @mousedown.prevent="onTouchDirectionStart('up')"
            @mouseup.prevent="onTouchDirectionEnd('up')"
            @mouseleave.prevent="onTouchDirectionEnd('up')"
          >
            ▲
          </button>
          <button
            type="button"
            class="touch-btn dpad-left"
            aria-label="Move left"
            @touchstart.prevent="onTouchDirectionStart('left')"
            @touchend.prevent="onTouchDirectionEnd('left')"
            @touchcancel.prevent="onTouchDirectionEnd('left')"
            @mousedown.prevent="onTouchDirectionStart('left')"
            @mouseup.prevent="onTouchDirectionEnd('left')"
            @mouseleave.prevent="onTouchDirectionEnd('left')"
          >
            ◀
          </button>
          <button
            type="button"
            class="touch-btn dpad-right"
            aria-label="Move right"
            @touchstart.prevent="onTouchDirectionStart('right')"
            @touchend.prevent="onTouchDirectionEnd('right')"
            @touchcancel.prevent="onTouchDirectionEnd('right')"
            @mousedown.prevent="onTouchDirectionStart('right')"
            @mouseup.prevent="onTouchDirectionEnd('right')"
            @mouseleave.prevent="onTouchDirectionEnd('right')"
          >
            ▶
          </button>
          <button
            type="button"
            class="touch-btn dpad-down"
            aria-label="Move down"
            @touchstart.prevent="onTouchDirectionStart('down')"
            @touchend.prevent="onTouchDirectionEnd('down')"
            @touchcancel.prevent="onTouchDirectionEnd('down')"
            @mousedown.prevent="onTouchDirectionStart('down')"
            @mouseup.prevent="onTouchDirectionEnd('down')"
            @mouseleave.prevent="onTouchDirectionEnd('down')"
          >
            ▼
          </button>
        </div>
        <div class="touch-actions">
          <button
            type="button"
            class="touch-btn touch-bomb"
            aria-label="Place bomb"
            @touchstart.prevent="onTouchBomb"
            @mousedown.prevent="onTouchBomb"
          >
            💣
          </button>
        </div>
      </div>
    </div>

    <aside class="player-bar">
      <div class="bar-left">
        <span v-if="gameState.map_name" class="map-chip" :title="gameState.map_id">
          {{ gameState.map_name }}
        </span>
        <ul class="player-scores">
          <li
            v-for="row in playerRows"
            :key="row.id"
            class="player-score-row"
            :class="{ me: row.id === playerId, dead: !row.bomber?.alive }"
          >
            <span
              class="color-dot"
              :style="{
                background: row.bomber?.color ?? '#666',
                boxShadow: row.id === playerId ? `0 0 10px ${row.bomber?.color ?? '#f97316'}` : undefined,
              }"
            />
            <span class="name">{{ row.nickname }}</span>
            <span class="stat-pills" title="Bombs / Range / Speed / Throw / Kick">
              <span class="pill bomb">💣{{ row.bomber?.max_bombs ?? 1 }}</span>
              <span class="pill range">🔥{{ row.bomber?.bomb_range ?? 1 }}</span>
              <span class="pill speed">⚡{{ row.bomber?.speed_level ?? 0 }}</span>
              <span v-if="row.bomber?.can_throw" class="pill throw" title="Throw">🧤</span>
              <span v-if="row.bomber?.can_kick" class="pill kick" title="Kick">🦵</span>
            </span>
            <span v-if="(row.bomber?.kills ?? 0) > 0" class="kills">×{{ row.bomber?.kills }}</span>
            <span v-if="!row.bomber?.alive" class="status">out</span>
          </li>
        </ul>
      </div>

      <div class="controls-hint">
        <button
          type="button"
          class="btn-secondary mute-btn"
          :aria-label="soundMuted ? 'Unmute sound' : 'Mute sound'"
          :title="soundMuted ? 'Unmute' : 'Mute'"
          @click="toggleSoundMute"
        >
          {{ soundMuted ? '🔇' : '🔊' }}
        </button>
        <button
          type="button"
          class="btn-secondary mute-btn scream-toggle"
          :title="showScreamTester ? 'Hide scream tester' : 'Show scream tester'"
          @click="showScreamTester = !showScreamTester"
        >
          😱
        </button>
        <p v-if="canControl && showTouchControls">
          <strong>Hold</strong> D-pad to move ·
          <strong>💣</strong> bomb<span v-if="myBomber?.can_throw">
            / {{ myBomber?.carrying_bomb_id ? 'throw' : 'pick up' }}</span>
          <span v-if="myBomber?.can_kick"> · walk into bombs to kick</span>
          <span class="muted">({{ myActiveBombs }}/{{ myBomber?.max_bombs ?? 1 }})</span>
        </p>
        <p v-else-if="canControl">
          <strong>Hold</strong> arrows / WASD ·
          <strong>Space</strong> bomb<span v-if="myBomber?.can_throw">
            / {{ myBomber?.carrying_bomb_id ? 'throw' : 'pick up' }}</span>
          <span v-if="myBomber?.can_kick"> · walk into bombs to kick</span>
          <span class="muted">({{ myActiveBombs }}/{{ myBomber?.max_bombs ?? 1 }})</span>
        </p>
        <p v-else-if="gameState.phase === 'playing' && !isAlive" class="muted">Spectating</p>
        <p v-else class="muted">Waiting to start…</p>
        <ul class="power-legend">
          <li><span class="legend-emoji">💣</span>Bomb+</li>
          <li><span class="legend-emoji">🔥</span>Range+</li>
          <li><span class="legend-emoji">⚡</span>Speed+</li>
          <li><span class="legend-emoji">🧤</span>Throw</li>
          <li><span class="legend-emoji">🦵</span>Kick</li>
        </ul>
      </div>
    </aside>

    <div v-if="showScreamTester" class="scream-tester">
      <div class="scream-tester-head">
        <span class="scream-tester-title">Scream tester</span>
        <span class="scream-tester-hint">Click to preview · selected plays on death</span>
      </div>
      <div class="scream-grid">
        <button
          v-for="v in SCREAM_VARIANTS"
          :key="v.id"
          type="button"
          class="scream-btn"
          :class="{ selected: selectedScream === v.id }"
          :title="v.description"
          @click="previewScream(v.id)"
        >
          <span class="scream-num">{{ v.id }}</span>
          <span class="scream-name">{{ v.name }}</span>
        </button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.bomberman-board {
  flex: 1;
  width: 100%;
  min-height: 0;
  display: flex;
  flex-direction: column;
  gap: 0.55rem;
  padding: 0 0.5rem 0.5rem;
}

.canvas-wrap {
  position: relative;
  flex: 1;
  min-height: 0;
  width: 100%;
  overflow: hidden;
  border: 1px solid rgba(var(--bm-accent-rgb, 249, 115, 22), 0.32);
  border-radius: calc(var(--radius) + 2px);
  background:
    radial-gradient(ellipse at 50% 0%, var(--bm-glow, rgba(255, 120, 40, 0.16)), transparent 45%),
    radial-gradient(ellipse at 80% 100%, rgba(40, 80, 140, 0.18), transparent 40%),
    linear-gradient(
      180deg,
      var(--bm-wrap-top, #101820) 0%,
      var(--bm-wrap-bottom, #0a0e14) 100%
    );
  box-shadow:
    inset 0 0 60px rgba(0, 0, 0, 0.45),
    0 0 32px rgba(var(--bm-accent-rgb, 249, 115, 22), 0.1);
}

.arena-glow {
  pointer-events: none;
  position: absolute;
  inset: -20%;
  background: radial-gradient(
    circle at 50% 40%,
    rgba(var(--bm-accent-rgb, 249, 115, 22), 0.08),
    transparent 55%
  );
  animation: arena-breathe 5.5s ease-in-out infinite;
}

@keyframes arena-breathe {
  0%,
  100% {
    opacity: 0.55;
    transform: scale(1);
  }
  50% {
    opacity: 1;
    transform: scale(1.04);
  }
}

.game-canvas {
  position: relative;
  z-index: 1;
  display: block;
  width: 100%;
  height: 100%;
}

.overlay {
  position: absolute;
  inset: 0;
  z-index: 2;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  background:
    radial-gradient(ellipse at 50% 40%, rgba(40, 18, 8, 0.35), transparent 55%),
    rgba(6, 8, 12, 0.72);
  backdrop-filter: blur(6px);
  gap: 0.4rem;
  padding: 1rem;
  text-align: center;
  animation: overlay-in 0.35s ease-out;
}

@keyframes overlay-in {
  from {
    opacity: 0;
  }
  to {
    opacity: 1;
  }
}

.overlay-kicker {
  font-size: 0.75rem;
  font-weight: 700;
  letter-spacing: 0.16em;
  text-transform: uppercase;
  color: rgba(249, 180, 120, 0.75);
}

.overlay-value {
  font-family: 'Outfit', 'DM Sans', system-ui, sans-serif;
  font-size: clamp(2rem, 5vw, 3.25rem);
  font-weight: 800;
  letter-spacing: -0.03em;
  text-shadow: 0 0 32px rgba(249, 115, 22, 0.5);
}

.overlay-value.pulse {
  animation: count-pulse 1s cubic-bezier(0.34, 1.4, 0.64, 1) infinite;
}

.overlay-value.win-pop {
  animation: win-pop 0.6s cubic-bezier(0.34, 1.56, 0.64, 1);
}

@keyframes count-pulse {
  0%,
  100% {
    transform: scale(1);
  }
  50% {
    transform: scale(1.14);
  }
}

@keyframes win-pop {
  0% {
    transform: scale(0.55);
    opacity: 0;
  }
  100% {
    transform: scale(1);
    opacity: 1;
  }
}

.overlay-label {
  font-size: 1.15rem;
  font-weight: 600;
  color: #f6d7b8;
}

.overlay-hint {
  font-size: 0.9rem;
  color: var(--text-muted);
}

.spectate-banner {
  position: absolute;
  top: 0.65rem;
  left: 50%;
  z-index: 2;
  transform: translateX(-50%);
  padding: 0.35rem 0.85rem;
  border-radius: 999px;
  background: rgba(12, 14, 18, 0.72);
  border: 1px solid rgba(249, 115, 22, 0.35);
  box-shadow: 0 4px 18px rgba(0, 0, 0, 0.35);
  pointer-events: none;
  animation: overlay-in 0.3s ease-out;
}

.spectate-label {
  font-size: 0.78rem;
  font-weight: 700;
  letter-spacing: 0.04em;
  color: #fdba74;
  white-space: nowrap;
}

.play-again-btn {
  margin-top: 0.65rem;
  animation: win-pop 0.7s cubic-bezier(0.34, 1.56, 0.64, 1) 0.15s both;
}

.player-bar {
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1rem;
  padding: 0.7rem 1rem;
  border: 1px solid rgba(249, 115, 22, 0.22);
  border-radius: calc(var(--radius) + 2px);
  background:
    linear-gradient(135deg, rgba(60, 32, 16, 0.55), transparent 40%),
    linear-gradient(180deg, rgba(28, 20, 14, 0.98), rgba(12, 10, 9, 0.99));
  box-shadow: inset 0 1px 0 rgba(255, 180, 100, 0.06);
  flex-wrap: wrap;
}

.bar-left {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 0.65rem 0.85rem;
  min-width: 0;
}

.map-chip {
  flex-shrink: 0;
  font-size: 0.7rem;
  font-weight: 700;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  padding: 0.25rem 0.55rem;
  border-radius: 999px;
  color: var(--bm-accent, #fdba74);
  background: rgba(var(--bm-accent-rgb, 249, 115, 22), 0.14);
  border: 1px solid rgba(var(--bm-accent-rgb, 249, 115, 22), 0.28);
}

.player-scores {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-wrap: wrap;
  gap: 0.45rem 0.85rem;
}

.player-score-row {
  display: flex;
  align-items: center;
  gap: 0.4rem;
  font-size: 0.85rem;
  padding: 0.2rem 0.45rem;
  border-radius: 999px;
  transition:
    opacity 0.25s ease,
    background 0.25s ease,
    transform 0.2s ease;
}

.player-score-row.me {
  font-weight: 700;
  background: rgba(249, 115, 22, 0.12);
}

.player-score-row.dead {
  opacity: 0.4;
  filter: grayscale(0.6);
}

.color-dot {
  width: 0.7rem;
  height: 0.7rem;
  border-radius: 50%;
  flex-shrink: 0;
  border: 1px solid rgba(255, 255, 255, 0.25);
}

.name {
  max-width: 7rem;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.stat-pills {
  display: inline-flex;
  gap: 0.25rem;
}

.pill {
  min-width: 1.15rem;
  padding: 0.05rem 0.3rem;
  border-radius: 999px;
  font-size: 0.72rem;
  font-weight: 700;
  text-align: center;
  line-height: 1.35;
  display: inline-flex;
  align-items: center;
  gap: 0.05rem;
}

.pill.bomb {
  background: rgba(249, 115, 22, 0.22);
  color: #fdba74;
}

.pill.range {
  background: rgba(56, 189, 248, 0.2);
  color: #7dd3fc;
}

.pill.speed {
  background: rgba(163, 230, 53, 0.18);
  color: #bef264;
}

.pill.throw {
  background: rgba(251, 191, 36, 0.2);
  color: #fcd34d;
}

.pill.kick {
  background: rgba(244, 114, 182, 0.2);
  color: #f9a8d4;
}

.kills {
  font-size: 0.75rem;
  font-weight: 700;
  color: #fb923c;
}

.status {
  font-size: 0.65rem;
  font-weight: 700;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  color: var(--text-muted);
}

.controls-hint {
  font-size: 0.8rem;
  color: var(--text-muted);
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 0.5rem 0.75rem;
}

.mute-btn {
  font-size: 1rem;
  padding: 0.25rem 0.5rem;
  line-height: 1;
  min-width: 2.25rem;
}

.controls-hint .muted {
  opacity: 0.75;
}

.power-legend {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  gap: 0.75rem;
  font-size: 0.75rem;
}

.power-legend li {
  display: flex;
  align-items: center;
  gap: 0.3rem;
}

.legend-emoji {
  font-size: 0.85rem;
  line-height: 1;
}

.touch-controls {
  position: absolute;
  inset: 0;
  z-index: 2;
  pointer-events: none;
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  padding: 0.75rem;
}

.touch-dpad {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  grid-template-rows: repeat(3, 1fr);
  gap: 0.25rem;
  width: 9.5rem;
  height: 9.5rem;
  pointer-events: auto;
}

.touch-btn {
  width: 3rem;
  height: 3rem;
  border-radius: 12px;
  border: 1px solid rgba(249, 115, 22, 0.4);
  background: rgba(18, 14, 12, 0.88);
  color: #fdba74;
  font-size: 1rem;
  font-weight: 700;
  backdrop-filter: blur(6px);
  box-shadow: 0 4px 14px rgba(0, 0, 0, 0.4);
  touch-action: none;
  user-select: none;
  display: flex;
  align-items: center;
  justify-content: center;
}

.touch-btn:active {
  transform: scale(0.95);
  background: rgba(249, 115, 22, 0.3);
}

.dpad-up {
  grid-column: 2;
  grid-row: 1;
}

.dpad-left {
  grid-column: 1;
  grid-row: 2;
}

.dpad-right {
  grid-column: 3;
  grid-row: 2;
}

.dpad-down {
  grid-column: 2;
  grid-row: 3;
}

.touch-actions {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
  pointer-events: auto;
}

.touch-bomb {
  width: 4.5rem;
  height: 4.5rem;
  border-radius: 50%;
  font-size: 2rem;
  border-color: rgba(239, 68, 68, 0.5);
}

.scream-tester {
  flex-shrink: 0;
  padding: 0.55rem 0.65rem 0.65rem;
  border-radius: calc(var(--radius) + 2px);
  border: 1px solid rgba(var(--bm-accent-rgb, 249, 115, 22), 0.28);
  background: rgba(10, 12, 16, 0.72);
}

.scream-tester-head {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 0.75rem;
  margin-bottom: 0.45rem;
}

.scream-tester-title {
  font-size: 0.72rem;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: rgba(255, 220, 180, 0.85);
}

.scream-tester-hint {
  font-size: 0.68rem;
  color: var(--text-muted);
}

.scream-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(9.5rem, 1fr));
  gap: 0.35rem;
}

.scream-btn {
  display: flex;
  align-items: center;
  gap: 0.4rem;
  text-align: left;
  padding: 0.4rem 0.5rem;
  border-radius: 8px;
  border: 1px solid rgba(255, 255, 255, 0.1);
  background: rgba(20, 22, 28, 0.85);
  color: var(--text);
  cursor: pointer;
  transition:
    border-color 0.12s ease,
    background 0.12s ease,
    transform 0.12s ease;
}

.scream-btn:hover {
  border-color: rgba(var(--bm-accent-rgb, 249, 115, 22), 0.55);
  transform: translateY(-1px);
}

.scream-btn.selected {
  border-color: rgba(var(--bm-accent-rgb, 249, 115, 22), 0.85);
  background: rgba(var(--bm-accent-rgb, 249, 115, 22), 0.16);
  box-shadow: 0 0 0 1px rgba(var(--bm-accent-rgb, 249, 115, 22), 0.25);
}

.scream-num {
  flex-shrink: 0;
  width: 1.25rem;
  height: 1.25rem;
  border-radius: 4px;
  display: grid;
  place-items: center;
  font-size: 0.68rem;
  font-weight: 800;
  background: rgba(var(--bm-accent-rgb, 249, 115, 22), 0.22);
  color: var(--bm-accent, #fdba74);
}

.scream-name {
  font-size: 0.75rem;
  font-weight: 600;
  line-height: 1.2;
}

@media (max-width: 720px) {
  .player-bar {
    flex-direction: column;
    align-items: flex-start;
  }

  .scream-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}
</style>
