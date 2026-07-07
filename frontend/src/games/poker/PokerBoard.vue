<script setup lang="ts">
import { computed, onUnmounted, ref, watch } from 'vue'
import type { Room, PokerGameState } from '@/types'
import PlayingCard from './PlayingCard.vue'

const CARD_REVEAL_MS = 700
const TURN_DELAY_MS = 1100
const ACTION_HOLD_MS = 1500
const SHOWDOWN_REVEAL_MS = 850
const PHASE_BANNER_MS = 2000
const BURN_CARD_MS = 700
const FOLD_ANIM_MS = 900
const ROUND_CIRCLE_PAUSE_MS = 1000
const POST_DEAL_PAUSE_MS = 1600
const POST_STREET_PAUSE_MS = 1400

const props = defineProps<{
  gameState: PokerGameState
  room: Room
  playerId: string
}>()

const emit = defineEmits<{
  action: [data: Record<string, unknown>]
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
    const entries = props.gameState.winners.map((winner) => ({
      playerId: winner.player_id,
      name:
        props.gameState.players.find((player) => player.id === winner.player_id)?.nickname ??
        'Player',
      amount: winner.amount,
      hand: winner.hand ? winner.hand.replace(/_/g, ' ') : null,
    }))
    const totalPot = entries.reduce((sum, entry) => sum + entry.amount, 0)
    const title =
      entries.length === 1
        ? `${entries[0].name} wins ${entries[0].amount}!`
        : `Split pot — ${totalPot} chips`

    return {
      type: 'hand' as const,
      eyebrow: entries.length === 1 ? 'Winner' : 'Winners',
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
  for (let i = 1; i <= steps; i++) {
    schedule(() => {
      displayedPot.value = Math.round(start + (diff * i) / steps)
    }, i * stepMs)
  }
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
}

function highlightActor(actorId: string | null, delayMs: number) {
  if (!actorId) {
    effectiveCurrentActorId.value = null
    return
  }
  effectiveCurrentActorId.value = null
  schedule(() => {
    effectiveCurrentActorId.value = actorId
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
    let delay = 0
    for (let i = current + 1; i <= targetCount; i++) {
      delay += CARD_REVEAL_MS
      const index = i
      schedule(() => {
        displayedCommunityCount.value = index
        lastDealtCommunityIndex.value = index - 1
      }, delay)
    }
    schedule(finishStreetDeal, delay + CARD_REVEAL_MS)
    return
  }

  streetTransitionPending.value = true
  let delay = 0
  let revealedUpTo = current

  for (const milestone of milestones) {
    const street = milestone === 3 ? 'flop' : milestone === 4 ? 'turn' : 'river'
    showPhaseBanner(street)
    delay += PHASE_BANNER_MS + BURN_CARD_MS

    for (let index = revealedUpTo + 1; index <= milestone; index++) {
      delay += CARD_REVEAL_MS
      schedule(() => {
        displayedCommunityCount.value = index
        lastDealtCommunityIndex.value = index - 1
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
    }, delay)
    delay += SHOWDOWN_REVEAL_MS
  }
}

const seatPositions = computed(() => {
  const order = props.gameState.seat_order
  const myIndex = order.indexOf(props.playerId)
  const rotated = [...order.slice(myIndex), ...order.slice(0, myIndex)]
  return rotated.map((id, visualIndex) => {
    const player = props.gameState.players.find((p) => p.id === id)
    const angle = (visualIndex / rotated.length) * 360 + 90
    const radiusX = 46
    const radiusY = 42
    const x = 50 + radiusX * Math.cos((angle * Math.PI) / 180)
    const y = 50 + radiusY * Math.sin((angle * Math.PI) / 180)
    return { id, player, x, y, visualIndex }
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
  emit('action', { type: 'fold' })
}

function check() {
  emit('action', { type: 'check' })
}

function call() {
  emit('action', { type: 'call' })
}

function raise() {
  emit('action', { type: 'raise', amount: raiseAmount.value })
}

function allIn() {
  emit('action', { type: 'all_in' })
}

function nextHand() {
  emit('action', { type: 'next_hand' })
}

watch(
  () => props.gameState.hand_number,
  (handNum) => {
    clearAllTimers()
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
  (communityCount) => {
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

    const playerId = String(action.player_id)
    const text = actionLabelFor(action)
    seatActionLabel.value = { playerId, text, type: String(action.type) }
    actionHighlightId.value = playerId
    holdForAction()

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
  (target) => {
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

onUnmounted(() => {
  clearAllTimers()
})
</script>

<template>
  <div class="poker-board">
    <div class="status-bar card">
      <span>Hand #{{ gameState.hand_number }}</span>
      <span class="phase">{{ phaseLabel }}</span>
      <span v-if="dealerPlayer" class="dealer-label">
        Dealer: <strong>{{ dealerPlayer.nickname }}</strong>
      </span>
      <span class="pot">Pot: <strong class="pot__amount">{{ displayedPot }}</strong></span>
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
          <div class="table-felt">
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

        <div class="community">
          <PlayingCard
            v-for="(card, i) in visibleCommunityCards"
            :key="`c-${gameState.hand_number}-${i}`"
            :rank="card.rank"
            :suit="card.suit"
            :deal="i === lastDealtCommunityIndex"
            small
          />
          <PlayingCard v-for="n in Math.max(0, 5 - visibleCommunityCards.length)" :key="`empty-${n}`" face-down small />
        </div>
        <div class="pot-center" :class="{ 'pot-center--pulse': actionHoldActive }">
          <span class="pot-center__label">Pot</span>
          <span class="pot-center__amount">{{ displayedPot }}</span>
        </div>

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
          <div v-if="gameState.dealer_player_id === seat.id" class="dealer-chip" title="Dealer">D</div>
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
                v-if="
                  visibleHoleCount(seat.id) >= cardIndex &&
                  showHoleCardFaceUp(seat.id) &&
                  seat.player?.hole_cards[cardIndex - 1]
                "
                :rank="seat.player?.hole_cards[cardIndex - 1]?.rank"
                :suit="seat.player?.hole_cards[cardIndex - 1]?.suit"
                :deal="shouldAnimateHoleCard(seat.id, cardIndex)"
                :flip="showdownRevealed.has(seat.id) && seat.id !== playerId"
                small
              />
              <PlayingCard
                v-else-if="visibleHoleCount(seat.id) >= cardIndex && seat.player?.status !== 'folded'"
                :deal="shouldAnimateHoleCard(seat.id, cardIndex)"
                face-down
                small
              />
            </template>
          </div>
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
          </div>
        </div>
      </div>
      </div>

      <aside class="poker-sidebar">
        <p
          v-if="lastActionText"
          class="last-action last-action--sidebar"
          :class="{ 'last-action--pop': actionHoldActive }"
        >
          {{ lastActionText }}
        </p>

        <div
          v-if="winnerCallout"
          class="winners card winners--reveal"
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

        <div v-if="canAct" class="action-bar card">
          <p class="turn-hint">Your turn — bet to call: {{ gameState.bet_to_call }}</p>
          <div class="action-buttons">
            <button type="button" class="btn-secondary" @click="fold">Fold</button>
            <button v-if="gameState.can_check" type="button" class="btn-secondary" @click="check">Check</button>
            <button v-if="gameState.bet_to_call > 0" type="button" class="btn-primary" @click="call">
              Call {{ gameState.bet_to_call }}
            </button>
            <button type="button" class="btn-secondary" @click="allIn">All-in</button>
          </div>
          <div v-if="raiseOptions.length" class="raise-row">
            <p class="raise-hint">
              Raise in {{ gameState.raise_increment }} chip increments
            </p>
            <div class="raise-presets">
              <button
                v-for="preset in raisePresets"
                :key="preset.label"
                type="button"
                class="btn-secondary"
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
              <button type="button" class="btn-primary" @click="raise">
                Raise to {{ raiseAmount }}
              </button>
            </div>
          </div>
        </div>

        <div
          v-else-if="!canAct && ['preflop', 'flop', 'turn', 'river'].includes(gameState.phase)"
          class="waiting card"
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

        <div v-if="gameState.phase === 'hand_complete' && isHost && !gameState.winner" class="next-hand card">
          <button type="button" class="btn-primary" @click="nextHand">Deal next hand</button>
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
}

.status-bar {
  display: flex;
  gap: 1.5rem;
  flex-wrap: wrap;
  font-weight: 600;
  padding: 0.75rem 1rem;
}

.dealer-label {
  color: #f0e6c8;
}

.dealer-label strong {
  color: #fff;
}

.pot {
  color: var(--success, #2ecc71);
}

.pot__amount {
  font-size: 1.35rem;
  font-weight: 800;
  font-variant-numeric: tabular-nums;
  color: #ffd700;
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
  background: rgba(0, 0, 0, 0.45);
  border-radius: inherit;
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
  top: 28%;
  left: 50%;
  transform: translateX(-50%);
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
}

.table-felt {
  position: absolute;
  inset: 0;
  background: radial-gradient(ellipse at center, #1e6b3a 0%, #0d3d22 100%);
  border-radius: 50% / 40%;
  border: 8px solid #5c3d1e;
  box-shadow: inset 0 0 40px rgba(0, 0, 0, 0.4);
}

.table-felt :deep(.playing-card--small) {
  width: clamp(56px, 5.8vw, 80px);
  height: clamp(80px, 8.2vw, 114px);
  font-size: clamp(0.9rem, 1.05vw, 1.1rem);
}

.table-felt :deep(.rank) {
  font-size: clamp(1rem, 1.2vw, 1.35rem);
}

.table-felt :deep(.suit) {
  font-size: clamp(1.25rem, 1.5vw, 1.65rem);
}

.community :deep(.playing-card--small) {
  width: clamp(62px, 6.5vw, 90px);
  height: clamp(88px, 9.2vw, 128px);
}

.seat.me .hole-cards :deep(.playing-card--small) {
  width: clamp(64px, 7vw, 94px);
  height: clamp(92px, 10vw, 136px);
}

.community {
  position: absolute;
  top: 38%;
  left: 50%;
  transform: translate(-50%, -50%);
  display: flex;
  gap: 0.5rem;
}

.pot-center {
  position: absolute;
  top: 52%;
  left: 50%;
  transform: translate(-50%, -50%);
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 0.15rem;
  text-align: center;
  pointer-events: none;
  transition: transform 0.3s ease, color 0.3s ease;
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
  min-width: clamp(90px, 8vw, 120px);
  transition: filter 0.35s ease, opacity 0.5s ease, transform 0.5s ease;
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
  background: rgba(0, 0, 0, 0.55);
  padding: 0.35rem 0.5rem;
  border-radius: 6px;
  color: #fff;
  font-size: 0.75rem;
  margin-bottom: 0.25rem;
  transition: background 0.3s ease, transform 0.3s ease;
}

.seat-bet {
  display: block;
  margin-top: 0.15rem;
  color: #ffd700;
  font-weight: 700;
  transition: transform 0.25s ease;
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
}

.dealer-chip {
  position: absolute;
  top: -0.65rem;
  right: -0.35rem;
  background: linear-gradient(145deg, #fff 0%, #e8e8e8 100%);
  color: #1a1a1a;
  border: 2px solid #c9a227;
  border-radius: 50%;
  width: 1.5rem;
  height: 1.5rem;
  line-height: 1.35rem;
  font-size: 0.7rem;
  font-weight: 900;
  box-shadow: 0 2px 6px rgba(0, 0, 0, 0.45);
  z-index: 3;
}

.blind-badge {
  display: inline-block;
  font-size: 0.55rem;
  font-weight: 800;
  padding: 0.1rem 0.3rem;
  border-radius: 3px;
  margin-right: 0.45rem;
  vertical-align: middle;
}

.blind-badge.sb {
  background: #3498db;
  color: #fff;
}

.blind-badge.bb {
  background: #e67e22;
  color: #fff;
}

.hole-cards {
  display: flex;
  gap: 0.35rem;
  justify-content: center;
}

.hand-desc {
  font-size: 0.65rem;
  color: #f0e6c8;
  margin: 0.2rem 0 0;
}

.action-bar,
.waiting,
.winners,
.game-over,
.next-hand {
  padding: 1rem;
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
  margin-bottom: 0.75rem;
  width: 100%;
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

.turn-hint {
  font-weight: 600;
  margin: 0;
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
}

@media (max-width: 640px) {
  .poker-board {
    padding: 0 0.75rem 0.75rem;
    min-height: auto;
  }

  .table-wrap {
    min-height: min(52vh, 440px);
  }

  .status-bar {
    gap: 0.75rem;
    font-size: 0.9rem;
  }
}
</style>
