<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import type { Room, DuelGameState } from '@/types'
import { DuelRenderer, POWERUP_ACTIVATION_TICKS, POWERUP_COLORS, POWERUP_ICONS, POWERUP_LABELS } from './duelRenderer'

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
const renderer = new DuelRenderer()

const myFighter = computed(() => props.gameState.fighters[props.playerId])
const isAlive = computed(() => myFighter.value?.alive ?? false)
const isHost = computed(() => props.room.host_player_id === props.playerId)
const isFinished = computed(() => props.gameState.phase === 'finished')
const isRoundOver = computed(() => props.gameState.phase === 'round_over')
const canControl = computed(
  () => props.gameState.phase === 'playing' && isAlive.value,
)
const chargeEnabled = computed(() => props.gameState.match_format !== 'quick_duel')
const powerupsEnabled = computed(() => props.gameState.match_format !== 'quick_duel')
const storedPowerup = computed(() => myFighter.value?.stored_powerup ?? null)

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
const activatingPowerup = ref(false)
const powerupActivationTicks = ref(0)
const localChargeInterval = ref<ReturnType<typeof setInterval> | null>(null)
const localPowerupInterval = ref<ReturnType<typeof setInterval> | null>(null)
const hpPulseId = ref<string | null>(null)

const MUTATOR_LABELS: Record<string, string> = {
  classic: 'Classic',
  chaos: 'Chaos',
  sniper: 'Sniper',
  bounce_house: 'Bounce House',
  fog: 'Fog',
}

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
    const approxX = bullet.x + speed * 0.85
    const ticks = Math.abs(approxX - myX) / speed
    if (ticks <= 8) rows.add(bullet.y)
  }
  return rows
})

function startNewGame() {
  emit('action', { type: 'start_game' })
}

function sendMove(direction: 'up' | 'down' | 'stop') {
  emit('action', { type: 'set_move', direction })
}

function startPowerupActivation() {
  if (!canControl.value || !powerupsEnabled.value || !storedPowerup.value) return
  activatingPowerup.value = true
  powerupActivationTicks.value = 0
  emit('action', { type: 'powerup_hold_start' })
  if (localPowerupInterval.value) clearInterval(localPowerupInterval.value)
  const tickMs = props.gameState.tick_ms || 75
  localPowerupInterval.value = setInterval(() => {
    if (activatingPowerup.value) {
      powerupActivationTicks.value = Math.min(
        POWERUP_ACTIVATION_TICKS,
        powerupActivationTicks.value + 1,
      )
    }
  }, tickMs)
}

function releasePowerupActivation() {
  if (!activatingPowerup.value) return
  activatingPowerup.value = false
  if (localPowerupInterval.value) {
    clearInterval(localPowerupInterval.value)
    localPowerupInterval.value = null
  }
  emit('action', {
    type: 'powerup_hold_release',
    powerup_activation_ticks: powerupActivationTicks.value,
  })
  powerupActivationTicks.value = 0
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
    if (storedPowerup.value && powerupsEnabled.value) {
      if (!activatingPowerup.value) startPowerupActivation()
    } else if (chargeEnabled.value) {
      if (!charging.value) startCharge()
    } else {
      quickShoot()
    }
    return
  }

  if ((e.key === 'f' || e.key === 'F') && storedPowerup.value && chargeEnabled.value) {
    e.preventDefault()
    if (!charging.value) startCharge()
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
    if (activatingPowerup.value) releasePowerupActivation()
    else if (charging.value) releaseCharge()
    return
  }

  if ((e.key === 'f' || e.key === 'F') && charging.value) {
    e.preventDefault()
    releaseCharge()
  }
}

function draw(now: number) {
  const canvas = canvasRef.value
  const wrap = canvasWrapRef.value
  if (!canvas || !wrap) return
  const ctx = canvas.getContext('2d')
  if (!ctx) return

  const displayW = wrap.clientWidth
  const displayH = wrap.clientHeight
  if (displayW <= 0 || displayH <= 0) return

  const hit = props.gameState.last_hit
  if (hit?.player_id) {
    hpPulseId.value = `${hit.player_id}-${props.gameState.tick}`
  }

  const dpr = window.devicePixelRatio || 1
  canvas.width = Math.floor(displayW * dpr)
  canvas.height = Math.floor(displayH * dpr)
  canvas.style.width = `${displayW}px`
  canvas.style.height = `${displayH}px`
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0)

  renderer.draw(ctx, props.gameState, props.playerId, displayW, displayH, now, dangerRows.value)
}

let resizeObserver: ResizeObserver | null = null
let animFrame = 0

function animationLoop() {
  draw(Date.now())
  animFrame = requestAnimationFrame(animationLoop)
}

onMounted(() => {
  window.addEventListener('keydown', onKeyDown)
  window.addEventListener('keyup', onKeyUp)
  if (canvasWrapRef.value) {
    resizeObserver = new ResizeObserver(() => draw(Date.now()))
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
  if (localPowerupInterval.value) clearInterval(localPowerupInterval.value)
  renderer.reset()
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
        <div
          class="charge-fill"
          :class="{ 'charge-full': chargeTicks >= 11 }"
          :style="{ width: `${(chargeTicks / 15) * 100}%` }"
        />
        <span class="charge-label">{{ chargeTicks >= 11 ? 'MAX POWER' : 'Charging…' }}</span>
      </div>

      <div v-if="activatingPowerup && canControl && storedPowerup" class="charge-bar powerup-bar">
        <div
          class="charge-fill powerup-fill"
          :class="{ 'charge-full': powerupActivationTicks >= POWERUP_ACTIVATION_TICKS }"
          :style="{
            width: `${(powerupActivationTicks / POWERUP_ACTIVATION_TICKS) * 100}%`,
            background: POWERUP_COLORS[storedPowerup] ?? '#a855f7',
          }"
        />
        <span class="charge-label powerup-label">
          {{
            powerupActivationTicks >= POWERUP_ACTIVATION_TICKS
              ? 'RELEASE!'
              : `Activating ${POWERUP_LABELS[storedPowerup] ?? storedPowerup}…`
          }}
        </span>
      </div>

      <div v-if="gameState.phase === 'countdown'" class="overlay countdown">
        <span class="overlay-value pulse">{{ countdownRemaining ?? '…' }}</span>
        <span class="overlay-label">Get ready!</span>
      </div>

      <div v-else-if="isRoundOver" class="overlay round-over">
        <span class="overlay-label slide-in">Round {{ gameState.round - 1 }} over</span>
        <span v-if="roundWinnerName" class="overlay-value pop-in">{{ roundWinnerName }} wins the round!</span>
        <span v-else class="overlay-value pop-in">Draw — rematch!</span>
        <span class="overlay-hint">Next round in {{ countdownRemaining ?? '…' }}</span>
      </div>

      <div v-else-if="isFinished" class="overlay finished">
        <span class="overlay-label slide-in">Match over</span>
        <span class="overlay-value winner-glow">{{ winnerName }} wins!</span>
        <button v-if="isHost" type="button" class="btn-primary play-again-btn" @click="startNewGame">
          Play Again
        </button>
        <p v-else class="overlay-hint">Waiting for host to start a new match…</p>
      </div>

      <div v-else-if="!isAlive && gameState.phase === 'playing'" class="overlay eliminated">
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
          :class="{
            me: row.id === playerId,
            dead: !row.fighter?.alive,
            'hp-hit': hpPulseId === `${row.id}-${gameState.tick}`,
          }"
        >
          <span class="color-dot" :style="{ background: row.fighter?.color ?? '#666' }" />
          <span class="name">{{ row.nickname }}</span>
          <span class="round-wins">{{ row.roundWins }}/{{ roundsToWin }}</span>
          <span v-if="row.fighter" class="hp-bar">
            <span
              v-for="i in row.fighter.max_hp"
              :key="i"
              class="hp-pip"
              :class="{ spent: i > row.fighter.hp, low: row.fighter.hp === 1 && i === 1 }"
            />
          </span>
          <span v-if="row.fighter?.effects?.rapid_fire_active" class="effect-badge" title="Rapid Fire">⚡</span>
          <span v-if="row.fighter?.effects?.wide_shot_active" class="effect-badge" title="Wide Shot">▣</span>
          <span v-if="row.fighter?.effects?.overdrive_active" class="effect-badge" title="Overdrive">✦</span>
          <span v-if="row.fighter?.effects?.shield_active" class="effect-badge shield-pulse">🛡</span>
          <span v-if="row.fighter?.effects?.ghost_active" class="effect-badge" title="Ghost">◎</span>
          <span v-if="row.fighter?.effects?.mirror_active" class="effect-badge" title="Mirror">⟲</span>
          <span v-if="row.fighter?.effects?.homing_active" class="effect-badge" title="Homing">↯</span>
          <span v-if="row.fighter?.effects?.freeze_active" class="effect-badge" title="Frozen">❄</span>
          <span
            v-if="row.id === playerId && row.fighter?.stored_powerup"
            class="effect-badge stored-powerup"
            :style="{ color: POWERUP_COLORS[row.fighter.stored_powerup] ?? '#fbbf24' }"
            :title="POWERUP_LABELS[row.fighter.stored_powerup]"
          >
            {{ POWERUP_ICONS[row.fighter.stored_powerup] ?? '★' }}
          </span>
          <span v-if="!row.fighter?.alive" class="status">out</span>
        </li>
      </ul>

      <div class="controls-hint">
        <p v-if="canControl && chargeEnabled && storedPowerup">
          <strong>Controls:</strong> W/S or ↑/↓ to move · Hold Space until the bar fills to activate · Hold F to charge & fire
        </p>
        <p v-else-if="canControl && chargeEnabled">
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
  padding: 0.15rem 0.55rem;
  border-radius: 999px;
  background: linear-gradient(135deg, rgba(91, 156, 255, 0.2), rgba(124, 108, 240, 0.2));
  border: 1px solid rgba(91, 156, 255, 0.25);
  font-size: 0.75rem;
  font-weight: 600;
  color: var(--accent);
}

.canvas-wrap {
  position: relative;
  flex: 1;
  min-height: 0;
  width: 100%;
  overflow: hidden;
  border: 1px solid rgba(91, 156, 255, 0.2);
  border-radius: var(--radius);
  background: #070b12;
  box-shadow: inset 0 0 40px rgba(0, 0, 0, 0.5), 0 0 24px rgba(91, 156, 255, 0.08);
}

.game-canvas {
  display: block;
  width: 100%;
  height: 100%;
}

.charge-bar {
  position: absolute;
  left: 50%;
  bottom: 0.85rem;
  transform: translateX(-50%);
  width: min(260px, 72%);
  height: 10px;
  border-radius: 999px;
  background: rgba(0, 0, 0, 0.45);
  border: 1px solid rgba(251, 191, 36, 0.35);
  overflow: hidden;
  box-shadow: 0 0 12px rgba(251, 191, 36, 0.2);
}

.charge-fill {
  height: 100%;
  background: linear-gradient(90deg, #fbbf24, #f97316, #ef4444);
  transition: width 75ms linear;
  box-shadow: 0 0 10px rgba(251, 191, 36, 0.6);
}

.charge-fill.charge-full {
  animation: chargePulse 0.5s ease-in-out infinite alternate;
}

.powerup-bar {
  border-color: rgba(168, 85, 247, 0.45);
  box-shadow: 0 0 12px rgba(168, 85, 247, 0.25);
}

.powerup-fill {
  background: linear-gradient(90deg, #a855f7, #ec4899, #f97316);
  box-shadow: 0 0 10px rgba(168, 85, 247, 0.6);
}

.powerup-label {
  color: #c084fc;
  text-shadow: 0 0 8px rgba(168, 85, 247, 0.6);
}

.stored-powerup {
  font-weight: 800;
  animation: shieldPulse 1.4s ease-in-out infinite;
}

.charge-label {
  position: absolute;
  top: -1.4rem;
  left: 50%;
  transform: translateX(-50%);
  font-size: 0.72rem;
  font-weight: 700;
  letter-spacing: 0.04em;
  color: #fbbf24;
  white-space: nowrap;
  text-shadow: 0 0 8px rgba(251, 191, 36, 0.6);
}

.overlay {
  position: absolute;
  inset: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  background: rgba(0, 0, 0, 0.72);
  backdrop-filter: blur(3px);
  gap: 0.5rem;
  padding: 1rem;
  text-align: center;
  animation: overlayIn 0.35s ease-out;
}

.overlay-value {
  font-size: clamp(1.75rem, 4vw, 2.5rem);
  font-weight: 800;
}

.overlay-value.pulse {
  animation: countPulse 1s ease-in-out infinite;
}

.overlay-value.pop-in {
  animation: popIn 0.45s cubic-bezier(0.34, 1.56, 0.64, 1);
}

.overlay-value.winner-glow {
  background: linear-gradient(135deg, #fbbf24, #5b9cff);
  -webkit-background-clip: text;
  background-clip: text;
  color: transparent;
  animation: winnerGlow 2s ease-in-out infinite;
}

.overlay-label {
  font-size: 1.1rem;
  font-weight: 600;
}

.overlay-label.slide-in {
  animation: slideIn 0.4s ease-out;
}

.overlay-hint {
  font-size: 0.9rem;
  color: var(--text-muted);
}

.play-again-btn {
  margin-top: 0.5rem;
  animation: popIn 0.5s cubic-bezier(0.34, 1.56, 0.64, 1) 0.2s both;
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
  transition: transform 0.2s ease;
}

.player-score-row.me {
  font-weight: 700;
}

.player-score-row.dead {
  opacity: 0.55;
}

.player-score-row.hp-hit {
  animation: hpShake 0.35s ease;
}

.color-dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  flex-shrink: 0;
  box-shadow: 0 0 6px currentColor;
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
  box-shadow: 0 0 4px rgba(34, 197, 94, 0.5);
  transition: background 0.25s ease, transform 0.25s ease;
}

.hp-pip.spent {
  background: #334155;
  box-shadow: none;
  transform: scaleY(0.6);
}

.hp-pip.low {
  background: #ef4444;
  animation: lowHpPulse 0.8s ease-in-out infinite;
}

.effect-badge {
  font-size: 0.85rem;
}

.shield-pulse {
  animation: shieldPulse 1.2s ease-in-out infinite;
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

@keyframes overlayIn {
  from { opacity: 0; }
  to { opacity: 1; }
}

@keyframes countPulse {
  0%, 100% { transform: scale(1); }
  50% { transform: scale(1.08); }
}

@keyframes popIn {
  from { opacity: 0; transform: scale(0.7); }
  to { opacity: 1; transform: scale(1); }
}

@keyframes slideIn {
  from { opacity: 0; transform: translateY(-12px); }
  to { opacity: 1; transform: translateY(0); }
}

@keyframes winnerGlow {
  0%, 100% { filter: drop-shadow(0 0 6px rgba(251, 191, 36, 0.4)); }
  50% { filter: drop-shadow(0 0 14px rgba(91, 156, 255, 0.6)); }
}

@keyframes chargePulse {
  from { box-shadow: 0 0 8px rgba(251, 191, 36, 0.5); }
  to { box-shadow: 0 0 18px rgba(239, 68, 68, 0.8); }
}

@keyframes hpShake {
  0%, 100% { transform: translateX(0); }
  25% { transform: translateX(-4px); }
  75% { transform: translateX(4px); }
}

@keyframes lowHpPulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.45; }
}

@keyframes shieldPulse {
  0%, 100% { transform: scale(1); }
  50% { transform: scale(1.15); }
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
