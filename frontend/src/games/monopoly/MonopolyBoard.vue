<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import type { MonopolyGameState, MonopolyPlayerState, Room } from '@/types'
import {
  COLOR_HEX,
  COLOR_LABEL,
  SPACE_TINY,
  spaceGridPos,
  spaceSide,
  tokenGlyph,
} from './boardData'
import { useMonopolyFx } from './useMonopolyFx'
import { disposeSounds, isSoundMuted, setSoundMuted, unlockAudio } from './sounds'

const props = defineProps<{
  gameState: MonopolyGameState
  room: Room
  playerId: string
}>()

const emit = defineEmits<{
  action: [data: Record<string, unknown>]
}>()

const soundMuted = ref(isSoundMuted())
const showManage = ref(false)
const showTrade = ref(false)
const tradeToId = ref('')
const tradeOfferCash = ref(0)
const tradeRequestCash = ref(0)
const tradeOfferProps = ref<number[]>([])
const tradeRequestProps = ref<number[]>([])
const bidAmount = ref(10)
const selectedSpaceId = ref<number | null>(null)

const ZOOM_MIN = 0.7
const ZOOM_MAX = 2.5
const ZOOM_STEP = 0.15

const boardWrapRef = ref<HTMLElement | null>(null)
const boardSizePx = ref(640)
const zoom = ref(1)
const panX = ref(0)
const panY = ref(0)
const isPanning = ref(false)
const panStart = ref({ x: 0, y: 0, panX: 0, panY: 0 })

const boardFitStyle = computed(() => ({
  width: `${boardSizePx.value}px`,
  height: `${boardSizePx.value}px`,
}))

const boardTransformStyle = computed(() => ({
  transform: `translate(${panX.value}px, ${panY.value}px) scale(${zoom.value})`,
  transformOrigin: 'center center',
}))

function clampZoom(value: number) {
  return Math.min(ZOOM_MAX, Math.max(ZOOM_MIN, Math.round(value * 100) / 100))
}

/** Zoom while keeping the wrap-local point (ox, oy) from the wrap center fixed on screen. */
function zoomToward(next: number, offsetX: number, offsetY: number) {
  const prev = zoom.value
  const z = clampZoom(next)
  if (z === prev) return

  if (z <= 1.01) {
    zoom.value = z
    panX.value = 0
    panY.value = 0
    return
  }

  // screen = pan + content * zoom  (offsets from wrap/board center)
  const contentX = (offsetX - panX.value) / prev
  const contentY = (offsetY - panY.value) / prev
  zoom.value = z
  panX.value = offsetX - contentX * z
  panY.value = offsetY - contentY * z
}

function setZoom(next: number) {
  // Toolbar +/- zooms toward the center of the viewport.
  zoomToward(next, 0, 0)
}

function zoomIn() {
  setZoom(zoom.value + ZOOM_STEP)
}

function zoomOut() {
  setZoom(zoom.value - ZOOM_STEP)
}

function zoomReset() {
  zoom.value = 1
  panX.value = 0
  panY.value = 0
}

function measureBoard() {
  const el = boardWrapRef.value
  if (!el) return
  const pad = 8
  const size = Math.floor(Math.min(el.clientWidth, el.clientHeight) - pad)
  boardSizePx.value = Math.max(280, size)
}

function onBoardWheel(event: WheelEvent) {
  if (!(event.ctrlKey || event.metaKey || Math.abs(event.deltaY) > 0)) return
  event.preventDefault()

  const wrap = boardWrapRef.value
  if (!wrap) {
    setZoom(zoom.value + (event.deltaY > 0 ? -ZOOM_STEP : ZOOM_STEP))
    return
  }

  const rect = wrap.getBoundingClientRect()
  // Cursor offset from the wrap center (matches transform-origin: center).
  const offsetX = event.clientX - rect.left - rect.width / 2
  const offsetY = event.clientY - rect.top - rect.height / 2
  const delta = event.deltaY > 0 ? -ZOOM_STEP : ZOOM_STEP
  zoomToward(zoom.value + delta, offsetX, offsetY)
}

function onPanStart(event: PointerEvent) {
  if (zoom.value <= 1.02) return
  if ((event.target as HTMLElement | null)?.closest?.('.cell, button, input, select, a')) return
  isPanning.value = true
  panStart.value = {
    x: event.clientX,
    y: event.clientY,
    panX: panX.value,
    panY: panY.value,
  }
  ;(event.currentTarget as HTMLElement).setPointerCapture(event.pointerId)
}

function onPanMove(event: PointerEvent) {
  if (!isPanning.value) return
  panX.value = panStart.value.panX + (event.clientX - panStart.value.x)
  panY.value = panStart.value.panY + (event.clientY - panStart.value.y)
}

function onPanEnd(event: PointerEvent) {
  if (!isPanning.value) return
  isPanning.value = false
  try {
    ;(event.currentTarget as HTMLElement).releasePointerCapture(event.pointerId)
  } catch {
    /* ignore */
  }
}

let resizeObserver: ResizeObserver | null = null

function toggleSoundMute() {
  const next = !soundMuted.value
  setSoundMuted(next)
  soundMuted.value = next
  if (!next) void unlockAudio()
}

onMounted(() => {
  measureBoard()
  if (boardWrapRef.value) {
    resizeObserver = new ResizeObserver(() => measureBoard())
    resizeObserver.observe(boardWrapRef.value)
  }
  window.addEventListener('pointerdown', unlockAudio, { once: true })
})

onUnmounted(() => {
  resizeObserver?.disconnect()
  window.removeEventListener('pointerdown', unlockAudio)
  disposeSounds()
})

watch(zoom, (z) => {
  if (z <= 1.01) {
    panX.value = 0
    panY.value = 0
  }
})

const gs = computed(() => props.gameState)
const {
  movingPlayerId,
  landPulseId,
  buyFlashId,
  hopSpaceId,
  diceRolling,
  displayDice,
  cardOverlay,
  cardFlipped,
  cardLeaving,
  banner: boardBanner,
  cashFxByPlayer,
  displayPositions,
  boardBusy,
} = useMonopolyFx(gs)

const me = computed(() => gs.value.players[props.playerId] ?? null)
const isActor = computed(() => gs.value.current_actor_id === props.playerId)
const isTurnPlayer = computed(() => {
  const order = gs.value.seat_order
  const idx = gs.value.current_player_index
  return order[idx] === props.playerId
})
const phase = computed(() => gs.value.phase)
const isFinished = computed(() => phase.value === 'finished' || Boolean(gs.value.winner))

const playersList = computed(() =>
  gs.value.seat_order.map((id) => gs.value.players[id]).filter(Boolean) as MonopolyPlayerState[],
)

const playerIndex = computed(() => {
  const map: Record<string, number> = {}
  gs.value.seat_order.forEach((id, i) => {
    map[id] = i
  })
  return map
})

const actorName = computed(() => {
  const id = gs.value.current_actor_id
  return id ? (gs.value.players[id]?.nickname ?? '…') : '…'
})

const myProps = computed(() =>
  Object.entries(gs.value.properties)
    .filter(([, p]) => p.owner_id === props.playerId)
    .map(([id, p]) => ({
      id: Number(id),
      ...p,
      space: gs.value.spaces.find((s) => s.id === Number(id)),
    }))
    .sort((a, b) => a.id - b.id),
)

const landSpace = computed(() => {
  const pos = me.value?.position
  if (pos == null) return null
  return gs.value.spaces.find((s) => s.id === pos) ?? null
})

const landPrice = computed(() => landSpace.value?.price ?? null)

const tokensBySpace = computed(() => {
  const map: Record<number, MonopolyPlayerState[]> = {}
  for (const p of playersList.value) {
    if (p.bankrupt) continue
    const pos = displayPositions.value[p.id] ?? p.position
    if (!map[pos]) map[pos] = []
    map[pos].push(p)
  }
  return map
})

function send(action: Record<string, unknown>) {
  if (boardBusy.value && action.type !== 'resign') return
  void unlockAudio()
  emit('action', action)
}

const statusText = computed(() => {
  if (isFinished.value) {
    const w = gs.value.winner ? gs.value.players[gs.value.winner]?.nickname : null
    return w ? `${w} wins the game!` : 'Game over'
  }
  const p = phase.value
  if (p === 'awaiting_roll') return isActor.value ? 'Your turn — roll the dice' : `${actorName.value} to roll`
  if (p === 'awaiting_buy') {
    const name = landSpace.value?.name ?? 'property'
    return isActor.value ? `Buy ${name}?` : `${actorName.value} deciding`
  }
  if (p === 'auction') return isActor.value ? 'Your bid' : `Auction — ${actorName.value}`
  if (p === 'awaiting_payment') return isActor.value ? 'Raise cash or go bankrupt' : `${actorName.value} settling debt`
  if (p === 'trade_pending') return isActor.value ? 'Respond to trade' : 'Trade pending'
  if (p === 'awaiting_end') return isActor.value ? 'Build, trade, or end turn' : `${actorName.value}'s turn`
  return `${actorName.value}'s turn`
})

const selectedDeed = computed(() => {
  const id = selectedSpaceId.value
  if (id == null) return null
  const space = gs.value.spaces.find((s) => s.id === id)
  const prop = gs.value.properties[String(id)]
  if (!space) return null
  return { space, prop }
})

const selectedDeedRentRows = computed(() => {
  const space = selectedDeed.value?.space
  if (!space) return [] as { label: string; amount: number | null; note?: string; active: boolean }[]
  const houses = selectedDeed.value?.prop?.houses ?? 0
  const ownerId = selectedDeed.value?.prop?.owner_id ?? null

  function ownedOfKind(kind: string): number {
    if (!ownerId) return 0
    let n = 0
    for (const [sid, p] of Object.entries(gs.value.properties)) {
      if (p.owner_id !== ownerId) continue
      if (gs.value.spaces.find((s) => s.id === Number(sid))?.kind === kind) n += 1
    }
    return n
  }

  if (space.kind === 'property' && space.rents?.length) {
    const labels = [
      'Rent',
      'With 1 House',
      'With 2 Houses',
      'With 3 Houses',
      'With 4 Houses',
      'With Hotel',
    ]
    return space.rents.map((amount, i) => ({
      label: labels[i] ?? `Tier ${i}`,
      amount,
      active: (houses <= 4 && houses === i) || (houses >= 5 && i === 5),
    }))
  }
  if (space.kind === 'railroad') {
    const rrCount = ownedOfKind('railroad')
    return [1, 2, 3, 4].map((n) => ({
      label: n === 1 ? 'Rent' : `If ${n} R.R.'s owned`,
      amount: 25 * 2 ** (n - 1),
      active: rrCount === n,
    }))
  }
  if (space.kind === 'utility') {
    const utilCount = ownedOfKind('utility')
    return [
      { label: 'If one Utility owned', amount: null, note: '4× dice roll', active: utilCount === 1 },
      { label: 'If both Utilities owned', amount: null, note: '10× dice roll', active: utilCount >= 2 },
    ]
  }
  return []
})

function ownerColor(spaceId: number): string | null {
  const owner = gs.value.properties[String(spaceId)]?.owner_id
  if (!owner) return null
  return gs.value.players[owner]?.token_color ?? '#888'
}

function houseCount(spaceId: number): number {
  return gs.value.properties[String(spaceId)]?.houses ?? 0
}

function isMortgaged(spaceId: number): boolean {
  return Boolean(gs.value.properties[String(spaceId)]?.mortgaged)
}

function kindIcon(kind: string, id: number): string {
  if (kind === 'railroad') return '🚂'
  if (kind === 'utility') return id === 12 ? '💡' : '💧'
  if (kind === 'chance') return '?'
  if (kind === 'community_chest') return '📦'
  if (kind === 'tax') return '💰'
  if (kind === 'go') return '→'
  if (kind === 'jail') return '🔒'
  if (kind === 'free_parking') return '🅿'
  if (kind === 'go_to_jail') return '👮'
  return ''
}

function toggleOfferProp(id: number) {
  const set = new Set(tradeOfferProps.value)
  if (set.has(id)) set.delete(id)
  else set.add(id)
  tradeOfferProps.value = [...set]
}

function toggleRequestProp(id: number) {
  const set = new Set(tradeRequestProps.value)
  if (set.has(id)) set.delete(id)
  else set.add(id)
  tradeRequestProps.value = [...set]
}

function proposeTrade() {
  if (!tradeToId.value) return
  send({
    type: 'propose_trade',
    to_id: tradeToId.value,
    offer_cash: tradeOfferCash.value,
    request_cash: tradeRequestCash.value,
    offer_props: tradeOfferProps.value,
    request_props: tradeRequestProps.value,
  })
  showTrade.value = false
}

const partnerProps = computed(() => {
  if (!tradeToId.value) return []
  return Object.entries(gs.value.properties)
    .filter(([, p]) => p.owner_id === tradeToId.value)
    .map(([id, p]) => ({
      id: Number(id),
      ...p,
      space: gs.value.spaces.find((s) => s.id === Number(id)),
    }))
})

const logLines = computed(() => (gs.value.log || []).slice(-10).reverse())

const pendingTrade = computed(() => gs.value.pending_trade)

function selectSpace(id: number) {
  selectedSpaceId.value = selectedSpaceId.value === id ? null : id
}
</script>

<template>
  <div class="mono-play">
    <aside class="sidebar">
      <div class="status-card" :class="{ 'status-pulse': isActor }">
        <p class="status-label">Status</p>
        <h2 class="status">{{ statusText }}</h2>
        <div
          v-if="displayDice || gs.last_dice"
          class="dice-row"
          :class="{ rolling: diceRolling }"
          aria-label="Last dice roll"
        >
          <span class="die">{{ (displayDice ?? gs.last_dice)![0] }}</span>
          <span class="die-plus">+</span>
          <span class="die">{{ (displayDice ?? gs.last_dice)![1] }}</span>
          <span class="die-total">
            =
            {{
              (displayDice ?? gs.last_dice)![0] + (displayDice ?? gs.last_dice)![1]
            }}
          </span>
        </div>
      </div>

      <Transition name="fx-fade">
        <div
          v-if="gs.last_card && !cardOverlay"
          class="drawn-card mono-mini"
          :class="gs.last_card.id.startsWith('chance') ? 'chance' : 'chest'"
        >
          <header class="mono-mini-banner">
            {{ gs.last_card.id.startsWith('chance') ? 'Chance' : 'Community Chest' }}
          </header>
          <p>{{ gs.last_card.text }}</p>
        </div>
      </Transition>

      <div v-if="gs.auction" class="banner auction">
        <strong>Auction</strong>
        <span>{{ gs.spaces.find((s) => s.id === gs.auction!.space_id)?.name }}</span>
        <span class="banner-cash">High bid ${{ gs.auction.high_bid }}</span>
      </div>
      <div v-if="gs.debt" class="banner debt">
        <strong>Debt due</strong>
        <span>${{ gs.debt.amount }} — {{ gs.debt.reason }}</span>
      </div>
      <div v-if="pendingTrade" class="banner trade">
        <strong>Trade offer</strong>
        <span>
          {{ gs.players[pendingTrade.from_id]?.nickname }} →
          {{ gs.players[pendingTrade.to_id]?.nickname }}
        </span>
      </div>

      <section class="players-section">
        <h3 class="side-title">Players</h3>
        <ul class="players">
          <li
            v-for="p in playersList"
            :key="p.id"
            :class="{
              active: p.id === gs.current_actor_id,
              me: p.id === playerId,
              out: p.bankrupt,
              moving: movingPlayerId === p.id,
              jailed: p.in_jail,
            }"
          >
            <span class="tok" :style="{ background: p.token_color }" :title="p.nickname">
              {{ tokenGlyph(playerIndex[p.id] ?? 0) }}
            </span>
            <div class="p-info">
              <div class="p-name">
                <strong>{{ p.nickname }}</strong>
                <span v-if="p.id === playerId" class="you">you</span>
                <span v-if="p.in_jail" class="jail">Jail</span>
              </div>
              <span class="cash">${{ p.cash.toLocaleString() }}</span>
            </div>
            <div class="cash-fx-layer" aria-hidden="true">
              <span
                v-for="event in cashFxByPlayer[p.id] || []"
                :key="event.id"
                class="cash-float"
                :class="{ gain: (event.amount ?? 0) > 0, loss: (event.amount ?? 0) < 0 }"
              >
                {{ (event.amount ?? 0) > 0 ? '+' : '' }}${{ event.amount }}
              </span>
            </div>
          </li>
        </ul>
      </section>

      <section v-if="myProps.length" class="deeds-section">
        <h3 class="side-title">Your deeds</h3>
        <div class="deed-strip">
          <button
            v-for="prop in myProps"
            :key="prop.id"
            type="button"
            class="mini-deed"
            :class="{ mortgaged: prop.mortgaged }"
            :style="{ '--deed': prop.space?.color ? COLOR_HEX[prop.space.color] : '#555' }"
            :title="prop.space?.name"
            @click="selectSpace(prop.id)"
          >
            <span class="mini-bar" />
            <span class="mini-name">{{ prop.space?.name?.split(' ')[0] }}</span>
            <span v-if="prop.houses === 5" class="mini-hotel">H</span>
            <span v-else-if="prop.houses" class="mini-houses">{{ prop.houses }}</span>
          </button>
        </div>
      </section>

      <div v-if="selectedDeed" class="deed-card">
        <div
          class="deed-header"
          :style="{
            background: selectedDeed.space.color
              ? COLOR_HEX[selectedDeed.space.color]
              : selectedDeed.space.kind === 'railroad'
                ? '#1a1a1a'
                : selectedDeed.space.kind === 'utility'
                  ? '#6b8e23'
                  : '#444',
          }"
        >
          <span v-if="selectedDeed.space.color" class="deed-group">
            TITLE DEED · {{ COLOR_LABEL[selectedDeed.space.color] }}
          </span>
          <span v-else-if="selectedDeed.space.kind === 'railroad'" class="deed-group">
            RAILROAD
          </span>
          <span v-else-if="selectedDeed.space.kind === 'utility'" class="deed-group">
            UTILITY
          </span>
          <strong>{{ selectedDeed.space.name }}</strong>
        </div>
        <div class="deed-body">
          <p v-if="selectedDeed.space.price" class="deed-price">
            Price ${{ selectedDeed.space.price }}
          </p>
          <p v-if="selectedDeed.prop?.owner_id">
            Owner: {{ gs.players[selectedDeed.prop.owner_id]?.nickname }}
          </p>
          <p v-else-if="selectedDeed.space.price">Unowned</p>
          <p v-if="selectedDeed.prop?.mortgaged" class="mort-tag">Mortgaged</p>
          <p v-if="(selectedDeed.prop?.houses ?? 0) > 0">
            {{ selectedDeed.prop!.houses === 5 ? 'Hotel' : `${selectedDeed.prop!.houses} house(s)` }}
          </p>

          <table v-if="selectedDeedRentRows.length" class="deed-rents">
            <tbody>
              <tr
                v-for="row in selectedDeedRentRows"
                :key="row.label"
                :class="{ active: row.active }"
              >
                <th>{{ row.label }}</th>
                <td>{{ row.note ?? `$${row.amount}` }}</td>
              </tr>
            </tbody>
          </table>

          <div v-if="selectedDeed.space.house_cost" class="deed-meta">
            <p>Houses cost ${{ selectedDeed.space.house_cost }} each</p>
            <p>Hotels, ${{ selectedDeed.space.house_cost }} plus 4 houses</p>
          </div>
          <p v-if="selectedDeed.space.mortgage" class="deed-mortgage">
            Mortgage value ${{ selectedDeed.space.mortgage }}
          </p>
          <p v-if="selectedDeed.space.kind === 'property'" class="deed-note">
            If a player owns all lots of a color group, rent is doubled on unimproved lots.
          </p>
        </div>
      </div>

      <div class="log">
        <h3 class="side-title">Log</h3>
        <div v-for="(line, i) in logLines" :key="i" class="log-line">{{ line.message }}</div>
      </div>
    </aside>

    <div class="main">
      <div class="board-toolbar">
        <div class="zoom-controls" role="group" aria-label="Board zoom">
          <button type="button" class="zoom-btn" title="Zoom out" @click="zoomOut">−</button>
          <button type="button" class="zoom-label" title="Reset zoom" @click="zoomReset">
            {{ Math.round(zoom * 100) }}%
          </button>
          <button type="button" class="zoom-btn" title="Zoom in" @click="zoomIn">+</button>
        </div>
        <p class="zoom-hint">Scroll to zoom · drag to pan when zoomed</p>
        <button
          type="button"
          class="mute-btn"
          :aria-label="soundMuted ? 'Unmute sound' : 'Mute sound'"
          :title="soundMuted ? 'Unmute' : 'Mute'"
          @click="toggleSoundMute"
        >
          {{ soundMuted ? '🔇' : '🔊' }}
        </button>
      </div>

      <div
        ref="boardWrapRef"
        class="board-wrap"
        :class="{ panning: isPanning, zoomed: zoom > 1.02 }"
        @wheel.prevent="onBoardWheel"
        @pointerdown="onPanStart"
        @pointermove="onPanMove"
        @pointerup="onPanEnd"
        @pointercancel="onPanEnd"
      >
        <div class="board-scaler" :style="boardTransformStyle">
          <div class="board-frame" :style="boardFitStyle">
            <div class="board">
              <div class="center">
                <div class="center-texture" />
                <div class="brand-wrap" :class="{ dimmed: diceRolling || (cardOverlay && cardFlipped) }">
                  <div class="brand">MONOPOLY</div>
                  <div class="brand-sub">PROPERTY TRADING GAME</div>
                </div>
                <div class="center-decks" :class="{ dimmed: diceRolling || (cardOverlay && cardFlipped) }">
                  <div
                    class="deck chest-deck"
                    :class="{ draw: cardOverlay?.cardKind === 'community_chest' && !cardFlipped }"
                  >
                    <div class="deck-back-art chest-art" aria-hidden="true">
                      <svg viewBox="0 0 64 48" class="deck-icon">
                        <rect x="8" y="18" width="48" height="26" rx="3" fill="#c9a227" stroke="#5a3d0a" stroke-width="2" />
                        <rect x="14" y="10" width="36" height="12" rx="2" fill="#a67c1a" stroke="#5a3d0a" stroke-width="2" />
                        <circle cx="32" cy="30" r="4" fill="#5a3d0a" />
                        <rect x="30" y="30" width="4" height="8" fill="#5a3d0a" />
                      </svg>
                    </div>
                    <span>COMMUNITY</span>
                    <span>CHEST</span>
                  </div>
                  <div
                    class="deck chance-deck"
                    :class="{ draw: cardOverlay?.cardKind === 'chance' && !cardFlipped }"
                  >
                    <span class="deck-q" aria-hidden="true">?</span>
                    <span>CHANCE</span>
                  </div>
                </div>

                <Transition name="fx-dice">
                  <div v-if="diceRolling || displayDice" class="center-dice" :class="{ settle: !diceRolling }">
                    <span class="center-die">{{ (displayDice ?? gs.last_dice)?.[0] }}</span>
                    <span class="center-die">{{ (displayDice ?? gs.last_dice)?.[1] }}</span>
                  </div>
                </Transition>

                <div
                  v-if="cardOverlay"
                  class="mono-card-stage"
                  :class="[
                    cardOverlay.cardKind === 'chance' ? 'chance' : 'chest',
                    { flipped: cardFlipped, leaving: cardLeaving },
                  ]"
                >
                  <div class="mono-card">
                    <div class="mono-card-inner">
                      <div class="mono-face back" aria-hidden="true">
                        <div class="mono-back-frame">
                          <div class="mono-back-pattern" />
                          <div class="mono-back-center">
                            <template v-if="cardOverlay.cardKind === 'chance'">
                              <span class="mono-back-q">?</span>
                              <span class="mono-back-title">CHANCE</span>
                            </template>
                            <template v-else>
                              <svg viewBox="0 0 64 48" class="mono-back-chest">
                                <rect
                                  x="8"
                                  y="18"
                                  width="48"
                                  height="26"
                                  rx="3"
                                  fill="#c9a227"
                                  stroke="#3d2a08"
                                  stroke-width="2"
                                />
                                <rect
                                  x="14"
                                  y="10"
                                  width="36"
                                  height="12"
                                  rx="2"
                                  fill="#a67c1a"
                                  stroke="#3d2a08"
                                  stroke-width="2"
                                />
                                <circle cx="32" cy="30" r="4.5" fill="#3d2a08" />
                                <rect x="29.5" y="30" width="5" height="9" fill="#3d2a08" />
                              </svg>
                              <span class="mono-back-title">COMMUNITY<br />CHEST</span>
                            </template>
                          </div>
                        </div>
                      </div>
                      <div class="mono-face front">
                        <header class="mono-front-banner">
                          {{
                            cardOverlay.cardKind === 'chance' ? 'CHANCE' : 'COMMUNITY CHEST'
                          }}
                        </header>
                        <div class="mono-front-art" aria-hidden="true">
                          <span v-if="cardOverlay.cardKind === 'chance'" class="mono-front-q">?</span>
                          <svg v-else viewBox="0 0 64 48" class="mono-front-chest">
                            <rect
                              x="8"
                              y="18"
                              width="48"
                              height="26"
                              rx="3"
                              fill="#c9a227"
                              stroke="#3d2a08"
                              stroke-width="2"
                            />
                            <rect
                              x="14"
                              y="10"
                              width="36"
                              height="12"
                              rx="2"
                              fill="#a67c1a"
                              stroke="#3d2a08"
                              stroke-width="2"
                            />
                            <circle cx="32" cy="30" r="4.5" fill="#3d2a08" />
                            <rect x="29.5" y="30" width="5" height="9" fill="#3d2a08" />
                          </svg>
                        </div>
                        <p class="mono-front-text">{{ cardOverlay.text }}</p>
                        <footer class="mono-front-footer">MONOPOLY</footer>
                      </div>
                    </div>
                  </div>
                </div>
              </div>

              <button
                v-for="space in gs.spaces"
                :key="space.id"
                type="button"
                class="cell"
                :class="[
                  `side-${spaceSide(space.id)}`,
                  `kind-${space.kind}`,
                  {
                    corner: [0, 10, 20, 30].includes(space.id),
                    mortgaged: isMortgaged(space.id),
                    selected: selectedSpaceId === space.id,
                    'land-pulse': landPulseId === space.id || hopSpaceId === space.id,
                    'buy-flash': buyFlashId === space.id,
                    'auction-hot': gs.auction?.space_id === space.id,
                    'hop-trail': hopSpaceId === space.id,
                  },
                ]"
                :style="{
                  gridRow: spaceGridPos(space.id).row,
                  gridColumn: spaceGridPos(space.id).col,
                  '--stripe': space.color ? COLOR_HEX[space.color] : 'transparent',
                  '--owner': ownerColor(space.id) || 'transparent',
                }"
                :title="space.name"
                @click="selectSpace(space.id)"
              >
                <div v-if="space.color" class="stripe" />
                <div class="cell-inner">
                  <div class="label-stack">
                    <div
                      v-if="kindIcon(space.kind, space.id)"
                      class="kind-slot"
                      aria-hidden="true"
                    >
                      <span class="kind-icon">{{ kindIcon(space.kind, space.id) }}</span>
                    </div>
                    <div class="name">{{ SPACE_TINY[space.id] ?? space.name }}</div>
                  </div>
                  <div v-if="houseCount(space.id) > 0" class="buildings">
                    <template v-if="houseCount(space.id) === 5">
                      <span class="hotel pop-in" />
                    </template>
                    <template v-else>
                      <span
                        v-for="n in houseCount(space.id)"
                        :key="n"
                        class="house"
                        :class="{ 'pop-in': buyFlashId === space.id && n === houseCount(space.id) }"
                      />
                    </template>
                  </div>
                  <div v-if="space.price && ![0, 10, 20, 30].includes(space.id)" class="price">
                    ${{ space.price }}
                  </div>
                  <div v-if="isMortgaged(space.id)" class="mort-stamp">MORTGAGED</div>
                </div>
                <div class="tokens">
                  <span
                    v-for="t in tokensBySpace[space.id] || []"
                    :key="t.id"
                    class="token"
                    :class="{ hop: movingPlayerId === t.id }"
                    :style="{ background: t.token_color }"
                    :title="t.nickname"
                  >
                    {{ tokenGlyph(playerIndex[t.id] ?? 0) }}
                  </span>
                </div>
                <div
                  v-if="ownerColor(space.id)"
                  class="owner-pip"
                  :class="{ stamp: buyFlashId === space.id }"
                  :style="{ background: ownerColor(space.id)! }"
                />
              </button>
            </div>
          </div>
        </div>

        <div class="board-fx-layer" aria-live="polite">
          <Transition name="fx-banner">
            <div
              v-if="boardBanner"
              :key="boardBanner.id"
              class="board-banner"
              :class="boardBanner.tone"
              role="status"
            >
              <div class="board-banner-panel">
                <p class="board-banner-title">{{ boardBanner.title }}</p>
                <p v-if="boardBanner.subtitle" class="board-banner-sub">{{ boardBanner.subtitle }}</p>
              </div>
            </div>
          </Transition>
        </div>
      </div>

      <div v-if="!isFinished" class="actions" :class="{ busy: boardBusy }">
        <p v-if="boardBusy" class="busy-hint">Watching the board…</p>
        <template v-if="phase === 'awaiting_roll' && isTurnPlayer">
          <template v-if="me?.in_jail">
            <button
              type="button"
              class="btn-primary"
              :disabled="boardBusy"
              @click="send({ type: 'roll_jail' })"
            >
              Roll for doubles
            </button>
            <button
              v-if="(me?.cash ?? 0) >= 50"
              type="button"
              class="btn-secondary"
              :disabled="boardBusy"
              @click="send({ type: 'pay_jail' })"
            >
              Pay $50
            </button>
            <button
              v-if="(me?.get_out_cards ?? 0) > 0"
              type="button"
              class="btn-secondary"
              :disabled="boardBusy"
              @click="send({ type: 'use_jail_card' })"
            >
              Get Out of Jail Free
            </button>
          </template>
          <button
            v-else
            type="button"
            class="btn-primary btn-roll"
            :disabled="boardBusy"
            @click="send({ type: 'roll' })"
          >
            🎲 Roll dice
          </button>
        </template>

        <template v-if="phase === 'awaiting_buy' && isActor">
          <button
            type="button"
            class="btn-primary"
            :disabled="boardBusy || (landPrice != null && (me?.cash ?? 0) < landPrice)"
            @click="send({ type: 'buy' })"
          >
            Buy{{ landPrice != null ? ` for $${landPrice}` : '' }}
          </button>
          <button
            type="button"
            class="btn-secondary"
            :disabled="boardBusy"
            @click="send({ type: 'decline' })"
          >
            Auction instead
          </button>
        </template>

        <template v-if="phase === 'auction' && isActor">
          <label class="bid-label">
            Bid
            <input v-model.number="bidAmount" type="number" min="1" step="10" :disabled="boardBusy" />
          </label>
          <button
            type="button"
            class="btn-primary"
            :disabled="boardBusy"
            @click="send({ type: 'bid', amount: bidAmount })"
          >
            Bid ${{ bidAmount }}
          </button>
          <button
            type="button"
            class="btn-secondary"
            :disabled="boardBusy"
            @click="send({ type: 'pass_auction' })"
          >
            Pass
          </button>
        </template>

        <template v-if="phase === 'awaiting_payment' && isActor">
          <button
            type="button"
            class="btn-primary"
            :disabled="boardBusy || (me?.cash ?? 0) < (gs.debt?.amount ?? 0)"
            @click="send({ type: 'pay_debt' })"
          >
            Pay ${{ gs.debt?.amount ?? 0 }}
          </button>
          <button
            type="button"
            class="btn-secondary"
            :disabled="boardBusy"
            @click="showManage = true"
          >
            Manage assets
          </button>
          <button
            type="button"
            class="btn-danger"
            :disabled="boardBusy"
            @click="send({ type: 'declare_bankruptcy' })"
          >
            Bankruptcy
          </button>
        </template>

        <template v-if="phase === 'trade_pending' && isActor">
          <button
            type="button"
            class="btn-primary"
            :disabled="boardBusy"
            @click="send({ type: 'accept_trade' })"
          >
            Accept trade
          </button>
          <button
            type="button"
            class="btn-secondary"
            :disabled="boardBusy"
            @click="send({ type: 'reject_trade' })"
          >
            Reject
          </button>
        </template>

        <template v-if="phase === 'awaiting_end' && isTurnPlayer">
          <button
            type="button"
            class="btn-secondary"
            :disabled="boardBusy"
            @click="showManage = true"
          >
            Build / Mortgage
          </button>
          <button
            type="button"
            class="btn-secondary"
            :disabled="boardBusy"
            @click="showTrade = true"
          >
            Trade
          </button>
          <button
            type="button"
            class="btn-primary"
            :disabled="boardBusy || gs.can_roll_again"
            @click="send({ type: 'end_turn' })"
          >
            End turn
          </button>
        </template>

        <button
          v-if="me && !me.bankrupt && phase !== 'finished'"
          type="button"
          class="btn-danger resign"
          @click="send({ type: 'resign' })"
        >
          Resign
        </button>
      </div>
    </div>

    <div v-if="showManage" class="modal" @click.self="showManage = false">
      <div class="modal-card">
        <h3>Manage properties</h3>
        <ul class="prop-list">
          <li v-for="prop in myProps" :key="prop.id">
            <div
              class="prop-swatch"
              :style="{ background: prop.space?.color ? COLOR_HEX[prop.space.color] : '#444' }"
            />
            <div class="prop-meta">
              <strong>{{ prop.space?.name ?? prop.id }}</strong>
              <span v-if="prop.mortgaged" class="muted">Mortgaged</span>
              <span v-else-if="prop.houses">{{ prop.houses === 5 ? 'Hotel' : `${prop.houses} houses` }}</span>
            </div>
            <div class="prop-actions">
              <button type="button" class="btn-mini" @click="send({ type: 'build', space_id: prop.id })">
                Build
              </button>
              <button type="button" class="btn-mini" @click="send({ type: 'sell_building', space_id: prop.id })">
                Sell
              </button>
              <button
                v-if="!prop.mortgaged"
                type="button"
                class="btn-mini"
                @click="send({ type: 'mortgage', space_id: prop.id })"
              >
                Mortgage
              </button>
              <button
                v-else
                type="button"
                class="btn-mini"
                @click="send({ type: 'unmortgage', space_id: prop.id })"
              >
                Unmortgage
              </button>
            </div>
          </li>
          <li v-if="!myProps.length" class="empty">You don’t own any properties yet.</li>
        </ul>
        <button type="button" class="btn-secondary" @click="showManage = false">Close</button>
      </div>
    </div>

    <div v-if="showTrade" class="modal" @click.self="showTrade = false">
      <div class="modal-card">
        <h3>Propose trade</h3>
        <label class="field">
          Partner
          <select v-model="tradeToId">
            <option value="" disabled>Select…</option>
            <option
              v-for="p in playersList.filter((x) => x.id !== playerId && !x.bankrupt)"
              :key="p.id"
              :value="p.id"
            >
              {{ p.nickname }}
            </option>
          </select>
        </label>
        <div class="cash-row">
          <label class="field">Offer cash <input v-model.number="tradeOfferCash" type="number" min="0" /></label>
          <label class="field">
            Request cash <input v-model.number="tradeRequestCash" type="number" min="0" />
          </label>
        </div>
        <div class="trade-cols">
          <div>
            <h4>You offer</h4>
            <label v-for="prop in myProps" :key="'o' + prop.id" class="check">
              <input
                type="checkbox"
                :checked="tradeOfferProps.includes(prop.id)"
                @change="toggleOfferProp(prop.id)"
              />
              {{ prop.space?.name }}
            </label>
          </div>
          <div>
            <h4>You request</h4>
            <label v-for="prop in partnerProps" :key="'r' + prop.id" class="check">
              <input
                type="checkbox"
                :checked="tradeRequestProps.includes(prop.id)"
                @change="toggleRequestProp(prop.id)"
              />
              {{ prop.space?.name }}
            </label>
            <p v-if="tradeToId && !partnerProps.length" class="muted">No properties</p>
          </div>
        </div>
        <div class="modal-actions">
          <button type="button" class="btn-primary" @click="proposeTrade">Send proposal</button>
          <button type="button" class="btn-secondary" @click="showTrade = false">Cancel</button>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
@import url('https://fonts.googleapis.com/css2?family=Libre+Baskerville:wght@400;700&family=Source+Sans+3:wght@500;600;700&display=swap');

.mono-play {
  --felt: #0f5c3a;
  --felt-deep: #0a3d28;
  --cream: #f3e6c8;
  --ink: #1c1812;
  --wood: #5c3a1e;
  --wood-light: #8b5a2b;
  --accent: #c41e3a;
  display: grid;
  grid-template-columns: minmax(200px, 260px) 1fr;
  gap: 0.5rem;
  height: 100%;
  min-height: 0;
  padding: 0.35rem 0.5rem 0.5rem;
  color: #f2ebe0;
  font-family: 'Source Sans 3', system-ui, sans-serif;
  background:
    radial-gradient(ellipse at 30% 20%, rgba(196, 30, 58, 0.08), transparent 50%),
    linear-gradient(160deg, #14181f 0%, #1a221c 100%);
}

.sidebar {
  display: flex;
  flex-direction: column;
  gap: 0.65rem;
  background: linear-gradient(180deg, #1a221c 0%, #12161a 100%);
  border: 1px solid rgba(243, 230, 200, 0.12);
  border-radius: 14px;
  padding: 0.85rem;
  overflow: auto;
  min-height: 0;
}

.status-card {
  background: rgba(15, 92, 58, 0.25);
  border: 1px solid rgba(243, 230, 200, 0.15);
  border-radius: 10px;
  padding: 0.7rem 0.8rem;
}
.status-label {
  margin: 0;
  font-size: 0.65rem;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  color: #9bb89a;
}
.status {
  margin: 0.2rem 0 0.5rem;
  font-family: 'Libre Baskerville', Georgia, serif;
  font-size: 1.05rem;
  color: var(--cream);
  line-height: 1.3;
}
.dice-row {
  display: flex;
  align-items: center;
  gap: 0.35rem;
}
.dice-row.rolling .die {
  animation: die-tumble 0.12s linear infinite;
}
.die {
  width: 1.7rem;
  height: 1.7rem;
  display: grid;
  place-items: center;
  background: #fff;
  color: #111;
  border-radius: 5px;
  font-weight: 700;
  box-shadow: 1px 2px 0 #0005;
  transition: transform 0.2s ease;
}
.status-card.status-pulse {
  animation: status-breathe 2.4s ease-in-out infinite;
}
.die-plus,
.die-total {
  font-size: 0.85rem;
  color: #c8d5c0;
}

.drawn-card.mono-mini {
  border-radius: 6px;
  padding: 0;
  overflow: hidden;
  background: #f7f1e3;
  color: #1a1208;
  border: 2px solid #1a1208;
  box-shadow: 2px 3px 0 #0004;
  font-size: 0.78rem;
  line-height: 1.35;
}
.mono-mini-banner {
  display: block;
  padding: 0.28rem 0.55rem;
  font-size: 0.62rem;
  font-weight: 800;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  text-align: center;
  font-family: 'Libre Baskerville', Georgia, serif;
}
.drawn-card.chest .mono-mini-banner {
  background: #2f6fd4;
  color: #f7f1e3;
}
.drawn-card.chance .mono-mini-banner {
  background: #e67e16;
  color: #1a1208;
}
.drawn-card.mono-mini p {
  margin: 0;
  padding: 0.45rem 0.55rem 0.55rem;
  font-weight: 600;
}

.banner {
  display: flex;
  flex-direction: column;
  gap: 0.15rem;
  padding: 0.5rem 0.65rem;
  border-radius: 8px;
  font-size: 0.8rem;
}
.banner.auction {
  background: rgba(247, 148, 29, 0.2);
  border: 1px solid rgba(247, 148, 29, 0.4);
}
.banner.debt {
  background: rgba(196, 30, 58, 0.2);
  border: 1px solid rgba(196, 30, 58, 0.45);
}
.banner.trade {
  background: rgba(91, 141, 239, 0.2);
  border: 1px solid rgba(91, 141, 239, 0.4);
}
.banner-cash {
  font-weight: 700;
  color: #f0c36a;
}

.side-title {
  margin: 0 0 0.4rem;
  font-size: 0.68rem;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  color: #9bb89a;
}
.players {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
}
.players li {
  position: relative;
  display: flex;
  gap: 0.55rem;
  align-items: center;
  padding: 0.45rem 0.5rem;
  border-radius: 8px;
  background: rgba(255, 255, 255, 0.03);
  transition: background 0.25s ease, transform 0.25s ease, box-shadow 0.25s ease;
}
.players li.active {
  background: rgba(15, 92, 58, 0.45);
  box-shadow: inset 0 0 0 1px rgba(243, 230, 200, 0.25);
  animation: turn-glow 1.8s ease-in-out infinite;
}
.players li.moving .tok {
  animation: tok-bounce 0.55s ease;
}
.players li.jailed .tok {
  filter: grayscale(0.35);
  box-shadow: inset 0 0 0 2px #c41e3a;
}
.players li.me {
  outline: 1px solid rgba(243, 230, 200, 0.28);
}
.players li.out {
  opacity: 0.4;
}
.tok {
  width: 1.85rem;
  height: 1.85rem;
  border-radius: 50%;
  display: grid;
  place-items: center;
  font-size: 0.85rem;
  border: 2px solid #fff8;
  flex-shrink: 0;
  box-shadow: 0 1px 3px #0006;
}
.p-info {
  min-width: 0;
  flex: 1;
}
.p-name {
  display: flex;
  align-items: center;
  gap: 0.35rem;
  flex-wrap: wrap;
  font-size: 0.88rem;
}
.you {
  font-size: 0.65rem;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  color: #c4b08a;
}
.jail {
  font-size: 0.65rem;
  padding: 0.05rem 0.3rem;
  border-radius: 3px;
  background: #c41e3a;
  color: #fff;
}
.cash {
  display: block;
  color: #7dce8a;
  font-variant-numeric: tabular-nums;
  font-weight: 600;
  font-size: 0.9rem;
}

.deed-strip {
  display: flex;
  flex-wrap: wrap;
  gap: 0.3rem;
}
.mini-deed {
  width: 2.6rem;
  border: 1px solid #0005;
  border-radius: 3px;
  background: var(--cream);
  color: var(--ink);
  padding: 0;
  cursor: pointer;
  overflow: hidden;
  font-size: 0.5rem;
  line-height: 1.1;
}
.mini-deed.mortgaged {
  opacity: 0.55;
  filter: grayscale(0.4);
}
.mini-bar {
  display: block;
  height: 0.35rem;
  background: var(--deed);
}
.mini-name {
  display: block;
  padding: 0.15rem;
  font-weight: 700;
  text-align: center;
}
.mini-houses,
.mini-hotel {
  display: block;
  text-align: center;
  font-weight: 700;
  color: #0f5c3a;
  padding-bottom: 0.1rem;
}
.mini-hotel {
  color: var(--accent);
}

.deed-card {
  background: var(--cream);
  color: var(--ink);
  border-radius: 6px;
  overflow: hidden;
  box-shadow: 0 4px 14px #0005;
  font-size: 0.78rem;
}
.deed-header {
  padding: 0.45rem 0.55rem;
  text-align: center;
  color: #fff;
  text-shadow: 0 1px 1px #0005;
}
.deed-header strong {
  display: block;
  font-family: 'Libre Baskerville', Georgia, serif;
  font-size: 0.85rem;
}
.deed-group {
  display: block;
  font-size: 0.58rem;
  letter-spacing: 0.1em;
  text-transform: uppercase;
  opacity: 0.9;
}
.deed-body {
  padding: 0.45rem 0.6rem 0.6rem;
}
.deed-body p {
  margin: 0.15rem 0;
}
.deed-price {
  font-weight: 700;
  text-align: center;
  margin-bottom: 0.25rem !important;
}
.deed-rents {
  width: 100%;
  border-collapse: collapse;
  margin: 0.4rem 0 0.35rem;
  font-size: 0.72rem;
}
.deed-rents th {
  text-align: left;
  font-weight: 600;
  padding: 0.18rem 0.2rem;
  border-bottom: 1px solid #0002;
}
.deed-rents td {
  text-align: right;
  font-variant-numeric: tabular-nums;
  font-weight: 700;
  padding: 0.18rem 0.2rem;
  border-bottom: 1px solid #0002;
  white-space: nowrap;
}
.deed-rents tr.active th,
.deed-rents tr.active td {
  background: rgba(15, 92, 58, 0.12);
  color: #0f5c3a;
}
.deed-meta {
  margin-top: 0.35rem;
  padding-top: 0.3rem;
  border-top: 1px dashed #0003;
  font-size: 0.68rem;
  opacity: 0.9;
}
.deed-meta p {
  margin: 0.1rem 0;
}
.deed-mortgage {
  font-size: 0.7rem;
  font-weight: 600;
  margin-top: 0.25rem !important;
}
.deed-note {
  margin-top: 0.35rem !important;
  font-size: 0.62rem;
  line-height: 1.3;
  opacity: 0.75;
  font-style: italic;
}
.mort-tag {
  color: var(--accent);
  font-weight: 700;
}

.log {
  margin-top: auto;
  font-size: 0.72rem;
  color: #9a958c;
  max-height: 8.5rem;
  overflow: auto;
}
.log-line {
  padding: 0.2rem 0;
  border-bottom: 1px solid rgba(255, 255, 255, 0.05);
}

.main {
  display: flex;
  flex-direction: column;
  min-width: 0;
  min-height: 0;
  gap: 0.4rem;
  height: 100%;
  position: relative;
}

.board-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.75rem;
  flex-shrink: 0;
  padding: 0 0.15rem;
}

.zoom-controls {
  display: inline-flex;
  align-items: center;
  gap: 0.2rem;
  background: rgba(18, 22, 26, 0.9);
  border: 1px solid rgba(243, 230, 200, 0.14);
  border-radius: 999px;
  padding: 0.15rem;
}

.zoom-btn,
.zoom-label {
  border: none;
  background: transparent;
  color: var(--cream);
  cursor: pointer;
  font-family: inherit;
  font-weight: 700;
}

.zoom-btn {
  width: 2rem;
  height: 2rem;
  border-radius: 50%;
  font-size: 1.2rem;
  line-height: 1;
}

.zoom-btn:hover,
.zoom-label:hover {
  background: rgba(243, 230, 200, 0.12);
}

.zoom-label {
  min-width: 3.4rem;
  padding: 0.35rem 0.4rem;
  border-radius: 999px;
  font-size: 0.8rem;
  font-variant-numeric: tabular-nums;
}

.zoom-hint {
  margin: 0;
  font-size: 0.72rem;
  color: #8a9584;
  flex: 1;
}

.mute-btn {
  flex-shrink: 0;
  border: 1px solid rgba(243, 230, 200, 0.18);
  background: rgba(18, 22, 26, 0.9);
  color: var(--cream);
  border-radius: 999px;
  padding: 0.35rem 0.55rem;
  cursor: pointer;
  font-size: 0.9rem;
  line-height: 1;
}

.mute-btn:hover {
  background: rgba(243, 230, 200, 0.12);
}

.board-wrap {
  flex: 1;
  display: grid;
  place-items: center;
  min-height: 0;
  overflow: hidden;
  padding: 0;
  border-radius: 12px;
  background: rgba(0, 0, 0, 0.2);
  touch-action: none;
  cursor: default;
  position: relative;
}

.board-fx-layer {
  position: absolute;
  inset: 0;
  z-index: 30;
  pointer-events: none;
  /* Keep out of the wrap’s centering grid so the board never shifts. */
  display: block;
}

.board-wrap.zoomed {
  cursor: grab;
}

.board-wrap.panning {
  cursor: grabbing;
}

.board-scaler {
  will-change: transform;
  transition: transform 0.05s linear;
  /* Explicit grid placement so overlays never share the centering track. */
  grid-area: 1 / 1;
}

.board-frame {
  padding: clamp(6px, 1.1%, 14px);
  box-sizing: border-box;
  background: linear-gradient(145deg, var(--wood-light), var(--wood) 40%, #3d2412);
  border-radius: 8px;
  box-shadow:
    0 12px 40px rgba(0, 0, 0, 0.45),
    inset 0 1px 0 rgba(255, 255, 255, 0.15);
}

.board {
  display: grid;
  grid-template-columns: 1.45fr repeat(9, 1fr) 1.45fr;
  grid-template-rows: 1.45fr repeat(9, 1fr) 1.45fr;
  gap: 0;
  background: #2c2118;
  border: 2px solid #1a120c;
  width: 100%;
  height: 100%;
  container-type: size;
}

.center {
  grid-column: 2 / 11;
  grid-row: 2 / 11;
  position: relative;
  background: var(--felt);
  overflow: hidden;
  display: grid;
  place-items: center;
}
.brand-wrap.dimmed,
.center-decks.dimmed {
  opacity: 0.28;
  transition: opacity 0.25s ease;
}
.deck {
  transition: box-shadow 0.35s ease;
}
.deck.draw {
  animation: deck-draw 0.55s ease;
  box-shadow: 0 0 16px rgba(255, 255, 255, 0.35);
}
.center-texture {
  position: absolute;
  inset: 0;
  background:
    repeating-linear-gradient(
      -45deg,
      transparent,
      transparent 8px,
      rgba(0, 0, 0, 0.03) 8px,
      rgba(0, 0, 0, 0.03) 16px
    ),
    radial-gradient(circle at 50% 50%, rgba(255, 255, 255, 0.06), transparent 60%);
  pointer-events: none;
}
.brand-wrap {
  position: relative;
  z-index: 1;
  transform: rotate(-45deg);
  text-align: center;
}
.brand {
  font-family: 'Libre Baskerville', Georgia, serif;
  font-weight: 700;
  font-size: clamp(1.6rem, 4.2vw, 3.2rem);
  letter-spacing: 0.08em;
  color: var(--accent);
  text-shadow:
    2px 2px 0 #fff8,
    -1px -1px 0 #0004;
  line-height: 1;
}
.brand-sub {
  margin-top: 0.35rem;
  font-size: clamp(0.45rem, 1vw, 0.7rem);
  letter-spacing: 0.28em;
  color: rgba(243, 230, 200, 0.75);
  font-weight: 600;
}
.center-decks {
  position: absolute;
  inset: 12%;
  z-index: 1;
  pointer-events: none;
}
.deck {
  position: absolute;
  width: 22%;
  aspect-ratio: 5 / 7;
  border: 2.5px solid rgba(20, 16, 10, 0.55);
  border-radius: 5px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 0.15rem;
  font-size: clamp(0.38rem, 0.8vw, 0.6rem);
  font-weight: 800;
  letter-spacing: 0.08em;
  text-align: center;
  line-height: 1.15;
  box-shadow:
    2px 3px 0 #0004,
    inset 0 0 0 3px rgba(255, 255, 255, 0.18);
  overflow: hidden;
  transition: box-shadow 0.35s ease;
}
.deck-icon {
  width: 42%;
  height: auto;
  margin-bottom: 0.1rem;
}
.deck-q {
  font-family: 'Libre Baskerville', Georgia, serif;
  font-size: clamp(1.1rem, 2.8cqi, 2rem);
  font-weight: 700;
  line-height: 1;
  margin-bottom: 0.05rem;
}
.chest-deck {
  top: 8%;
  left: 8%;
  transform: rotate(45deg);
  background:
    radial-gradient(circle at 30% 25%, rgba(255, 255, 255, 0.22), transparent 45%),
    repeating-linear-gradient(
      45deg,
      #3a6fd0 0 6px,
      #2f5fba 6px 12px
    );
  color: #f4efe4;
  text-shadow: 0 1px 0 #1a3a7a;
}
.chance-deck {
  bottom: 8%;
  right: 8%;
  transform: rotate(45deg);
  background:
    radial-gradient(circle at 70% 30%, rgba(255, 255, 255, 0.28), transparent 45%),
    repeating-linear-gradient(
      -45deg,
      #f0a020 0 6px,
      #e08910 6px 12px
    );
  color: #1a1208;
}

.cell {
  position: relative;
  background: var(--cream);
  color: var(--ink);
  border: 1px solid #2c2118;
  padding: 0;
  margin: 0;
  cursor: pointer;
  overflow: hidden;
  display: flex;
  flex-direction: column;
  font-family: 'Source Sans 3', system-ui, sans-serif;
  box-shadow: inset 0 0 0 2.5px var(--owner);
  transition: filter 0.12s ease, transform 0.2s ease, box-shadow 0.25s ease;
}
.cell:hover,
.cell.selected {
  filter: brightness(1.06);
  z-index: 2;
}
.cell.mortgaged {
  background: #ddd3bc;
}
.cell.corner {
  font-weight: 700;
}
.cell.kind-go {
  background: #d6f0d6;
}
.cell.kind-jail {
  background: #f0e0c8;
}
.cell.kind-free_parking {
  background: #e8f0ff;
}
.cell.kind-go_to_jail {
  background: #f5d6d6;
}
.cell.kind-chance {
  background: #ffe2b8;
}
.cell.kind-community_chest {
  background: #cfe0ff;
}
.cell.kind-tax {
  background: #efe8d8;
}
.cell.kind-railroad {
  background: #ebe6dc;
}
.cell.kind-utility {
  background: #e8efe4;
}

.stripe {
  background: var(--stripe);
  flex-shrink: 0;
  border-bottom: 1px solid #0003;
}
.side-bottom .stripe,
.side-top .stripe {
  height: 22%;
  width: 100%;
}
.side-top {
  flex-direction: column-reverse;
}
.side-top .stripe {
  border-bottom: none;
  border-top: 1px solid #0003;
}
.side-left,
.side-right {
  flex-direction: row;
}
.side-left .stripe,
.side-right .stripe {
  width: 22%;
  height: 100%;
  border-bottom: none;
}
.side-left {
  flex-direction: row-reverse;
}
.side-left .stripe {
  border-left: 1px solid #0003;
}
.side-right .stripe {
  border-right: 1px solid #0003;
}

.cell-inner {
  flex: 1;
  min-width: 0;
  min-height: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 1px 2px;
  gap: 1px;
  position: relative;
}
/*
 * Rotate the whole content stack on side cells so “icon above name” stays
 * correct in the text’s local orientation (not just screen-up).
 */
.side-right .cell-inner {
  writing-mode: horizontal-tb;
  text-orientation: mixed;
  transform: rotate(90deg);
}
.side-left .cell-inner {
  writing-mode: horizontal-tb;
  text-orientation: mixed;
  transform: rotate(-90deg);
}
.side-top .cell-inner {
  transform: rotate(180deg);
}

/* Icon sits directly above the name; the parent rotation carries both. */
.label-stack {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 0.14em;
  max-width: 100%;
  max-height: 100%;
}
.kind-slot {
  flex: 0 0 auto;
  display: grid;
  place-items: center;
  line-height: 0;
}
.kind-icon {
  display: grid;
  place-items: center;
  width: 1.15em;
  height: 1.15em;
  font-size: clamp(0.62rem, 1.55cqi, 1.05rem);
  line-height: 1;
}
.name {
  font-size: clamp(0.42rem, 1.15cqi, 0.72rem);
  font-weight: 700;
  line-height: 1.05;
  text-align: center;
  white-space: pre-line;
  letter-spacing: -0.01em;
  text-transform: uppercase;
}
.corner .name {
  font-size: clamp(0.55rem, 1.5cqi, 0.95rem);
}
.price {
  font-size: clamp(0.38rem, 1cqi, 0.62rem);
  font-weight: 600;
  opacity: 0.85;
}
.buildings {
  display: flex;
  gap: 2px;
  flex-wrap: wrap;
  justify-content: center;
}
.house {
  width: clamp(7px, 1.4cqi, 12px);
  height: clamp(6px, 1.15cqi, 10px);
  background: #1fb25a;
  border: 0.5px solid #0a5c2e;
  border-radius: 1px 1px 0 0;
  box-shadow: inset 0 1px 0 #fff4;
}
.hotel {
  width: clamp(12px, 2.2cqi, 18px);
  height: clamp(8px, 1.6cqi, 14px);
  background: var(--accent);
  border: 0.5px solid #7a1020;
  border-radius: 1px;
}
.mort-stamp {
  position: absolute;
  inset: 0;
  display: grid;
  place-items: center;
  font-size: clamp(0.35rem, 0.9cqi, 0.55rem);
  font-weight: 800;
  color: var(--accent);
  letter-spacing: 0.04em;
  transform: rotate(-25deg);
  opacity: 0.75;
  pointer-events: none;
}
.tokens {
  position: absolute;
  bottom: 3px;
  right: 3px;
  display: flex;
  flex-wrap: wrap;
  gap: 2px;
  max-width: 92%;
  justify-content: flex-end;
  z-index: 3;
}
.side-top .tokens {
  bottom: auto;
  top: 3px;
}
.token {
  width: clamp(18px, 3.4cqi, 28px);
  height: clamp(18px, 3.4cqi, 28px);
  border-radius: 50%;
  border: 2px solid #fff;
  display: grid;
  place-items: center;
  font-size: clamp(9px, 1.7cqi, 14px);
  line-height: 1;
  box-shadow: 0 2px 4px #0008;
}
.owner-pip {
  position: absolute;
  top: 3px;
  left: 3px;
  width: clamp(6px, 1.2cqi, 10px);
  height: clamp(6px, 1.2cqi, 10px);
  border-radius: 50%;
  border: 1px solid #fff8;
  z-index: 2;
}
.side-bottom .owner-pip {
  top: auto;
  bottom: 2px;
}

.actions {
  display: flex;
  flex-wrap: wrap;
  gap: 0.45rem;
  align-items: center;
  padding: 0.55rem 0.65rem;
  background: rgba(18, 22, 26, 0.92);
  border: 1px solid rgba(243, 230, 200, 0.1);
  border-radius: 12px;
}
.btn-primary,
.btn-secondary,
.btn-danger,
.btn-mini {
  border-radius: 8px;
  padding: 0.55rem 0.95rem;
  border: 1px solid transparent;
  cursor: pointer;
  font-weight: 700;
  font-family: inherit;
}
.btn-primary {
  background: linear-gradient(180deg, #e8c97a, #c4a04a);
  color: #1a1408;
  box-shadow: 0 2px 0 #8a6a28;
}
.btn-roll {
  font-size: 1rem;
  padding: 0.65rem 1.2rem;
}
.btn-secondary {
  background: rgba(255, 255, 255, 0.07);
  color: var(--cream);
  border-color: rgba(243, 230, 200, 0.18);
}
.btn-danger {
  background: linear-gradient(180deg, #d64545, #a82020);
  color: #fff;
}
.btn-mini {
  padding: 0.28rem 0.5rem;
  font-size: 0.72rem;
  background: rgba(28, 24, 18, 0.08);
  color: var(--ink);
  border: 1px solid rgba(0, 0, 0, 0.15);
}
.btn-primary:disabled {
  opacity: 0.45;
  cursor: not-allowed;
}
.resign {
  margin-left: auto;
}
.bid-label,
.field {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
  font-size: 0.8rem;
}
.bid-label {
  flex-direction: row;
  align-items: center;
  gap: 0.4rem;
}
.bid-label input,
.field input,
.field select,
.modal-card input,
.modal-card select {
  background: #1a1f28;
  color: #eee;
  border: 1px solid rgba(255, 255, 255, 0.15);
  border-radius: 6px;
  padding: 0.35rem 0.5rem;
  width: 5.5rem;
  font-family: inherit;
}
.field select {
  width: 100%;
}

.modal {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.6);
  display: grid;
  place-items: center;
  z-index: 40;
  padding: 1rem;
}
.modal-card {
  background: linear-gradient(180deg, #243028, #1a1f24);
  border: 1px solid rgba(243, 230, 200, 0.15);
  border-radius: 14px;
  padding: 1.25rem;
  width: min(560px, 94vw);
  max-height: 85vh;
  overflow: auto;
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
  color: var(--cream);
}
.modal-card h3 {
  margin: 0;
  font-family: 'Libre Baskerville', Georgia, serif;
}
.prop-list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}
.prop-list li {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
  align-items: center;
  padding: 0.5rem;
  background: rgba(255, 255, 255, 0.04);
  border-radius: 8px;
  font-size: 0.85rem;
}
.prop-swatch {
  width: 0.85rem;
  height: 1.6rem;
  border-radius: 2px;
  flex-shrink: 0;
}
.prop-meta {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 0.1rem;
  min-width: 6rem;
}
.prop-actions {
  display: flex;
  gap: 0.25rem;
  flex-wrap: wrap;
}
.prop-actions .btn-mini {
  background: rgba(243, 230, 200, 0.12);
  color: var(--cream);
  border-color: rgba(243, 230, 200, 0.2);
}
.muted {
  color: #9a958c;
  font-size: 0.75rem;
}
.empty {
  justify-content: center;
  color: #9a958c;
}
.cash-row {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 0.75rem;
}
.trade-cols {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 0.75rem;
}
.trade-cols h4 {
  margin: 0 0 0.35rem;
  font-size: 0.8rem;
  color: #9bb89a;
}
.check {
  display: flex;
  gap: 0.35rem;
  font-size: 0.8rem;
  margin: 0.2rem 0;
  align-items: flex-start;
}
.modal-actions {
  display: flex;
  gap: 0.5rem;
}

/* ——— Motion / FX ——— */
.cash-fx-layer {
  position: absolute;
  right: 0.4rem;
  top: 0.15rem;
  pointer-events: none;
  z-index: 2;
}
.cash-float {
  display: block;
  font-size: 0.78rem;
  font-weight: 800;
  animation: cash-rise 1.4s ease-out forwards;
  text-shadow: 0 1px 2px #0008;
}
.cash-float.gain {
  color: #7dce8a;
}
.cash-float.loss {
  color: #ff8a7a;
}

.cell.land-pulse {
  animation: land-pulse 0.9s ease;
  z-index: 4;
}
.cell.buy-flash {
  animation: buy-flash 1s ease;
  z-index: 4;
}
.cell.auction-hot {
  animation: auction-pulse 1.2s ease-in-out infinite;
}
.cell.hop-trail {
  filter: brightness(1.12);
}

.actions.busy {
  opacity: 0.92;
}
.busy-hint {
  width: 100%;
  margin: 0 0 0.15rem;
  font-size: 0.78rem;
  color: #c4b08a;
  letter-spacing: 0.04em;
}
.btn-primary:disabled,
.btn-secondary:disabled {
  opacity: 0.45;
  cursor: not-allowed;
  animation: none;
}

.token {
  transition: transform 0.2s ease;
}
.token.hop {
  animation: token-hop 0.65s cubic-bezier(0.22, 1.2, 0.36, 1);
  z-index: 5;
}
.owner-pip.stamp {
  animation: pip-stamp 0.55s ease;
}
.house.pop-in,
.hotel.pop-in {
  animation: build-pop 0.45s cubic-bezier(0.2, 1.4, 0.3, 1);
}

.center-dice {
  position: absolute;
  z-index: 5;
  display: flex;
  gap: 0.75rem;
  align-items: center;
  justify-content: center;
}
.center-die {
  width: clamp(2.6rem, 8cqi, 4.2rem);
  height: clamp(2.6rem, 8cqi, 4.2rem);
  border-radius: 12px;
  background: #fff;
  color: #111;
  display: grid;
  place-items: center;
  font-size: clamp(1.3rem, 4cqi, 2rem);
  font-weight: 800;
  box-shadow: 0 8px 24px #0006;
  animation: die-tumble 0.1s linear infinite;
}
.center-dice.settle .center-die {
  animation: die-land 0.45s ease;
}

.mono-card-stage {
  position: absolute;
  inset: 0;
  z-index: 8;
  display: grid;
  place-items: center;
  perspective: 1100px;
  pointer-events: none;
}
.mono-card-stage.leaving {
  animation: mono-card-leave 0.4s ease forwards;
}
.mono-card {
  width: min(54%, 250px);
  aspect-ratio: 5 / 7;
  transform-style: preserve-3d;
  filter: drop-shadow(0 14px 28px rgba(0, 0, 0, 0.45));
}
.mono-card-stage.chest .mono-card {
  animation: draw-from-chest 0.62s cubic-bezier(0.22, 1, 0.36, 1) both;
}
.mono-card-stage.chance .mono-card {
  animation: draw-from-chance 0.62s cubic-bezier(0.22, 1, 0.36, 1) both;
}
.mono-card-inner {
  position: relative;
  width: 100%;
  height: 100%;
  transform-style: preserve-3d;
  transition: transform 0.72s cubic-bezier(0.4, 0.05, 0.2, 1);
}
.mono-card-stage.flipped .mono-card-inner {
  transform: rotateY(180deg);
}
.mono-face {
  position: absolute;
  inset: 0;
  backface-visibility: hidden;
  -webkit-backface-visibility: hidden;
  border-radius: 10px;
  overflow: hidden;
  border: 2.5px solid #1a1208;
}
.mono-face.back {
  transform: rotateY(0deg);
}
.mono-face.front {
  transform: rotateY(180deg);
  display: flex;
  flex-direction: column;
  background: #f7f1e3;
  color: #1a1208;
}
.mono-back-frame {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 8%;
}
.mono-card-stage.chest .mono-face.back {
  background:
    radial-gradient(circle at 30% 20%, rgba(255, 255, 255, 0.25), transparent 50%),
    repeating-linear-gradient(45deg, #3a6fd0 0 7px, #2f5fba 7px 14px);
}
.mono-card-stage.chance .mono-face.back {
  background:
    radial-gradient(circle at 70% 25%, rgba(255, 255, 255, 0.3), transparent 50%),
    repeating-linear-gradient(-45deg, #f0a020 0 7px, #e08910 7px 14px);
}
.mono-back-pattern {
  position: absolute;
  inset: 7%;
  border: 2px solid rgba(255, 255, 255, 0.35);
  border-radius: 6px;
  box-shadow: inset 0 0 0 3px rgba(0, 0, 0, 0.12);
  pointer-events: none;
}
.mono-back-center {
  position: relative;
  z-index: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 0.35rem;
  text-align: center;
}
.mono-back-q {
  font-family: 'Libre Baskerville', Georgia, serif;
  font-size: clamp(2.4rem, 9cqi, 4rem);
  font-weight: 700;
  line-height: 0.9;
  color: #1a1208;
  text-shadow: 0 2px 0 rgba(255, 255, 255, 0.35);
}
.mono-back-chest {
  width: clamp(3.2rem, 12cqi, 5rem);
  height: auto;
  filter: drop-shadow(0 2px 0 rgba(0, 0, 0, 0.25));
}
.mono-back-title {
  font-family: 'Libre Baskerville', Georgia, serif;
  font-size: clamp(0.55rem, 2cqi, 0.78rem);
  font-weight: 700;
  letter-spacing: 0.12em;
  line-height: 1.2;
  color: #f7f1e3;
  text-shadow: 0 1px 0 rgba(0, 0, 0, 0.35);
}
.mono-card-stage.chance .mono-back-title {
  color: #1a1208;
  text-shadow: 0 1px 0 rgba(255, 255, 255, 0.35);
}
.mono-front-banner {
  flex-shrink: 0;
  padding: 0.45rem 0.5rem;
  font-family: 'Libre Baskerville', Georgia, serif;
  font-size: clamp(0.58rem, 2.1cqi, 0.78rem);
  font-weight: 700;
  letter-spacing: 0.14em;
  text-align: center;
  color: #f7f1e3;
}
.mono-card-stage.chest .mono-front-banner {
  background: linear-gradient(180deg, #3f7ee0, #2a5fbe);
  border-bottom: 2px solid #1a3a7a;
}
.mono-card-stage.chance .mono-front-banner {
  background: linear-gradient(180deg, #f5a623, #e07b10);
  color: #1a1208;
  border-bottom: 2px solid #a35a08;
}
.mono-front-art {
  flex-shrink: 0;
  display: grid;
  place-items: center;
  padding: 0.45rem 0.35rem 0.15rem;
  min-height: 22%;
}
.mono-front-q {
  font-family: 'Libre Baskerville', Georgia, serif;
  font-size: clamp(1.6rem, 6cqi, 2.6rem);
  font-weight: 700;
  color: #e07b10;
  line-height: 1;
}
.mono-front-chest {
  width: clamp(2.4rem, 9cqi, 3.6rem);
  height: auto;
}
.mono-front-text {
  flex: 1;
  margin: 0;
  padding: 0.35rem 0.7rem 0.5rem;
  font-size: clamp(0.72rem, 2.35cqi, 0.92rem);
  font-weight: 600;
  line-height: 1.35;
  text-align: center;
  display: flex;
  align-items: center;
  justify-content: center;
}
.mono-front-footer {
  flex-shrink: 0;
  padding: 0.28rem 0.5rem 0.4rem;
  font-family: 'Libre Baskerville', Georgia, serif;
  font-size: clamp(0.45rem, 1.5cqi, 0.58rem);
  letter-spacing: 0.22em;
  text-align: center;
  color: #8a7a62;
  border-top: 1px dashed #cbbfa8;
}

.board-banner {
  position: absolute;
  inset: 0;
  display: grid;
  place-items: center;
  pointer-events: none;
  padding: 1rem;
}
.board-banner-panel {
  position: relative;
  z-index: 1;
  max-width: min(92%, 520px);
  text-align: center;
  padding: 1rem 1.4rem 1.15rem;
  border-radius: 14px;
  background: linear-gradient(180deg, rgba(18, 24, 20, 0.94), rgba(10, 14, 12, 0.92));
  border: 2px solid rgba(243, 230, 200, 0.35);
  box-shadow:
    0 18px 48px rgba(0, 0, 0, 0.55),
    inset 0 1px 0 rgba(255, 255, 255, 0.08);
}

.fx-banner-enter-active .board-banner-panel {
  animation: banner-panel-in 0.45s cubic-bezier(0.2, 1.2, 0.3, 1) both;
}
.fx-banner-leave-active .board-banner-panel {
  animation: banner-panel-out 0.28s ease forwards;
}
@keyframes banner-panel-in {
  0% {
    opacity: 0;
    transform: scale(0.72);
  }
  60% {
    opacity: 1;
    transform: scale(1.06);
  }
  100% {
    opacity: 1;
    transform: scale(1);
  }
}
@keyframes banner-panel-out {
  0% {
    opacity: 1;
    transform: scale(1);
  }
  100% {
    opacity: 0;
    transform: scale(0.92) translateY(-8px);
  }
}
.board-banner-title {
  margin: 0;
  font-family: 'Libre Baskerville', Georgia, serif;
  font-weight: 700;
  font-size: clamp(1.55rem, 4.8cqi, 3rem);
  line-height: 1.05;
  letter-spacing: 0.04em;
  text-transform: uppercase;
  color: var(--cream);
  text-shadow: 0 3px 0 rgba(0, 0, 0, 0.35);
  word-break: break-word;
}
.board-banner-sub {
  margin: 0.45rem 0 0;
  font-size: clamp(0.85rem, 2.2cqi, 1.15rem);
  font-weight: 600;
  color: rgba(243, 230, 200, 0.82);
  line-height: 1.25;
}

.board-banner.doubles .board-banner-panel,
.board-banner.win .board-banner-panel {
  border-color: rgba(232, 201, 122, 0.7);
  background: linear-gradient(180deg, rgba(70, 48, 12, 0.95), rgba(28, 18, 6, 0.94));
}
.board-banner.doubles .board-banner-title,
.board-banner.win .board-banner-title {
  color: #f3d48a;
}
.board-banner.jail .board-banner-panel,
.board-banner.bankrupt .board-banner-panel {
  border-color: rgba(220, 80, 70, 0.65);
  background: linear-gradient(180deg, rgba(70, 18, 18, 0.95), rgba(28, 8, 8, 0.94));
}
.board-banner.jail .board-banner-title,
.board-banner.bankrupt .board-banner-title {
  color: #ffb4a8;
}
.board-banner.buy .board-banner-panel,
.board-banner.build .board-banner-panel,
.board-banner.gain .board-banner-panel {
  border-color: rgba(80, 190, 120, 0.55);
}
.board-banner.buy .board-banner-title,
.board-banner.build .board-banner-title,
.board-banner.gain .board-banner-title {
  color: #9be7b0;
}
.board-banner.rent .board-banner-title {
  color: #ffc28a;
}
.board-banner.auction .board-banner-title {
  color: #9ec5ff;
}
.board-banner.card .board-banner-title {
  color: #f0a020;
}
.board-banner.turn .board-banner-title {
  color: #e8c97a;
}
.board-banner.land .board-banner-title {
  font-size: clamp(1.2rem, 3.6cqi, 2.2rem);
  text-transform: none;
  letter-spacing: 0.02em;
}
.board-banner.dice .board-banner-title {
  font-size: clamp(2.2rem, 7cqi, 4rem);
}

.fx-dice-enter-active,
.fx-dice-leave-active,
.fx-fade-enter-active,
.fx-fade-leave-active {
  transition: opacity 0.28s ease, transform 0.28s ease;
}
.fx-dice-enter-from {
  opacity: 0;
  transform: scale(0.7) rotate(-8deg);
}
.fx-dice-leave-to {
  opacity: 0;
  transform: scale(0.85);
}
.fx-fade-enter-from,
.fx-fade-leave-to {
  opacity: 0;
}

.btn-primary,
.btn-secondary {
  transition: transform 0.12s ease, filter 0.12s ease;
}
.btn-primary:active,
.btn-secondary:active {
  transform: scale(0.97);
}
.btn-roll {
  animation: roll-ready 1.6s ease-in-out infinite;
}

@keyframes die-tumble {
  0% { transform: rotate(0deg) scale(1); }
  50% { transform: rotate(12deg) scale(1.05); }
  100% { transform: rotate(-8deg) scale(0.98); }
}
@keyframes die-land {
  0% { transform: scale(1.25) rotate(-10deg); }
  60% { transform: scale(0.94) rotate(4deg); }
  100% { transform: scale(1) rotate(0deg); }
}
@keyframes token-hop {
  0% { transform: translateY(0) scale(1); }
  35% { transform: translateY(-12px) scale(1.25); }
  70% { transform: translateY(2px) scale(1.05); }
  100% { transform: translateY(0) scale(1); }
}
@keyframes land-pulse {
  0% { box-shadow: inset 0 0 0 2px transparent; filter: brightness(1); }
  35% { box-shadow: inset 0 0 0 3px #f0c36a; filter: brightness(1.18); }
  100% { box-shadow: inset 0 0 0 2.5px var(--owner); filter: brightness(1); }
}
@keyframes buy-flash {
  0% { filter: brightness(1); }
  30% { filter: brightness(1.35); transform: scale(1.04); }
  100% { filter: brightness(1); transform: scale(1); }
}
@keyframes auction-pulse {
  0%, 100% { box-shadow: inset 0 0 0 2px #f7941d88; }
  50% { box-shadow: inset 0 0 0 3px #f7941d; filter: brightness(1.08); }
}
@keyframes cash-rise {
  0% { opacity: 0; transform: translateY(6px); }
  15% { opacity: 1; }
  100% { opacity: 0; transform: translateY(-18px); }
}
@keyframes tok-bounce {
  0%, 100% { transform: scale(1); }
  40% { transform: scale(1.2); }
}
@keyframes turn-glow {
  0%, 100% { box-shadow: inset 0 0 0 1px rgba(243, 230, 200, 0.25); }
  50% { box-shadow: inset 0 0 0 1px rgba(243, 230, 200, 0.55), 0 0 12px rgba(15, 92, 58, 0.35); }
}
@keyframes status-breathe {
  0%, 100% { border-color: rgba(243, 230, 200, 0.15); }
  50% { border-color: rgba(232, 201, 122, 0.45); }
}
@keyframes deck-draw {
  0% { transform: rotate(45deg) scale(1); }
  40% { transform: rotate(45deg) scale(1.12); }
  100% { transform: rotate(45deg) scale(1); }
}
@keyframes draw-from-chest {
  0% {
    opacity: 0.7;
    transform: translate(-42%, -38%) rotate(45deg) scale(0.42);
  }
  55% {
    opacity: 1;
    transform: translate(4%, 2%) rotate(-4deg) scale(1.04);
  }
  100% {
    opacity: 1;
    transform: translate(0, 0) rotate(0deg) scale(1);
  }
}
@keyframes draw-from-chance {
  0% {
    opacity: 0.7;
    transform: translate(42%, 38%) rotate(45deg) scale(0.42);
  }
  55% {
    opacity: 1;
    transform: translate(-4%, -2%) rotate(5deg) scale(1.04);
  }
  100% {
    opacity: 1;
    transform: translate(0, 0) rotate(0deg) scale(1);
  }
}
@keyframes mono-card-leave {
  0% {
    opacity: 1;
    transform: scale(1);
  }
  100% {
    opacity: 0;
    transform: scale(0.88) translateY(-10px);
  }
}
@keyframes pip-stamp {
  0% { transform: scale(2.4); opacity: 0; }
  100% { transform: scale(1); opacity: 1; }
}
@keyframes build-pop {
  0% { transform: scale(0.2); opacity: 0; }
  100% { transform: scale(1); opacity: 1; }
}
@keyframes roll-ready {
  0%, 100% { box-shadow: 0 2px 0 #8a6a28; }
  50% { box-shadow: 0 2px 0 #8a6a28, 0 0 0 4px rgba(232, 201, 122, 0.25); }
}

@media (max-width: 900px) {
  .mono-play {
    grid-template-columns: 1fr;
    height: 100%;
  }
  .sidebar {
    max-height: 11rem;
    order: 2;
  }
  .main {
    order: 1;
    min-height: 55vh;
  }
  .zoom-hint {
    display: none;
  }
}
</style>
