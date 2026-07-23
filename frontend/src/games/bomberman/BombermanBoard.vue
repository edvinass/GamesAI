<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import type { Room, BombermanGameState, BombermanBomb } from '@/types'
import TouchDpad from '@/components/TouchDpad.vue'
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
  playBombStop,
  playBombThrow,
  playCountdownGo,
  playCountdownTick,
  playDeath,
  playExplosion,
  playLose,
  playPowerup,
  playSoftDestroy,
  playStep,
  playWin,
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

const myBomber = computed(() => props.gameState.bombers[props.playerId])
const isAlive = computed(() => myBomber.value?.alive ?? false)
const isRespawning = computed(() => (myBomber.value?.respawn_ticks ?? 0) > 0)
const isHost = computed(() => props.room.host_player_id === props.playerId)
const isFinished = computed(() => props.gameState.phase === 'finished')
const canControl = computed(
  () =>
    props.gameState.phase === 'playing' &&
    isAlive.value &&
    !isRespawning.value,
)
/** Eliminated or waiting to respawn — free camera pan with arrows/WASD. */
const isSpectating = computed(
  () => props.gameState.phase === 'playing' && !canControl.value,
)

const myNickname = computed(
  () => props.gameState.players.find((p) => p.id === props.playerId)?.nickname ?? 'You',
)

const countdownRemaining = computed(() => {
  if (props.gameState.phase !== 'countdown' || !props.gameState.countdown_ends_at) return null
  const end = new Date(props.gameState.countdown_ends_at).getTime()
  return Math.max(0, Math.ceil((end - Date.now()) / 1000))
})

/** Full marker during countdown; fades out over the first few seconds of play. */
const SELF_MARKER_FADE_MS = 3500
let playingStartedAt: number | null = null

function selfMarkerStrength(now = performance.now()): number {
  const phase = props.gameState.phase
  if (phase === 'countdown') return 1
  if (phase !== 'playing' || !isAlive.value) return 0
  if (playingStartedAt == null) playingStartedAt = now
  const t = (now - playingStartedAt) / SELF_MARKER_FADE_MS
  if (t >= 1) return 0
  return 1 - t
}

const winnerName = computed(() => {
  const team = props.gameState.winning_team
  if (team === 'red') return 'Red team'
  if (team === 'blue') return 'Blue team'
  const winnerId = props.gameState.winner
  if (!winnerId) return null
  return props.gameState.players.find((p) => p.id === winnerId)?.nickname ?? 'Unknown'
})

const winReasonLabel = computed(() => {
  const reason = props.gameState.win_reason
  if (reason === 'last_standing') return 'Last bomber standing'
  if (reason === 'most_kills') return 'Most kills'
  if (reason === 'team_eliminated') return 'Team victory'
  if (reason === 'kill_race') return 'Kill race'
  if (reason === 'time_up') return 'Time up'
  return null
})

const modeChip = computed(() => {
  const mode = props.gameState.game_mode ?? 'classic'
  if (mode === 'team') return 'Team Battle'
  if (mode === 'kill_race') return `Kill Race · ${props.gameState.kill_target ?? 5}`
  const lives = myBomber.value?.lives
  if (typeof lives === 'number' && lives > 1) return `Stock · ${lives} lives`
  return null
})

const timerLabel = computed(() => {
  const sec = props.gameState.time_remaining_sec
  if (sec == null || props.gameState.phase !== 'playing') return null
  const m = Math.floor(sec / 60)
  const s = sec % 60
  return `${m}:${String(s).padStart(2, '0')}`
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

function onTouchDirection(direction: string) {
  if (!canControl.value) return
  void unlockAudio()
  touchDirection.value = direction
  emit('action', { type: 'set_direction', direction })
}

function onTouchStop() {
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

/** Spectate camera pan — separate from movement so respawn doesn't inherit hold. */
const spectateDirectionStack: string[] = []
let spectateFocus: { x: number; y: number } | null = null
const SPECTATE_PAN_CELLS_PER_SEC = 10

function desiredDirection(): string {
  return directionStack.length ? directionStack[directionStack.length - 1]! : 'stop'
}

function desiredSpectateDirection(): string {
  return spectateDirectionStack.length
    ? spectateDirectionStack[spectateDirectionStack.length - 1]!
    : 'stop'
}

function seedSpectateFocus() {
  const me = myBomber.value
  const gridW = props.gameState.grid_width
  const gridH = props.gameState.grid_height
  spectateFocus = {
    x: me ? me.x : (gridW - 1) / 2,
    y: me ? me.y : (gridH - 1) / 2,
  }
}

function clearSpectateInput() {
  spectateDirectionStack.length = 0
  spectateFocus = null
}

function updateSpectateFocus(dt: number) {
  if (!isSpectating.value) return
  if (!spectateFocus) seedSpectateFocus()
  const dir = desiredSpectateDirection()
  const delta = DIR_DELTAS[dir]
  if (!delta || !spectateFocus) return
  const [dx, dy] = delta
  const gridW = props.gameState.grid_width
  const gridH = props.gameState.grid_height
  const step = SPECTATE_PAN_CELLS_PER_SEC * dt
  spectateFocus.x = Math.min(gridW - 1, Math.max(0, spectateFocus.x + dx * step))
  spectateFocus.y = Math.min(gridH - 1, Math.max(0, spectateFocus.y + dy * step))
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
  if (isSpectating.value) {
    const direction = codeToDirection[e.code]
    if (!direction) return
    e.preventDefault()
    if (e.repeat) return
    if (!spectateFocus) seedSpectateFocus()
    const idx = spectateDirectionStack.indexOf(direction)
    if (idx >= 0) spectateDirectionStack.splice(idx, 1)
    spectateDirectionStack.push(direction)
    return
  }
  if (e.code === 'Space' || e.key === ' ') {
    if (!canControl.value) return
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
  if (!acceptsMoveKeys()) return
  e.preventDefault()
  if (e.repeat) return
  const idx = directionStack.indexOf(direction)
  if (idx >= 0) directionStack.splice(idx, 1)
  directionStack.push(direction)
  if (canControl.value) emitDirection()
}

function onKeyUp(e: KeyboardEvent) {
  const direction = codeToDirection[e.code]
  if (!direction) return
  e.preventDefault()
  if (isSpectating.value) {
    const idx = spectateDirectionStack.indexOf(direction)
    if (idx >= 0) spectateDirectionStack.splice(idx, 1)
    return
  }
  const idx = directionStack.indexOf(direction)
  if (idx >= 0) directionStack.splice(idx, 1)
  if (!acceptsMoveKeys()) {
    directionStack.length = 0
    currentDirection = 'stop'
    return
  }
  if (canControl.value) emitDirection()
}

function onWindowBlur() {
  clearMovementInput()
  spectateDirectionStack.length = 0
}

let rafId = 0
let resizeObserver: ResizeObserver | null = null
let lastFrameTime = performance.now()
let lastTick = -1
let tickReceivedAt = performance.now()
/** EMA of actual inter-tick gaps so lerp doesn't constantly overshoot. */
let smoothedTickMs = 0
/** Previous tick positions (lerp origin — may be fractional from last display). */
let prevBombers: Record<string, BomberSnapshot> = {}
/** Latest server truth positions. */
let targetBombers: Record<string, BomberSnapshot> = {}
/** Previous / current bomb cells for kick/throw lerp. */
let prevBombPos: Record<string, { x: number; y: number }> = {}
let targetBombPos: Record<string, { x: number; y: number }> = {}

function configuredTickMs(): number {
  return props.gameState.tick_ms ?? Number(props.room.settings?.tick_ms ?? 150)
}

function lerpTickMs(): number {
  const configured = configuredTickMs()
  return Math.max(16, smoothedTickMs > 0 ? smoothedTickMs : configured)
}

function currentLerpT(now = performance.now()): number {
  if (props.gameState.phase !== 'playing') return 1
  return (now - tickReceivedAt) / lerpTickMs()
}

/** Keep held keys through countdown so GO isn't a dead press. */
function acceptsMoveKeys(): boolean {
  return canControl.value || props.gameState.phase === 'countdown'
}

function snapshotFromDisplay(
  display: Record<string, SmoothBomber>,
  meta: Record<string, BomberSnapshot>,
): Record<string, BomberSnapshot> {
  const out: Record<string, BomberSnapshot> = {}
  for (const [pid, b] of Object.entries(meta)) {
    const d = display[pid]
    if (
      d &&
      d.alive &&
      b.alive &&
      Math.abs(d.x - b.x) <= 1.6 &&
      Math.abs(d.y - b.y) <= 1.6
    ) {
      out[pid] = {
        ...b,
        x: d.x,
        y: d.y,
        direction: d.direction,
      }
    } else {
      out[pid] = { ...b }
    }
  }
  return out
}
let particles: Particle[] = []
let shake = 0

const POWERUP_COLORS: Record<string, string> = {
  bomb: '#f97316',
  range: '#38bdf8',
  speed: '#a3e635',
  throw: '#fbbf24',
  kick: '#f472b6',
  skull: '#64748b',
}

/** Snapshot used to detect gameplay events for SFX. */
let prevSoundSnap: {
  phase: string
  bombIds: Set<string>
  bombs: BombermanBomb[]
  explosionCount: number
  softCount: number
  alive: Record<string, boolean>
  lives: Record<string, number>
  respawning: Record<string, boolean>
  countdownSec: number | null
  myStats: {
    maxBombs: number
    bombRange: number
    speedLevel: number
    canThrow: boolean
    canKick: boolean
    diseased: boolean
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
  const softCount = countSoftBlocks(state.grid ?? [])
  const softCells = softCellKeys(state.grid ?? [])
  const explKeys = explosionKeys(state)
  const alive: Record<string, boolean> = {}
  const lives: Record<string, number> = {}
  const respawning: Record<string, boolean> = {}
  for (const [pid, b] of Object.entries(state.bombers)) {
    alive[pid] = Boolean(b.alive)
    lives[pid] = Number(b.lives ?? 1)
    respawning[pid] = Number(b.respawn_ticks ?? 0) > 0
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
      lives: { ...lives },
      respawning: { ...respawning },
      countdownSec,
      myStats: me
        ? {
            maxBombs: me.max_bombs,
            bombRange: me.bomb_range,
            speedLevel: me.speed_level,
            canThrow: Boolean(me.can_throw),
            canKick: Boolean(me.can_kick),
            diseased: Boolean(me.disease),
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
  if (prev.phase !== 'playing' && state.phase === 'playing') {
    playingStartedAt = performance.now()
  }
  if (state.phase !== 'playing') {
    playingStartedAt = null
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

  // Power-up pickup (detect via our bomber stats rising or skull infection)
  const prevMeStats = prev.myStats
  if (me && prevMeStats && !prevMeStats.diseased && Boolean(me.disease)) {
    playPowerup('skull')
    particles.push(...spawnPowerupParticles(me.x, me.y, POWERUP_COLORS.skull ?? '#64748b'))
  } else if (
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

  // Deaths / life loss (stock & kill race keep alive=true while respawning)
  for (const pid of new Set([...Object.keys(prev.alive), ...Object.keys(alive)])) {
    const wasAlive = Boolean(prev.alive[pid])
    const nowAlive = Boolean(alive[pid])
    const lifeLost =
      (prev.lives?.[pid] ?? 1) > (lives[pid] ?? 1) ||
      (!prev.respawning?.[pid] && respawning[pid])
    if ((wasAlive && !nowAlive) || (wasAlive && lifeLost)) {
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
    const meBomber = state.bombers[props.playerId]
    const myTeamWin =
      state.winning_team && meBomber?.team && state.winning_team === meBomber.team
    if (state.winner === props.playerId || myTeamWin) playWin()
    else playLose()
  }

  prevSoundSnap = {
    phase: state.phase,
    bombIds,
    bombs: (state.bombs ?? []).map((b) => ({ ...b })),
    explosionCount,
    softCount,
    alive: { ...alive },
    lives: { ...lives },
    respawning: { ...respawning },
    countdownSec,
    myStats: me
      ? {
          maxBombs: me.max_bombs,
          bombRange: me.bomb_range,
          speedLevel: me.speed_level,
          canThrow: Boolean(me.can_throw),
          canKick: Boolean(me.can_kick),
          diseased: Boolean(me.disease),
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
  const now = performance.now()

  if (tick !== lastTick) {
    const matchReset = lastTick >= 0 && tick < lastTick
    const prevTargets = targetBombers
    // Continue from the currently drawn pose (incl. micro-glide). Seeding from
    // the last integer cell made the sprite jump backward every late tick.
    if (!matchReset && Object.keys(prevTargets).length) {
      const display = interpolateBombers(prevBombers, prevTargets, currentLerpT(now))
      prevBombers = snapshotFromDisplay(display, prevTargets)
      // Stationary bombers: drop overshoot so releasing a key doesn't ease backward.
      for (const [pid, b] of Object.entries(snap)) {
        const old = prevTargets[pid]
        if (old && old.x === b.x && old.y === b.y) {
          prevBombers[pid] = { ...b }
        }
      }
    } else {
      prevBombers = snap
    }
    prevBombPos = Object.keys(targetBombPos).length ? { ...targetBombPos } : bombSnap
    targetBombers = snap
    targetBombPos = bombSnap
    const configured = configuredTickMs()
    if (matchReset || lastTick < 0) {
      smoothedTickMs = configured
    } else {
      const gap = now - tickReceivedAt
      // Ignore huge stalls (tab background) so EMA doesn't blow up.
      if (gap > 16 && gap < configured * 4) {
        smoothedTickMs =
          smoothedTickMs > 0 ? smoothedTickMs * 0.75 + gap * 0.25 : gap
      }
    }
    lastTick = tick
    tickReceivedAt = now
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
    // Keep direction keys through countdown so a held press still walks on GO.
    if (props.gameState.phase !== 'countdown') {
      directionStack.length = 0
      currentDirection = 'stop'
    }
    if (isSpectating.value) seedSpectateFocus()
  } else {
    clearSpectateInput()
    if (desiredDirection() !== 'stop') {
      // Re-assert held direction after countdown / reconnect.
      emitDirection(true)
    }
  }
})

watch(isSpectating, (spectating) => {
  if (spectating) {
    seedSpectateFocus()
  } else {
    clearSpectateInput()
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
  updateSpectateFocus(dt)

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

  const rawT = currentLerpT(now)

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
    grid: props.gameState.grid ?? [],
    bombers: displayBombers,
    bombs: renderedBombs,
    explosions: props.gameState.explosions ?? [],
    powerups: props.gameState.powerups ?? [],
    playerId: props.playerId,
    time: now,
    particles,
    shake,
    mapId: props.gameState.map_id,
    selfMarker: selfMarkerStrength(now),
    focusX: isSpectating.value && spectateFocus ? spectateFocus.x : undefined,
    focusY: isSpectating.value && spectateFocus ? spectateFocus.y : undefined,
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
        <div v-if="myBomber" class="you-are">
          <span
            class="you-are-swatch"
            :style="{
              background: myBomber.color,
              boxShadow: `0 0 14px ${myBomber.color}`,
            }"
          />
          <span class="you-are-text">
            You’re <strong>{{ myNickname }}</strong>
          </span>
        </div>
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
        v-else-if="isAlive && isRespawning && gameState.phase === 'playing'"
        class="spectate-banner"
      >
        <span class="spectate-label">Respawning… · arrows to pan</span>
      </div>

      <div
        v-else-if="!isAlive && gameState.phase === 'playing'"
        class="spectate-banner"
      >
        <span class="spectate-label">Eliminated — spectating · arrows to pan</span>
      </div>

      <div
        v-if="showTouchControls && canControl"
        class="touch-controls"
        aria-label="Touch controls"
      >
        <TouchDpad
          accent-color="#fdba74"
          :emit-stop="true"
          @direction="onTouchDirection"
          @stop="onTouchStop"
        />
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
        <span v-if="modeChip" class="map-chip mode-chip">{{ modeChip }}</span>
        <span v-if="timerLabel" class="map-chip timer-chip">⏱ {{ timerLabel }}</span>
        <span v-if="gameState.sudden_death_active" class="map-chip sd-chip">Sudden death</span>
        <ul class="player-scores">
          <li
            v-for="row in playerRows"
            :key="row.id"
            class="player-score-row"
            :class="{
              me: row.id === playerId,
              dead: !row.bomber?.alive,
              'team-red': row.bomber?.team === 'red',
              'team-blue': row.bomber?.team === 'blue',
            }"
          >
            <span
              class="color-dot"
              :style="{
                background: row.bomber?.color ?? '#666',
                boxShadow: row.id === playerId ? `0 0 10px ${row.bomber?.color ?? '#f97316'}` : undefined,
              }"
            />
            <span class="name">{{ row.nickname }}</span>
            <span
              v-if="row.bomber?.team"
              class="team-tag"
              :class="row.bomber.team"
            >{{ row.bomber.team === 'red' ? 'R' : 'B' }}</span>
            <span
              v-if="(row.bomber?.lives ?? 1) > 1"
              class="lives"
              title="Lives"
            >♥{{ row.bomber?.lives }}</span>
            <span class="stat-pills" title="Bombs / Range / Speed / Throw / Kick">
              <span class="pill bomb">💣{{ row.bomber?.max_bombs ?? 1 }}</span>
              <span class="pill range">🔥{{ row.bomber?.bomb_range ?? 1 }}</span>
              <span class="pill speed">⚡{{ row.bomber?.speed_level ?? 0 }}</span>
              <span v-if="row.bomber?.can_throw" class="pill throw" title="Throw">🧤</span>
              <span v-if="row.bomber?.can_kick" class="pill kick" title="Kick">🦵</span>
              <span
                v-if="row.bomber?.disease"
                class="pill skull"
                title="Cursed — touch another player to pass it on"
              >💀</span>
            </span>
            <span
              v-if="gameState.game_mode === 'kill_race' || (row.bomber?.kills ?? 0) > 0"
              class="kills"
            >×{{ row.bomber?.kills ?? 0 }}</span>
            <span v-if="(row.bomber?.respawn_ticks ?? 0) > 0" class="status">wait</span>
            <span v-else-if="!row.bomber?.alive" class="status">out</span>
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
        <p v-else-if="gameState.phase === 'playing' && !isAlive" class="muted">
          Spectating · arrows / WASD to pan
        </p>
        <p v-else-if="isSpectating" class="muted">
          Arrows / WASD to pan map
        </p>
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

.you-are {
  display: inline-flex;
  align-items: center;
  gap: 0.55rem;
  margin-top: 0.55rem;
  padding: 0.45rem 0.85rem;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.08);
  border: 1px solid rgba(255, 255, 255, 0.14);
  animation: you-are-in 0.45s cubic-bezier(0.34, 1.4, 0.64, 1) both;
}

@keyframes you-are-in {
  from {
    opacity: 0;
    transform: translateY(8px) scale(0.94);
  }
  to {
    opacity: 1;
    transform: translateY(0) scale(1);
  }
}

.you-are-swatch {
  width: 1.05rem;
  height: 1.05rem;
  border-radius: 50%;
  border: 2px solid rgba(255, 255, 255, 0.85);
  flex-shrink: 0;
  animation: you-swatch-pulse 1.1s ease-in-out infinite;
}

@keyframes you-swatch-pulse {
  0%,
  100% {
    transform: scale(1);
  }
  50% {
    transform: scale(1.12);
  }
}

.you-are-text {
  font-size: 0.95rem;
  font-weight: 600;
  color: #f6d7b8;
}

.you-are-text strong {
  color: #fff;
  font-weight: 800;
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

.mode-chip,
.timer-chip {
  color: #93c5fd;
  background: rgba(59, 130, 246, 0.12);
  border-color: rgba(59, 130, 246, 0.28);
}

.sd-chip {
  color: #fca5a5;
  background: rgba(239, 68, 68, 0.15);
  border-color: rgba(239, 68, 68, 0.35);
}

.team-tag {
  font-size: 0.65rem;
  font-weight: 800;
  padding: 0.05rem 0.3rem;
  border-radius: 4px;
}

.team-tag.red {
  color: #fecaca;
  background: rgba(239, 68, 68, 0.25);
}

.team-tag.blue {
  color: #bfdbfe;
  background: rgba(59, 130, 246, 0.25);
}

.lives {
  font-size: 0.75rem;
  font-weight: 700;
  color: #f87171;
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

.pill.skull {
  background: rgba(100, 116, 139, 0.35);
  color: #e2e8f0;
  animation: skull-pulse 0.7s ease-in-out infinite alternate;
}

@keyframes skull-pulse {
  from {
    opacity: 0.55;
  }
  to {
    opacity: 1;
  }
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

.touch-actions {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
  pointer-events: auto;
}

.touch-btn {
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

.touch-bomb {
  width: 4.5rem;
  height: 4.5rem;
  border-radius: 50%;
  font-size: 2rem;
  border-color: rgba(239, 68, 68, 0.5);
}

@media (max-width: 720px) {
  .player-bar {
    flex-direction: column;
    align-items: flex-start;
  }
}
</style>
