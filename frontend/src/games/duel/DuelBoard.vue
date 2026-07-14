<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import type { Room, DuelGameState } from '@/types'
import { DuelRenderer, POWERUP_COLORS, POWERUP_ICONS, POWERUP_LABELS } from './duelRenderer'
import {
  POWERUP_HINTS,
  POWERUP_TIER_LABELS,
  canUseStoredPowerup,
  formatPowerupSeconds,
  isInstantPowerup,
  listActivePowerupEffects,
  powerupChannelTicks,
  powerupTier,
  powerupUseHint,
} from './powerupMeta'
import {
  isSoundMuted,
  playArenaShrinkSound,
  playHazardTickSound,
  playHitSound,
  playPowerupActivateSound,
  playPowerupCollectSound,
  playRoundWinSound,
  playShieldBlockSound,
  playShootSound,
  setSoundMuted,
  unlockAudio,
} from './sounds'
import { loadKeybinds, matchesBinding } from './keybinds'
import { chargeTierForTicks } from './chargeTiers'
import { loadMilestones, recordMatchMilestones } from './stats'
import { resolveTheme } from './themes'

const props = defineProps<{
  gameState: DuelGameState
  room: Room
  playerId: string
}>()

const emit = defineEmits<{
  action: [data: Record<string, unknown>]
  lobby: []
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
const powerupsEnabled = computed(() => props.gameState.powerups_enabled ?? props.gameState.match_format !== 'quick_duel')
const chargeMaxTicks = computed(() => props.gameState.charge_max_ticks ?? 15)
const tickMs = computed(() => props.gameState.tick_ms || 75)
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
const channelTicksRequired = computed(() => powerupChannelTicks(storedPowerup.value))
const canUsePowerup = computed(() =>
  canUseStoredPowerup(
    storedPowerup.value,
    myFighter.value?.hp ?? 0,
    myFighter.value?.max_hp ?? 3,
  ),
)
const powerupReady = computed(
  () =>
    activatingPowerup.value &&
    (powerupActivationTicks.value >= channelTicksRequired.value ||
      (myFighter.value?.powerup_activation_ticks ?? 0) >= channelTicksRequired.value),
)
const localChargeInterval = ref<ReturnType<typeof setInterval> | null>(null)
const localPowerupInterval = ref<ReturnType<typeof setInterval> | null>(null)
const hpPulseId = ref<string | null>(null)
const powerupNotice = ref<{ text: string; tone: 'info' | 'success' | 'warn' } | null>(null)
let powerupNoticeTimer: ReturnType<typeof setTimeout> | null = null
let autoReleaseTimer: ReturnType<typeof setTimeout> | null = null
const lastSeenPowerupKey = ref('')
const lastStoredPowerup = ref<string | null>(null)
const lastActionStamp = ref('')
const lastHitSoundStamp = ref('')
const lastActionSoundStamp = ref('')
const soundMuted = ref(isSoundMuted())
const playableBoundsInitialized = ref(false)
const showTouchControls = ref(false)
const coachHint = ref<string | null>(null)
const lastPlayableMin = ref(0)
const lastPlayableMax = ref(999)
const lastRoundPhase = ref('')
const keybinds = ref(loadKeybinds())
const predictedMoveDir = ref<'up' | 'down' | null>(null)
const milestones = ref(loadMilestones())
const matchPowerupActions = ref<string[]>([])
const lastHazardSoundTick = ref(-1)
const isDraftPhase = computed(() => props.gameState.phase === 'powerup_draft')
const myBan = computed(() => props.gameState.powerup_bans?.[props.playerId] ?? null)
const eventFeed = computed(() => (props.gameState.event_log ?? []).slice(-8).reverse())
const roundRecapRows = computed(() =>
  props.gameState.players.map((p) => ({
    nickname: p.nickname,
    stats: props.gameState.round_stats?.[p.id],
  })),
)
const chargeTier = computed(() =>
  chargeTierForTicks(chargeTicks.value, props.gameState.mutator === 'sniper'),
)
const draftPowerupOptions = computed(() => Object.keys(POWERUP_LABELS))
const draftBanSummary = computed(() => {
  const bans = props.gameState.powerup_bans ?? {}
  return Object.entries(bans).map(([playerId, ptype]) => {
    const player = props.gameState.players.find((p) => p.id === playerId)
    return {
      nickname: player?.nickname ?? 'Player',
      label: POWERUP_LABELS[ptype] ?? ptype,
    }
  })
})
const canvasTheme = computed(() => resolveTheme(props.gameState.arena_theme))
const incomingBulletCount = computed(() => {
  if (!myFighter.value?.alive) return 0
  const myX = myFighter.value.x
  return props.gameState.bullets.filter((bullet) => {
    if (bullet.owner_id === props.playerId) return false
    return (
      (myFighter.value!.side === 'left' && bullet.vx < 0 && bullet.x >= myX) ||
      (myFighter.value!.side === 'right' && bullet.vx > 0 && bullet.x <= myX)
    )
  }).length
})
const playableHeight = computed(
  () => props.gameState.playable_y_max - props.gameState.playable_y_min + 1,
)
const shrinkTicksUntil = computed(() => {
  if (!props.gameState.shrinking_arena || props.gameState.phase !== 'playing') return null
  const start = props.gameState.shrink_start_tick ?? 240
  const interval = props.gameState.shrink_interval_ticks ?? 80
  if (props.gameState.tick < start) return start - props.gameState.tick
  const elapsed = props.gameState.tick - start
  const nextShrink = start + (Math.floor(elapsed / interval) + 1) * interval
  return Math.max(0, nextShrink - props.gameState.tick)
})
const shrinkWarningActive = computed(() => {
  const until = shrinkTicksUntil.value
  return until !== null && until <= Math.ceil(2400 / tickMs.value)
})
const showCoachHint = computed(
  () => coachHint.value && (props.gameState.phase === 'playing' || props.gameState.phase === 'countdown'),
)

function toggleSound() {
  const next = !soundMuted.value
  setSoundMuted(next)
  soundMuted.value = next
}

function detectTouchControls() {
  showTouchControls.value =
    window.matchMedia('(pointer: coarse)').matches || window.innerWidth < 900
}

function updateCoachHint() {
  if (!props.gameState.tutorial_mode) {
    coachHint.value = null
    return
  }
  if (props.gameState.phase === 'countdown' && props.gameState.round === 1) {
    if (chargeEnabled.value && powerupsEnabled.value) {
      coachHint.value = 'Hold Space to charge shots · Hold E to activate power-ups'
    } else if (chargeEnabled.value) {
      coachHint.value = 'Hold Space to charge a spread shot, release to fire'
    } else {
      coachHint.value = 'W/S or the on-screen arrows move your ship · Space fires'
    }
    return
  }
  if (props.gameState.phase !== 'playing' || props.gameState.round > 1) {
    coachHint.value = null
    return
  }
  if (props.gameState.tick < 120) {
    if (props.gameState.shrinking_arena) {
      coachHint.value = 'Use cover, then watch the red hazard zones — they deal damage'
    } else {
      coachHint.value = 'Center-row hits deal bonus damage'
    }
    return
  }
  coachHint.value = null
}

function playGameSounds() {
  if (soundMuted.value) return

  const hit = props.gameState.last_hit
  if (hit?.player_id && hit.damage !== undefined) {
    const stamp = `${hit.player_id}-${props.gameState.tick}-${hit.damage}-${hit.blocked ? 'b' : 'h'}`
    if (stamp !== lastHitSoundStamp.value) {
      lastHitSoundStamp.value = stamp
      if (hit.blocked) playShieldBlockSound()
      else playHitSound(Boolean(hit.crit))
    }
  }

  const action = props.gameState.last_action
  if (action) {
    const actionStamp = JSON.stringify(action)
    if (actionStamp !== lastActionSoundStamp.value) {
      lastActionSoundStamp.value = actionStamp
      const type = action.type as string
      const pid = action.player_id as string | undefined
      if (pid === props.playerId) {
        if (type === 'shoot' || type === 'release_charge') {
          playShootSound(type === 'release_charge' && Number(action.charge_ticks ?? 0) >= 8)
        } else if (type === 'powerup_collected') {
          playPowerupCollectSound()
        } else if (type === 'powerup_activated') {
          const ptype = action.powerup_type as string
          matchPowerupActions.value.push(ptype)
          playPowerupActivateSound(powerupTier(ptype))
        }
      }
    }
  }

  if (
    myFighter.value?.alive &&
    props.gameState.shrinking_arena &&
    props.gameState.phase === 'playing'
  ) {
    const inHazard =
      myFighter.value.y < props.gameState.playable_y_min ||
      myFighter.value.y + props.gameState.fighter_height - 1 > props.gameState.playable_y_max
    const hazardInterval = props.gameState.hazard_damage_interval_ticks ?? 20
    if (
      inHazard &&
      props.gameState.tick % hazardInterval === 0 &&
      props.gameState.tick !== lastHazardSoundTick.value
    ) {
      lastHazardSoundTick.value = props.gameState.tick
      playHazardTickSound()
    }
  }

  if (playableBoundsInitialized.value) {
    if (
      props.gameState.shrinking_arena &&
      (props.gameState.playable_y_min > lastPlayableMin.value ||
        props.gameState.playable_y_max < lastPlayableMax.value)
    ) {
      playArenaShrinkSound()
    }
  } else {
    playableBoundsInitialized.value = true
  }
  lastPlayableMin.value = props.gameState.playable_y_min
  lastPlayableMax.value = props.gameState.playable_y_max

  if (props.gameState.phase === 'round_over' && lastRoundPhase.value === 'playing') {
    playRoundWinSound()
  }
  lastRoundPhase.value = props.gameState.phase
}

const storedPowerupHint = computed(() => powerupUseHint(storedPowerup.value, tickMs.value))
const storedPowerupDescription = computed(() =>
  storedPowerup.value ? POWERUP_HINTS[storedPowerup.value] ?? '' : '',
)
const isInstantStored = computed(() => isInstantPowerup(storedPowerup.value))
const storedPowerupTier = computed(() => powerupTier(storedPowerup.value))
const arenaPowerup = computed(() => props.gameState.powerup)
const arenaPowerupTier = computed(() => powerupTier(arenaPowerup.value?.type))
const activeBuffs = computed(() =>
  listActivePowerupEffects(
    myFighter.value?.effects as Record<string, unknown> | undefined,
    props.gameState.tick,
    tickMs.value,
    props.gameState.effect_duration_ticks ?? 80,
  ),
)

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

function clearHeldInputs() {
  if (heldMove.value) {
    sendMove('stop')
    heldMove.value = null
  }
  if (charging.value) releaseCharge()
  if (activatingPowerup.value) releasePowerupActivation()
}

function onVisibilityChange() {
  if (document.visibilityState === 'hidden') {
    clearHeldInputs()
  }
}

function startNewGame(sameSeed = false) {
  const payload: Record<string, unknown> = { type: 'start_game' }
  const seed =
    props.room.settings?.layout_seed ??
    (props.gameState as { layout_seed?: number }).layout_seed
  if (sameSeed && seed != null) {
    payload.layout_seed = seed
  }
  emit('action', payload)
}

function returnToLobby() {
  emit('lobby')
}

function banPowerup(type: string) {
  emit('action', { type: 'ban_powerup', powerup_type: type })
}

function sendMove(direction: 'up' | 'down' | 'stop') {
  predictedMoveDir.value = direction === 'stop' ? null : direction
  emit('action', { type: 'set_move', direction })
}

function showPowerupNotice(text: string, tone: 'info' | 'success' | 'warn' = 'info') {
  powerupNotice.value = { text, tone }
  if (powerupNoticeTimer) clearTimeout(powerupNoticeTimer)
  powerupNoticeTimer = setTimeout(() => {
    powerupNotice.value = null
    powerupNoticeTimer = null
  }, 2800)
}

function useStoredPowerup() {
  if (!canControl.value || !powerupsEnabled.value || !storedPowerup.value || !canUsePowerup.value) {
    if (storedPowerup.value === 'heal' && !canUsePowerup.value) {
      showPowerupNotice('Already at full health', 'warn')
    }
    return
  }
  if (isInstantStored.value) {
    emit('action', { type: 'powerup_activate' })
    return
  }
  if (!activatingPowerup.value) startPowerupActivation()
}

function onPowerupButtonDown(e: MouseEvent | TouchEvent) {
  e.preventDefault()
  if (!canControl.value || !powerupsEnabled.value || !storedPowerup.value) return
  if (isInstantStored.value) {
    useStoredPowerup()
    return
  }
  if (!canUsePowerup.value) return
  if (!activatingPowerup.value) startPowerupActivation()
}

function onPowerupButtonUp(e: MouseEvent | TouchEvent) {
  e.preventDefault()
  if (activatingPowerup.value && !isInstantStored.value) {
    releasePowerupActivation()
  }
}

function startPowerupActivation() {
  if (!canControl.value || !powerupsEnabled.value || !storedPowerup.value || !canUsePowerup.value) return
  activatingPowerup.value = true
  powerupActivationTicks.value = 0
  emit('action', { type: 'powerup_hold_start' })
  if (localPowerupInterval.value) clearInterval(localPowerupInterval.value)
  const required = channelTicksRequired.value
  localPowerupInterval.value = setInterval(() => {
    if (activatingPowerup.value) {
      powerupActivationTicks.value = Math.min(required, powerupActivationTicks.value + 1)
    }
  }, tickMs.value)
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
    powerup_activation_ticks: Math.max(
      powerupActivationTicks.value,
      myFighter.value?.powerup_activation_ticks ?? 0,
    ),
  })
  powerupActivationTicks.value = 0
}

watch(
  () => myFighter.value?.powerup_activation_ticks,
  (serverTicks) => {
    if (!activatingPowerup.value || typeof serverTicks !== 'number') return
    powerupActivationTicks.value = Math.max(
      powerupActivationTicks.value,
      Math.min(channelTicksRequired.value, serverTicks),
    )
  },
)

watch(
  () => myFighter.value?.stored_powerup,
  (stored, prev) => {
    if (stored && stored !== prev) {
      const label = POWERUP_LABELS[stored] ?? stored
      showPowerupNotice(`${label} collected — ${powerupUseHint(stored, tickMs.value)}`, 'success')
    }
    if (!stored) {
      activatingPowerup.value = false
      powerupActivationTicks.value = 0
      if (localPowerupInterval.value) {
        clearInterval(localPowerupInterval.value)
        localPowerupInterval.value = null
      }
    }
    lastStoredPowerup.value = stored ?? null
  },
)

watch(
  () => arenaPowerup.value,
  (orb) => {
    if (!orb || !powerupsEnabled.value) return
    const key = `${orb.x}:${orb.y}:${orb.type}:${props.gameState.tick}`
    if (key === lastSeenPowerupKey.value) return
    lastSeenPowerupKey.value = key
    const label = POWERUP_LABELS[orb.type] ?? orb.type
    showPowerupNotice(`${label} spawned — shoot or touch to collect`, 'info')
  },
)

function onTouchMoveUp(e: TouchEvent | MouseEvent) {
  e.preventDefault()
  unlockAudio()
  if (heldMove.value !== 'up') {
    heldMove.value = 'up'
    sendMove('up')
  }
}

function onTouchMoveDown(e: TouchEvent | MouseEvent) {
  e.preventDefault()
  unlockAudio()
  if (heldMove.value !== 'down') {
    heldMove.value = 'down'
    sendMove('down')
  }
}

function onTouchMoveStop(e: TouchEvent | MouseEvent) {
  e.preventDefault()
  if (heldMove.value) {
    heldMove.value = null
    sendMove('stop')
  }
}

function onTouchFireDown(e: TouchEvent | MouseEvent) {
  e.preventDefault()
  unlockAudio()
  if (!canControl.value) return
  if (chargeEnabled.value) {
    if (!charging.value) startCharge()
  } else {
    quickShoot()
  }
}

function onTouchFireUp(e: TouchEvent | MouseEvent) {
  e.preventDefault()
  if (charging.value) releaseCharge()
}

watch(
  () => [
    props.gameState.tick,
    props.gameState.last_hit,
    props.gameState.last_action,
    props.gameState.phase,
    props.gameState.playable_y_min,
    props.gameState.playable_y_max,
  ],
  () => {
    playGameSounds()
    updateCoachHint()
  },
)

watch(
  () => props.gameState.phase,
  () => updateCoachHint(),
  { immediate: true },
)

watch(
  () => props.gameState.last_action,
  (action) => {
    if (!action) return
    const stamp = JSON.stringify(action)
    if (stamp === lastActionStamp.value) return
    lastActionStamp.value = stamp
    const type = action.type as string
    const pid = action.player_id as string | undefined
    if (pid !== props.playerId) return
    if (type === 'powerup_activated') {
      const ptype = action.powerup_type as string
      showPowerupNotice(`${POWERUP_LABELS[ptype] ?? ptype} activated!`, 'success')
    } else if (type === 'powerup_blocked' && action.reason === 'max_hp') {
      showPowerupNotice('Heal saved — you are already at full health', 'warn')
    } else if (type === 'powerup_hold_release' && action.activated === false) {
      showPowerupNotice(
        `Hold E a bit longer (${formatPowerupSeconds(channelTicksRequired.value, tickMs.value)})`,
        'warn',
      )
    }
  },
)

watch(powerupReady, (ready) => {
  if (autoReleaseTimer) {
    clearTimeout(autoReleaseTimer)
    autoReleaseTimer = null
  }
  if (ready && activatingPowerup.value) {
    autoReleaseTimer = setTimeout(() => {
      if (activatingPowerup.value && powerupReady.value) {
        releasePowerupActivation()
      }
      autoReleaseTimer = null
    }, 180)
  }
})

watch(
  () => props.gameState.phase,
  (phase, prev) => {
    if (phase === 'finished' && prev !== 'finished') {
      milestones.value = recordMatchMilestones(
        props.playerId,
        props.gameState.match_stats,
        matchPowerupActions.value,
      )
      matchPowerupActions.value = []
    }
    if (phase === 'countdown' && prev === 'finished') {
      matchPowerupActions.value = []
    }
  },
)

watch(
  () => myFighter.value?.y,
  () => {
    predictedMoveDir.value = null
  },
)

function startCharge() {
  if (!canControl.value || !chargeEnabled.value) return
  charging.value = true
  chargeTicks.value = 0
  emit('action', { type: 'charge_start' })
  if (localChargeInterval.value) clearInterval(localChargeInterval.value)
  localChargeInterval.value = setInterval(() => {
    if (charging.value) {
      chargeTicks.value = Math.min(chargeMaxTicks.value, chargeTicks.value + 1)
    }
  }, tickMs.value)
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

  if (matchesBinding(e.code, keybinds.value.moveUp)) {
    e.preventDefault()
    if (heldMove.value !== 'up') {
      heldMove.value = 'up'
      sendMove('up')
    }
    return
  }

  if (matchesBinding(e.code, keybinds.value.moveDown)) {
    e.preventDefault()
    if (heldMove.value !== 'down') {
      heldMove.value = 'down'
      sendMove('down')
    }
    return
  }

  if (matchesBinding(e.code, keybinds.value.fire)) {
    e.preventDefault()
    if (chargeEnabled.value) {
      if (!charging.value) startCharge()
    } else {
      quickShoot()
    }
    return
  }

  if (
    matchesBinding(e.code, keybinds.value.powerup) &&
    storedPowerup.value &&
    powerupsEnabled.value
  ) {
    e.preventDefault()
    if (isInstantStored.value) {
      useStoredPowerup()
    } else if (!activatingPowerup.value && canUsePowerup.value) {
      startPowerupActivation()
    }
    return
  }
}

function onKeyUp(e: KeyboardEvent) {
  if (!canControl.value) return

  if (matchesBinding(e.code, keybinds.value.moveUp) && heldMove.value === 'up') {
    heldMove.value = null
    sendMove('stop')
    return
  }

  if (matchesBinding(e.code, keybinds.value.moveDown) && heldMove.value === 'down') {
    heldMove.value = null
    sendMove('stop')
    return
  }

  if (matchesBinding(e.code, keybinds.value.fire)) {
    e.preventDefault()
    if (charging.value) releaseCharge()
    return
  }

  if (matchesBinding(e.code, keybinds.value.powerup) && activatingPowerup.value && !isInstantStored.value) {
    e.preventDefault()
    releasePowerupActivation()
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

  renderer.draw(ctx, renderStateForFrame(), props.playerId, displayW, displayH, now, dangerRows.value)
}

function renderStateForFrame(): DuelGameState {
  const base = props.gameState
  const fighter = base.fighters[props.playerId]
  if (!fighter || !predictedMoveDir.value || !canControl.value) return base
  const minY = base.playable_y_min
  const maxY = Math.min(
    base.grid_height - base.fighter_height,
    base.playable_y_max - base.fighter_height + 1,
  )
  const delta = predictedMoveDir.value === 'up' ? -1 : 1
  const predictedY = Math.max(minY, Math.min(maxY, fighter.y + delta))
  if (predictedY === fighter.y) return base
  return {
    ...base,
    fighters: {
      ...base.fighters,
      [props.playerId]: { ...fighter, y: predictedY, display_y: predictedY },
    },
  }
}

let resizeObserver: ResizeObserver | null = null
let animFrame = 0

function animationLoop() {
  draw(Date.now())
  animFrame = requestAnimationFrame(animationLoop)
}

onMounted(() => {
  detectTouchControls()
  lastPlayableMin.value = props.gameState.playable_y_min
  lastPlayableMax.value = props.gameState.playable_y_max
  lastRoundPhase.value = props.gameState.phase
  window.addEventListener('resize', detectTouchControls)
  window.addEventListener('keydown', onKeyDown)
  window.addEventListener('keyup', onKeyUp)
  window.addEventListener('blur', clearHeldInputs)
  document.addEventListener('visibilitychange', onVisibilityChange)
  if (canvasWrapRef.value) {
    resizeObserver = new ResizeObserver(() => draw(Date.now()))
    resizeObserver.observe(canvasWrapRef.value)
  }
  animFrame = requestAnimationFrame(animationLoop)
})

onUnmounted(() => {
  window.removeEventListener('resize', detectTouchControls)
  window.removeEventListener('keydown', onKeyDown)
  window.removeEventListener('keyup', onKeyUp)
  window.removeEventListener('blur', clearHeldInputs)
  document.removeEventListener('visibilitychange', onVisibilityChange)
  resizeObserver?.disconnect()
  cancelAnimationFrame(animFrame)
  if (localChargeInterval.value) clearInterval(localChargeInterval.value)
  if (localPowerupInterval.value) clearInterval(localPowerupInterval.value)
  if (powerupNoticeTimer) clearTimeout(powerupNoticeTimer)
  if (autoReleaseTimer) clearTimeout(autoReleaseTimer)
  renderer.reset()
})
</script>

<template>
  <div class="duel-board">
    <div class="match-bar">
      <span class="match-format">Round {{ gameState.round }} · Best of {{ gameState.best_of }}</span>
      <span v-if="shrinkWarningActive" class="shrink-warning">
        Arena shrinks in {{ formatPowerupSeconds(shrinkTicksUntil ?? 0, tickMs) }}
      </span>
      <span class="mutator-tag">{{ MUTATOR_LABELS[gameState.mutator] ?? gameState.mutator }}</span>
      <button
        type="button"
        class="sound-toggle"
        :aria-label="soundMuted ? 'Unmute sound' : 'Mute sound'"
        @click="toggleSound"
      >
        {{ soundMuted ? '🔇' : '🔊' }}
      </button>
    </div>

    <div ref="canvasWrapRef" class="canvas-wrap" :style="{ background: canvasTheme.canvasCss }">
      <canvas ref="canvasRef" class="game-canvas" />

      <Transition name="powerup-notice">
        <div v-if="showCoachHint" class="coach-hint">
          {{ coachHint }}
        </div>
      </Transition>

      <Transition name="powerup-notice">
        <div
          v-if="powerupNotice && gameState.phase === 'playing'"
          class="powerup-notice"
          :class="powerupNotice.tone"
        >
          {{ powerupNotice.text }}
        </div>
      </Transition>

      <div
        v-if="canControl && storedPowerup && powerupsEnabled"
        class="powerup-slot"
        :class="[`tier-${storedPowerupTier}`, { instant: isInstantStored, activating: activatingPowerup }]"
        :style="{
          borderColor: POWERUP_COLORS[storedPowerup] ?? '#a855f7',
          boxShadow: `0 8px 28px rgba(0,0,0,0.35), 0 0 24px ${POWERUP_COLORS[storedPowerup] ?? '#a855f7'}33`,
        }"
      >
        <span class="powerup-slot-icon" :style="{ color: POWERUP_COLORS[storedPowerup] }">
          {{ POWERUP_ICONS[storedPowerup] ?? '★' }}
        </span>
        <div class="powerup-slot-copy">
          <div class="powerup-slot-title">
            <strong>{{ POWERUP_LABELS[storedPowerup] ?? storedPowerup }}</strong>
            <span class="powerup-tier">{{ POWERUP_TIER_LABELS[storedPowerupTier] }}</span>
          </div>
          <span>{{ storedPowerupDescription }}</span>
          <span class="powerup-slot-hint">{{ storedPowerupHint }}</span>
        </div>
        <button
          type="button"
          class="powerup-use-btn"
          :class="{ disabled: !canUsePowerup }"
          :disabled="!canUsePowerup"
          @mousedown="onPowerupButtonDown"
          @mouseup="onPowerupButtonUp"
          @mouseleave="onPowerupButtonUp"
          @touchstart.prevent="onPowerupButtonDown"
          @touchend.prevent="onPowerupButtonUp"
          @touchcancel.prevent="onPowerupButtonUp"
        >
          {{
            !canUsePowerup && storedPowerup === 'heal'
              ? 'Full HP'
              : isInstantStored
                ? 'Use [E]'
                : 'Hold [E]'
          }}
        </button>
      </div>

      <div v-if="canControl && activeBuffs.length" class="active-buffs">
        <div
          v-for="buff in activeBuffs"
          :key="buff.id"
          class="active-buff"
          :style="{ '--buff-color': POWERUP_COLORS[buff.id] ?? '#a855f7' }"
        >
          <span class="active-buff-icon">{{ POWERUP_ICONS[buff.id] ?? '★' }}</span>
          <span class="active-buff-label">{{ buff.label }}</span>
          <span class="active-buff-time">{{ formatPowerupSeconds(buff.remainingTicks, tickMs) }}</span>
          <span class="active-buff-ring">
            <svg viewBox="0 0 36 36">
              <circle cx="18" cy="18" r="15" class="ring-bg" />
              <circle
                cx="18"
                cy="18"
                r="15"
                class="ring-fill"
                :style="{ strokeDashoffset: `${94 * (1 - buff.progress)}` }"
              />
            </svg>
          </span>
        </div>
      </div>

      <div v-if="canControl && powerupsEnabled && arenaPowerup && !storedPowerup" class="powerup-callout">
        <span class="callout-dot" :style="{ background: POWERUP_COLORS[arenaPowerup.type] }" />
        <span class="callout-icon">{{ POWERUP_ICONS[arenaPowerup.type] ?? '★' }}</span>
        <span class="callout-copy">
          <strong>{{ POWERUP_LABELS[arenaPowerup.type] ?? arenaPowerup.type }}</strong>
          <span class="callout-tier">{{ POWERUP_TIER_LABELS[arenaPowerupTier] }} · in arena</span>
        </span>
      </div>

      <div v-if="charging && canControl" class="charge-bar">
        <div
          class="charge-fill"
          :class="{ 'charge-full': chargeTicks >= 11 }"
          :style="{ width: `${(chargeTicks / chargeMaxTicks) * 100}%` }"
        />
        <span class="charge-label">
          {{ chargeTicks >= 11 ? 'MAX POWER' : `${chargeTier.label} · ${chargeTier.hint}` }}
        </span>
      </div>

      <div v-if="activatingPowerup && canControl && storedPowerup" class="charge-bar powerup-bar">
        <div
          class="charge-fill powerup-fill"
          :class="{ 'charge-full': powerupReady, 'powerup-charging': !powerupReady }"
          :style="{
            width: `${(powerupActivationTicks / channelTicksRequired) * 100}%`,
            background: `linear-gradient(90deg, ${POWERUP_COLORS[storedPowerup] ?? '#a855f7'}, #fff)`,
          }"
        />
        <span class="charge-label powerup-label">
          {{
            powerupReady
              ? 'RELEASE!'
              : `Activating… ${formatPowerupSeconds(
                  Math.max(0, channelTicksRequired - powerupActivationTicks),
                  tickMs,
                )} left`
          }}
        </span>
      </div>

      <div v-if="eventFeed.length" class="event-feed" aria-live="polite">
        <div v-for="(entry, idx) in eventFeed" :key="`${entry.tick}-${idx}`" :class="['feed-line', entry.kind]">
          {{ entry.message }}
        </div>
      </div>

      <div v-if="isDraftPhase && !myBan" class="overlay draft">
        <span class="overlay-label">Ban a power-up</span>
        <div class="draft-grid">
          <button
            v-for="ptype in draftPowerupOptions"
            :key="ptype"
            type="button"
            class="btn-secondary draft-btn"
            @click="banPowerup(ptype)"
          >
            {{ POWERUP_LABELS[ptype] ?? ptype }}
          </button>
        </div>
      </div>

      <div v-else-if="isDraftPhase" class="overlay draft">
        <span class="overlay-hint">Waiting for opponent to ban…</span>
        <ul v-if="draftBanSummary.length" class="draft-bans">
          <li v-for="ban in draftBanSummary" :key="ban.nickname">
            {{ ban.nickname }} banned {{ ban.label }}
          </li>
        </ul>
      </div>

      <div v-if="gameState.phase === 'countdown'" class="overlay countdown">
        <span class="overlay-value pulse">{{ countdownRemaining ?? '…' }}</span>
        <span class="overlay-label">Get ready!</span>
      </div>

      <div v-else-if="isRoundOver" class="overlay round-over">
        <span class="overlay-label slide-in">Round {{ gameState.round - 1 }} over</span>
        <span v-if="roundWinnerName" class="overlay-value pop-in">{{ roundWinnerName }} wins the round!</span>
        <span v-else class="overlay-value pop-in">Draw — rematch!</span>
        <div v-if="roundRecapRows.length" class="round-recap">
          <div v-for="row in roundRecapRows" :key="row.nickname" class="recap-row">
            <strong>{{ row.nickname }}</strong>
            <span v-if="row.stats">
              {{ row.stats.damage_dealt }} dealt · {{ row.stats.damage_taken }} taken ·
              {{ row.stats.powerups_used }} power-ups · {{ row.stats.hazard_ticks }} hazard ticks
            </span>
          </div>
        </div>
        <span class="overlay-hint">Next round in {{ countdownRemaining ?? '…' }}</span>
      </div>

      <div v-else-if="isFinished" class="overlay finished">
        <span class="overlay-label slide-in">Match over</span>
        <span class="overlay-value winner-glow">{{ winnerName }} wins!</span>
        <div class="milestones">
          <p>Career: {{ milestones.matchesPlayed }} matches · {{ milestones.perfectRounds }} perfect rounds · {{ milestones.critsLanded }} crits</p>
        </div>
        <div v-if="isHost" class="finished-actions">
          <button type="button" class="btn-primary play-again-btn" @click="startNewGame(false)">
            Rematch
          </button>
          <button type="button" class="btn-secondary play-again-btn" @click="startNewGame(true)">
            Same seed rematch
          </button>
          <button type="button" class="btn-secondary play-again-btn" @click="returnToLobby">
            Back to lobby
          </button>
        </div>
        <p v-else class="overlay-hint">Waiting for host…</p>
      </div>

      <div v-else-if="!isAlive && gameState.phase === 'playing'" class="overlay eliminated">
        <span class="overlay-label">You were eliminated!</span>
        <div class="spectator-stats spectator-dual">
          <p v-for="row in playerRows" :key="row.id">
            <strong>{{ row.nickname }}</strong>
            · {{ row.fighter?.hp ?? 0 }}/{{ row.fighter?.max_hp ?? 3 }} HP
            · {{ row.roundWins }} round wins
          </p>
          <p>
            Arena {{ playableHeight }} rows · {{ gameState.bullets.length }} bullets
            <span v-if="incomingBulletCount"> · {{ incomingBulletCount }} incoming</span>
          </p>
        </div>
        <span class="overlay-hint">Watch the round continue…</span>
      </div>

      <div
        v-if="showTouchControls && canControl"
        class="touch-controls"
        aria-label="Touch controls"
      >
        <div class="touch-move">
          <button
            type="button"
            class="touch-btn"
            aria-label="Move up"
            @touchstart.prevent="onTouchMoveUp"
            @touchend.prevent="onTouchMoveStop"
            @touchcancel.prevent="onTouchMoveStop"
            @mousedown.prevent="onTouchMoveUp"
            @mouseup.prevent="onTouchMoveStop"
            @mouseleave.prevent="onTouchMoveStop"
          >
            ▲
          </button>
          <button
            type="button"
            class="touch-btn"
            aria-label="Move down"
            @touchstart.prevent="onTouchMoveDown"
            @touchend.prevent="onTouchMoveStop"
            @touchcancel.prevent="onTouchMoveStop"
            @mousedown.prevent="onTouchMoveDown"
            @mouseup.prevent="onTouchMoveStop"
            @mouseleave.prevent="onTouchMoveStop"
          >
            ▼
          </button>
        </div>
        <button
          type="button"
          class="touch-btn touch-fire"
          :aria-label="chargeEnabled ? 'Hold to charge and fire' : 'Fire'"
          @touchstart.prevent="onTouchFireDown"
          @touchend.prevent="onTouchFireUp"
          @touchcancel.prevent="onTouchFireUp"
          @mousedown.prevent="onTouchFireDown"
          @mouseup.prevent="onTouchFireUp"
          @mouseleave.prevent="onTouchFireUp"
        >
          {{ chargeEnabled ? '⚡' : '●' }}
        </button>
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
          <span
            class="ship-avatar"
            :class="{ left: row.fighter?.side === 'left', right: row.fighter?.side === 'right' }"
            :style="{ '--ship-color': row.fighter?.color ?? '#666' }"
            aria-hidden="true"
          />
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
          <span v-if="row.fighter?.effects?.machine_gun_active" class="effect-badge" title="Machine Gun">🔫</span>
          <span v-if="row.fighter?.effects?.wide_shot_active" class="effect-badge" title="Wide Shot">▣</span>
          <span v-if="row.fighter?.effects?.pierce_active" class="effect-badge" title="Pierce">➤</span>
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
          <strong>Controls:</strong> W/S move · Space charge & fire ·
          {{ isInstantStored ? 'E to use power-up' : `Hold E ~${formatPowerupSeconds(channelTicksRequired, tickMs)} to activate` }}
        </p>
        <p v-else-if="canControl && chargeEnabled && powerupsEnabled && arenaPowerup">
          <strong>Controls:</strong> W/S move · Space charge & fire · Collect the {{ POWERUP_LABELS[arenaPowerup.type] ?? 'power-up' }} (shoot or touch it)
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
  flex-wrap: wrap;
}

.shrink-warning {
  padding: 0.15rem 0.55rem;
  border-radius: 999px;
  background: rgba(239, 68, 68, 0.18);
  border: 1px solid rgba(239, 68, 68, 0.35);
  color: #fecaca;
  font-size: 0.75rem;
  font-weight: 600;
  animation: shrinkPulse 1.2s ease-in-out infinite;
}

@keyframes shrinkPulse {
  0%,
  100% {
    opacity: 0.85;
  }
  50% {
    opacity: 1;
  }
}

.sound-toggle {
  margin-left: auto;
  border: 1px solid rgba(255, 255, 255, 0.12);
  background: rgba(15, 23, 42, 0.65);
  border-radius: 8px;
  padding: 0.2rem 0.45rem;
  cursor: pointer;
  font-size: 0.95rem;
}

.coach-hint {
  position: absolute;
  bottom: 0.85rem;
  left: 50%;
  transform: translateX(-50%);
  z-index: 4;
  max-width: min(92%, 460px);
  padding: 0.5rem 0.9rem;
  border-radius: 10px;
  font-size: 0.78rem;
  font-weight: 600;
  text-align: center;
  color: #dbeafe;
  background: rgba(15, 23, 42, 0.88);
  border: 1px solid rgba(91, 156, 255, 0.35);
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.35);
}

.spectator-stats {
  margin: 0.75rem 0;
  font-size: 0.85rem;
  line-height: 1.5;
  color: #cbd5e1;
}

.event-feed {
  position: absolute;
  left: 0.65rem;
  bottom: 0.65rem;
  z-index: 3;
  max-width: min(48%, 320px);
  display: flex;
  flex-direction: column;
  gap: 0.2rem;
  pointer-events: none;
}

.feed-line {
  font-size: 0.72rem;
  padding: 0.2rem 0.45rem;
  border-radius: 6px;
  background: rgba(15, 23, 42, 0.72);
  color: #cbd5e1;
}

.feed-line.success { color: #86efac; }
.feed-line.warn { color: #fca5a5; }

.draft-grid {
  display: flex;
  flex-wrap: wrap;
  gap: 0.4rem;
  justify-content: center;
  max-width: 520px;
}

.round-recap {
  margin: 0.75rem 0;
  text-align: left;
  font-size: 0.82rem;
}

.finished-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
  justify-content: center;
}

.milestones {
  font-size: 0.85rem;
  opacity: 0.85;
  margin: 0.5rem 0;
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

.touch-move {
  display: flex;
  flex-direction: column;
  gap: 0.45rem;
  pointer-events: auto;
}

.touch-btn {
  width: 3.1rem;
  height: 3.1rem;
  border-radius: 14px;
  border: 1px solid rgba(255, 255, 255, 0.18);
  background: rgba(8, 12, 20, 0.72);
  color: #e2e8f0;
  font-size: 1.1rem;
  font-weight: 700;
  backdrop-filter: blur(6px);
  box-shadow: 0 6px 18px rgba(0, 0, 0, 0.35);
  touch-action: none;
  user-select: none;
}

.touch-btn:active,
.touch-fire:active {
  transform: scale(0.96);
  background: rgba(91, 156, 255, 0.28);
}

.touch-fire {
  pointer-events: auto;
  align-self: flex-end;
  width: 4rem;
  height: 4rem;
  border-radius: 999px;
  font-size: 1.35rem;
  border-color: rgba(251, 191, 36, 0.45);
  color: #fde68a;
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

.powerup-notice {
  position: absolute;
  top: 0.75rem;
  left: 50%;
  transform: translateX(-50%);
  z-index: 4;
  max-width: min(92%, 420px);
  padding: 0.45rem 0.85rem;
  border-radius: 999px;
  font-size: 0.78rem;
  font-weight: 600;
  text-align: center;
  backdrop-filter: blur(8px);
  border: 1px solid rgba(255, 255, 255, 0.12);
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.35);
}

.powerup-notice.info {
  background: rgba(15, 23, 42, 0.82);
  color: #cbd5e1;
}

.powerup-notice.success {
  background: rgba(6, 78, 59, 0.82);
  color: #a7f3d0;
  border-color: rgba(52, 211, 153, 0.35);
}

.powerup-notice.warn {
  background: rgba(120, 53, 15, 0.82);
  color: #fde68a;
  border-color: rgba(251, 191, 36, 0.35);
}

.powerup-notice-enter-active,
.powerup-notice-leave-active {
  transition: opacity 0.25s ease, transform 0.25s ease;
}

.powerup-notice-enter-from,
.powerup-notice-leave-to {
  opacity: 0;
  transform: translateX(-50%) translateY(-8px);
}

.powerup-slot {
  position: absolute;
  top: 0.75rem;
  left: 0.75rem;
  z-index: 3;
  display: flex;
  align-items: center;
  gap: 0.65rem;
  max-width: min(88%, 320px);
  padding: 0.55rem 0.7rem;
  border-radius: 12px;
  border: 1px solid rgba(168, 85, 247, 0.45);
  background: rgba(8, 12, 20, 0.82);
  backdrop-filter: blur(8px);
  animation: slotGlow 2.4s ease-in-out infinite;
}

.powerup-slot.tier-rare {
  border-color: rgba(192, 132, 252, 0.55);
}

.powerup-slot.tier-epic {
  border-color: rgba(252, 211, 77, 0.65);
  animation: slotGlowEpic 1.8s ease-in-out infinite;
}

.powerup-slot.instant {
  animation: slotPulse 1.6s ease-in-out infinite;
}

.powerup-slot.activating {
  animation: slotActivate 0.8s ease-in-out infinite;
}

.powerup-slot-title {
  display: flex;
  align-items: center;
  gap: 0.45rem;
}

.powerup-tier {
  font-size: 0.62rem;
  font-weight: 700;
  letter-spacing: 0.04em;
  text-transform: uppercase;
  padding: 0.08rem 0.35rem;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.08);
  color: #cbd5e1;
}

.tier-rare .powerup-tier {
  color: #e9d5ff;
  background: rgba(192, 132, 252, 0.18);
}

.tier-epic .powerup-tier {
  color: #fde68a;
  background: rgba(252, 211, 77, 0.18);
}

.active-buffs {
  position: absolute;
  top: 0.75rem;
  right: 0.75rem;
  z-index: 3;
  display: flex;
  flex-wrap: wrap;
  gap: 0.4rem;
  max-width: min(52%, 240px);
  justify-content: flex-end;
}

.active-buff {
  display: flex;
  align-items: center;
  gap: 0.35rem;
  padding: 0.28rem 0.45rem 0.28rem 0.35rem;
  border-radius: 999px;
  background: rgba(8, 12, 20, 0.78);
  border: 1px solid color-mix(in srgb, var(--buff-color) 45%, transparent);
  backdrop-filter: blur(6px);
  font-size: 0.68rem;
  color: #e2e8f0;
}

.active-buff-icon {
  color: var(--buff-color);
  font-size: 0.85rem;
}

.active-buff-label {
  font-weight: 600;
}

.active-buff-ring {
  width: 18px;
  height: 18px;
}

.active-buff-ring svg {
  width: 100%;
  height: 100%;
  transform: rotate(-90deg);
}

.active-buff-ring .ring-bg {
  fill: none;
  stroke: rgba(255, 255, 255, 0.12);
  stroke-width: 3;
}

.active-buff-ring .ring-fill {
  fill: none;
  stroke: var(--buff-color);
  stroke-width: 3;
  stroke-linecap: round;
  stroke-dasharray: 94;
  transition: stroke-dashoffset 80ms linear;
}

.powerup-callout {
  position: absolute;
  bottom: 0.75rem;
  left: 50%;
  transform: translateX(-50%);
  z-index: 3;
  display: flex;
  align-items: center;
  gap: 0.55rem;
  padding: 0.45rem 0.85rem;
  border-radius: 999px;
  background: rgba(8, 12, 20, 0.82);
  border: 1px solid rgba(255, 255, 255, 0.1);
  backdrop-filter: blur(8px);
  font-size: 0.78rem;
  color: #e2e8f0;
  animation: calloutBounce 2s ease-in-out infinite;
}

.callout-icon {
  font-size: 1rem;
}

.callout-copy {
  display: flex;
  flex-direction: column;
  gap: 0.05rem;
  line-height: 1.15;
}

.callout-tier {
  font-size: 0.65rem;
  color: #94a3b8;
}

.powerup-fill.powerup-charging {
  animation: powerupChargePulse 0.9s ease-in-out infinite;
}

@keyframes slotGlow {
  0%,
  100% {
    box-shadow: 0 8px 28px rgba(0, 0, 0, 0.35);
  }
  50% {
    box-shadow: 0 8px 28px rgba(0, 0, 0, 0.35), 0 0 18px rgba(168, 85, 247, 0.25);
  }
}

@keyframes slotGlowEpic {
  0%,
  100% {
    box-shadow: 0 8px 28px rgba(0, 0, 0, 0.35), 0 0 12px rgba(252, 211, 77, 0.2);
  }
  50% {
    box-shadow: 0 8px 28px rgba(0, 0, 0, 0.35), 0 0 26px rgba(252, 211, 77, 0.45);
  }
}

@keyframes slotPulse {
  0%,
  100% {
    transform: scale(1);
  }
  50% {
    transform: scale(1.02);
  }
}

@keyframes slotActivate {
  0%,
  100% {
    filter: brightness(1);
  }
  50% {
    filter: brightness(1.15);
  }
}

@keyframes calloutBounce {
  0%,
  100% {
    transform: translateX(-50%) translateY(0);
  }
  50% {
    transform: translateX(-50%) translateY(-3px);
  }
}

@keyframes powerupChargePulse {
  0%,
  100% {
    opacity: 0.85;
  }
  50% {
    opacity: 1;
  }
}

.powerup-slot-icon {
  font-size: 1.35rem;
  line-height: 1;
  flex-shrink: 0;
}

.powerup-slot-copy {
  display: flex;
  flex-direction: column;
  gap: 0.1rem;
  min-width: 0;
  font-size: 0.72rem;
  color: var(--text-muted);
}

.powerup-slot-copy strong {
  font-size: 0.82rem;
  color: #f8fafc;
}

.powerup-slot-hint {
  color: #c084fc;
}

.powerup-use-btn {
  flex-shrink: 0;
  padding: 0.35rem 0.55rem;
  border-radius: 8px;
  border: 1px solid rgba(168, 85, 247, 0.45);
  background: rgba(168, 85, 247, 0.18);
  color: #e9d5ff;
  font-size: 0.72rem;
  font-weight: 700;
  cursor: pointer;
}

.powerup-use-btn:hover:not(:disabled) {
  background: rgba(168, 85, 247, 0.3);
}

.powerup-use-btn.disabled,
.powerup-use-btn:disabled {
  opacity: 0.55;
  cursor: not-allowed;
}

.active-buff-time {
  font-size: 0.62rem;
  font-weight: 700;
  color: #94a3b8;
  min-width: 1.8rem;
  text-align: right;
}

.callout-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  box-shadow: 0 0 8px currentColor;
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
  padding: 0.35rem 0.65rem 0.35rem 0.5rem;
  border-radius: 999px;
  border: 1px solid transparent;
  background: rgba(15, 23, 42, 0.35);
  transition: transform 0.2s ease, border-color 0.2s ease, box-shadow 0.2s ease;
}

.player-score-row.me {
  font-weight: 700;
  border-color: rgba(91, 156, 255, 0.35);
  background: linear-gradient(135deg, rgba(91, 156, 255, 0.12), rgba(124, 108, 240, 0.08));
  box-shadow: 0 0 0 1px rgba(91, 156, 255, 0.08), 0 4px 14px rgba(91, 156, 255, 0.12);
}

.player-score-row.dead {
  opacity: 0.55;
}

.player-score-row.hp-hit {
  animation: hpShake 0.35s ease;
}

.ship-avatar {
  position: relative;
  width: 22px;
  height: 16px;
  flex-shrink: 0;
  filter: drop-shadow(0 0 4px color-mix(in srgb, var(--ship-color) 55%, transparent));
}

.ship-avatar::before {
  content: '';
  position: absolute;
  inset: 0;
  background: linear-gradient(
    135deg,
    color-mix(in srgb, var(--ship-color) 70%, white),
    var(--ship-color) 55%,
    color-mix(in srgb, var(--ship-color) 80%, black)
  );
  clip-path: polygon(18% 12%, 88% 50%, 18% 88%, 8% 62%, 0% 50%, 8% 38%);
}

.ship-avatar::after {
  content: '';
  position: absolute;
  top: 50%;
  left: 58%;
  width: 5px;
  height: 7px;
  transform: translate(-50%, -50%);
  border-radius: 50%;
  background: rgba(224, 242, 254, 0.9);
  box-shadow: inset 0 0 0 1px rgba(255, 255, 255, 0.45);
}

.ship-avatar.right::before {
  clip-path: polygon(82% 12%, 12% 50%, 82% 88%, 92% 62%, 100% 50%, 92% 38%);
}

.ship-avatar.right::after {
  left: 42%;
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
  width: 9px;
  height: 9px;
  border-radius: 2px;
  background: linear-gradient(180deg, #4ade80, #16a34a);
  box-shadow: 0 0 5px rgba(34, 197, 94, 0.55);
  transition: background 0.25s ease, transform 0.25s ease, opacity 0.25s ease;
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
