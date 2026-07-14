<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import type { Room, DuelGameState } from '@/types'
import { DuelRenderer, POWERUP_COLORS, POWERUP_ICONS, POWERUP_LABELS } from './duelRenderer'
import {
  POWERUP_HINTS,
  POWERUP_TIER_LABELS,
  canUseStoredPowerup,
  formatPowerupSeconds,
  listActivePowerupEffects,
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
  playMatchWinSound,
  playShieldBlockSound,
  playShootSound,
  setSoundMuted,
  unlockAudio,
} from './sounds'
import { loadKeybinds, matchesBinding, saveKeybinds, DEFAULT_KEYBINDS, formatBindingLabel, KEYBIND_ACTION_LABELS, type DuelKeybindAction } from './keybinds'
import { chargeTierForTicks } from './chargeTiers'
import { loadMilestones, recordMatchMilestones } from './stats'
import { resolveTheme } from './themes'
import {
  buildDraftTierGroups,
  DRILL_HINTS,
  DRILL_LABELS,
  mutatorStackLabel,
  PERSONALITY_LABELS,
} from './duelHudMeta'
import {
  isColorblindMode,
  isHitStopEnabled,
  loadShakeIntensity,
  saveShakeIntensity,
  setColorblindMode,
  setHitStopEnabled,
  hasSeenDangerLegend,
  markDangerLegendSeen,
} from './visualPrefs'

const props = defineProps<{
  gameState: DuelGameState
  room: Room
  playerId: string
  inputSuspended?: boolean
}>()

const emit = defineEmits<{
  action: [data: Record<string, unknown>]
  lobby: []
  showRules: []
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
  () =>
    !props.inputSuspended &&
    props.gameState.phase === 'playing' &&
    isAlive.value,
)
const chargeEnabled = computed(
  () => props.gameState.charge_shot_enabled ?? props.gameState.match_format !== 'quick_duel',
)
const powerupsEnabled = computed(() => Boolean(props.gameState.powerups_enabled))
const chargeMaxTicks = computed(() => props.gameState.charge_max_ticks ?? 15)
const tickMs = computed(() => props.gameState.tick_ms || 75)
const storedPowerup = computed(() => myFighter.value?.stored_powerup ?? null)
const storedPowerupCharges = computed(() => myFighter.value?.powerup_charges ?? null)

const roundsToWin = computed(() => Math.ceil(props.gameState.best_of / 2))

const countdownNow = ref(Date.now())
const countdownRemaining = computed(() => {
  if (
    props.gameState.phase !== 'countdown' &&
    props.gameState.phase !== 'round_over'
  ) {
    return null
  }
  if (!props.gameState.countdown_ends_at) return null
  const end = new Date(props.gameState.countdown_ends_at).getTime()
  return Math.max(0, Math.ceil((end - countdownNow.value) / 1000))
})

const winnerName = computed(() => {
  const winnerId = props.gameState.winner
  if (!winnerId) return null
  const player = props.gameState.players.find((p) => p.id === winnerId)
  return player?.nickname ?? 'Unknown'
})

const matchResultText = computed(() => {
  if (!props.gameState.winner) return 'Match drawn!'
  return `${winnerName.value} wins!`
})

const matchWinnerId = computed(() => props.gameState.winner ?? null)

const matchPodium = computed(() => {
  const winnerId = matchWinnerId.value
  return [...playerRows.value]
    .sort((a, b) => {
      if (a.id === winnerId) return -1
      if (b.id === winnerId) return 1
      return b.roundWins - a.roundWins
    })
    .map((row) => ({
      ...row,
      isWinner: Boolean(winnerId && row.id === winnerId),
      isMe: row.id === props.playerId,
    }))
})

const viewerMatchOutcome = computed(() => {
  if (!isFinished.value) return null
  const winnerId = matchWinnerId.value
  if (!winnerId) {
    return {
      kind: 'draw' as const,
      headline: 'Draw',
      sub: 'No match winner — scores tied',
    }
  }
  if (winnerId === props.playerId) {
    return {
      kind: 'victory' as const,
      headline: 'Victory!',
      sub: 'You won the match',
    }
  }
  return {
    kind: 'defeat' as const,
    headline: `${winnerName.value} wins`,
    sub: 'You lost the match',
  }
})

const matchScoreSummary = computed(() => {
  const rows = playerRows.value
  if (rows.length !== 2) {
    return rows.map((row) => `${row.nickname} ${row.roundWins}`).join(' · ')
  }
  const [left, right] = rows
  return `${left.nickname} ${left.roundWins} – ${right.roundWins} ${right.nickname}`
})

const phaseAnnouncement = computed(() => {
  if (props.gameState.phase === 'countdown') {
    return `Get ready! ${countdownRemaining.value ?? ''}`
  }
  if (isRoundOver.value) {
    if (roundWinnerName.value) return `${roundWinnerName.value} wins the round`
    return 'Round drawn'
  }
  if (isFinished.value) return matchResultText.value
  return ''
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
const shootOnCooldown = computed(() => {
  const tick = props.gameState.tick ?? 0
  const until = myFighter.value?.cooldown_until_tick ?? 0
  return tick < until
})
const canUsePowerup = computed(() =>
  canUseStoredPowerup(
    storedPowerup.value,
    myFighter.value?.hp ?? 0,
    myFighter.value?.max_hp ?? 3,
  ),
)
const hpPulseId = ref<string | null>(null)
const powerupNotice = ref<{ text: string; tone: 'info' | 'success' | 'warn' } | null>(null)
let powerupNoticeTimer: ReturnType<typeof setTimeout> | null = null
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
const showVisualPrefs = ref(false)
const colorblindMode = ref(isColorblindMode())
const shakeIntensity = ref(loadShakeIntensity())
const hitStopEnabled = ref(isHitStopEnabled())
const canvasDisplaySize = ref({ w: 0, h: 0 })
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
const bannedPowerupTypes = computed(() => Object.values(props.gameState.powerup_bans ?? {}))
const draftTierGroups = computed(() => buildDraftTierGroups(bannedPowerupTypes.value))
const draftBanCount = computed(() => Object.keys(props.gameState.powerup_bans ?? {}).length)
const draftPlayerCount = computed(() => props.gameState.players.length)
const matchMutatorLabel = computed(() =>
  mutatorStackLabel(props.gameState.mutator, props.gameState.mutator_secondary),
)
const activeDrill = computed(() => props.gameState.training_drill ?? 'none')
const drillBadge = computed(() => DRILL_LABELS[activeDrill.value] ?? '')
const drillHintText = computed(() => DRILL_HINTS[activeDrill.value] ?? '')
const aiPersonalityLabel = computed(() => {
  if (!props.gameState.players.some((p) => p.is_ai)) return ''
  const personality = String(props.room.settings?.ai_personality ?? 'balanced')
  return PERSONALITY_LABELS[personality] ?? ''
})
const quickLoadoutLabel = computed(() => {
  if (props.gameState.match_format !== 'quick_duel') return null
  const loadout = String(props.room.settings?.quick_duel_loadout ?? 'none')
  if (loadout === 'none') return null
  return POWERUP_LABELS[loadout] ?? loadout.replace(/_/g, ' ')
})
const fogActive = computed(
  () =>
    props.gameState.mutator === 'fog' ||
    props.gameState.mutator_secondary === 'fog' ||
    Boolean(props.gameState.fog),
)
const disconnectMessage = computed(() => {
  if (props.gameState.win_reason !== 'opponent_disconnect' || !isFinished.value) return null
  if (props.gameState.winner === props.playerId) return 'Opponent disconnected — you win'
  return 'Opponent disconnected'
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
const shrinkSoftWarningActive = computed(() => {
  const until = shrinkTicksUntil.value
  return (
    until !== null &&
    until <= Math.ceil(4800 / tickMs.value) &&
    until > Math.ceil(2400 / tickMs.value)
  )
})
const showCoachHint = computed(
  () => coachHint.value && props.gameState.phase !== 'finished',
)
const showDangerLegend = ref(!hasSeenDangerLegend())
const bindingCapture = ref<DuelKeybindAction | null>(null)
const keybindActions = Object.keys(KEYBIND_ACTION_LABELS) as DuelKeybindAction[]

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
  if (
    showDangerLegend.value &&
    props.gameState.phase === 'playing' &&
    isAlive.value &&
    incomingBulletCount.value > 0
  ) {
    coachHint.value = 'Flashing rows on your ship = incoming fire'
    markDangerLegendSeen()
    showDangerLegend.value = false
    return
  }

  if (!props.gameState.tutorial_mode) {
    coachHint.value = null
    return
  }

  if (props.gameState.phase === 'powerup_draft') {
    coachHint.value =
      'Remove one orb type from the pool for the rest of the match — pick what you never want to face'
    return
  }

  if (props.gameState.phase === 'countdown') {
    if (props.gameState.round === 1 && fogActive.value) {
      coachHint.value =
        'Fog jitters enemy aim rows — bullet trails and movement reveal true position'
      return
    }
    if (props.gameState.round === 1) {
      if (chargeEnabled.value && powerupsEnabled.value) {
        coachHint.value = 'Hold Space to charge shots · Press E to use power-ups'
      } else if (chargeEnabled.value) {
        coachHint.value = 'Hold Space to charge a spread shot, release to fire'
      } else {
        coachHint.value = 'W/S or the on-screen arrows move your ship · Space fires'
      }
      return
    }
    if (draftBanSummary.value.length) {
      coachHint.value = `Banned: ${draftBanSummary.value.map((b) => b.label).join(', ')}`
      return
    }
    coachHint.value = null
    return
  }

  if (
    props.gameState.phase === 'playing' &&
    shrinkSoftWarningActive.value &&
    props.gameState.shrinking_arena
  ) {
    coachHint.value = 'Arena will shrink soon — red hazard zones deal damage over time'
    return
  }

  if (props.gameState.phase !== 'playing' || props.gameState.round > 1) {
    coachHint.value = null
    return
  }

  if (props.gameState.tick < 120) {
    if (props.gameState.shrinking_arena) {
      coachHint.value = 'Use cover, then watch the red hazard zones — they deal damage'
    } else if (chargeEnabled.value) {
      coachHint.value = 'Center-row hits deal bonus damage · higher charge tiers spread wider'
    } else {
      coachHint.value = 'Center-row hits deal bonus damage'
    }
    return
  }

  coachHint.value = null
}

function playGameSounds() {
  if (soundMuted.value) return

  const tickHits = props.gameState.tick_hits ?? []
  for (const hit of tickHits) {
    if (!hit?.player_id || hit.damage === undefined) continue
    const stamp = `${hit.player_id}-${props.gameState.tick}-${hit.damage}-${hit.blocked ? 'b' : 'h'}-multi`
    if (stamp === lastHitSoundStamp.value) continue
    lastHitSoundStamp.value = stamp
    if (hit.blocked) playShieldBlockSound()
    else playHitSound(Boolean(hit.crit))
  }

  const hit = props.gameState.last_hit
  if (hit?.player_id && hit.damage !== undefined && !tickHits.length) {
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
    !myFighter.value.effects?.shield_active &&
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

const storedPowerupHint = computed(() =>
  powerupUseHint(storedPowerup.value, tickMs.value, storedPowerupCharges.value),
)
const storedPowerupDescription = computed(() =>
  storedPowerup.value ? POWERUP_HINTS[storedPowerup.value] ?? '' : '',
)
const storedPowerupTier = computed(() => powerupTier(storedPowerup.value))
const arenaPowerup = computed(() => props.gameState.powerup)
const arenaPowerupTier = computed(() => powerupTier(arenaPowerup.value?.type))
const activeBuffs = computed(() =>
  listActivePowerupEffects(
    myFighter.value?.effects as Record<string, unknown> | undefined,
    props.gameState.tick,
    tickMs.value,
    props.gameState.effect_duration_ticks ?? 160,
  ),
)

function fighterEffects(
  effects: Record<string, unknown> | undefined,
) {
  return listActivePowerupEffects(
    effects,
    props.gameState.tick,
    tickMs.value,
    props.gameState.effect_duration_ticks ?? 160,
  )
}

function isInputBinding(code: string): boolean {
  return (
    matchesBinding(code, keybinds.value.moveUp) ||
    matchesBinding(code, keybinds.value.moveDown) ||
    matchesBinding(code, keybinds.value.fire) ||
    matchesBinding(code, keybinds.value.powerup)
  )
}

function showPhaseBlockedNotice() {
  if (props.gameState.phase === 'countdown') {
    showPowerupNotice('Wait for the round to start', 'info')
  } else if (props.gameState.phase === 'powerup_draft') {
    showPowerupNotice('Finish the power-up ban first', 'info')
  } else if (props.gameState.phase === 'round_over' || props.gameState.phase === 'finished') {
    showPowerupNotice('Round is over', 'info')
  } else if (!isAlive.value && props.gameState.phase === 'playing') {
    return
  } else {
    showPowerupNotice('Not available right now', 'info')
  }
}

function startBindingCapture(action: DuelKeybindAction) {
  bindingCapture.value = action
}

function onBindingCaptureKey(e: KeyboardEvent) {
  if (!bindingCapture.value) return
  e.preventDefault()
  e.stopPropagation()
  if (e.code === 'Escape') {
    bindingCapture.value = null
    return
  }
  const action = bindingCapture.value
  keybinds.value = { ...keybinds.value, [action]: [e.code] }
  saveKeybinds(keybinds.value)
  bindingCapture.value = null
}

const dangerRows = computed(() => {
  const rows = new Set<number>()
  if (!myFighter.value?.alive) return rows
  const myX = myFighter.value.x
  const myTop = myFighter.value.y
  const myBottom = myTop + props.gameState.fighter_height - 1
  for (const bullet of props.gameState.bullets) {
    if (bullet.owner_id === props.playerId) continue
    const vx = bullet.vx ?? 0
    const vy = bullet.vy ?? 0
    const headingToward =
      (myFighter.value.side === 'left' && vx < 0 && bullet.x >= myX) ||
      (myFighter.value.side === 'right' && vx > 0 && bullet.x <= myX)
    if (!headingToward && bullet.kind !== 'bomb') continue
    const approxX = bullet.x + vx * 6
    const approxY = bullet.y + vy * 6
    const ticks = Math.abs(approxX - myX) / Math.max(1, Math.abs(vx) || 1)
    if (ticks > 10 && bullet.kind !== 'bomb') continue
    for (let row = Math.max(0, approxY - 1); row <= approxY + 1; row++) {
      if (row >= myTop - 1 && row <= myBottom + 1) rows.add(row)
    }
    if (bullet.kind === 'bomb' && Math.abs(bullet.x - myX) <= 2) {
      for (let row = myTop; row <= myBottom; row++) rows.add(row)
    }
  }
  return rows
})

function clearHeldInputs() {
  if (heldMove.value) {
    sendMove('stop')
    heldMove.value = null
  }
  if (charging.value) releaseCharge()
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
  emit('action', { type: 'powerup_activate' })
}

function onPowerupButtonClick(e: MouseEvent | TouchEvent) {
  e.preventDefault()
  unlockAudio()
  useStoredPowerup()
}

watch(
  () => myFighter.value?.stored_powerup,
  (stored, prev) => {
    if (stored && stored !== prev) {
      const label = POWERUP_LABELS[stored] ?? stored
      showPowerupNotice(`${label} collected — ${powerupUseHint(stored, tickMs.value, myFighter.value?.powerup_charges)}`, 'success')
    }
    lastStoredPowerup.value = stored ?? null
  },
)

watch(
  () => myFighter.value?.charge_ticks,
  (serverTicks) => {
    if (!charging.value || typeof serverTicks !== 'number') return
    chargeTicks.value = Math.min(chargeMaxTicks.value, serverTicks)
  },
)

watch(
  () => arenaPowerup.value?.type,
  (ptype, prev) => {
    if (!ptype || !powerupsEnabled.value) return
    const orb = arenaPowerup.value
    if (!orb) return
    const key = `${orb.x}:${orb.y}:${ptype}`
    if (key === lastSeenPowerupKey.value || ptype === prev) return
    lastSeenPowerupKey.value = key
    const label = POWERUP_LABELS[ptype] ?? ptype
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
      const charges = action.charges_remaining as number | undefined
      if (ptype === 'bomb' && typeof charges === 'number' && charges > 0) {
        showPowerupNotice(`${POWERUP_LABELS.bomb} launched — ${charges} left`, 'success')
      } else {
        showPowerupNotice(`${POWERUP_LABELS[ptype] ?? ptype} activated!`, 'success')
      }
    } else if (type === 'powerup_blocked' && action.reason === 'max_hp') {
      showPowerupNotice('Heal saved — you are already at full health', 'warn')
    } else if (type === 'action_rejected') {
      const reason = action.reason as string | undefined
      const attempted = action.attempted as string | undefined
      if (attempted === 'charge_start') {
        cancelLocalCharge()
      }
      const messages: Record<string, string> = {
        wrong_phase: 'Not available right now',
        not_alive: 'You are eliminated',
        already_banned: 'You already banned a power-up',
        invalid_powerup: 'Invalid power-up choice',
        on_cooldown: 'Wait for reload before charging',
      }
      showPowerupNotice(messages[reason ?? ''] ?? 'Action rejected', 'warn')
    }
  },
)

watch(
  () => props.gameState.phase,
  (phase, prev) => {
    if (phase !== 'playing' || !isAlive.value) {
      clearHeldInputs()
    }
    if (phase === 'finished' && prev !== 'finished') {
      milestones.value = recordMatchMilestones(props.playerId, props.gameState.match_stats)
      matchPowerupActions.value = []
      if (props.gameState.winner === props.playerId) {
        playMatchWinSound()
      } else if (props.gameState.winner) {
        playRoundWinSound()
      }
    }
    if (phase === 'countdown' && prev === 'finished') {
      matchPowerupActions.value = []
    }
  },
)

watch(
  () => isAlive.value,
  (alive) => {
    if (!alive) clearHeldInputs()
  },
)

watch(
  () => props.inputSuspended,
  (suspended) => {
    if (suspended) clearHeldInputs()
  },
)

function cancelLocalCharge() {
  charging.value = false
  chargeTicks.value = 0
}

function startCharge() {
  if (!canControl.value || !chargeEnabled.value) return
  if (shootOnCooldown.value) {
    showPowerupNotice('Wait for reload before charging', 'warn')
    return
  }
  charging.value = true
  chargeTicks.value = 0
  emit('action', { type: 'charge_start' })
}

function releaseCharge() {
  if (!charging.value) return
  charging.value = false
  const serverTicks = myFighter.value?.charge_ticks ?? chargeTicks.value
  // Credit one in-flight tick so a release right as the bar fills still reaches spread tier.
  const ticks = Math.min(chargeMaxTicks.value, serverTicks + 1)
  emit('action', { type: 'release_charge', charge_ticks: ticks })
  chargeTicks.value = 0
}

function quickShoot() {
  emit('action', { type: 'shoot' })
}

function onKeyDown(e: KeyboardEvent) {
  if (props.inputSuspended) return

  if (bindingCapture.value) {
    onBindingCaptureKey(e)
    return
  }

  if (matchesBinding(e.code, keybinds.value.fire) && charging.value) return

  if (!canControl.value) {
    if (isInputBinding(e.code)) {
      e.preventDefault()
      showPhaseBlockedNotice()
    }
    return
  }

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
    useStoredPowerup()
    return
  }
}

function onKeyUp(e: KeyboardEvent) {
  if (props.inputSuspended) return

  if (matchesBinding(e.code, keybinds.value.moveUp) && heldMove.value === 'up') {
    heldMove.value = null
    if (canControl.value) sendMove('stop')
    return
  }

  if (matchesBinding(e.code, keybinds.value.moveDown) && heldMove.value === 'down') {
    heldMove.value = null
    if (canControl.value) sendMove('stop')
    return
  }

  if (matchesBinding(e.code, keybinds.value.fire)) {
    e.preventDefault()
    if (charging.value) releaseCharge()
    return
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
  if (canvasDisplaySize.value.w !== displayW || canvasDisplaySize.value.h !== displayH) {
    canvasDisplaySize.value = { w: displayW, h: displayH }
    canvas.width = Math.floor(displayW * dpr)
    canvas.height = Math.floor(displayH * dpr)
    canvas.style.width = `${displayW}px`
    canvas.style.height = `${displayH}px`
  }
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0)

  renderer.draw(ctx, props.gameState, props.playerId, displayW, displayH, now, dangerRows.value)
}

function applyVisualPrefs() {
  setColorblindMode(colorblindMode.value)
  saveShakeIntensity(shakeIntensity.value)
  setHitStopEnabled(hitStopEnabled.value)
  renderer.reset()
}

function resetKeybinds() {
  keybinds.value = { ...DEFAULT_KEYBINDS }
  saveKeybinds(keybinds.value)
}

let resizeObserver: ResizeObserver | null = null
let animFrame = 0
let countdownTimer: ReturnType<typeof setInterval> | null = null

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
  countdownTimer = setInterval(() => {
    countdownNow.value = Date.now()
  }, 250)
})

onUnmounted(() => {
  window.removeEventListener('resize', detectTouchControls)
  window.removeEventListener('keydown', onKeyDown)
  window.removeEventListener('keyup', onKeyUp)
  window.removeEventListener('blur', clearHeldInputs)
  document.removeEventListener('visibilitychange', onVisibilityChange)
  resizeObserver?.disconnect()
  cancelAnimationFrame(animFrame)
  if (countdownTimer) clearInterval(countdownTimer)
  if (powerupNoticeTimer) clearTimeout(powerupNoticeTimer)
  renderer.reset()
})
</script>

<template>
  <div class="duel-board">
    <div class="match-bar">
      <span class="match-format">
        Round {{ gameState.round }} · Best of {{ gameState.best_of }} · First to {{ roundsToWin }}
      </span>
      <span v-if="shrinkSoftWarningActive" class="shrink-soft">Arena shrinking soon</span>
      <span v-if="shrinkWarningActive" class="shrink-warning">
        Arena shrinks in {{ formatPowerupSeconds(shrinkTicksUntil ?? 0, tickMs) }}
      </span>
      <span class="mutator-tag">{{ matchMutatorLabel }}</span>
      <span v-if="fogActive" class="match-chip fog" title="Enemy aim rows are imprecise">Fog</span>
      <span v-if="drillBadge" class="match-chip drill" :title="drillHintText">{{ drillBadge }}</span>
      <span v-if="quickLoadoutLabel" class="match-chip loadout">Loadout: {{ quickLoadoutLabel }}</span>
      <span v-if="aiPersonalityLabel" class="match-chip ai">{{ aiPersonalityLabel }}</span>
      <button type="button" class="match-link" @click="emit('showRules')">Power-ups</button>
      <button
        type="button"
        class="sound-toggle labeled"
        :aria-label="soundMuted ? 'Unmute sound' : 'Mute sound'"
        @click="toggleSound"
      >
        <span aria-hidden="true">{{ soundMuted ? '🔇' : '🔊' }}</span>
        <span class="toggle-label">Sound</span>
      </button>
      <button
        type="button"
        class="sound-toggle labeled"
        aria-label="Visual and accessibility settings"
        @click="showVisualPrefs = !showVisualPrefs"
      >
        <span aria-hidden="true">⚙</span>
        <span class="toggle-label">Settings</span>
      </button>
    </div>

    <div v-if="showVisualPrefs" class="visual-prefs card">
      <label class="checkbox-label">
        <input v-model="colorblindMode" type="checkbox" @change="applyVisualPrefs" />
        Colorblind bullet palettes
      </label>
      <label>
        Screen shake
        <input
          v-model.number="shakeIntensity"
          type="range"
          min="0"
          max="1"
          step="0.1"
          @change="applyVisualPrefs"
        />
      </label>
      <label class="checkbox-label">
        <input v-model="hitStopEnabled" type="checkbox" @change="applyVisualPrefs" />
        Hit stop on crits
      </label>
      <div class="keybind-list">
        <p class="muted keybind-lead">Click a row, then press a key to rebind. Esc cancels.</p>
        <div v-for="action in keybindActions" :key="action" class="keybind-row">
          <span>{{ KEYBIND_ACTION_LABELS[action] }}</span>
          <button
            type="button"
            class="btn-secondary keybind-btn"
            :class="{ capturing: bindingCapture === action }"
            @click="startBindingCapture(action)"
          >
            {{
              bindingCapture === action
                ? 'Press a key…'
                : formatBindingLabel(keybinds[action])
            }}
          </button>
        </div>
      </div>
      <button type="button" class="btn-secondary" @click="resetKeybinds">Reset keybinds</button>
    </div>

    <div ref="canvasWrapRef" class="canvas-wrap" :style="{ background: canvasTheme.canvasCss }">
      <canvas
        ref="canvasRef"
        class="game-canvas"
        role="img"
        aria-label="Side Duel arena"
      />

      <div class="sr-only" aria-live="assertive" aria-atomic="true">
        {{ phaseAnnouncement }}
      </div>

      <Transition name="powerup-notice">
        <div v-if="showCoachHint" class="coach-hint">
          {{ coachHint }}
        </div>
      </Transition>

      <Transition name="powerup-notice">
        <div
          v-if="powerupNotice"
          class="powerup-notice"
          :class="powerupNotice.tone"
        >
          {{ powerupNotice.text }}
        </div>
      </Transition>

      <div
        v-if="canControl && storedPowerup && powerupsEnabled"
        class="powerup-slot"
        :class="`tier-${storedPowerupTier}`"
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
            <span
              v-if="storedPowerup === 'bomb' && storedPowerupCharges"
              class="powerup-charges-badge"
            >
              ×{{ storedPowerupCharges }}
            </span>
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
          @click="onPowerupButtonClick"
        >
          {{
            !canUsePowerup && storedPowerup === 'heal'
              ? 'Full HP'
              : `Use [${formatBindingLabel(keybinds.powerup)}]`
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

      <div v-if="eventFeed.length" class="event-feed" :class="{ 'feed-touch': showTouchControls }" aria-live="polite">
        <div v-for="(entry, idx) in eventFeed" :key="`${entry.tick}-${idx}`" :class="['feed-line', entry.kind]">
          {{ entry.message }}
        </div>
      </div>

      <div v-if="isDraftPhase && !myBan" class="overlay draft">
        <span class="overlay-label">Ban a power-up</span>
        <p class="overlay-hint draft-explainer">
          Remove one orb type from the pool for the rest of the match. Banned types won't spawn again.
        </p>
        <div v-for="group in draftTierGroups" :key="group.tier" class="draft-tier-group">
          <span class="draft-tier-label">{{ group.label }}</span>
          <div class="draft-grid">
            <button
              v-for="opt in group.options"
              :key="opt.id"
              type="button"
              class="btn-secondary draft-btn"
              :class="{ banned: opt.banned }"
              :disabled="opt.banned"
              :style="{ borderColor: opt.color }"
              @click="banPowerup(opt.id)"
            >
              <span class="draft-icon" :style="{ color: opt.color }">{{ opt.icon }}</span>
              <span>{{ opt.label }}</span>
              <span v-if="opt.banned" class="draft-banned-tag">Banned</span>
            </button>
          </div>
        </div>
      </div>

      <div v-else-if="isDraftPhase" class="overlay draft">
        <span class="overlay-hint">Waiting for opponent to ban…</span>
        <p class="draft-progress">{{ draftBanCount }}/{{ draftPlayerCount }} bans locked in</p>
        <ul v-if="draftBanSummary.length" class="draft-bans">
          <li v-for="ban in draftBanSummary" :key="ban.nickname">
            {{ ban.nickname }} banned {{ ban.label }}
          </li>
        </ul>
      </div>

      <div v-if="gameState.phase === 'countdown'" class="overlay countdown">
        <span class="overlay-value pulse">{{ countdownRemaining ?? '…' }}</span>
        <span class="overlay-label">Get ready!</span>
        <span class="overlay-hint">
          Round {{ gameState.round }} · First to {{ roundsToWin }} wins
          <template v-if="playerRows.length">
            ·
            <template v-for="(row, idx) in playerRows" :key="row.id">
              {{ row.nickname }} {{ row.roundWins }}/{{ roundsToWin }}<span v-if="idx < playerRows.length - 1"> · </span>
            </template>
          </template>
        </span>
      </div>

      <div v-else-if="isRoundOver" class="overlay round-over">
        <span class="overlay-label slide-in">Round {{ gameState.round - 1 }} over</span>
        <span v-if="roundWinnerName" class="overlay-value pop-in">{{ roundWinnerName }} wins the round!</span>
        <span v-else class="overlay-value pop-in">Draw — rematch!</span>
        <div v-if="roundRecapRows.length" class="round-recap">
          <div
            v-for="row in roundRecapRows"
            :key="row.nickname"
            class="recap-row"
            :class="{ winner: row.nickname === roundWinnerName }"
          >
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
        <div v-if="matchWinnerId" class="match-confetti" aria-hidden="true">
          <span v-for="i in 28" :key="i" class="confetti-piece" :style="{ '--i': i }" />
        </div>

        <div
          v-if="viewerMatchOutcome"
          class="match-outcome-banner"
          :class="viewerMatchOutcome.kind"
        >
          <span class="match-outcome-icon" aria-hidden="true">
            {{
              viewerMatchOutcome.kind === 'victory'
                ? '🏆'
                : viewerMatchOutcome.kind === 'defeat'
                  ? '💫'
                  : '🤝'
            }}
          </span>
          <span class="match-outcome-headline">{{ viewerMatchOutcome.headline }}</span>
          <span class="match-outcome-sub">{{ viewerMatchOutcome.sub }}</span>
          <span class="match-outcome-score">{{ matchScoreSummary }}</span>
        </div>

        <div class="match-podium">
          <article
            v-for="row in matchPodium"
            :key="row.id"
            class="podium-card"
            :class="{
              winner: row.isWinner,
              runner: matchWinnerId && !row.isWinner,
              me: row.isMe,
            }"
            :style="
              row.fighter?.color
                ? { '--podium-color': row.fighter.color }
                : undefined
            "
          >
            <span v-if="row.isWinner" class="podium-crown" aria-hidden="true">👑</span>
            <span
              class="ship-avatar podium-avatar"
              :class="{ left: row.fighter?.side === 'left', right: row.fighter?.side === 'right' }"
              :style="{ '--ship-color': row.fighter?.color ?? '#666' }"
              aria-hidden="true"
            />
            <div class="podium-copy">
              <div class="podium-name-row">
                <strong class="podium-name">{{ row.nickname }}</strong>
                <span v-if="row.isMe" class="podium-you">You</span>
              </div>
              <span class="podium-score">{{ row.roundWins }} / {{ roundsToWin }} rounds</span>
              <span v-if="row.isWinner" class="podium-badge">Match winner</span>
              <span v-else-if="matchWinnerId" class="podium-badge muted">Runner-up</span>
            </div>
          </article>
        </div>

        <p v-if="disconnectMessage" class="disconnect-note">{{ disconnectMessage }}</p>
        <div class="milestones">
          <span class="milestones-note">Saved on this device only</span>
          <div class="milestone-chips">
            <span class="milestone-chip">{{ milestones.matchesPlayed }} matches</span>
            <span class="milestone-chip">{{ milestones.perfectRounds }} perfect rounds</span>
            <span class="milestone-chip">{{ milestones.critsLanded }} crits</span>
            <span class="milestone-chip" title="Kills with railgun power-up">{{ milestones.railgunKills }} railgun kills</span>
            <span class="milestone-chip" title="Heals used at 1 HP">{{ milestones.clutchHeals }} clutch heals</span>
          </div>
        </div>
        <div v-if="isHost" class="finished-actions">
          <button type="button" class="btn-primary play-again-btn" @click="startNewGame(false)">
            Rematch
          </button>
          <button type="button" class="btn-secondary play-again-btn" @click="startNewGame(true)">
            Rematch (same arena layout)
          </button>
          <button type="button" class="btn-secondary play-again-btn" @click="returnToLobby">
            Back to lobby
          </button>
        </div>
        <div v-else class="finished-actions guest-finished">
          <p class="overlay-hint">Waiting for host to start a rematch…</p>
          <button type="button" class="btn-primary play-again-btn" @click="returnToLobby">
            Return to lobby
          </button>
        </div>
      </div>

      <div v-else-if="!isAlive && gameState.phase === 'playing'" class="spectator-banner">
        <span class="spectator-title">You were eliminated — spectating</span>
        <span class="spectator-meta">
          <template v-for="(row, idx) in playerRows" :key="row.id">
            {{ row.nickname }} {{ row.fighter?.hp ?? 0 }}/{{ row.fighter?.max_hp ?? 3 }} HP
            <span v-if="idx < playerRows.length - 1"> · </span>
          </template>
          <span v-if="incomingBulletCount"> · {{ incomingBulletCount }} bullets incoming</span>
        </span>
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
        <div class="touch-actions">
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
        <button
          v-if="storedPowerup && powerupsEnabled"
          type="button"
          class="touch-btn touch-powerup"
          :aria-label="'Use power-up'"
          :disabled="!canUsePowerup"
          @click.prevent="onPowerupButtonClick"
        >
          {{ POWERUP_ICONS[storedPowerup] ?? '★' }}
        </button>
        </div>
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
            <span v-if="row.fighter.max_hp === 1" class="hp-text">{{ row.fighter.hp }}/1</span>
          </span>
          <span
            v-for="buff in fighterEffects(row.fighter?.effects as Record<string, unknown> | undefined)"
            :key="`${row.id}-${buff.id}`"
            class="effect-chip"
            :style="{ borderColor: POWERUP_COLORS[buff.id] ?? '#a855f7' }"
          >
            {{ buff.label }}
            <span class="effect-chip-time">{{ formatPowerupSeconds(buff.remainingTicks, tickMs) }}</span>
          </span>
          <span
            v-if="fogActive && row.id !== playerId"
            class="effect-chip fog-chip"
            title="Aim rows are imprecise in fog"
          >
            Imprecise aim
          </span>
          <span
            v-if="row.id === playerId && row.fighter?.stored_powerup"
            class="effect-chip stored"
            :style="{ color: POWERUP_COLORS[row.fighter.stored_powerup] ?? '#fbbf24' }"
            :title="POWERUP_LABELS[row.fighter.stored_powerup]"
          >
            {{ POWERUP_ICONS[row.fighter.stored_powerup] ?? '★' }}
            {{ POWERUP_LABELS[row.fighter.stored_powerup] }}
          </span>
          <span v-if="!row.fighter?.alive" class="status">out</span>
        </li>
      </ul>

      <div class="controls-hint">
        <p v-if="showTouchControls && canControl && storedPowerup && powerupsEnabled">
          <strong>Touch:</strong> Arrows move · ⚡ {{ chargeEnabled ? 'hold to charge' : 'fire' }} ·
          {{ POWERUP_ICONS[storedPowerup] ?? '★' }} tap power-up
        </p>
        <p v-else-if="showTouchControls && canControl && chargeEnabled">
          <strong>Touch:</strong> Use on-screen arrows to move · Hold ⚡ to charge and release to fire
        </p>
        <p v-else-if="showTouchControls && canControl">
          <strong>Touch:</strong> Arrows move · ● fires
        </p>
        <p v-else-if="canControl && chargeEnabled && storedPowerup">
          <strong>Controls:</strong> {{ formatBindingLabel(keybinds.moveUp) }}/{{ formatBindingLabel(keybinds.moveDown) }} move · {{ formatBindingLabel(keybinds.fire) }} charge & fire ·
          {{ formatBindingLabel(keybinds.powerup) }} to use power-up
        </p>
        <p v-else-if="canControl && chargeEnabled && powerupsEnabled && arenaPowerup">
          <strong>Controls:</strong> {{ formatBindingLabel(keybinds.moveUp) }}/{{ formatBindingLabel(keybinds.moveDown) }} move · {{ formatBindingLabel(keybinds.fire) }} charge & fire · Collect the {{ POWERUP_LABELS[arenaPowerup.type] ?? 'power-up' }} (shoot or touch it)
        </p>
        <p v-else-if="canControl && chargeEnabled">
          <strong>Controls:</strong> {{ formatBindingLabel(keybinds.moveUp) }}/{{ formatBindingLabel(keybinds.moveDown) }} to move · Hold {{ formatBindingLabel(keybinds.fire) }} to charge, release to fire
        </p>
        <p v-else-if="canControl">
          <strong>Controls:</strong> {{ formatBindingLabel(keybinds.moveUp) }}/{{ formatBindingLabel(keybinds.moveDown) }} to move · {{ formatBindingLabel(keybinds.fire) }} to shoot
        </p>
        <p v-else-if="drillHintText && gameState.phase === 'playing'">
          <strong>Drill:</strong> {{ drillHintText }}
        </p>
        <p v-else-if="gameState.phase === 'playing' && !isAlive" class="muted">Spectating — canvas stays live</p>
        <p v-else class="muted">Waiting…</p>
        <p v-if="gameState.phase === 'playing' || gameState.phase === 'countdown'" class="muted rules-link">
          <button type="button" class="inline-link" @click="emit('showRules')">See Rules</button>
          for the full power-up list
        </p>
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

.shrink-soft {
  padding: 0.15rem 0.55rem;
  border-radius: 999px;
  background: rgba(251, 191, 36, 0.12);
  border: 1px solid rgba(251, 191, 36, 0.28);
  color: #fde68a;
  font-size: 0.75rem;
  font-weight: 600;
}

.match-chip {
  padding: 0.15rem 0.55rem;
  border-radius: 999px;
  background: rgba(15, 23, 42, 0.55);
  border: 1px solid rgba(255, 255, 255, 0.1);
  font-size: 0.72rem;
  font-weight: 600;
  color: #cbd5e1;
}

.match-chip.drill {
  border-color: rgba(52, 211, 153, 0.35);
  color: #a7f3d0;
}

.match-chip.loadout {
  border-color: rgba(168, 85, 247, 0.35);
  color: #e9d5ff;
}

.match-chip.fog {
  border-color: rgba(148, 163, 184, 0.35);
  color: #e2e8f0;
}

.match-link {
  border: none;
  background: transparent;
  color: var(--accent);
  font-size: 0.78rem;
  font-weight: 600;
  cursor: pointer;
  text-decoration: underline;
  text-underline-offset: 2px;
}

.sound-toggle.labeled {
  display: inline-flex;
  align-items: center;
  gap: 0.3rem;
}

.toggle-label {
  font-size: 0.72rem;
  color: var(--text-muted);
}

.keybind-list {
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
}

.keybind-lead {
  margin: 0;
}

.keybind-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.5rem;
}

.keybind-btn {
  min-width: 7rem;
  font-size: 0.78rem;
}

.keybind-btn.capturing {
  border-color: var(--accent);
  color: var(--accent);
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

.visual-prefs {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
  padding: 0.65rem 0.85rem;
  font-size: 0.85rem;
}

.sr-only {
  position: absolute;
  width: 1px;
  height: 1px;
  padding: 0;
  margin: -1px;
  overflow: hidden;
  clip: rect(0, 0, 0, 0);
  white-space: nowrap;
  border: 0;
}

.sound-toggle {
  margin-left: 0;
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

.event-feed.feed-touch {
  bottom: 9rem;
  max-width: min(62%, 280px);
}

.spectator-banner {
  position: absolute;
  top: 0.65rem;
  left: 50%;
  transform: translateX(-50%);
  z-index: 5;
  display: flex;
  flex-direction: column;
  gap: 0.2rem;
  max-width: min(92%, 520px);
  padding: 0.55rem 0.9rem;
  border-radius: 12px;
  text-align: center;
  background: rgba(15, 23, 42, 0.9);
  border: 1px solid rgba(239, 68, 68, 0.35);
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.35);
  pointer-events: none;
}

.spectator-title {
  font-size: 0.85rem;
  font-weight: 700;
  color: #fecaca;
}

.spectator-meta {
  font-size: 0.72rem;
  color: #cbd5e1;
}

.draft-explainer {
  max-width: 420px;
  margin: 0 0 0.5rem;
}

.draft-tier-group {
  margin-top: 0.65rem;
  width: 100%;
  max-width: 560px;
}

.draft-tier-label {
  display: block;
  font-size: 0.72rem;
  font-weight: 700;
  letter-spacing: 0.04em;
  text-transform: uppercase;
  color: #94a3b8;
  margin-bottom: 0.35rem;
}

.draft-btn {
  display: inline-flex;
  align-items: center;
  gap: 0.35rem;
}

.draft-btn.banned {
  opacity: 0.45;
}

.draft-icon {
  font-size: 1rem;
}

.draft-banned-tag {
  font-size: 0.62rem;
  text-transform: uppercase;
}

.draft-progress {
  font-size: 0.85rem;
  font-weight: 600;
  color: #e2e8f0;
}

.recap-row.winner {
  border-left: 3px solid #fbbf24;
  padding-left: 0.5rem;
  background: rgba(251, 191, 36, 0.08);
  border-radius: 6px;
}

.disconnect-note {
  margin: 0;
  font-size: 0.9rem;
  color: #fca5a5;
}

.milestones-note {
  display: block;
  font-size: 0.72rem;
  color: var(--text-muted);
  margin-bottom: 0.35rem;
}

.milestone-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 0.35rem;
  justify-content: center;
}

.milestone-chip {
  padding: 0.2rem 0.55rem;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.06);
  border: 1px solid rgba(255, 255, 255, 0.1);
  font-size: 0.75rem;
}

.guest-finished {
  flex-direction: column;
  align-items: center;
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

.touch-actions {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 0.45rem;
  pointer-events: auto;
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
  width: 4rem;
  height: 4rem;
  border-radius: 999px;
  font-size: 1.35rem;
  border-color: rgba(251, 191, 36, 0.45);
  color: #fde68a;
}

.touch-powerup {
  width: 3.4rem;
  height: 3.4rem;
  border-radius: 999px;
  font-size: 1.2rem;
  border-color: rgba(168, 85, 247, 0.45);
  color: #e9d5ff;
}

.touch-powerup:disabled {
  opacity: 0.45;
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

.powerup-charges-badge {
  font-size: 0.72rem;
  font-weight: 800;
  padding: 0.1rem 0.4rem;
  border-radius: 999px;
  background: rgba(251, 146, 60, 0.2);
  color: #fdba74;
  border: 1px solid rgba(251, 146, 60, 0.35);
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

.overlay.finished {
  gap: 1rem;
  overflow: hidden;
}

.match-confetti {
  pointer-events: none;
  position: absolute;
  inset: 0;
  overflow: hidden;
}

.confetti-piece {
  position: absolute;
  top: -8%;
  left: calc((var(--i) * 3.7%) + 1%);
  width: 8px;
  height: 14px;
  border-radius: 2px;
  opacity: 0.85;
  animation: confettiFall 3.2s linear infinite;
  animation-delay: calc(var(--i) * -0.12s);
  background: hsl(calc(var(--i) * 13), 85%, 62%);
}

.match-outcome-banner {
  position: relative;
  z-index: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 0.25rem;
  padding: 0.85rem 1.25rem;
  border-radius: 16px;
  border: 1px solid rgba(255, 255, 255, 0.12);
  background: rgba(15, 23, 42, 0.55);
  animation: popIn 0.5s cubic-bezier(0.34, 1.56, 0.64, 1);
}

.match-outcome-banner.victory {
  border-color: rgba(251, 191, 36, 0.55);
  box-shadow: 0 0 40px rgba(251, 191, 36, 0.25);
}

.match-outcome-banner.defeat {
  border-color: rgba(148, 163, 184, 0.35);
}

.match-outcome-banner.draw {
  border-color: rgba(96, 165, 250, 0.4);
}

.match-outcome-icon {
  font-size: 2.25rem;
  line-height: 1;
}

.match-outcome-headline {
  font-size: clamp(1.85rem, 5vw, 2.75rem);
  font-weight: 800;
  letter-spacing: -0.02em;
}

.match-outcome-banner.victory .match-outcome-headline {
  background: linear-gradient(135deg, #fde68a, #fbbf24, #f59e0b);
  -webkit-background-clip: text;
  background-clip: text;
  color: transparent;
  animation: winnerGlow 2.2s ease-in-out infinite;
}

.match-outcome-sub {
  font-size: 0.95rem;
  color: #cbd5e1;
}

.match-outcome-score {
  margin-top: 0.15rem;
  font-size: 0.85rem;
  font-weight: 600;
  color: #94a3b8;
}

.match-podium {
  position: relative;
  z-index: 1;
  display: flex;
  flex-wrap: wrap;
  justify-content: center;
  gap: 0.75rem;
  width: min(100%, 520px);
}

.podium-card {
  position: relative;
  display: flex;
  align-items: center;
  gap: 0.75rem;
  flex: 1 1 220px;
  padding: 0.85rem 1rem;
  border-radius: 14px;
  border: 1px solid rgba(148, 163, 184, 0.25);
  background: rgba(15, 23, 42, 0.65);
  animation: slideIn 0.45s ease-out both;
}

.podium-card.winner {
  flex: 1 1 100%;
  transform: scale(1.02);
  border-color: color-mix(in srgb, var(--podium-color, #fbbf24) 65%, white);
  background: linear-gradient(
    135deg,
    color-mix(in srgb, var(--podium-color, #fbbf24) 22%, transparent),
    rgba(15, 23, 42, 0.75)
  );
  box-shadow:
    0 0 0 1px color-mix(in srgb, var(--podium-color, #fbbf24) 35%, transparent),
    0 12px 36px color-mix(in srgb, var(--podium-color, #fbbf24) 25%, transparent);
  animation: podiumWinnerIn 0.55s cubic-bezier(0.34, 1.56, 0.64, 1) both;
}

.podium-card.runner {
  opacity: 0.72;
  filter: saturate(0.85);
}

.podium-card.me:not(.winner) {
  border-color: rgba(91, 156, 255, 0.35);
}

.podium-crown {
  position: absolute;
  top: -0.65rem;
  left: 50%;
  transform: translateX(-50%);
  font-size: 1.35rem;
  filter: drop-shadow(0 2px 6px rgba(0, 0, 0, 0.45));
  animation: crownBob 1.8s ease-in-out infinite;
}

.podium-avatar {
  width: 32px;
  height: 22px;
  flex-shrink: 0;
}

.podium-copy {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 0.15rem;
  min-width: 0;
}

.podium-name-row {
  display: flex;
  align-items: center;
  gap: 0.4rem;
}

.podium-name {
  font-size: 1.05rem;
}

.podium-you {
  font-size: 0.65rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  padding: 0.1rem 0.35rem;
  border-radius: 999px;
  background: rgba(91, 156, 255, 0.2);
  color: #93c5fd;
}

.podium-score {
  font-size: 0.88rem;
  color: #cbd5e1;
}

.podium-badge {
  font-size: 0.72rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: #fde68a;
}

.podium-badge.muted {
  color: #94a3b8;
  font-weight: 600;
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

.hp-text {
  font-size: 0.72rem;
  font-weight: 700;
  color: #fca5a5;
  margin-left: 0.15rem;
}

.effect-chip {
  display: inline-flex;
  align-items: center;
  gap: 0.2rem;
  padding: 0.12rem 0.4rem;
  border-radius: 999px;
  border: 1px solid rgba(255, 255, 255, 0.12);
  background: rgba(15, 23, 42, 0.55);
  font-size: 0.65rem;
  font-weight: 600;
  color: #e2e8f0;
}

.effect-chip-time {
  opacity: 0.75;
  font-weight: 500;
}

.effect-chip.fog-chip {
  border-color: rgba(148, 163, 184, 0.35);
  color: #cbd5e1;
}

.effect-chip.stored {
  border-color: rgba(251, 191, 36, 0.35);
}

.controls-hint .inline-link {
  border: none;
  background: transparent;
  color: var(--accent);
  font-size: inherit;
  padding: 0;
  cursor: pointer;
  text-decoration: underline;
}

.rules-link {
  margin-top: 0.15rem;
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

@keyframes confettiFall {
  0% {
    transform: translate3d(0, -10vh, 0) rotate(0deg);
    opacity: 0;
  }
  10% {
    opacity: 0.9;
  }
  100% {
    transform: translate3d(calc((var(--i) - 14) * 8px), 110vh, 0) rotate(720deg);
    opacity: 0.2;
  }
}

@keyframes podiumWinnerIn {
  from {
    opacity: 0;
    transform: scale(0.92) translateY(12px);
  }
  to {
    opacity: 1;
    transform: scale(1.02) translateY(0);
  }
}

@keyframes crownBob {
  0%, 100% { transform: translateX(-50%) translateY(0); }
  50% { transform: translateX(-50%) translateY(-4px); }
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

@media (max-width: 900px) {
  .duel-board {
    padding: 0 0.35rem 0.35rem;
  }

  .match-bar {
    gap: 0.4rem;
  }

  .toggle-label {
    display: none;
  }

  .powerup-slot {
    max-width: min(94%, 280px);
    font-size: 0.85rem;
  }

  .active-buffs {
    max-width: min(58%, 200px);
  }
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
