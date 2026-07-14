<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import type { Room, PokerGameState } from '@/types'
import PlayingCard from './PlayingCard.vue'
import { pokerReactionEmojis, type PokerReaction } from './reactions'
import {
  disposeSounds,
  isSoundMuted,
  playActionSound,
  playBurnCard,
  playDealCard,
  playShowdownFlip,
  playStreetReveal,
  playWin,
  playYourTurn,
  setSoundMuted,
  unlockAudio,
} from './sounds'

const CARD_REVEAL_MS = 380
const TURN_DELAY_MS = 1100
const ACTION_HOLD_MS = 1500
const SHOWDOWN_REVEAL_MS = 500
const PHASE_BANNER_MS = 1100
const BURN_CARD_MS = 350
const FOLD_ANIM_MS = 900
const ROUND_CIRCLE_PAUSE_MS = 400
const POST_DEAL_PAUSE_MS = 700
const POST_STREET_PAUSE_MS = 600

const props = defineProps<{
  gameState: PokerGameState
  room: Room
  playerId: string
  reactions: PokerReaction[]
}>()

const emit = defineEmits<{
  action: [data: Record<string, unknown>]
  reaction: [emoji: string]
}>()

const raiseAmount = ref(0)
const displayedCommunityCount = ref(0)
const holeCardsRevealed = ref<Record<string, number>>({})
const showdownRevealed = ref<Set<string>>(new Set())
const effectiveCurrentActorId = ref<string | null>(null)
const lastDealtCommunityIndex = ref(-1)
const lastDealtHoleKey = ref('')
const dealInProgress = ref(false)
const bettingRoundReady = ref(false)
const showdownRevealStarted = ref(false)
const displayedPot = ref(0)
const phaseBanner = ref<{ text: string; visible: boolean }>({ text: '', visible: false })
const actionHighlightId = ref<string | null>(null)
const seatActionLabel = ref<{ playerId: string; text: string; type: string } | null>(null)
const foldingSeats = ref<Set<string>>(new Set())
const betPulseSeats = ref<Set<string>>(new Set())
const actionHoldUntil = ref(0)
const actionHoldActive = ref(false)
const streetTransitionPending = ref(false)
const soundMuted = ref(isSoundMuted())
const suppressSounds = ref(true)
const reactionCooldown = ref(false)
const chipFlies = ref<{ id: string; seatId: string }[]>([])
const potRising = ref(false)
const burnCardVisible = ref(false)
const communityPulse = ref(false)

function toggleSound() {
  const next = !soundMuted.value
  setSoundMuted(next)
  soundMuted.value = next
  if (!next) void unlockAudio()
}

function playSfx(fn: () => void) {
  if (suppressSounds.value || soundMuted.value) return
  fn()
}

const timers = new Set<ReturnType<typeof setTimeout>>()

function schedule(fn: () => void, ms: number) {
  const id = setTimeout(() => {
    timers.delete(id)
    fn()
  }, ms)
  timers.add(id)
  return id
}

function clearAllTimers() {
  for (const id of timers) clearTimeout(id)
  timers.clear()
}

const isHost = computed(() => props.room.host_player_id === props.playerId)
const myPlayer = computed(() => props.gameState.players.find((p) => p.id === props.playerId))
const isMyTurn = computed(() => effectiveCurrentActorId.value === props.playerId)

const dealerPlayer = computed(() =>
  props.gameState.players.find((p) => p.id === props.gameState.dealer_player_id),
)

const eligibleSeatIds = computed(() =>
  props.gameState.seat_order.filter((id) => {
    const player = props.gameState.players.find((p) => p.id === id)
    return player && player.status !== 'eliminated'
  }),
)

function nextEligibleAfter(seatId: string): string | null {
  const order = props.gameState.seat_order
  const eligible = eligibleSeatIds.value
  const fromIdx = order.indexOf(seatId)
  if (fromIdx < 0) return null
  for (let i = 1; i <= order.length; i++) {
    const id = order[(fromIdx + i) % order.length]
    if (eligible.includes(id)) return id
  }
  return null
}

const blindRoles = computed(() => {
  const dealerId = props.gameState.dealer_player_id
  if (!dealerId) return { sb: null as string | null, bb: null as string | null }
  const eligible = eligibleSeatIds.value
  if (eligible.length < 2) return { sb: null, bb: null }
  if (eligible.length === 2) {
    return { sb: dealerId, bb: nextEligibleAfter(dealerId) }
  }
  const sb = nextEligibleAfter(dealerId)
  const bb = sb ? nextEligibleAfter(sb) : null
  return { sb, bb }
})

const dealOrder = computed(() => {
  const order = props.gameState.seat_order
  const eligible = eligibleSeatIds.value
  const startId = blindRoles.value.sb ?? props.gameState.dealer_player_id
  if (!startId) return eligible
  const startIdx = order.indexOf(startId)
  const rotated: string[] = []
  for (let i = 0; i < order.length; i++) {
    const id = order[(startIdx + i) % order.length]
    if (eligible.includes(id)) rotated.push(id)
  }
  return rotated
})

const visibleCommunityCards = computed(() =>
  props.gameState.community_cards.slice(0, displayedCommunityCount.value),
)

const communityStreetLabel = computed(() => {
  const count = displayedCommunityCount.value
  const target = props.gameState.community_cards.length
  if (!streetTransitionPending.value) return ''
  if (count < 3 && target >= 3) return 'Dealing the flop — 3 cards'
  if (count < 4 && target >= 4) return 'Dealing the turn'
  if (count < 5 && target >= 5) return 'Dealing the river'
  return 'Burning a card…'
})

const showHandDescriptions = computed(
  () =>
    props.gameState.phase === 'showdown' ||
    props.gameState.phase === 'hand_complete' ||
    showdownRevealed.value.size > 0,
)
const phaseLabel = computed(() => {
  const map: Record<string, string> = {
    preflop: 'Pre-flop',
    flop: 'Flop',
    turn: 'Turn',
    river: 'River',
    showdown: 'Showdown',
    hand_complete: 'Hand complete',
    game_over: 'Game over',
  }
  return map[props.gameState.phase] ?? props.gameState.phase
})

const winnerSeatIds = computed(() => {
  const ids = new Set(props.gameState.winners.map((winner) => winner.player_id))
  if (props.gameState.phase === 'game_over' && props.gameState.winner) {
    ids.add(props.gameState.winner)
  }
  return ids
})

const iWonHand = computed(() => winnerSeatIds.value.has(props.playerId))

const winnerCallout = computed(() => {
  if (props.gameState.phase === 'game_over' && props.gameState.winner) {
    const name =
      props.gameState.players.find((player) => player.id === props.gameState.winner)?.nickname ??
      'Player'
    return {
      type: 'game' as const,
      eyebrow: 'Game over',
      title: `${name} wins!`,
      entries: [] as { playerId: string; name: string; amount: number; hand: string | null }[],
    }
  }

  if (props.gameState.phase === 'hand_complete' && props.gameState.winners.length) {
    const aggregated = new Map<
      string,
      { playerId: string; name: string; amount: number; hand: string | null }
    >()

    for (const winner of props.gameState.winners) {
      const name =
        props.gameState.players.find((player) => player.id === winner.player_id)?.nickname ??
        'Player'
      const hand = winner.hand ? winner.hand.replace(/_/g, ' ') : null
      const existing = aggregated.get(winner.player_id)
      if (existing) {
        existing.amount += winner.amount
        if (!existing.hand && hand) existing.hand = hand
      } else {
        aggregated.set(winner.player_id, {
          playerId: winner.player_id,
          name,
          amount: winner.amount,
          hand,
        })
      }
    }

    const entries = [...aggregated.values()]
    const totalPot = entries.reduce((sum, entry) => sum + entry.amount, 0)
    const isSplitPot =
      entries.length > 1 &&
      entries.every((entry) => entry.amount === entries[0].amount && entry.hand === entries[0].hand)

    let title: string
    if (entries.length === 1) {
      title = `${entries[0].name} wins ${entries[0].amount}!`
    } else if (isSplitPot) {
      title = `Split pot — ${totalPot} chips`
    } else {
      title = entries.map((entry) => `${entry.name} +${entry.amount}`).join(' · ')
    }

    return {
      type: 'hand' as const,
      eyebrow: entries.length === 1 ? 'Winner' : isSplitPot ? 'Split pot' : 'Winners',
      title,
      entries,
    }
  }

  return null
})

const lastActionText = computed(() => seatActionLabel.value?.text ?? '')

function actionLabelFor(action: Record<string, unknown>): string {
  const player = props.gameState.players.find((p) => p.id === action.player_id)
  const name = player?.nickname ?? 'Player'
  switch (action.type) {
    case 'fold':
      return `${name} folded`
    case 'check':
      return `${name} checked`
    case 'call':
      return `${name} called ${action.amount}`
    case 'raise':
      return `${name} raised to ${action.amount}`
    case 'all_in':
      return `${name} went all-in (${action.amount})`
    default:
      return ''
  }
}

function seatActionBubble(seatId: string): string | null {
  if (seatActionLabel.value?.playerId !== seatId) return null
  const action = props.gameState.last_action
  if (!action) return null
  switch (action.type) {
    case 'fold':
      return 'Fold'
    case 'check':
      return 'Check'
    case 'call':
      return `Call ${action.amount}`
    case 'raise':
      return `Raise ${action.amount}`
    case 'all_in':
      return `All-in ${action.amount}`
    default:
      return null
  }
}

function showPhaseBanner(phase: string) {
  const labels: Record<string, string> = {
    preflop: 'Pre-flop',
    flop: 'The Flop',
    turn: 'The Turn',
    river: 'The River',
    showdown: 'Showdown',
    hand_complete: 'Hand Complete',
    game_over: 'Game Over',
  }
  if (phase === 'flop' || phase === 'turn' || phase === 'river') {
    playSfx(() => playStreetReveal(phase))
  }
  phaseBanner.value = { text: labels[phase] ?? phase, visible: true }
  schedule(() => {
    phaseBanner.value = { ...phaseBanner.value, visible: false }
  }, PHASE_BANNER_MS)
}

function animatePotTo(target: number) {
  const start = displayedPot.value
  const diff = target - start
  if (diff === 0) return
  const steps = Math.min(Math.max(Math.abs(diff), 1), 24)
  const stepMs = 45
  potRising.value = true
  for (let i = 1; i <= steps; i++) {
    schedule(() => {
      displayedPot.value = Math.round(start + (diff * i) / steps)
    }, i * stepMs)
  }
  schedule(() => {
    potRising.value = false
  }, steps * stepMs + 80)
}

function holdForAction() {
  actionHoldActive.value = true
  actionHoldUntil.value = Date.now() + ACTION_HOLD_MS
  schedule(() => {
    actionHoldActive.value = false
  }, ACTION_HOLD_MS)
}

function msUntilActionHoldDone(): number {
  return Math.max(0, actionHoldUntil.value - Date.now())
}

const canAct = computed(
  () =>
    !dealInProgress.value &&
    bettingRoundReady.value &&
    !streetTransitionPending.value &&
    !actionHoldActive.value &&
    isMyTurn.value &&
    myPlayer.value?.status === 'active' &&
    ['preflop', 'flop', 'turn', 'river'].includes(props.gameState.phase) &&
    effectiveCurrentActorId.value === props.gameState.current_actor_id,
)

const raisePanelOpen = ref(false)

const isWaitingForTurn = computed(
  () =>
    !canAct.value && ['preflop', 'flop', 'turn', 'river'].includes(props.gameState.phase),
)

const showNextHandControl = computed(
  () =>
    props.gameState.phase === 'hand_complete' && isHost.value && !props.gameState.winner,
)

watch(canAct, (active) => {
  if (!active) raisePanelOpen.value = false
})

function visibleHoleCount(seatId: string): number {
  return holeCardsRevealed.value[seatId] ?? 0
}

function showHoleCardFaceUp(seatId: string): boolean {
  return seatId === props.playerId || showdownRevealed.value.has(seatId)
}

function shouldAnimateHoleCard(seatId: string, cardIndex: number): boolean {
  const key = `${props.gameState.hand_number}-${seatId}-${cardIndex}`
  if (lastDealtHoleKey.value === key) return true
  return false
}

function shouldAnimateCommunityCard(slot: number): boolean {
  return lastDealtCommunityIndex.value === slot - 1
}

function chipFlyStyle(seatId: string): Record<string, string> {
  const seat = seatPositions.value.find((entry) => entry.id === seatId)
  if (!seat) return {}
  return {
    '--start-x': `${seat.x}%`,
    '--start-y': `${seat.y}%`,
    left: `${seat.x}%`,
    top: `${seat.y}%`,
  }
}

function triggerChipFly(seatId: string) {
  const id = `${seatId}-${Date.now()}`
  chipFlies.value = [...chipFlies.value, { id, seatId }]
  schedule(() => {
    chipFlies.value = chipFlies.value.filter((entry) => entry.id !== id)
  }, 720)
}

function resetHandAnimations() {
  displayedCommunityCount.value = 0
  holeCardsRevealed.value = {}
  showdownRevealed.value = new Set()
  lastDealtCommunityIndex.value = -1
  lastDealtHoleKey.value = ''
  showdownRevealStarted.value = false
  actionHighlightId.value = null
  seatActionLabel.value = null
  foldingSeats.value = new Set()
  betPulseSeats.value = new Set()
  actionHoldUntil.value = 0
  actionHoldActive.value = false
  streetTransitionPending.value = false
  bettingRoundReady.value = false
  displayedPot.value = props.gameState.pot_total
  chipFlies.value = []
  potRising.value = false
  burnCardVisible.value = false
  communityPulse.value = false
}

function syncHandStateFromServer() {
  const gs = props.gameState
  const holeRevealed: Record<string, number> = {}

  if (gs.hand_number > 0) {
    for (const seatId of gs.seat_order) {
      const player = gs.players.find((p) => p.id === seatId)
      if (player && player.status !== 'eliminated') {
        holeRevealed[seatId] = 2
      }
    }
  }

  holeCardsRevealed.value = holeRevealed
  displayedCommunityCount.value = gs.community_cards.length
  displayedPot.value = gs.pot_total
  dealInProgress.value = false
  bettingRoundReady.value = gs.hand_number > 0
  streetTransitionPending.value = false
  effectiveCurrentActorId.value = gs.current_actor_id
  lastDealtHoleKey.value = ''
  lastDealtCommunityIndex.value = -1
  showdownRevealStarted.value = false
  showdownRevealed.value = new Set()

  if (['showdown', 'hand_complete', 'game_over'].includes(gs.phase)) {
    showdownRevealStarted.value = true
    const revealed = new Set<string>()
    for (const player of gs.players) {
      if (
        player.id !== props.playerId &&
        player.status !== 'folded' &&
        player.hole_cards.length >= 2
      ) {
        revealed.add(player.id)
      }
    }
    showdownRevealed.value = revealed
  }
}

function highlightActor(actorId: string | null, delayMs: number) {
  if (!actorId) {
    effectiveCurrentActorId.value = null
    return
  }
  effectiveCurrentActorId.value = null
  schedule(() => {
    effectiveCurrentActorId.value = actorId
    if (actorId === props.playerId) playSfx(playYourTurn)
  }, delayMs)
}

function runHoleCardDealAnimation() {
  const order = dealOrder.value
  if (!order.length) {
    dealInProgress.value = false
    bettingRoundReady.value = true
    return
  }
  dealInProgress.value = true
  bettingRoundReady.value = false
  let delay = 0
  for (let round = 0; round < 2; round++) {
    if (round > 0) {
      delay += ROUND_CIRCLE_PAUSE_MS
    }
    for (const seatId of order) {
      delay += CARD_REVEAL_MS
      const cardIndex = round + 1
      schedule(() => {
        const current = holeCardsRevealed.value[seatId] ?? 0
        if (current < cardIndex) {
          holeCardsRevealed.value = { ...holeCardsRevealed.value, [seatId]: cardIndex }
          lastDealtHoleKey.value = `${props.gameState.hand_number}-${seatId}-${cardIndex}`
          playSfx(playDealCard)
        }
      }, delay)
    }
  }
  schedule(() => {
    dealInProgress.value = false
    schedule(() => {
      bettingRoundReady.value = true
      highlightActor(props.gameState.current_actor_id, TURN_DELAY_MS)
    }, POST_DEAL_PAUSE_MS)
  }, delay + CARD_REVEAL_MS)
}

function finishStreetDeal() {
  streetTransitionPending.value = false
  communityPulse.value = false
  schedule(() => {
    if (props.gameState.current_actor_id) {
      highlightActor(props.gameState.current_actor_id, TURN_DELAY_MS)
    }
  }, POST_STREET_PAUSE_MS)
}

function animateCommunityCards(targetCount: number) {
  const current = displayedCommunityCount.value
  if (targetCount <= current) {
    displayedCommunityCount.value = targetCount
    streetTransitionPending.value = false
    return
  }

  const milestones = [3, 4, 5].filter((m) => m > current && m <= targetCount)
  if (milestones.length === 0) {
    communityPulse.value = true
    let delay = 0
    for (let i = current + 1; i <= targetCount; i++) {
      delay += CARD_REVEAL_MS
      const index = i
      schedule(() => {
        displayedCommunityCount.value = index
        lastDealtCommunityIndex.value = index - 1
        playSfx(playDealCard)
      }, delay)
    }
    schedule(finishStreetDeal, delay + CARD_REVEAL_MS)
    return
  }

  streetTransitionPending.value = true
  communityPulse.value = true
  let delay = 0
  let revealedUpTo = current

  for (const milestone of milestones) {
    const street = milestone === 3 ? 'flop' : milestone === 4 ? 'turn' : 'river'
    showPhaseBanner(street)
    schedule(() => playSfx(playBurnCard), delay + PHASE_BANNER_MS)
    delay += PHASE_BANNER_MS
    schedule(() => {
      burnCardVisible.value = true
      schedule(() => {
        burnCardVisible.value = false
      }, BURN_CARD_MS)
    }, delay)
    delay += BURN_CARD_MS

    for (let index = revealedUpTo + 1; index <= milestone; index++) {
      delay += CARD_REVEAL_MS
      schedule(() => {
        displayedCommunityCount.value = index
        lastDealtCommunityIndex.value = index - 1
        playSfx(playDealCard)
      }, delay)
    }
    revealedUpTo = milestone
  }

  schedule(finishStreetDeal, delay + CARD_REVEAL_MS)
}

function runShowdownReveal() {
  if (showdownRevealStarted.value) return
  showdownRevealStarted.value = true
  const contenders = dealOrder.value.filter((id) => {
    const player = props.gameState.players.find((p) => p.id === id)
    return player && player.status !== 'folded'
  })
  let delay = CARD_REVEAL_MS
  for (const seatId of contenders) {
    if (seatId === props.playerId) continue
    schedule(() => {
      showdownRevealed.value = new Set([...showdownRevealed.value, seatId])
      playSfx(playShowdownFlip)
    }, delay)
    delay += SHOWDOWN_REVEAL_MS
  }
}

const seatPositions = computed(() => {
  const order = props.gameState.seat_order
  const myIndex = order.indexOf(props.playerId)
  const rotated = [...order.slice(myIndex), ...order.slice(0, myIndex)]
  const count = rotated.length
  const radiusByCount =
    count <= 2
      ? { x: 38, y: 34 }
      : count <= 4
        ? { x: 44, y: 40 }
        : count <= 5
          ? { x: 42, y: 38 }
          : { x: 40, y: 36 }
  return rotated.map((id, visualIndex) => {
    const player = props.gameState.players.find((p) => p.id === id)
    const angle = (visualIndex / rotated.length) * 360 + 90
    const x = 50 + radiusByCount.x * Math.cos((angle * Math.PI) / 180)
    const y = 50 + radiusByCount.y * Math.sin((angle * Math.PI) / 180)
    return { id, player, x, y, visualIndex, playerCount: count }
  })
})

function snapToRaiseOption(target: number, options: number[]): number | null {
  if (!options.length) return null
  const legal = options.filter((amount) => amount >= target)
  if (legal.length) return legal[0]
  return options[options.length - 1]
}

const raiseOptions = computed(() => props.gameState.raise_options ?? [])

const raisePresets = computed(() => {
  const options = raiseOptions.value
  if (!options.length) return []

  const bb = props.gameState.raise_increment || 10
  const pot = props.gameState.pot_total
  const currentBet = props.gameState.current_bet
  const candidates = [
    { label: 'Min', target: options[0] },
    { label: '2× BB', target: currentBet + bb * 2 },
    { label: '3× BB', target: currentBet + bb * 3 },
    { label: '½ Pot', target: currentBet + Math.floor(pot / 2) },
    { label: 'Pot', target: currentBet + pot + props.gameState.bet_to_call },
  ]

  const seen = new Set<number>()
  const presets: { label: string; amount: number }[] = []
  for (const candidate of candidates) {
    const amount =
      candidate.label === 'Min'
        ? candidate.target
        : snapToRaiseOption(candidate.target, options)
    if (amount == null || seen.has(amount)) continue
    seen.add(amount)
    presets.push({ label: candidate.label, amount })
  }
  return presets
})

function syncRaiseDefault() {
  const options = raiseOptions.value
  raiseAmount.value = options[0] ?? props.gameState.min_raise_to
}

function selectRaise(amount: number) {
  raiseAmount.value = amount
  raise()
}

function fold() {
  void unlockAudio()
  emit('action', { type: 'fold' })
}

function check() {
  void unlockAudio()
  emit('action', { type: 'check' })
}

function call() {
  void unlockAudio()
  emit('action', { type: 'call' })
}

function raise() {
  void unlockAudio()
  emit('action', { type: 'raise', amount: raiseAmount.value })
}

function allIn() {
  void unlockAudio()
  emit('action', { type: 'all_in' })
}

function nextHand() {
  void unlockAudio()
  emit('action', { type: 'next_hand' })
}

function sendReaction(emoji: string) {
  if (reactionCooldown.value) return
  reactionCooldown.value = true
  emit('reaction', emoji)
  schedule(() => {
    reactionCooldown.value = false
  }, 1500)
}

function reactionsForSeat(seatId: string): PokerReaction[] {
  return props.reactions.filter((reaction) => reaction.playerId === seatId)
}

watch(
  () => props.gameState.hand_number,
  (handNum, prevHandNum) => {
    clearAllTimers()
    if (prevHandNum === undefined) {
      syncHandStateFromServer()
      return
    }
    resetHandAnimations()
    if (handNum > 0) {
      showPhaseBanner('preflop')
      schedule(() => runHoleCardDealAnimation(), PHASE_BANNER_MS * 0.5)
    } else {
      runHoleCardDealAnimation()
    }
  },
  { immediate: true },
)

watch(
  () => props.gameState.community_cards.length,
  (communityCount, prevCount) => {
    if (prevCount === undefined) {
      displayedCommunityCount.value = communityCount
      return
    }
    if (communityCount < displayedCommunityCount.value) {
      displayedCommunityCount.value = communityCount
      return
    }
    if (communityCount <= displayedCommunityCount.value) return
    animateCommunityCards(communityCount)
  },
  { immediate: true },
)

watch(
  () => props.gameState.phase,
  (phase, oldPhase) => {
    if (!oldPhase || phase === oldPhase) return
    if (phase === 'showdown' || phase === 'hand_complete') {
      showPhaseBanner(phase)
      runShowdownReveal()
      if (phase === 'hand_complete' && winnerSeatIds.value.has(props.playerId)) {
        playSfx(playWin)
      }
    } else if (phase === 'game_over') {
      showPhaseBanner(phase)
    }
  },
)

watch(
  () => props.gameState.last_action,
  (action, prev) => {
    if (!action) return
    const prevKey = prev ? `${prev.player_id}-${prev.type}-${prev.amount ?? ''}` : ''
    const nextKey = `${action.player_id}-${action.type}-${action.amount ?? ''}`
    if (prevKey === nextKey) return
    if (!prev && suppressSounds.value) return

    const playerId = String(action.player_id)
    const text = actionLabelFor(action)
    seatActionLabel.value = { playerId, text, type: String(action.type) }
    actionHighlightId.value = playerId
    holdForAction()
    playSfx(() => playActionSound(String(action.type)))

    if (action.type === 'fold') {
      foldingSeats.value = new Set([...foldingSeats.value, playerId])
      schedule(() => {
        const next = new Set(foldingSeats.value)
        next.delete(playerId)
        foldingSeats.value = next
      }, FOLD_ANIM_MS)
    }

    if (['call', 'raise', 'all_in'].includes(String(action.type))) {
      betPulseSeats.value = new Set([...betPulseSeats.value, playerId])
      triggerChipFly(playerId)
      schedule(() => {
        const next = new Set(betPulseSeats.value)
        next.delete(playerId)
        betPulseSeats.value = next
      }, ACTION_HOLD_MS)
    }

    schedule(() => {
      if (seatActionLabel.value?.playerId === playerId) {
        seatActionLabel.value = null
      }
      if (actionHighlightId.value === playerId) {
        actionHighlightId.value = null
      }
    }, ACTION_HOLD_MS)
  },
)

watch(
  () => props.gameState.pot_total,
  (target, prev) => {
    if (prev === undefined) {
      displayedPot.value = target
      return
    }
    animatePotTo(target)
  },
  { immediate: true },
)

watch(
  () => props.gameState.current_actor_id,
  (newId, oldId) => {
    if (dealInProgress.value || !bettingRoundReady.value) return
    if (!newId) {
      effectiveCurrentActorId.value = null
      return
    }
    if (oldId === newId) return

    const delay = Math.max(TURN_DELAY_MS, msUntilActionHoldDone())
    highlightActor(newId, delay)
  },
)

watch(
  () => props.gameState.raise_options,
  (options) => {
    if (!options?.length) return
    if (!options.includes(raiseAmount.value)) {
      raiseAmount.value = options[0]
    }
  },
  { immediate: true },
)

onMounted(() => {
  schedule(() => {
    suppressSounds.value = false
  }, 300)
})

onUnmounted(() => {
  clearAllTimers()
  disposeSounds()
})
</script>

<template>
  <div
    class="poker-board"
    :class="{ 'poker-board--acting': canAct, 'poker-board--waiting': isWaitingForTurn }"
  >
    <div class="status-bar card">
      <div class="status-pills">
        <span class="status-pill status-pill--hand">Hand #{{ gameState.hand_number }}</span>
        <Transition name="phase-pill" mode="out-in">
          <span :key="phaseLabel" class="status-pill status-pill--phase">{{ phaseLabel }}</span>
        </Transition>
        <span v-if="dealerPlayer" class="status-pill status-pill--dealer">
          Dealer <strong>{{ dealerPlayer.nickname }}</strong>
        </span>
      </div>
      <div class="status-bar__right">
        <div class="status-pot" :class="{ 'status-pot--rising': potRising }">
          <span class="status-pot__chip" aria-hidden="true" />
          <span class="status-pot__label">Pot</span>
          <strong class="status-pot__amount">{{ displayedPot }}</strong>
        </div>
        <button
          type="button"
          class="sound-toggle"
          :aria-label="soundMuted ? 'Unmute sound' : 'Mute sound'"
          :title="soundMuted ? 'Unmute' : 'Mute'"
          @click="toggleSound"
        >
          {{ soundMuted ? '🔇' : '🔊' }}
        </button>
      </div>
    </div>

    <div class="poker-layout">
      <div class="table-column">
        <p
          v-if="lastActionText"
          class="last-action last-action--table"
          :class="{ 'last-action--pop': actionHoldActive }"
        >
          {{ lastActionText }}
        </p>

        <div class="table-wrap">
          <div class="table-room-glow" aria-hidden="true" />
          <div
            class="table-felt"
            :class="{
              'table-felt--spotlight': canAct,
              'table-felt--dealing': streetTransitionPending || communityPulse,
            }"
          >
        <Transition name="burn-flash">
          <div v-if="burnCardVisible" class="burn-card-flash" aria-hidden="true">
            <PlayingCard face-down small />
            <span class="burn-card-flash__label">Burn</span>
          </div>
        </Transition>

        <TransitionGroup name="chip-fly" tag="div" class="chip-fly-layer" aria-hidden="true">
          <div
            v-for="fly in chipFlies"
            :key="fly.id"
            class="chip-fly"
            :style="chipFlyStyle(fly.seatId)"
          />
        </TransitionGroup>
        <Transition name="phase-banner">
          <div v-if="phaseBanner.visible" class="phase-banner">{{ phaseBanner.text }}</div>
        </Transition>

        <Transition name="burn-hint">
          <div v-if="streetTransitionPending && communityStreetLabel" class="burn-hint">
            {{ communityStreetLabel }}
          </div>
        </Transition>

        <Transition name="winner-banner">
          <div v-if="winnerCallout" class="winner-overlay" role="status" aria-live="polite">
            <div class="winner-sparkles" aria-hidden="true">
              <span v-for="n in 14" :key="n" class="sparkle" :style="{ '--i': n }" />
            </div>
            <div class="winner-banner" :class="`winner-banner--${winnerCallout.type}`">
              <p class="winner-banner__eyebrow">{{ winnerCallout.eyebrow }}</p>
              <h2 class="winner-banner__title">{{ winnerCallout.title }}</h2>
              <ul v-if="winnerCallout.entries.length > 1" class="winner-banner__list">
                <li v-for="entry in winnerCallout.entries" :key="entry.playerId">
                  <strong>{{ entry.name }}</strong>
                  <span class="winner-banner__amount">+{{ entry.amount }}</span>
                  <span v-if="entry.hand" class="winner-banner__hand">{{ entry.hand }}</span>
                </li>
              </ul>
              <p
                v-else-if="winnerCallout.entries.length === 1 && winnerCallout.entries[0].hand"
                class="winner-banner__hand winner-banner__hand--solo"
              >
                {{ winnerCallout.entries[0].hand }}
              </p>
              <p v-if="iWonHand && winnerCallout.type === 'hand'" class="winner-banner__you">
                You won this hand!
              </p>
            </div>
          </div>
        </Transition>

        <div class="table-center">
          <div
            class="community-zone"
            :class="{ 'community-zone--pulse': communityPulse || streetTransitionPending }"
          >
            <div class="community">
            <div
              v-for="slot in 5"
              :key="`c-${gameState.hand_number}-${slot}`"
              class="community-slot"
              :class="{ 'community-slot--live': slot <= displayedCommunityCount }"
            >
              <PlayingCard
                :rank="visibleCommunityCards[slot - 1]?.rank"
                :suit="visibleCommunityCards[slot - 1]?.suit"
                :face-down="slot > displayedCommunityCount"
                :reveal="shouldAnimateCommunityCard(slot)"
                :slot-index="slot - 1"
                small
              />
            </div>
            </div>
          </div>
          <div
            class="pot-center"
            :class="{ 'pot-center--pulse': actionHoldActive, 'pot-center--rising': potRising }"
          >
            <div class="pot-center__chips" aria-hidden="true">
              <span class="chip-stack" />
              <span class="chip-stack chip-stack--offset" />
            </div>
            <span class="pot-center__label">Pot</span>
            <span class="pot-center__amount">{{ displayedPot }}</span>
          </div>
        </div>
          </div>

        <div class="table-seats">
        <div
          v-for="seat in seatPositions"
          :key="seat.id"
          class="seat"
          :class="{
            active: effectiveCurrentActorId === seat.id,
            acted: actionHighlightId === seat.id,
            folding: foldingSeats.has(seat.id),
            folded: seat.player?.status === 'folded',
            dealer: gameState.dealer_player_id === seat.id,
            me: seat.id === playerId,
            winner: winnerSeatIds.has(seat.id),
            [`seat--players-${seat.playerCount}`]: true,
          }"
          :style="{ left: `${seat.x}%`, top: `${seat.y}%` }"
        >
          <Transition name="action-bubble">
            <div
              v-if="seatActionBubble(seat.id)"
              class="action-bubble"
              :class="`action-bubble--${gameState.last_action?.type}`"
            >
              {{ seatActionBubble(seat.id) }}
            </div>
          </Transition>
          <div
            v-for="(reaction, reactionIndex) in reactionsForSeat(seat.id)"
            :key="reaction.id"
            class="seat-reaction"
            :style="{ '--reaction-offset': reactionIndex }"
            :title="`${reaction.nickname} reacted ${reaction.emoji}`"
          >
            {{ reaction.emoji }}
          </div>
          <Transition name="dealer-move">
            <div
              v-if="gameState.dealer_player_id === seat.id"
              :key="`${gameState.hand_number}-${seat.id}-dealer`"
              class="dealer-chip"
              title="Dealer"
            >
              D
            </div>
          </Transition>
          <div class="seat-info">
            <span class="seat-name">{{ seat.player?.nickname }}</span>
            <span v-if="blindRoles.sb === seat.id" class="blind-badge sb">SB</span>
            <span v-if="blindRoles.bb === seat.id" class="blind-badge bb">BB</span>
            <span class="seat-chips">{{ seat.player?.chips }} chips</span>
            <span v-if="seat.player && seat.player.bet_this_round > 0" class="seat-bet" :class="{ 'seat-bet--pulse': betPulseSeats.has(seat.id) }">
              Bet {{ seat.player.bet_this_round }}
            </span>
          </div>
          <div class="hole-cards" :class="{ 'hole-cards--folding': foldingSeats.has(seat.id) }">
            <template v-for="cardIndex in 2" :key="`${seat.id}-hole-${cardIndex}`">
              <PlayingCard
                v-if="visibleHoleCount(seat.id) >= cardIndex && seat.player?.status !== 'folded'"
                :rank="seat.player?.hole_cards[cardIndex - 1]?.rank"
                :suit="seat.player?.hole_cards[cardIndex - 1]?.suit"
                :face-down="!showHoleCardFaceUp(seat.id)"
                :deal="shouldAnimateHoleCard(seat.id, cardIndex)"
                :slot-index="cardIndex - 1"
                small
              />
            </template>
          </div>
          <Transition name="hand-desc">
            <p
              v-if="
                seat.player?.hand_description &&
                showHandDescriptions &&
                (seat.id === playerId || showdownRevealed.has(seat.id))
              "
              class="hand-desc"
            >
              {{ seat.player.hand_description }}
            </p>
          </Transition>
          </div>
        </div>
      </div>
      </div>

      <aside class="poker-sidebar">
        <div class="sidebar-scroll">
          <p
            v-if="lastActionText"
            class="last-action last-action--sidebar"
            :class="{ 'last-action--pop': actionHoldActive }"
          >
            {{ lastActionText }}
          </p>

          <div
            v-if="winnerCallout"
            class="winners card winners--reveal winners--sidebar"
            :class="{
              'winners--you': iWonHand,
              'winners--game': winnerCallout.type === 'game',
            }"
          >
            <p class="winners__eyebrow">{{ winnerCallout.eyebrow }}</p>
            <h3 class="winners__title">{{ winnerCallout.title }}</h3>
            <ul v-if="winnerCallout.entries.length" class="winners__list">
              <li v-for="entry in winnerCallout.entries" :key="entry.playerId">
                <span class="winners__name">{{ entry.name }}</span>
                <span class="winners__amount">+{{ entry.amount }}</span>
                <span v-if="entry.hand" class="winners__hand">{{ entry.hand }}</span>
              </li>
            </ul>
            <p v-if="iWonHand && winnerCallout.type === 'hand'" class="winners__you">Nice hand!</p>
          </div>

          <div v-else-if="gameState.phase === 'game_over'" class="game-over card game-over--reveal">
            <h2>
              {{ gameState.players.find((p) => p.id === gameState.winner)?.nickname }} wins the game!
            </h2>
          </div>
        </div>

        <div class="controls-dock">
          <Transition name="action-dock">
            <div v-if="canAct" class="action-bar card action-bar--your-turn">
            <p class="turn-hint">
              <span class="turn-hint__dot" aria-hidden="true" />
              Your turn
              <span v-if="gameState.bet_to_call > 0" class="turn-hint__call">
                — call {{ gameState.bet_to_call }}
              </span>
            </p>
            <div class="action-buttons">
              <button type="button" class="btn-action btn-action--fold" @click="fold">Fold</button>
              <button
                v-if="gameState.can_check"
                type="button"
                class="btn-action btn-action--check"
                @click="check"
              >
                Check
              </button>
              <button
                v-if="gameState.bet_to_call > 0"
                type="button"
                class="btn-action btn-action--call"
                @click="call"
              >
                Call {{ gameState.bet_to_call }}
              </button>
              <button type="button" class="btn-action btn-action--all-in" @click="allIn">All-in</button>
            </div>
            <div v-if="raiseOptions.length" class="raise-row">
              <p class="raise-hint raise-hint--desktop">
                Raise in {{ gameState.raise_increment }} chip increments
              </p>
              <button
                type="button"
                class="raise-toggle"
                :aria-expanded="raisePanelOpen"
                @click="raisePanelOpen = !raisePanelOpen"
              >
                <span>Custom raise</span>
                <span class="raise-toggle__chevron" :class="{ 'raise-toggle__chevron--open': raisePanelOpen }">
                  ▾
                </span>
              </button>
              <div class="raise-panel" :class="{ 'raise-panel--open': raisePanelOpen }">
                <div class="raise-presets">
                  <button
                    v-for="preset in raisePresets"
                    :key="preset.label"
                    type="button"
                    class="btn-secondary raise-preset-btn"
                    :class="{ 'raise-preset--active': raiseAmount === preset.amount }"
                    @click="selectRaise(preset.amount)"
                  >
                    {{ preset.label }} ({{ preset.amount }})
                  </button>
                </div>
                <div class="raise-select-row">
                  <label>
                    Raise to
                    <select v-model.number="raiseAmount" @focus="syncRaiseDefault">
                      <option v-for="amount in raiseOptions" :key="amount" :value="amount">
                        {{ amount }}
                      </option>
                    </select>
                  </label>
                  <button type="button" class="btn-action btn-action--raise" @click="raise">
                    Raise to {{ raiseAmount }}
                  </button>
                </div>
              </div>
            </div>
            </div>
          </Transition>

          <Transition name="action-dock">
            <div
              v-if="isWaitingForTurn"
              class="waiting card waiting--dock"
            >
            <p v-if="dealInProgress">Dealing hole cards…</p>
            <p v-else-if="!bettingRoundReady">Cards dealt — betting begins…</p>
            <p v-else-if="streetTransitionPending">Dealing the {{ phaseLabel.toLowerCase() }}…</p>
            <p v-else-if="actionHoldActive">{{ lastActionText }}</p>
            <p v-else>
              Waiting for
              {{ gameState.players.find((p) => p.id === (effectiveCurrentActorId ?? gameState.current_actor_id))?.nickname }}…
            </p>
            </div>
          </Transition>

          <Transition name="action-dock">
            <div v-if="showNextHandControl" class="next-hand card next-hand--dock">
              <button type="button" class="btn-primary" @click="nextHand">Deal next hand</button>
            </div>
          </Transition>

          <section class="reactions card" aria-label="Emoji reactions">
            <span class="reactions-label">React</span>
            <div class="reaction-buttons" role="toolbar" aria-label="Send reaction">
              <button
                v-for="emoji in pokerReactionEmojis"
                :key="emoji"
                type="button"
                class="reaction-btn"
                :disabled="reactionCooldown"
                :aria-label="`React with ${emoji}`"
                @click="sendReaction(emoji)"
              >
                {{ emoji }}
              </button>
            </div>
          </section>
        </div>
      </aside>
    </div>
  </div>
</template>

<style scoped>
.poker-board {
  max-width: 1440px;
  margin: 0 auto;
  padding: 0 1rem 1rem;
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
  min-height: calc(100vh - 5.5rem);
  background:
    radial-gradient(ellipse 90% 50% at 50% 0%, rgba(91, 156, 255, 0.06) 0%, transparent 55%),
    radial-gradient(ellipse 70% 40% at 50% 100%, rgba(61, 214, 140, 0.04) 0%, transparent 50%);
}

.poker-layout {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
  flex: 1;
  min-height: 0;
}

.table-column {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
  flex: 1;
  min-height: 0;
  min-width: 0;
}

.poker-sidebar {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
  min-width: 0;
}

.sidebar-scroll {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
  min-width: 0;
}

.status-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1rem;
  flex-wrap: wrap;
  padding: 0.65rem 1rem;
  background: linear-gradient(135deg, rgba(21, 28, 44, 0.98) 0%, rgba(16, 22, 36, 0.98) 100%);
  border-color: rgba(42, 54, 80, 0.9);
}

.status-pills {
  display: flex;
  flex-wrap: wrap;
  gap: 0.45rem;
  align-items: center;
}

.status-pill {
  display: inline-flex;
  align-items: center;
  gap: 0.35rem;
  padding: 0.3rem 0.7rem;
  border-radius: 999px;
  font-size: 0.78rem;
  font-weight: 700;
  letter-spacing: 0.02em;
  background: rgba(255, 255, 255, 0.05);
  border: 1px solid rgba(255, 255, 255, 0.08);
  color: var(--text-muted);
}

.status-pill--hand {
  color: var(--text);
  background: rgba(91, 156, 255, 0.1);
  border-color: rgba(91, 156, 255, 0.22);
}

.status-pill--phase {
  color: #ffe58a;
  background: rgba(255, 215, 0, 0.1);
  border-color: rgba(255, 215, 0, 0.25);
  text-transform: uppercase;
  font-size: 0.72rem;
  letter-spacing: 0.08em;
}

.status-pill--dealer strong {
  color: #fff;
  font-weight: 800;
}

.status-bar__right {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  margin-left: auto;
}

.status-pot {
  display: flex;
  align-items: center;
  gap: 0.45rem;
}

.status-pot__chip {
  width: 1.1rem;
  height: 1.1rem;
  border-radius: 50%;
  background: linear-gradient(145deg, #ffe066 0%, #d4a017 55%, #b8860b 100%);
  border: 2px dashed rgba(255, 255, 255, 0.55);
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.35);
  flex-shrink: 0;
}

.status-pot__label {
  font-size: 0.75rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.1em;
  color: var(--text-muted);
}

.status-pot__amount {
  font-size: 1.35rem;
  font-weight: 800;
  font-variant-numeric: tabular-nums;
  color: #ffd700;
  text-shadow: 0 0 20px rgba(255, 215, 0, 0.25);
  transition: transform 0.25s ease, color 0.25s ease;
}

.status-pot--rising .status-pot__chip {
  animation: chipStackBounce 0.55s ease-out;
}

.status-pot--rising .status-pot__amount {
  animation: potCountGlow 0.65s ease-out;
  color: #fff3a0;
}

@keyframes chipStackBounce {
  0%,
  100% {
    transform: translateY(0) scale(1);
  }
  35% {
    transform: translateY(-4px) scale(1.12);
  }
  65% {
    transform: translateY(1px) scale(0.96);
  }
}

@keyframes potCountGlow {
  0% {
    transform: scale(1);
    text-shadow: 0 0 20px rgba(255, 215, 0, 0.25);
  }
  40% {
    transform: scale(1.12);
    text-shadow: 0 0 28px rgba(255, 215, 0, 0.55);
  }
  100% {
    transform: scale(1);
    text-shadow: 0 0 20px rgba(255, 215, 0, 0.25);
  }
}

.phase-pill-enter-active,
.phase-pill-leave-active {
  transition:
    opacity 0.28s ease,
    transform 0.28s cubic-bezier(0.22, 1, 0.36, 1);
}

.phase-pill-enter-from {
  opacity: 0;
  transform: translateY(6px) scale(0.92);
}

.phase-pill-leave-to {
  opacity: 0;
  transform: translateY(-6px) scale(0.92);
}

.sound-toggle {
  padding: 0.35rem 0.55rem;
  border: 1px solid var(--border);
  border-radius: 8px;
  background: rgba(255, 255, 255, 0.04);
  color: var(--text);
  font-size: 1rem;
  line-height: 1;
  cursor: pointer;
  transition: background 0.2s ease, transform 0.15s ease;
  flex-shrink: 0;
}

.sound-toggle:hover {
  background: var(--surface-hover);
  transform: scale(1.05);
}

.last-action {
  text-align: center;
  color: var(--text-muted);
  font-size: 0.95rem;
  margin: 0;
  transition: transform 0.25s ease, opacity 0.25s ease;
}

.last-action--sidebar {
  display: none;
}

.last-action--table {
  flex-shrink: 0;
}

.last-action--pop {
  color: #fff;
  font-weight: 700;
  font-size: 1.05rem;
  animation: actionPop 0.45s ease-out;
}

@keyframes actionPop {
  from {
    opacity: 0;
    transform: translateY(8px) scale(0.96);
  }
  to {
    opacity: 1;
    transform: translateY(0) scale(1);
  }
}

.phase-banner {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  z-index: 10;
  background: rgba(0, 0, 0, 0.82);
  color: #ffd700;
  font-size: 1.75rem;
  font-weight: 900;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  padding: 1rem 2rem;
  border-radius: 12px;
  border: 2px solid rgba(255, 215, 0, 0.45);
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.5);
  pointer-events: none;
}

.phase-banner-enter-active,
.phase-banner-leave-active {
  transition: opacity 0.45s ease, transform 0.45s ease;
}

.phase-banner-enter-from,
.phase-banner-leave-to {
  opacity: 0;
  transform: translate(-50%, -50%) scale(0.85);
}

.winner-overlay {
  position: absolute;
  inset: 0;
  z-index: 12;
  display: flex;
  align-items: center;
  justify-content: center;
  pointer-events: none;
}

.winner-banner {
  text-align: center;
  max-width: min(92%, 420px);
  padding: 1.35rem 1.75rem;
  border-radius: 16px;
  border: 3px solid rgba(255, 215, 0, 0.75);
  background: linear-gradient(160deg, rgba(28, 18, 4, 0.96) 0%, rgba(8, 24, 14, 0.96) 100%);
  box-shadow:
    0 0 0 1px rgba(255, 215, 0, 0.2),
    0 16px 48px rgba(0, 0, 0, 0.55),
    0 0 40px rgba(255, 215, 0, 0.22);
  animation: winnerGlow 2.4s ease-in-out infinite;
}

.winner-banner--game {
  border-color: rgba(255, 180, 60, 0.9);
  box-shadow:
    0 0 0 1px rgba(255, 180, 60, 0.25),
    0 20px 56px rgba(0, 0, 0, 0.6),
    0 0 56px rgba(255, 140, 0, 0.35);
}

.winner-banner__eyebrow {
  margin: 0 0 0.35rem;
  font-size: 0.75rem;
  font-weight: 800;
  letter-spacing: 0.16em;
  text-transform: uppercase;
  color: #f0c84b;
}

.winner-banner__title {
  margin: 0;
  font-size: clamp(1.35rem, 4vw, 2rem);
  font-weight: 900;
  line-height: 1.15;
  color: #fff;
  text-shadow: 0 2px 12px rgba(0, 0, 0, 0.45);
}

.winner-banner__list {
  list-style: none;
  margin: 0.85rem 0 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 0.45rem;
}

.winner-banner__list li {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: center;
  gap: 0.45rem;
  font-size: 0.95rem;
  color: #f5f5f5;
}

.winner-banner__amount {
  color: #7dffb0;
  font-weight: 800;
}

.winner-banner__hand {
  display: inline-block;
  padding: 0.15rem 0.55rem;
  border-radius: 999px;
  background: rgba(255, 215, 0, 0.16);
  color: #ffe58a;
  font-size: 0.78rem;
  font-weight: 700;
  text-transform: capitalize;
}

.winner-banner__hand--solo {
  margin: 0.75rem 0 0;
}

.winner-banner__you {
  margin: 0.85rem 0 0;
  font-size: 1rem;
  font-weight: 800;
  color: #7dffb0;
}

.winner-banner-enter-active,
.winner-banner-leave-active {
  transition: opacity 0.45s ease;
}

.winner-banner-enter-active .winner-banner,
.winner-banner-leave-active .winner-banner {
  transition: transform 0.45s ease, opacity 0.45s ease;
}

.winner-banner-enter-from,
.winner-banner-leave-to {
  opacity: 0;
}

.winner-banner-enter-from .winner-banner,
.winner-banner-leave-to .winner-banner {
  opacity: 0;
  transform: scale(0.82) translateY(12px);
}

@keyframes winnerGlow {
  0%,
  100% {
    box-shadow:
      0 0 0 1px rgba(255, 215, 0, 0.2),
      0 16px 48px rgba(0, 0, 0, 0.55),
      0 0 32px rgba(255, 215, 0, 0.18);
  }
  50% {
    box-shadow:
      0 0 0 1px rgba(255, 215, 0, 0.35),
      0 16px 48px rgba(0, 0, 0, 0.55),
      0 0 52px rgba(255, 215, 0, 0.38);
  }
}

.seat.winner .seat-info {
  outline: 3px solid #ffd700;
  background: rgba(80, 62, 8, 0.82);
  animation: winnerSeatPulse 1.6s ease-in-out infinite;
}

@keyframes winnerSeatPulse {
  0%,
  100% {
    box-shadow: 0 0 0 0 rgba(255, 215, 0, 0.45);
  }
  50% {
    box-shadow: 0 0 18px 6px rgba(255, 215, 0, 0.35);
  }
}

.burn-hint {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, calc(-50% - 5.5rem));
  z-index: 5;
  color: #f0e6c8;
  font-size: 0.8rem;
  font-weight: 600;
  background: rgba(0, 0, 0, 0.55);
  padding: 0.3rem 0.75rem;
  border-radius: 999px;
  pointer-events: none;
}

.burn-hint-enter-active,
.burn-hint-leave-active {
  transition: opacity 0.35s ease;
}

.burn-hint-enter-from,
.burn-hint-leave-to {
  opacity: 0;
}

.table-wrap {
  position: relative;
  width: 100%;
  flex: 1;
  min-height: min(58vh, 520px);
  padding: 1.25rem;
  border-radius: 28px;
  background:
    radial-gradient(ellipse at center, rgba(40, 28, 12, 0.55) 0%, rgba(10, 14, 23, 0.92) 72%);
  box-shadow:
    inset 0 0 60px rgba(0, 0, 0, 0.55),
    0 12px 40px rgba(0, 0, 0, 0.4);
}

.table-room-glow {
  position: absolute;
  inset: 12% 8% 18%;
  border-radius: 50% / 42%;
  background: radial-gradient(ellipse at center, rgba(255, 200, 80, 0.07) 0%, transparent 68%);
  pointer-events: none;
  z-index: 0;
}

.table-felt {
  position: absolute;
  inset: 1.25rem;
  background:
    radial-gradient(ellipse 85% 65% at 50% 42%, rgba(255, 255, 255, 0.06) 0%, transparent 55%),
    repeating-linear-gradient(
      90deg,
      transparent 0,
      transparent 3px,
      rgba(0, 0, 0, 0.025) 3px,
      rgba(0, 0, 0, 0.025) 4px
    ),
    radial-gradient(ellipse at center, #2a8f4e 0%, #1a6b38 38%, #0d4a26 72%, #082e18 100%);
  border-radius: 50% / 40%;
  box-shadow:
    inset 0 0 0 10px #4a2f18,
    inset 0 0 0 12px #6b4423,
    inset 0 0 0 14px #3d2512,
    inset 0 0 0 16px #7a5030,
    inset 0 0 50px rgba(0, 0, 0, 0.45),
    0 8px 32px rgba(0, 0, 0, 0.5);
  z-index: 1;
  transition: box-shadow 0.45s ease, filter 0.45s ease;
}

.table-seats {
  position: absolute;
  inset: 1.25rem;
  z-index: 3;
  pointer-events: none;
}

.table-seats > .seat {
  pointer-events: auto;
}

.table-felt--spotlight {
  box-shadow:
    inset 0 0 0 10px #4a2f18,
    inset 0 0 0 12px #6b4423,
    inset 0 0 0 14px #3d2512,
    inset 0 0 0 16px #7a5030,
    inset 0 0 50px rgba(0, 0, 0, 0.45),
    0 8px 32px rgba(0, 0, 0, 0.5),
    inset 0 0 80px rgba(255, 215, 0, 0.08);
  animation: tableSpotlight 2.4s ease-in-out infinite;
}

.table-felt--dealing {
  animation: tableDealPulse 1.1s ease-in-out infinite;
}

@keyframes tableSpotlight {
  0%,
  100% {
    filter: brightness(1);
  }
  50% {
    filter: brightness(1.06);
  }
}

@keyframes tableDealPulse {
  0%,
  100% {
    box-shadow:
      inset 0 0 0 10px #4a2f18,
      inset 0 0 0 12px #6b4423,
      inset 0 0 0 14px #3d2512,
      inset 0 0 0 16px #7a5030,
      inset 0 0 50px rgba(0, 0, 0, 0.45),
      0 8px 32px rgba(0, 0, 0, 0.5);
  }
  50% {
    box-shadow:
      inset 0 0 0 10px #4a2f18,
      inset 0 0 0 12px #6b4423,
      inset 0 0 0 14px #3d2512,
      inset 0 0 0 16px #7a5030,
      inset 0 0 50px rgba(0, 0, 0, 0.45),
      0 8px 32px rgba(0, 0, 0, 0.5),
      inset 0 0 60px rgba(91, 156, 255, 0.12);
  }
}

.chip-fly-layer {
  position: absolute;
  inset: 0;
  pointer-events: none;
  z-index: 6;
  overflow: hidden;
}

.chip-fly {
  position: absolute;
  width: 1rem;
  height: 1rem;
  margin-left: -0.5rem;
  margin-top: -0.5rem;
  border-radius: 50%;
  background: linear-gradient(145deg, #ffe066 0%, #d4a017 55%, #b8860b 100%);
  border: 2px dashed rgba(255, 255, 255, 0.55);
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.45);
  animation: chipFlyToPot 0.68s cubic-bezier(0.22, 1, 0.36, 1) forwards;
}

@keyframes chipFlyToPot {
  0% {
    left: var(--start-x, 50%);
    top: var(--start-y, 50%);
    opacity: 1;
    transform: translate(-50%, -50%) scale(1);
  }
  100% {
    left: 50%;
    top: 50%;
    opacity: 0;
    transform: translate(-50%, -50%) scale(0.35);
  }
}

.chip-fly-enter-active {
  animation: chipFlyToPot 0.68s cubic-bezier(0.22, 1, 0.36, 1) forwards;
}

.chip-fly-leave-active {
  opacity: 0;
}

.burn-card-flash {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  z-index: 8;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 0.35rem;
  pointer-events: none;
}

.burn-card-flash__label {
  font-size: 0.72rem;
  font-weight: 800;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  color: #ffb4a2;
  text-shadow: 0 0 12px rgba(255, 100, 60, 0.45);
}

.burn-flash-enter-active {
  animation: burnFlashIn 0.38s ease-out;
}

.burn-flash-leave-active {
  animation: burnFlashOut 0.32s ease-in forwards;
}

@keyframes burnFlashIn {
  from {
    opacity: 0;
    transform: translate(-50%, -50%) scale(0.6) rotate(-12deg);
    filter: brightness(2);
  }
  to {
    opacity: 1;
    transform: translate(-50%, -50%) scale(1) rotate(0deg);
    filter: brightness(1);
  }
}

@keyframes burnFlashOut {
  to {
    opacity: 0;
    transform: translate(-50%, -70%) scale(0.75) rotate(8deg);
    filter: brightness(0.5) blur(2px);
  }
}

.winner-sparkles {
  position: absolute;
  inset: 0;
  pointer-events: none;
  overflow: hidden;
}

.sparkle {
  position: absolute;
  left: 50%;
  top: 50%;
  width: 0.45rem;
  height: 0.45rem;
  border-radius: 50%;
  background: radial-gradient(circle, #fff9c4 0%, #ffd700 45%, transparent 70%);
  animation: sparkleBurst 1.8s ease-out infinite;
  animation-delay: calc(var(--i, 0) * 0.11s);
  transform: rotate(calc(var(--i, 0) * 25.7deg)) translateY(0);
}

@keyframes sparkleBurst {
  0% {
    opacity: 0;
    transform: rotate(calc(var(--i, 0) * 25.7deg)) translateY(0) scale(0.2);
  }
  20% {
    opacity: 1;
  }
  100% {
    opacity: 0;
    transform: rotate(calc(var(--i, 0) * 25.7deg)) translateY(calc(-4.5rem - var(--i, 0) * 0.15rem)) scale(0.6);
  }
}

.table-felt::before {
  content: '';
  position: absolute;
  inset: 9% 11%;
  border:  2px solid rgba(255, 215, 0, 0.1);
  border-radius: 50% / 40%;
  pointer-events: none;
}

.table-felt::after {
  content: '';
  position: absolute;
  inset: 14% 16%;
  border: 1px dashed rgba(255, 255, 255, 0.06);
  border-radius: 50% / 40%;
  pointer-events: none;
}

.table-felt :deep(.playing-card--small) {
  width: clamp(56px, 5.8vw, 80px);
  height: clamp(80px, 8.2vw, 114px);
  font-size: clamp(1.05rem, 1.25vw, 1.3rem);
}

/* Hole cards — explicit sizes on desktop; flex-fit on mobile (see media queries) */
.table-seats .hole-cards :deep(.playing-card) {
  flex: 0 0 auto;
  min-width: 0;
}

.table-seats .hole-cards :deep(.playing-card--small) {
  width: clamp(56px, 5.8vw, 80px);
  height: clamp(80px, 8.2vw, 114px);
  font-size: clamp(1.05rem, 1.25vw, 1.3rem);
}

.table-seats .hole-cards :deep(.corner__rank) {
  font-size: clamp(0.9rem, 1.2vw, 1.15rem);
}

.table-seats .hole-cards :deep(.corner__suit) {
  font-size: clamp(0.8rem, 1.05vw, 1rem);
}

.table-seats .hole-cards :deep(.suit--center) {
  font-size: clamp(1.75rem, 2.4vw, 2.6rem);
}

@media (min-width: 1024px) {
  .seat {
    min-width: clamp(120px, 11vw, 200px);
    max-width: min(26vw, 220px);
  }

  .seat--players-6 {
    min-width: clamp(108px, 10vw, 168px);
    max-width: min(22vw, 180px);
  }

  .seat.me .hole-cards :deep(.playing-card--small) {
    width: clamp(64px, 7vw, 94px);
    height: clamp(92px, 10vw, 136px);
    font-size: clamp(1.15rem, 1.45vw, 1.5rem);
  }

  .seat.me .hole-cards :deep(.corner__rank) {
    font-size: clamp(1rem, 1.35vw, 1.3rem);
  }

  .seat.me .hole-cards :deep(.corner__suit) {
    font-size: clamp(0.9rem, 1.2vw, 1.15rem);
  }

  .seat.me .hole-cards :deep(.suit--center) {
    font-size: clamp(2rem, 2.75vw, 3rem);
  }

  .seat.me .hole-cards {
    gap: 0.4rem;
  }
}

.table-felt :deep(.corner__rank) {
  font-size: clamp(0.9rem, 1.2vw, 1.15rem);
}

.table-felt :deep(.corner__suit) {
  font-size: clamp(0.8rem, 1.05vw, 1rem);
}

.table-felt :deep(.suit--center) {
  font-size: clamp(1.75rem, 2.4vw, 2.6rem);
}

.community :deep(.playing-card--small) {
  width: clamp(62px, 6.5vw, 90px);
  height: clamp(88px, 9.2vw, 128px);
  font-size: clamp(1.1rem, 1.35vw, 1.4rem);
}

.community :deep(.corner__rank) {
  font-size: clamp(0.95rem, 1.3vw, 1.25rem);
}

.community :deep(.corner__suit) {
  font-size: clamp(0.85rem, 1.15vw, 1.1rem);
}

.community :deep(.suit--center) {
  font-size: clamp(1.9rem, 2.6vw, 2.85rem);
}

.table-center {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 0.65rem;
  z-index: 2;
}

.community-zone {
  position: relative;
  padding: 0.65rem 1rem;
  border-radius: 14px;
  background: rgba(0, 0, 0, 0.18);
  border: 1px solid rgba(255, 255, 255, 0.06);
  box-shadow: inset 0 2px 12px rgba(0, 0, 0, 0.25);
  transition:
    box-shadow 0.35s ease,
    border-color 0.35s ease,
    transform 0.35s ease;
}

.community-zone--pulse {
  animation: communityZonePulse 0.85s ease-out;
  border-color: rgba(255, 215, 0, 0.22);
}

@keyframes communityZonePulse {
  0% {
    transform: scale(1);
    box-shadow: inset 0 2px 12px rgba(0, 0, 0, 0.25);
  }
  35% {
    transform: scale(1.04);
    box-shadow:
      inset 0 2px 12px rgba(0, 0, 0, 0.25),
      0 0 24px rgba(255, 215, 0, 0.18);
  }
  100% {
    transform: scale(1);
    box-shadow: inset 0 2px 12px rgba(0, 0, 0, 0.25);
  }
}

.community {
  display: flex;
  gap: 0.5rem;
}

.community-slot {
  flex-shrink: 0;
  transition: transform 0.3s ease;
}

.community-slot--live:not(:has(.playing-card--reveal)) {
  animation: communitySlotSettle 0.4s ease-out;
}

@keyframes communitySlotSettle {
  from {
    transform: translateY(4px);
  }
  to {
    transform: translateY(0);
  }
}

.pot-center {
  position: relative;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 0.2rem;
  text-align: center;
  pointer-events: none;
  transition: transform 0.3s ease, color 0.3s ease;
}

.pot-center__chips {
  position: relative;
  width: 2.5rem;
  height: 1.1rem;
  margin-bottom: 0.15rem;
}

.chip-stack {
  position: absolute;
  left: 50%;
  bottom: 0;
  width: 1.35rem;
  height: 1.35rem;
  margin-left: -0.9rem;
  border-radius: 50%;
  background: linear-gradient(145deg, #ffe066 0%, #d4a017 50%, #a67c00 100%);
  border: 2px dashed rgba(255, 255, 255, 0.5);
  box-shadow: 0 2px 6px rgba(0, 0, 0, 0.4);
}

.chip-stack--offset {
  margin-left: 0.1rem;
  bottom: 0.35rem;
  width: 1.2rem;
  height: 1.2rem;
  background: linear-gradient(145deg, #ff6b6b 0%, #c0392b 50%, #922b21 100%);
  opacity: 0.92;
}

.pot-center__label {
  color: #f0e6c8;
  font-size: clamp(0.7rem, 1.1vw, 0.9rem);
  font-weight: 700;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  opacity: 0.9;
}

.pot-center__amount {
  color: #ffd700;
  font-size: clamp(2rem, 5.5vw, 3.75rem);
  font-weight: 900;
  line-height: 1;
  font-variant-numeric: tabular-nums;
  text-shadow: 0 2px 12px rgba(0, 0, 0, 0.55), 0 0 24px rgba(255, 215, 0, 0.25);
}

.pot-center--pulse .pot-center__amount {
  animation: potPulse 0.6s ease-out;
  color: #fff3a0;
}

.pot-center--rising .pot-center__chips {
  animation: chipStackBounce 0.55s ease-out;
}

.pot-center--rising .pot-center__amount {
  animation: potCountGlow 0.65s ease-out;
  color: #fff3a0;
}

@keyframes potPulse {
  0% {
    transform: scale(1);
  }
  40% {
    transform: scale(1.15);
  }
  100% {
    transform: scale(1);
  }
}

.phase {
  color: var(--accent);
}

.seat {
  position: absolute;
  transform: translate(-50%, -50%);
  text-align: center;
  min-width: clamp(96px, 10vw, 158px);
  max-width: min(42vw, 158px);
  container-type: inline-size;
  container-name: seat;
  transition: filter 0.35s ease, opacity 0.5s ease, transform 0.5s ease;
}

.seat--players-6 {
  min-width: clamp(84px, 8.5vw, 132px);
  max-width: min(36vw, 132px);
}

.seat--players-6 .seat-info {
  padding: 0.4rem 0.55rem;
}

.seat--players-6 .hole-cards {
  gap: 0.2rem;
}

.seat.acted .seat-info {
  animation: actedFlash 0.55s ease-out;
}

@keyframes actedFlash {
  0% {
    background: rgba(255, 215, 0, 0.55);
    transform: scale(1.06);
  }
  100% {
    background: rgba(0, 0, 0, 0.55);
    transform: scale(1);
  }
}

.seat.folding {
  opacity: 0.55;
}

.action-bubble {
  position: absolute;
  top: -2.1rem;
  left: 50%;
  transform: translateX(-50%);
  white-space: nowrap;
  font-size: 0.72rem;
  font-weight: 800;
  padding: 0.28rem 0.55rem;
  border-radius: 999px;
  z-index: 4;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.35);
}

.action-bubble--fold {
  background: #7f8c8d;
  color: #fff;
}

.action-bubble--check {
  background: #3498db;
  color: #fff;
}

.action-bubble--call {
  background: #27ae60;
  color: #fff;
}

.action-bubble--raise,
.action-bubble--all_in {
  background: #e67e22;
  color: #fff;
}

.seat-reaction {
  position: absolute;
  top: -2.4rem;
  left: calc(50% + (var(--reaction-offset, 0) * 1.4rem));
  transform: translateX(-50%);
  font-size: 1.65rem;
  line-height: 1;
  z-index: 5;
  pointer-events: none;
  filter: drop-shadow(0 2px 6px rgba(0, 0, 0, 0.45));
  animation: reactionFloat 2.2s ease-out forwards;
}

@keyframes reactionFloat {
  0% {
    opacity: 0;
    transform: translateX(-50%) translateY(10px) scale(0.45);
  }
  18% {
    opacity: 1;
    transform: translateX(-50%) translateY(0) scale(1.15);
  }
  72% {
    opacity: 1;
    transform: translateX(-50%) translateY(-14px) scale(1);
  }
  100% {
    opacity: 0;
    transform: translateX(-50%) translateY(-30px) scale(0.85);
  }
}

.action-bubble-enter-active {
  animation: bubbleIn 0.4s ease-out;
}

.action-bubble-leave-active {
  animation: bubbleOut 0.35s ease-in;
}

@keyframes bubbleIn {
  from {
    opacity: 0;
    transform: translateX(-50%) translateY(10px) scale(0.8);
  }
  to {
    opacity: 1;
    transform: translateX(-50%) translateY(0) scale(1);
  }
}

@keyframes bubbleOut {
  from {
    opacity: 1;
    transform: translateX(-50%) translateY(0) scale(1);
  }
  to {
    opacity: 0;
    transform: translateX(-50%) translateY(-8px) scale(0.85);
  }
}

.seat.active {
  filter: drop-shadow(0 0 10px rgba(255, 215, 0, 0.85));
  z-index: 2;
}

.seat.active .seat-info {
  outline: 2px solid #ffd700;
  border-radius: 6px;
  animation: turnPulse 1.2s ease-in-out infinite;
}

@keyframes turnPulse {
  0%,
  100% {
    box-shadow: 0 0 0 0 rgba(255, 215, 0, 0.5);
  }
  50% {
    box-shadow: 0 0 12px 4px rgba(255, 215, 0, 0.35);
  }
}

.seat.dealer .seat-info {
  border: 1px solid rgba(255, 255, 255, 0.35);
}

.seat.folded {
  opacity: 0.45;
}

.seat.me .seat-name {
  color: #ffd700;
}

.seat-info {
  background: rgba(8, 12, 20, 0.72);
  backdrop-filter: blur(8px);
  padding: 0.55rem 0.75rem;
  border-radius: 10px;
  border: 1px solid rgba(255, 255, 255, 0.08);
  color: #fff;
  font-size: clamp(0.82rem, 1.15vw, 0.95rem);
  margin-bottom: 0.35rem;
  transition: background 0.3s ease, transform 0.3s ease, border-color 0.3s ease;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.25);
}

.seat-bet {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 0.3rem;
  margin-top: 0.25rem;
  padding: 0.15rem 0.5rem;
  border-radius: 999px;
  background: rgba(255, 215, 0, 0.12);
  border: 1px solid rgba(255, 215, 0, 0.22);
  color: #ffd700;
  font-weight: 800;
  font-size: clamp(0.75rem, 1vw, 0.82rem);
  transition: transform 0.25s ease;
}

.seat-bet__chip {
  width: 0.65rem;
  height: 0.65rem;
  border-radius: 50%;
  background: linear-gradient(145deg, #ffe066, #c9a227);
  border: 1px dashed rgba(255, 255, 255, 0.45);
  flex-shrink: 0;
}

.seat-bet--pulse {
  animation: betPulse 0.55s ease-out;
}

@keyframes betPulse {
  0% {
    transform: scale(1);
  }
  35% {
    transform: scale(1.35);
    color: #fff;
  }
  100% {
    transform: scale(1);
  }
}

.hole-cards--folding {
  animation: foldCards 0.75s ease-in forwards;
}

@keyframes foldCards {
  to {
    opacity: 0;
    transform: translateY(12px) scale(0.75);
  }
}

.seat-name {
  display: block;
  font-weight: 700;
  font-size: clamp(0.88rem, 1.25vw, 1.05rem);
  line-height: 1.25;
}

.seat-chips {
  display: block;
  margin-top: 0.2rem;
  font-size: clamp(0.78rem, 1.05vw, 0.88rem);
  line-height: 1.3;
  opacity: 0.92;
}

.dealer-chip {
  position: absolute;
  top: -0.9rem;
  right: -0.5rem;
  background: linear-gradient(145deg, #fff 0%, #e0e0e0 100%);
  color: #1a1a1a;
  border: 2px solid #c9a227;
  border-radius: 50%;
  width: 1.9rem;
  height: 1.9rem;
  line-height: 1.65rem;
  font-size: 0.78rem;
  font-weight: 900;
  box-shadow:
    0 2px 6px rgba(0, 0, 0, 0.45),
    inset 0 1px 0 rgba(255, 255, 255, 0.8);
  z-index: 3;
}

.dealer-move-enter-active {
  animation: dealerChipLand 0.55s cubic-bezier(0.22, 1, 0.36, 1);
}

.dealer-move-leave-active {
  animation: dealerChipLift 0.35s ease-in forwards;
}

@keyframes dealerChipLand {
  0% {
    opacity: 0;
    transform: scale(0.3) translateY(-16px) rotate(-120deg);
  }
  60% {
    transform: scale(1.15) translateY(2px) rotate(8deg);
  }
  100% {
    opacity: 1;
    transform: scale(1) translateY(0) rotate(0deg);
  }
}

@keyframes dealerChipLift {
  to {
    opacity: 0;
    transform: scale(0.4) translateY(-12px) rotate(90deg);
  }
}

.blind-badge {
  display: inline-block;
  font-size: 0.62rem;
  font-weight: 800;
  padding: 0.15rem 0.4rem;
  border-radius: 999px;
  margin-right: 0.35rem;
  vertical-align: middle;
  letter-spacing: 0.04em;
}

.blind-badge.sb {
  background: rgba(52, 152, 219, 0.85);
  color: #fff;
  box-shadow: 0 0 8px rgba(52, 152, 219, 0.35);
}

.blind-badge.bb {
  background: rgba(230, 126, 34, 0.9);
  color: #fff;
  box-shadow: 0 0 8px rgba(230, 126, 34, 0.35);
}

.hole-cards {
  display: flex;
  gap: 0.35rem;
  justify-content: center;
  width: 100%;
  max-width: 100%;
}

.hand-desc {
  font-size: 0.65rem;
  color: #f0e6c8;
  margin: 0.2rem 0 0;
}

.hand-desc-enter-active {
  animation: handDescIn 0.5s cubic-bezier(0.22, 1, 0.36, 1);
}

.hand-desc-leave-active {
  animation: handDescIn 0.25s ease-in reverse;
}

@keyframes handDescIn {
  from {
    opacity: 0;
    transform: translateY(6px) scale(0.92);
  }
  to {
    opacity: 1;
    transform: translateY(0) scale(1);
  }
}

.action-dock-enter-active {
  animation: actionDockIn 0.42s cubic-bezier(0.22, 1, 0.36, 1);
}

.action-dock-leave-active {
  animation: actionDockIn 0.28s ease-in reverse;
}

@keyframes actionDockIn {
  from {
    opacity: 0;
    transform: translateY(18px) scale(0.96);
  }
  to {
    opacity: 1;
    transform: translateY(0) scale(1);
  }
}

.action-bar--your-turn {
  border-color: rgba(255, 215, 0, 0.35);
  box-shadow:
    var(--shadow),
    0 0 0 1px rgba(255, 215, 0, 0.08),
    inset 0 1px 0 rgba(255, 255, 255, 0.04);
  background: linear-gradient(160deg, rgba(28, 32, 48, 0.98) 0%, rgba(18, 24, 38, 0.98) 100%);
  animation: yourTurnGlow 2s ease-in-out infinite;
}

@keyframes yourTurnGlow {
  0%,
  100% {
    box-shadow:
      var(--shadow),
      0 0 0 1px rgba(255, 215, 0, 0.08),
      inset 0 1px 0 rgba(255, 255, 255, 0.04);
  }
  50% {
    box-shadow:
      var(--shadow),
      0 0 0 1px rgba(255, 215, 0, 0.22),
      0 0 20px rgba(255, 215, 0, 0.12),
      inset 0 1px 0 rgba(255, 255, 255, 0.04);
  }
}

.action-bar,
.waiting,
.winners,
.game-over,
.next-hand,
.reactions {
  padding: 1rem;
}

.reactions {
  margin-top: auto;
}

.controls-dock {
  display: flex;
  flex-direction: column;
  gap: 0.65rem;
  min-width: 0;
}

.controls-dock .action-bar,
.controls-dock .waiting,
.controls-dock .next-hand,
.controls-dock .reactions {
  margin-top: 0;
}

.reactions-label {
  display: block;
  font-size: 0.7rem;
  font-weight: 600;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  color: var(--text-muted);
  margin-bottom: 0.6rem;
}

.reaction-buttons {
  display: flex;
  flex-wrap: wrap;
  gap: 0.35rem;
}

.reaction-btn {
  width: 2.35rem;
  height: 2.35rem;
  border-radius: 10px;
  border: 1px solid var(--border);
  background: var(--surface-hover);
  font-size: 1.2rem;
  line-height: 1;
  cursor: pointer;
  transition:
    transform 0.15s var(--ease-bounce),
    border-color 0.15s,
    background 0.15s;
}

.reaction-btn:hover:not(:disabled) {
  transform: scale(1.1);
  border-color: rgba(255, 215, 80, 0.45);
  background: rgba(255, 215, 80, 0.1);
}

.reaction-btn:active:not(:disabled) {
  transform: scale(0.95);
}

.reaction-btn:disabled {
  opacity: 0.45;
  cursor: not-allowed;
}

.turn-hint {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  font-weight: 700;
  margin: 0;
  color: #fff;
}

.turn-hint__dot {
  width: 0.55rem;
  height: 0.55rem;
  border-radius: 50%;
  background: #7dffb0;
  box-shadow: 0 0 10px rgba(125, 255, 176, 0.65);
  animation: turnDotPulse 1.2s ease-in-out infinite;
  flex-shrink: 0;
}

.turn-hint__call {
  color: var(--text-muted);
  font-weight: 600;
}

@keyframes turnDotPulse {
  0%,
  100% {
    opacity: 1;
    transform: scale(1);
  }
  50% {
    opacity: 0.65;
    transform: scale(0.85);
  }
}

.btn-action {
  font-family: inherit;
  cursor: pointer;
  border: none;
  border-radius: 10px;
  font-weight: 700;
  padding: 0.7rem 1rem;
  font-size: 0.92rem;
  transition:
    background 0.2s var(--ease-smooth),
    transform 0.15s var(--ease-smooth),
    box-shadow 0.2s var(--ease-smooth);
}

.btn-action:active:not(:disabled) {
  transform: scale(0.97);
}

.btn-action--fold {
  background: rgba(127, 140, 141, 0.25);
  color: #dfe6e9;
  border: 1px solid rgba(127, 140, 141, 0.45);
}

.btn-action--fold:hover:not(:disabled) {
  background: rgba(127, 140, 141, 0.4);
}

.btn-action--check {
  background: rgba(52, 152, 219, 0.2);
  color: #74b9ff;
  border: 1px solid rgba(52, 152, 219, 0.4);
}

.btn-action--check:hover:not(:disabled) {
  background: rgba(52, 152, 219, 0.32);
}

.btn-action--call {
  background: linear-gradient(135deg, #27ae60 0%, #1e8449 100%);
  color: #fff;
  border: 1px solid rgba(255, 255, 255, 0.12);
}

.btn-action--call:hover:not(:disabled) {
  transform: translateY(-1px);
  box-shadow: 0 4px 16px rgba(39, 174, 96, 0.35);
}

.btn-action--all-in {
  background: rgba(230, 126, 34, 0.18);
  color: #f39c12;
  border: 1px solid rgba(230, 126, 34, 0.45);
}

.btn-action--all-in:hover:not(:disabled) {
  background: rgba(230, 126, 34, 0.3);
}

.btn-action--raise {
  background: linear-gradient(135deg, var(--accent) 0%, #7c6cf0 100%);
  color: #fff;
  border: 1px solid rgba(255, 255, 255, 0.1);
}

.btn-action--raise:hover:not(:disabled) {
  transform: translateY(-1px);
  box-shadow: var(--shadow-glow);
}

.action-bar .action-buttons {
  flex-direction: column;
}

.action-bar .action-buttons button {
  width: 100%;
}

.action-bar .raise-row {
  flex-direction: column;
  align-items: stretch;
}

.action-bar .raise-row label {
  width: 100%;
}

.action-bar .raise-row button {
  width: 100%;
}

.raise-toggle {
  display: none;
}

.raise-panel {
  display: flex;
  flex-direction: column;
  gap: 0.65rem;
  width: 100%;
}

.next-hand button {
  width: 100%;
}

.action-buttons {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
  margin: 0.75rem 0;
}

.raise-hint {
  margin: 0 0 0.5rem;
  font-size: 0.9rem;
  color: var(--text-muted);
  width: 100%;
}

.raise-presets {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
  margin-bottom: 0;
  width: 100%;
}

.raise-preset-btn {
  flex: 1 1 calc(50% - 0.25rem);
  min-width: 0;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.raise-preset--active {
  outline: 2px solid var(--accent, #ffd700);
}

.raise-select-row {
  display: flex;
  align-items: center;
  gap: 1rem;
  flex-wrap: wrap;
  width: 100%;
}

.raise-select-row label {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.raise-select-row select {
  min-width: 6rem;
  padding: 0.35rem 0.5rem;
}

.raise-row {
  display: flex;
  align-items: center;
  gap: 1rem;
  flex-wrap: wrap;
}

.raise-row label {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  flex: 1;
}

.winners--reveal {
  animation: winnersIn 0.65s ease-out;
}

.winners {
  border: 2px solid rgba(255, 215, 0, 0.55);
  background: linear-gradient(160deg, rgba(36, 28, 8, 0.95) 0%, rgba(12, 28, 18, 0.95) 100%);
  box-shadow: 0 8px 28px rgba(0, 0, 0, 0.35);
}

.winners--you {
  border-color: rgba(125, 255, 176, 0.7);
  box-shadow:
    0 8px 28px rgba(0, 0, 0, 0.35),
    0 0 24px rgba(125, 255, 176, 0.2);
}

.winners--game {
  border-color: rgba(255, 160, 60, 0.75);
}

.winners__eyebrow {
  margin: 0 0 0.25rem;
  font-size: 0.7rem;
  font-weight: 800;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  color: #f0c84b;
}

.winners__title {
  margin: 0;
  font-size: 1.35rem;
  font-weight: 900;
  line-height: 1.2;
  color: #fff;
}

.winners__list {
  list-style: none;
  margin: 0.75rem 0 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.winners__list li {
  display: flex;
  flex-wrap: wrap;
  align-items: baseline;
  gap: 0.4rem;
}

.winners__name {
  font-weight: 700;
  color: #fff;
}

.winners__amount {
  color: #7dffb0;
  font-weight: 800;
}

.winners__hand {
  width: 100%;
  font-size: 0.85rem;
  color: #ffe58a;
  text-transform: capitalize;
}

.winners__you {
  margin: 0.75rem 0 0;
  font-weight: 800;
  color: #7dffb0;
}

@keyframes winnersIn {
  from {
    opacity: 0;
    transform: translateY(16px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

.winners ul {
  margin: 0.5rem 0 0;
  padding-left: 1.25rem;
}

.game-over {
  text-align: center;
  border: 2px solid rgba(255, 160, 60, 0.7);
  background: linear-gradient(160deg, rgba(40, 20, 4, 0.95) 0%, rgba(18, 10, 4, 0.95) 100%);
}

.game-over--reveal {
  animation: winnersIn 0.65s ease-out;
}

.game-over h2 {
  margin: 0;
  font-size: 1.4rem;
  font-weight: 900;
  color: #ffd700;
}

.waiting {
  animation: fadeIn 0.35s ease-out;
}

@keyframes fadeIn {
  from {
    opacity: 0.5;
  }
  to {
    opacity: 1;
  }
}

@media (min-width: 1024px) {
  .poker-layout {
    display: grid;
    grid-template-columns: minmax(0, 1fr) minmax(280px, 340px);
    gap: 1rem;
    align-items: stretch;
  }

  .table-wrap {
    min-height: min(72vh, 780px);
  }

  .last-action--table {
    display: none;
  }

  .last-action--sidebar {
    display: block;
    text-align: left;
  }

  .poker-sidebar {
    position: sticky;
    top: 0.75rem;
    align-self: start;
    max-height: calc(100vh - 6rem);
    overflow-y: auto;
  }

  .sidebar-scroll {
    flex: 1;
    min-height: 0;
    overflow-y: auto;
  }

  .controls-dock {
    flex-shrink: 0;
  }

  .action-bar .action-buttons {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 0.5rem;
  }

  .action-bar .action-buttons button {
    width: auto;
    min-width: 0;
  }
}

@media (max-width: 1023px) {
  .poker-board {
    padding-bottom: calc(5.75rem + env(safe-area-inset-bottom, 0px));
  }

  .poker-board--waiting {
    padding-bottom: calc(8.5rem + env(safe-area-inset-bottom, 0px));
  }

  .poker-board--acting {
    padding-bottom: calc(17.5rem + env(safe-area-inset-bottom, 0px));
  }

  .winners--sidebar {
    display: none;
  }

  .controls-dock {
    position: fixed;
    left: 0;
    right: 0;
    bottom: 0;
    z-index: 40;
    gap: 0.45rem;
    padding:
      0.55rem 0.75rem
      max(0.65rem, env(safe-area-inset-bottom, 0px));
    background:
      linear-gradient(180deg, rgba(12, 16, 26, 0) 0%, rgba(12, 16, 26, 0.88) 18%, rgba(10, 14, 22, 0.98) 100%);
    backdrop-filter: blur(14px);
    -webkit-backdrop-filter: blur(14px);
    border-top: 1px solid rgba(255, 255, 255, 0.08);
    box-shadow: 0 -12px 40px rgba(0, 0, 0, 0.45);
  }

  .controls-dock .action-bar,
  .controls-dock .waiting,
  .controls-dock .next-hand,
  .controls-dock .reactions {
    padding: 0.65rem 0.75rem;
    border-radius: 14px;
    box-shadow: var(--shadow);
  }

  .controls-dock .reactions {
    padding-top: 0.5rem;
    padding-bottom: 0.5rem;
  }

  .controls-dock .reactions-label {
    margin-bottom: 0.4rem;
  }

  .controls-dock .reaction-buttons {
    flex-wrap: nowrap;
    overflow-x: auto;
    -webkit-overflow-scrolling: touch;
    scrollbar-width: none;
    gap: 0.3rem;
    padding-bottom: 0.1rem;
  }

  .controls-dock .reaction-buttons::-webkit-scrollbar {
    display: none;
  }

  .controls-dock .reaction-btn {
    flex: 0 0 auto;
    width: 2.5rem;
    height: 2.5rem;
    touch-action: manipulation;
  }

  .action-bar .action-buttons {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 0.45rem;
    margin: 0.55rem 0 0;
  }

  .action-bar .action-buttons button {
    min-height: 2.75rem;
    touch-action: manipulation;
  }

  .raise-hint--desktop {
    display: none;
  }

  .raise-toggle {
    display: flex;
    align-items: center;
    justify-content: space-between;
    width: 100%;
    margin-top: 0.35rem;
    padding: 0.55rem 0.75rem;
    border-radius: 10px;
    border: 1px solid var(--border);
    background: rgba(255, 255, 255, 0.04);
    color: var(--text-muted);
    font-family: inherit;
    font-size: 0.85rem;
    font-weight: 600;
    cursor: pointer;
    touch-action: manipulation;
  }

  .raise-toggle__chevron {
    display: inline-block;
    transition: transform 0.2s ease;
  }

  .raise-toggle__chevron--open {
    transform: rotate(180deg);
  }

  .raise-panel {
    display: none;
    gap: 0.5rem;
  }

  .raise-panel--open {
    display: flex;
  }

  .raise-presets {
    flex-wrap: nowrap;
    overflow-x: auto;
    -webkit-overflow-scrolling: touch;
    scrollbar-width: none;
    gap: 0.4rem;
    padding-bottom: 0.15rem;
  }

  .raise-presets::-webkit-scrollbar {
    display: none;
  }

  .raise-preset-btn {
    flex: 0 0 auto;
    min-width: max-content;
    padding-inline: 0.75rem;
  }

  .raise-select-row {
    gap: 0.5rem;
  }

  .raise-select-row label {
    flex: 1;
    min-width: 0;
    font-size: 0.85rem;
  }

  .raise-select-row select {
    flex: 1;
    min-width: 0;
    min-height: 2.5rem;
  }

  .waiting--dock p,
  .next-hand--dock {
    margin: 0;
  }

  .waiting--dock {
    text-align: center;
    font-size: 0.92rem;
  }

  .pot-center {
    display: none;
  }

  .table-wrap {
    min-height: min(50vh, 400px);
    padding: 0.85rem;
  }

  .table-felt {
    inset: 0.85rem;
  }

  .table-seats {
    inset: 0.85rem;
  }

  .community-zone {
    padding: 0.45rem 0.55rem;
  }

  .community {
    gap: clamp(0.15rem, 1.2vw, 0.35rem);
  }

  .community :deep(.playing-card--small) {
    width: clamp(42px, 13.5vw, 68px);
    height: clamp(60px, 19vw, 96px);
    font-size: clamp(0.95rem, 3.2vw, 1.15rem);
  }

  .community :deep(.corner__rank) {
    font-size: clamp(0.78rem, 2.8vw, 0.95rem);
  }

  .community :deep(.corner__suit) {
    font-size: clamp(0.7rem, 2.4vw, 0.85rem);
  }

  .community :deep(.suit--center) {
    font-size: clamp(1.45rem, 5vw, 2rem);
  }

  .table-felt :deep(.playing-card--small) {
    width: clamp(44px, 10vw, 72px);
    height: clamp(62px, 14vw, 102px);
  }

  .table-seats .hole-cards :deep(.playing-card) {
    flex: 1 1 0;
    max-width: calc(50% - 0.175rem);
  }

  .table-seats .hole-cards :deep(.playing-card--small) {
    width: 100%;
    height: auto;
    aspect-ratio: 24 / 34;
    font-size: clamp(0.52rem, 12cqw, 0.82rem);
  }

  .table-seats .hole-cards :deep(.corner__rank) {
    font-size: 0.9em;
  }

  .table-seats .hole-cards :deep(.corner__suit) {
    font-size: 0.82em;
  }

  .table-seats .hole-cards :deep(.suit--center) {
    font-size: 1.65em;
  }

  .hole-cards {
    gap: 0.25rem;
  }

  .phase-banner {
    font-size: clamp(1rem, 4.5vw, 1.45rem);
    padding: 0.65rem 1.15rem;
  }

  .winner-banner {
    padding: 1rem 1.15rem;
  }
}

@media (max-width: 640px) {
  .poker-board {
    padding: 0 0.65rem 0.65rem;
    min-height: auto;
  }

  .status-bar {
    gap: 0.55rem;
    padding: 0.55rem 0.75rem;
  }

  .status-pill {
    font-size: 0.72rem;
    padding: 0.25rem 0.55rem;
  }

  .status-pill--dealer {
    display: none;
  }

  .status-pot__amount {
    font-size: 1.15rem;
  }

  .last-action--table {
    font-size: 0.85rem;
  }

  .table-wrap {
    min-height: min(46vh, 360px);
    padding: 0.65rem;
    border-radius: 20px;
  }

  .table-felt {
    inset: 0.65rem;
  }

  .table-seats {
    inset: 0.65rem;
  }

  .seat {
    min-width: clamp(78px, 22vw, 112px);
    max-width: min(40vw, 112px);
  }

  .seat--players-6 {
    min-width: clamp(70px, 19vw, 98px);
    max-width: min(34vw, 98px);
  }

  .seat-info {
    padding: 0.4rem 0.5rem;
    font-size: 0.78rem;
  }

  .seat-name {
    font-size: 0.82rem;
  }

  .seat-chips {
    font-size: 0.72rem;
  }

  .hand-desc {
    font-size: 0.58rem;
  }

  .table-seats .hole-cards :deep(.playing-card--small) {
    font-size: clamp(0.48rem, 13cqw, 0.72rem);
  }

  .table-seats .hole-cards :deep(.suit--center) {
    font-size: 1.5em;
  }

  .hole-cards {
    gap: 0.2rem;
  }

  .seat.me {
    max-width: min(46vw, 120px);
  }

  .poker-board--waiting {
    padding-bottom: calc(8rem + env(safe-area-inset-bottom, 0px));
  }

  .poker-board--acting {
    padding-bottom: calc(16rem + env(safe-area-inset-bottom, 0px));
  }
}

@media (max-width: 1023px) and (orientation: landscape) {
  .table-wrap {
    min-height: min(72vh, 280px);
  }

  .poker-board {
    padding-bottom: calc(5rem + env(safe-area-inset-bottom, 0px));
  }

  .poker-board--waiting {
    padding-bottom: calc(6.5rem + env(safe-area-inset-bottom, 0px));
  }

  .poker-board--acting {
    padding-bottom: calc(10.5rem + env(safe-area-inset-bottom, 0px));
  }

  .controls-dock {
    display: grid;
    grid-template-columns: minmax(0, 1fr) auto;
    align-items: end;
    gap: 0.45rem 0.65rem;
  }

  .controls-dock .reactions {
    grid-column: 1 / -1;
    order: -1;
  }

  .controls-dock .action-bar,
  .controls-dock .waiting,
  .controls-dock .next-hand {
    margin: 0;
  }

  .action-bar .action-buttons {
    grid-template-columns: repeat(4, minmax(0, 1fr));
    margin-top: 0.35rem;
  }

  .raise-panel--open {
    grid-column: 1 / -1;
  }
}

@media (prefers-reduced-motion: reduce) {
  .phase-banner,
  .winner-banner,
  .seat.active .seat-info,
  .seat.winner .seat-info,
  .pot-center--pulse .pot-center__amount,
  .pot-center--rising .pot-center__amount,
  .pot-center--rising .pot-center__chips,
  .status-pot--rising .status-pot__amount,
  .status-pot--rising .status-pot__chip,
  .last-action--pop,
  .seat-reaction,
  .turn-hint__dot,
  .table-felt--spotlight,
  .table-felt--dealing,
  .community-zone--pulse,
  .action-bar--your-turn,
  .sparkle,
  .chip-fly,
  .burn-card-flash {
    animation: none !important;
  }

  .phase-pill-enter-active,
  .phase-pill-leave-active,
  .action-dock-enter-active,
  .action-dock-leave-active,
  .hand-desc-enter-active,
  .hand-desc-leave-active,
  .dealer-move-enter-active,
  .dealer-move-leave-active,
  .burn-flash-enter-active,
  .burn-flash-leave-active {
    transition: none !important;
    animation: none !important;
  }

  .seat,
  .last-action,
  .pot-center,
  .btn-action,
  .reaction-btn,
  .table-felt,
  .community-zone {
    transition: none !important;
  }
}
</style>
