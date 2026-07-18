<script setup lang="ts">
import { computed, nextTick, onMounted, onUnmounted, ref, watch } from 'vue'
import type { CSSProperties } from 'vue'
import type { Room, SolitaireCard, SolitaireGameState } from '@/types'
import {
  disposeSounds,
  isSoundMuted,
  playActionSound,
  playPickup,
  playWin,
  setSoundMuted,
  unlockAudio,
} from './sounds'

const props = defineProps<{
  gameState: SolitaireGameState
  room: Room
  playerId: string
}>()

const emit = defineEmits<{
  action: [data: Record<string, unknown>]
}>()

type CardRef = {
  source: 'waste' | 'tableau' | 'foundation'
  sourceIndex?: number
  cardIndex?: number
}

const selectedCard = ref<CardRef | null>(null)

const lastMoveTime = ref(Date.now())
const soundMuted = ref(isSoundMuted())
const suppressSounds = ref(true)
const lastSoundActionKey = ref('')
const coachMessage = ref('')
let coachMessageTimer: ReturnType<typeof setTimeout> | null = null

/** Per-column tableau spacing — only tall decks get compacted. */
const boardEl = ref<HTMLElement | null>(null)
const tableauEl = ref<HTMLElement | null>(null)
const MIN_FACE_DOWN_OFFSET = 8
const MAX_FACE_DOWN_OFFSET = 14
const MIN_FACE_UP_OFFSET = 18
const MAX_FACE_UP_OFFSET = 34
type ColumnOffsets = { fd: number; fu: number }
const defaultColumnOffsets = (): ColumnOffsets => ({
  fd: MAX_FACE_DOWN_OFFSET,
  fu: MAX_FACE_UP_OFFSET,
})
const columnOffsets = ref<ColumnOffsets[]>(
  Array.from({ length: 7 }, () => defaultColumnOffsets()),
)
let tableauResizeObserver: ResizeObserver | null = null

/** Board-level defaults for waste fan / drag ghost (tableau overrides per column). */
const boardLayoutStyle = computed((): CSSProperties => ({
  '--card-offset': `${MAX_FACE_UP_OFFSET}px`,
  '--card-offset-down': `${MAX_FACE_DOWN_OFFSET}px`,
}))

function peekStats(col: SolitaireCard[]): { down: number; up: number } {
  let down = 0
  let up = 0
  for (let i = 0; i < col.length - 1; i++) {
    if (col[i]?.face_up) up += 1
    else down += 1
  }
  return { down, up }
}

function offsetsForColumn(colIndex: number): ColumnOffsets {
  return columnOffsets.value[colIndex] ?? defaultColumnOffsets()
}

function columnLayoutStyle(colIndex: number): CSSProperties {
  const { fd, fu } = offsetsForColumn(colIndex)
  return {
    '--card-offset': `${fu}px`,
    '--card-offset-down': `${fd}px`,
  }
}

function cardStackTop(colIndex: number, col: SolitaireCard[], cardIndex: number): number {
  const { fd, fu } = offsetsForColumn(colIndex)
  let top = 0
  for (let i = 0; i < cardIndex; i++) {
    top += col[i]?.face_up ? fu : fd
  }
  return top
}

function measureCardHeight(tableau: HTMLElement, root: HTMLElement): number {
  const sample =
    (tableau.querySelector('.tableau-card--top .playing-card') as HTMLElement | null) ||
    (tableau.querySelector('.empty-column') as HTMLElement | null) ||
    (root.querySelector('.playing-card') as HTMLElement | null)
  const measured = sample?.getBoundingClientRect().height ?? 0
  if (measured > 0) return measured
  const widthVar = getComputedStyle(root).getPropertyValue('--card-width')
  const width = Number.parseFloat(widthVar)
  return Number.isFinite(width) && width > 0 ? width * 1.4 : 110
}

function computeColumnOffsets(
  down: number,
  up: number,
  cardHeight: number,
  available: number,
): ColumnOffsets {
  let fd = MAX_FACE_DOWN_OFFSET
  let fu = MAX_FACE_UP_OFFSET
  if (down + up === 0) return { fd, fu }

  const fits = (d: number, u: number) => cardHeight + down * d + up * u <= available

  if (!fits(fd, fu)) {
    // Shrink face-up peeks first (they're the bulk of long cascades)
    if (up > 0) {
      const room = available - cardHeight - down * fd
      fu = Math.max(MIN_FACE_UP_OFFSET, Math.floor(room / up))
    }
    if (!fits(fd, fu) && down > 0) {
      fu = Math.max(fu, MIN_FACE_UP_OFFSET)
      const room = available - cardHeight - up * fu
      fd = Math.max(MIN_FACE_DOWN_OFFSET, Math.floor(room / down))
    }
    if (!fits(fd, fu)) {
      fd = MIN_FACE_DOWN_OFFSET
      if (up > 0) {
        const room = available - cardHeight - down * fd
        fu = Math.max(MIN_FACE_UP_OFFSET, Math.floor(room / up))
      } else {
        fu = MIN_FACE_UP_OFFSET
      }
    }
  }
  return { fd, fu }
}

function recomputeStackOffsets() {
  const tableau = tableauEl.value
  const root = boardEl.value
  if (!tableau || !root) return

  const cardHeight = measureCardHeight(tableau, root)
  // Leave a little slack so the top card isn't flush against the chrome
  const available = Math.max(tableau.clientHeight - 8, cardHeight + 24)
  const cols = board.value.tableau

  columnOffsets.value = cols.map((col) => {
    const { down, up } = peekStats(col)
    return computeColumnOffsets(down, up, cardHeight, available)
  })
}

const AUTOPLAY_FLIGHT_MS = 900
const ANIMATABLE_ACTIONS = new Set([
  'move_to_tableau',
  'move_to_foundation',
  'draw',
  'reset_stock',
])

type FlightAnim = {
  cards: SolitaireCard[]
  x: number
  y: number
  offsetX: number
  offsetY: number
  source: CardRef
  dimStock?: boolean
}

/** Freeze the pre-move board while a Watch-mode card flies to its target. */
function cloneBoard(state: SolitaireGameState): SolitaireGameState {
  return JSON.parse(JSON.stringify(state)) as SolitaireGameState
}

const frozenBoard = ref<SolitaireGameState | null>(null)
const flight = ref<FlightAnim | null>(null)
const prevBoard = ref<SolitaireGameState>(cloneBoard(props.gameState))
const lastAutoplayAnimKey = ref('')
let flightRaf = 0

const board = computed(() => frozenBoard.value ?? props.gameState)

watch(() => props.gameState.moves, () => {
  lastMoveTime.value = Date.now()
})

const isFinished = computed(() => props.gameState.phase === 'finished')
const isAutoplay = computed(() => Boolean(props.gameState.autoplay))
const hint = computed(() => board.value.hint ?? null)
const isFlightAnimating = computed(() => flight.value !== null)

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

function ensureAudio() {
  void unlockAudio()
}

function showCoachMessage(text: string, ms = 4000) {
  coachMessage.value = text
  if (coachMessageTimer) clearTimeout(coachMessageTimer)
  coachMessageTimer = setTimeout(() => {
    coachMessage.value = ''
    coachMessageTimer = null
  }, ms)
}

function requestHint() {
  if (isFinished.value) return
  ensureAudio()
  emit('action', { type: 'hint' })
}

function toggleAutoplay() {
  if (isFinished.value) return
  ensureAudio()
  emit('action', { type: 'set_autoplay', enabled: !isAutoplay.value })
}

const DRAG_THRESHOLD = 8

type DragState = {
  source: CardRef
  cards: SolitaireCard[]
  startX: number
  startY: number
  x: number
  y: number
  offsetX: number
  offsetY: number
  active: boolean
  pointerId: number
  captureEl: HTMLElement | null
}

const dragState = ref<DragState | null>(null)

const suppressClick = ref(false)
const dragOverTableau = ref<number | null>(null)
const dragOverFoundation = ref<string | null>(null)

const isDragging = computed(() => Boolean(dragState.value?.active || flight.value))

function stopFlightRaf() {
  if (flightRaf) {
    cancelAnimationFrame(flightRaf)
    flightRaf = 0
  }
}

function cancelFlight() {
  stopFlightRaf()
  flight.value = null
  frozenBoard.value = null
}

function queryBoardEl(selector: string): HTMLElement | null {
  return document.querySelector(`.solitaire-board ${selector}`)
}

function rectCenter(rect: DOMRect): { x: number; y: number } {
  return { x: rect.left + rect.width * 0.4, y: rect.top + Math.min(28, rect.height * 0.25) }
}

function sourceRectForAction(
  action: Record<string, unknown>,
  state: SolitaireGameState,
): DOMRect | null {
  const type = String(action.type)
  if (type === 'draw' || type === 'reset_stock') {
    return queryBoardEl('[data-slot="stock"]')?.getBoundingClientRect() ?? null
  }
  const source = action.source
  if (source === 'waste') {
    return queryBoardEl('[data-slot="waste"]')?.getBoundingClientRect() ?? null
  }
  if (source === 'foundation') {
    const idx = Number(action.source_index)
    const suit = suitOrder[idx]
    if (!suit) return null
    return (
      queryBoardEl(`[data-drop="foundation"][data-suit="${suit}"]`)?.getBoundingClientRect() ??
      null
    )
  }
  if (source === 'tableau') {
    const col = Number(action.source_index)
    let cardIndex = Number(action.card_index ?? 0)
    if (type === 'move_to_foundation') {
      cardIndex = Math.max(0, (state.tableau[col]?.length ?? 1) - 1)
    }
    return (
      queryBoardEl(
        `[data-slot="tableau-card"][data-col="${col}"][data-card="${cardIndex}"]`,
      )?.getBoundingClientRect() ?? null
    )
  }
  return null
}

function targetRectForAction(action: Record<string, unknown>): DOMRect | null {
  const type = String(action.type)
  if (type === 'draw' || type === 'reset_stock') {
    return queryBoardEl('[data-slot="waste"]')?.getBoundingClientRect() ?? null
  }
  if (type === 'move_to_foundation') {
    // Suit inferred later via cards; prefer data-hint from moving card suit on next board
    return null
  }
  if (type === 'move_to_tableau') {
    const col = Number(action.target_col)
    const top = queryBoardEl(
      `[data-slot="tableau-card"][data-col="${col}"].tableau-card--top`,
    )
    if (top) return top.getBoundingClientRect()
    return queryBoardEl(`[data-drop="tableau"][data-col="${col}"]`)?.getBoundingClientRect() ?? null
  }
  return null
}

function cardsForAutoplayAction(
  prev: SolitaireGameState,
  next: SolitaireGameState,
  action: Record<string, unknown>,
): SolitaireCard[] {
  const type = String(action.type)
  if (type === 'draw') {
    // Face-down ghost; rank/suit unused while face_up is false
    return [{ rank: next.waste_top?.rank ?? 'A', suit: next.waste_top?.suit ?? 'spades', face_up: false }]
  }
  if (type === 'reset_stock') {
    return prev.waste_top
      ? [{ ...prev.waste_top, face_up: false }]
      : [{ rank: 'A', suit: 'spades', face_up: false }]
  }
  if (action.source === 'waste' && prev.waste_top) {
    return [{ ...prev.waste_top, face_up: true }]
  }
  if (action.source === 'foundation') {
    const idx = Number(action.source_index)
    const suit = suitOrder[idx]
    const top = suit ? prev.foundations[suit]?.top : null
    return top ? [{ ...top, face_up: true }] : []
  }
  if (action.source === 'tableau') {
    const col = Number(action.source_index)
    const pile = prev.tableau[col] ?? []
    if (type === 'move_to_foundation') {
      const top = pile[pile.length - 1]
      return top ? [{ ...top, face_up: true }] : []
    }
    const cardIndex = Number(action.card_index ?? 0)
    return pile.slice(cardIndex).filter((c) => c.face_up)
  }
  return []
}

function sourceRefFromAction(action: Record<string, unknown>): CardRef {
  const source = String(action.source ?? 'waste') as CardRef['source']
  if (source === 'waste') return { source: 'waste' }
  if (source === 'foundation') {
    return { source: 'foundation', sourceIndex: Number(action.source_index ?? 0) }
  }
  return {
    source: 'tableau',
    sourceIndex: Number(action.source_index ?? 0),
    cardIndex: Number(action.card_index ?? 0),
  }
}

function animateFlight(
  from: DOMRect,
  to: DOMRect,
  cards: SolitaireCard[],
  source: CardRef,
  dimStock = false,
): Promise<void> {
  stopFlightRaf()
  const offsetX = Math.min(Math.max(from.width * 0.35, 8), 40)
  const offsetY = 18
  const start = rectCenter(from)
  const end = {
    x: to.left + Math.min(to.width * 0.4, 40),
    y: to.top + Math.min(28, to.height * 0.2),
  }

  flight.value = {
    cards,
    x: start.x,
    y: start.y,
    offsetX,
    offsetY,
    source,
    dimStock,
  }

  return new Promise((resolve) => {
    const t0 = performance.now()
    const tick = (now: number) => {
      const t = Math.min(1, (now - t0) / AUTOPLAY_FLIGHT_MS)
      const eased = 1 - (1 - t) ** 3
      const cur = flight.value
      if (cur) {
        flight.value = {
          ...cur,
          x: start.x + (end.x - start.x) * eased,
          y: start.y + (end.y - start.y) * eased,
        }
      }
      if (t < 1) {
        flightRaf = requestAnimationFrame(tick)
      } else {
        flightRaf = 0
        flight.value = null
        resolve()
      }
    }
    flightRaf = requestAnimationFrame(tick)
  })
}

async function runAutoplayFlight(
  prev: SolitaireGameState,
  next: SolitaireGameState,
  action: Record<string, unknown>,
) {
  const type = String(action.type)
  const cards = cardsForAutoplayAction(prev, next, action)
  if (!cards.length) return

  frozenBoard.value = cloneBoard(prev)
  await nextTick()

  let from = sourceRectForAction(action, prev)
  let to = targetRectForAction(action)

  if (type === 'move_to_foundation') {
    const suit = cards[0]?.suit
    if (suit) {
      to =
        queryBoardEl(`[data-drop="foundation"][data-suit="${suit}"]`)?.getBoundingClientRect() ??
        to
    }
  }

  const isStockMove = type === 'draw' || type === 'reset_stock'
  const flightCards = isStockMove
    ? cards.map((c) => ({
        ...c,
        // Show a face-down card leaving the stock for draw/recycle
        face_up: false,
      }))
    : cards

  if (!from || !to) {
    frozenBoard.value = null
    return
  }

  const reason = action.reason
  if (typeof reason === 'string' && reason) {
    showCoachMessage(reason, 2200)
  }

  playSfx(playPickup)
  const source = isStockMove ? { source: 'waste' as const } : sourceRefFromAction(action)

  await animateFlight(from, to, flightCards, source, isStockMove)
  playSfx(() => playActionSound(type))
  frozenBoard.value = null
}

const suitSymbols: Record<string, string> = {
  hearts: '♥',
  diamonds: '♦',
  clubs: '♣',
  spades: '♠',
}

const suitOrder = ['hearts', 'diamonds', 'clubs', 'spades']
const RANK_ORDER = ['A', '2', '3', '4', '5', '6', '7', '8', '9', '10', 'J', 'Q', 'K']

function getSuitSymbol(suit: string | null): string {
  return suit ? suitSymbols[suit] ?? '' : ''
}

function isRed(suit: string | null): boolean {
  return suit === 'hearts' || suit === 'diamonds'
}

function rankValue(rank: string | null | undefined): number {
  if (!rank) return -1
  return RANK_ORDER.indexOf(rank) + 1
}

function canStackOnTableau(
  card: { rank: string | null; suit: string | null },
  target: { rank: string | null; suit: string | null },
): boolean {
  if (!card.rank || !card.suit || !target.rank || !target.suit) return false
  if (isRed(card.suit) === isRed(target.suit)) return false
  return rankValue(target.rank) === rankValue(card.rank) + 1
}

function getMovingCardFrom(ref: CardRef | null): { rank: string | null; suit: string | null } | null {
  if (!ref) return null
  if (ref.source === 'waste') {
    return props.gameState.waste_top
  }
  if (ref.source === 'tableau') {
    const col = props.gameState.tableau[ref.sourceIndex!]
    return col?.[ref.cardIndex ?? 0] ?? null
  }
  if (ref.source === 'foundation') {
    const suit = suitOrder[ref.sourceIndex!]
    return props.gameState.foundations[suit]?.top ?? null
  }
  return null
}

function getSelectedMovingCard(): { rank: string | null; suit: string | null } | null {
  return getMovingCardFrom(selectedCard.value)
}

function getDragCards(source: CardRef): SolitaireCard[] {
  if (source.source === 'waste') {
    return props.gameState.waste_top ? [props.gameState.waste_top] : []
  }
  if (source.source === 'foundation') {
    const suit = suitOrder[source.sourceIndex!]
    const top = props.gameState.foundations[suit]?.top
    return top ? [{ ...top, face_up: true }] : []
  }
  const col = props.gameState.tableau[source.sourceIndex!]
  if (!col) return []
  return col.slice(source.cardIndex ?? 0)
}

function canMoveRefToTableau(ref: CardRef, targetCol: number): boolean {
  const moving = getMovingCardFrom(ref)
  if (!moving) return false
  if (ref.source === 'tableau' && ref.sourceIndex === targetCol) return false
  const target = props.gameState.tableau[targetCol]
  if (!target.length) return moving.rank === 'K'
  const top = target[target.length - 1]
  if (!top.face_up) return false
  return canStackOnTableau(moving, top)
}

function canMoveRefToFoundation(ref: CardRef): boolean {
  if (ref.source === 'waste') {
    const card = props.gameState.waste_top
    return Boolean(card?.suit && canStackOnFoundation(card, card.suit))
  }
  if (ref.source === 'tableau') {
    const col = props.gameState.tableau[ref.sourceIndex!]
    if (!col?.length) return false
    if (ref.cardIndex !== col.length - 1) return false
    const card = col[col.length - 1]
    return Boolean(card.suit && canStackOnFoundation(card, card.suit))
  }
  return false
}

function canStackOnFoundation(
  card: { rank: string | null; suit: string | null },
  suit: string,
): boolean {
  if (!card.rank || !card.suit || card.suit !== suit) return false
  const foundation = props.gameState.foundations[suit]
  if (!foundation) return false
  if (foundation.count === 0) return card.rank === 'A'
  const top = foundation.top
  if (!top) return false
  return rankValue(card.rank) === rankValue(top.rank) + 1
}

function canMoveSelectionToTableau(targetCol: number): boolean {
  if (!selectedCard.value) return false
  return canMoveRefToTableau(selectedCard.value, targetCol)
}

function canMoveSelectionToFoundation(): boolean {
  if (!selectedCard.value) return false
  return canMoveRefToFoundation(selectedCard.value)
}

function activeMoveRef(): CardRef | null {
  return dragState.value?.active ? dragState.value.source : selectedCard.value
}

function isDropHighlightTableau(colIndex: number): boolean {
  const ref = activeMoveRef()
  return Boolean(ref && canMoveRefToTableau(ref, colIndex))
}

function isDropHighlightFoundation(suit: string): boolean {
  const ref = activeMoveRef()
  if (!ref || !canMoveRefToFoundation(ref)) return false
  return getMovingCardFrom(ref)?.suit === suit
}

function drawCard() {
  if (isFinished.value) return
  ensureAudio()
  if (props.gameState.stock_count > 0) {
    emit('action', { type: 'draw' })
  } else if (props.gameState.waste_count > 0) {
    emit('action', { type: 'reset_stock' })
  }
  clearSelection()
}

function selectWaste() {
  if (suppressClick.value || isFinished.value || !props.gameState.waste_top) return

  if (selectedCard.value?.source === 'waste') {
    clearSelection()
    return
  }

  selectedCard.value = { source: 'waste' }
}

function selectTableauCard(colIndex: number, cardIndex: number) {
  if (suppressClick.value || isFinished.value) return
  const col = props.gameState.tableau[colIndex]
  const card = col[cardIndex]
  if (!card) return

  if (selectedCard.value) {
    const sameCard =
      selectedCard.value.source === 'tableau' &&
      selectedCard.value.sourceIndex === colIndex &&
      selectedCard.value.cardIndex === cardIndex

    if (sameCard) {
      // Second single-click toggles off; use double-click for foundation
      clearSelection()
      return
    }

    if (canMoveSelectionToTableau(colIndex)) {
      moveToTableau(colIndex)
      return
    }

    // Illegal drop on a face-up card: treat as a new selection instead
    if (card.face_up) {
      selectedCard.value = { source: 'tableau', sourceIndex: colIndex, cardIndex }
      return
    }

    // Face-down peek in another column — keep current selection
    return
  }

  if (!card.face_up) return
  selectedCard.value = { source: 'tableau', sourceIndex: colIndex, cardIndex }
}

function selectEmptyTableau(colIndex: number) {
  if (suppressClick.value || isFinished.value) return
  if (selectedCard.value) {
    moveToTableau(colIndex)
  }
}

function selectFoundation(suit: string) {
  if (suppressClick.value || isFinished.value) return
  const foundation = props.gameState.foundations[suit]

  if (selectedCard.value) {
    if (selectedCard.value.source === 'foundation') {
      clearSelection()
      return
    }
    sendSelectedToFoundation()
    return
  }

  if (foundation.count > 0) {
    const suitIndex = suitOrder.indexOf(suit)
    selectedCard.value = { source: 'foundation', sourceIndex: suitIndex }
  }
}

function sendToFoundation(source: 'waste' | 'tableau', sourceIndex?: number) {
  if (source === 'waste') {
    const card = props.gameState.waste_top
    if (!card?.suit || !canStackOnFoundation(card, card.suit)) {
      clearSelection()
      return
    }
  } else if (source === 'tableau' && sourceIndex !== undefined) {
    const col = props.gameState.tableau[sourceIndex]
    const card = col?.[col.length - 1]
    if (!card?.suit || !canStackOnFoundation(card, card.suit)) {
      clearSelection()
      return
    }
  }

  emit('action', {
    type: 'move_to_foundation',
    source,
    source_index: sourceIndex,
  })
  clearSelection()
}

function sendSelectedToFoundation() {
  if (!selectedCard.value) return

  if (selectedCard.value.source === 'waste') {
    sendToFoundation('waste')
    return
  }
  if (selectedCard.value.source === 'tableau') {
    const colIndex = selectedCard.value.sourceIndex!
    const col = props.gameState.tableau[colIndex]
    if (selectedCard.value.cardIndex === col.length - 1) {
      sendToFoundation('tableau', colIndex)
    }
    return
  }
  clearSelection()
}

function moveRefToTableau(ref: CardRef, targetCol: number): boolean {
  if (isFinished.value) return false
  if (ref.source === 'tableau' && ref.sourceIndex === targetCol) return false
  if (!canMoveRefToTableau(ref, targetCol)) return false

  emit('action', {
    type: 'move_to_tableau',
    source: ref.source,
    source_index: ref.sourceIndex ?? null,
    card_index: ref.cardIndex ?? 0,
    target_col: targetCol,
  })
  clearSelection()
  return true
}

function moveToTableau(targetCol: number) {
  if (!selectedCard.value) return
  moveRefToTableau(selectedCard.value, targetCol)
}

function moveRefToFoundation(ref: CardRef): boolean {
  if (!canMoveRefToFoundation(ref)) return false
  if (ref.source === 'waste') {
    sendToFoundation('waste')
    return true
  }
  if (ref.source === 'tableau') {
    sendToFoundation('tableau', ref.sourceIndex)
    return true
  }
  return false
}

function onTableauDoubleClick(colIndex: number, cardIndex: number) {
  if (suppressClick.value || isFinished.value) return
  const col = props.gameState.tableau[colIndex]
  if (cardIndex !== col.length - 1 || !col[cardIndex]?.face_up) return
  selectedCard.value = { source: 'tableau', sourceIndex: colIndex, cardIndex }
  sendToFoundation('tableau', colIndex)
}

function onWasteDoubleClick() {
  if (suppressClick.value || isFinished.value || !props.gameState.waste_top) return
  selectedCard.value = { source: 'waste' }
  sendToFoundation('waste')
}

function endDragListeners() {
  window.removeEventListener('pointermove', onDragPointerMove)
  window.removeEventListener('pointerup', onDragPointerUp)
  window.removeEventListener('pointercancel', onDragPointerUp)
}

function releaseDragCapture(drag: DragState) {
  const el = drag.captureEl
  if (!el?.hasPointerCapture?.(drag.pointerId)) return
  try {
    el.releasePointerCapture(drag.pointerId)
  } catch {
    // ignore release failures
  }
}

function findDropTarget(clientX: number, clientY: number): HTMLElement | null {
  const stack = document.elementsFromPoint(clientX, clientY)
  for (const node of stack) {
    if (!(node instanceof HTMLElement)) continue
    if (node.closest('.solitaire-drag-ghost')) continue
    const drop = node.closest('[data-drop]') as HTMLElement | null
    if (drop) return drop
  }
  return null
}

function updateDragHover(clientX: number, clientY: number) {
  const drop = findDropTarget(clientX, clientY)
  if (!drop || !dragState.value) {
    dragOverTableau.value = null
    dragOverFoundation.value = null
    return
  }
  const kind = drop.dataset.drop
  if (kind === 'tableau') {
    const col = Number(drop.dataset.col)
    dragOverTableau.value = Number.isFinite(col) ? col : null
    dragOverFoundation.value = null
  } else if (kind === 'foundation') {
    dragOverFoundation.value = drop.dataset.suit ?? null
    dragOverTableau.value = null
  } else {
    dragOverTableau.value = null
    dragOverFoundation.value = null
  }
}

function patchDrag(patch: Partial<DragState>) {
  const current = dragState.value
  if (!current) return
  dragState.value = { ...current, ...patch }
}

function onDragPointerMove(event: PointerEvent) {
  const drag = dragState.value
  if (!drag || event.pointerId !== drag.pointerId) return

  const dx = event.clientX - drag.startX
  const dy = event.clientY - drag.startY
  let active = drag.active
  if (!active && (Math.abs(dx) > DRAG_THRESHOLD || Math.abs(dy) > DRAG_THRESHOLD)) {
    active = true
    selectedCard.value = { ...drag.source }
    suppressClick.value = true
    playSfx(playPickup)
  }
  if (!active) return

  event.preventDefault()
  patchDrag({ active: true, x: event.clientX, y: event.clientY })
  updateDragHover(event.clientX, event.clientY)
}

function onDragPointerUp(event: PointerEvent) {
  const drag = dragState.value
  if (!drag || event.pointerId !== drag.pointerId) return

  endDragListeners()
  releaseDragCapture(drag)

  if (drag.active) {
    updateDragHover(event.clientX, event.clientY)
    const ref = drag.source
    let dropped = false

    if (dragOverTableau.value !== null) {
      dropped = moveRefToTableau(ref, dragOverTableau.value)
    } else if (dragOverFoundation.value) {
      const moving = getMovingCardFrom(ref)
      if (moving?.suit === dragOverFoundation.value) {
        dropped = moveRefToFoundation(ref)
      }
    }

    if (!dropped) {
      clearSelection()
    }

    // Ignore the click that follows a drag gesture
    window.setTimeout(() => {
      suppressClick.value = false
    }, 0)
  }

  dragState.value = null
  dragOverTableau.value = null
  dragOverFoundation.value = null
}

function startDrag(event: PointerEvent, source: CardRef) {
  if (isFinished.value || event.button !== 0) return
  const cards = getDragCards(source)
  if (!cards.length || cards.some((c) => !c.face_up)) return

  ensureAudio()

  // Cancel any in-progress gesture before starting a new one
  if (dragState.value) {
    endDragListeners()
    releaseDragCapture(dragState.value)
    dragState.value = null
  }

  const target = event.currentTarget as HTMLElement | null
  const rect = target?.getBoundingClientRect()
  // Buried peeks are short; keep the grab offset near the top of a full card
  const offsetX = rect ? Math.min(Math.max(event.clientX - rect.left, 8), Math.max(rect.width - 8, 8)) : 20
  const offsetY = rect ? Math.min(Math.max(event.clientY - rect.top, 8), 28) : 20

  dragState.value = {
    source: { ...source },
    cards,
    startX: event.clientX,
    startY: event.clientY,
    x: event.clientX,
    y: event.clientY,
    offsetX,
    offsetY,
    active: false,
    pointerId: event.pointerId,
    captureEl: target,
  }

  try {
    target?.setPointerCapture(event.pointerId)
  } catch {
    // ignore capture failures
  }

  window.addEventListener('pointermove', onDragPointerMove, { passive: false })
  window.addEventListener('pointerup', onDragPointerUp)
  window.addEventListener('pointercancel', onDragPointerUp)
}

function onWastePointerDown(event: PointerEvent) {
  if (!props.gameState.waste_top) return
  startDrag(event, { source: 'waste' })
}

function onTableauPointerDown(event: PointerEvent, colIndex: number, cardIndex: number) {
  const card = props.gameState.tableau[colIndex]?.[cardIndex]
  if (!card?.face_up) return
  startDrag(event, { source: 'tableau', sourceIndex: colIndex, cardIndex })
}

function onFoundationPointerDown(event: PointerEvent, suit: string) {
  if (props.gameState.foundations[suit].count <= 0) return
  startDrag(event, { source: 'foundation', sourceIndex: suitOrder.indexOf(suit) })
}

function isDragSourceCard(colIndex: number, cardIndex: number): boolean {
  const active = dragState.value?.active ? dragState.value : flight.value
  if (!active || active.source.source !== 'tableau') return false
  if (active.source.sourceIndex !== colIndex) return false
  return cardIndex >= (active.source.cardIndex ?? 0)
}

function isFlightSourceWaste(): boolean {
  return Boolean(flight.value && flight.value.source.source === 'waste' && !flight.value.dimStock)
}

function isFlightSourceStock(): boolean {
  return Boolean(flight.value?.dimStock)
}

function isFlightSourceFoundation(suit: string): boolean {
  const f = flight.value
  if (!f || f.source.source !== 'foundation') return false
  return suitOrder[f.source.sourceIndex ?? -1] === suit
}

function autoComplete() {
  ensureAudio()
  emit('action', { type: 'auto_complete' })
}

function newGame() {
  ensureAudio()
  emit('action', { type: 'new_game' })
  clearSelection()
}

function clearSelection() {
  selectedCard.value = null
}

watch(
  () =>
    [
      props.gameState.moves,
      props.gameState.phase,
      props.gameState.stock_count,
      props.gameState.waste_count,
      props.gameState.last_action?.type ?? '',
    ] as const,
  () => {
    // Don't yank cards out from under an active drag (state sync mid-gesture)
    if (dragState.value?.active) return
    clearSelection()
    if (dragState.value) {
      endDragListeners()
      releaseDragCapture(dragState.value)
      dragState.value = null
    }
    dragOverTableau.value = null
    dragOverFoundation.value = null
  },
)

watch(
  () => props.gameState.last_action,
  (action) => {
    if (!action?.type) return
    const key = `${action.type}:${props.gameState.moves}:${props.gameState.stock_count}:${props.gameState.waste_count}:${props.gameState.phase}`
    if (key === lastSoundActionKey.value) return
    lastSoundActionKey.value = key
    if (suppressSounds.value) return
    if (action.type === 'autoplay_stuck') {
      const reason = props.gameState.hint?.reason || 'No useful moves left'
      showCoachMessage(reason)
      return
    }
    if (action.type === 'hint' && props.gameState.hint?.reason) {
      showCoachMessage(props.gameState.hint.reason, 6000)
    }
    // Autoplay move sounds play at the end of the flight animation
    if (action.via === 'autoplay' && ANIMATABLE_ACTIONS.has(String(action.type))) return
    playSfx(() => playActionSound(String(action.type)))
  },
)

watch(
  () =>
    [
      props.gameState.moves,
      props.gameState.stock_count,
      props.gameState.waste_count,
      props.gameState.phase,
      props.gameState.last_action?.type ?? '',
      props.gameState.last_action?.via ?? '',
      props.gameState.last_action?.target_col ?? '',
      props.gameState.last_action?.source_index ?? '',
      props.gameState.last_action?.card_index ?? '',
    ] as const,
  async () => {
    const next = props.gameState
    const action = next.last_action
    if (!action?.type) {
      prevBoard.value = cloneBoard(next)
      return
    }

    const animKey = `${action.type}:${action.via}:${next.moves}:${next.stock_count}:${next.waste_count}:${action.source ?? ''}:${action.source_index ?? ''}:${action.card_index ?? ''}:${action.target_col ?? ''}`
    if (animKey === lastAutoplayAnimKey.value) return

    const prev = prevBoard.value
    const shouldAnimate =
      action.via === 'autoplay' && ANIMATABLE_ACTIONS.has(String(action.type)) && !isFlightAnimating.value

    lastAutoplayAnimKey.value = animKey

    if (shouldAnimate) {
      try {
        await runAutoplayFlight(prev, next, action)
      } catch {
        cancelFlight()
      }
      prevBoard.value = cloneBoard(next)
      return
    }

    cancelFlight()
    prevBoard.value = cloneBoard(next)
  },
)

watch(
  () => props.gameState.phase,
  (phase, prev) => {
    if (!prev || phase === prev) return
    if (phase === 'finished') playSfx(playWin)
  },
)

watch(
  () => board.value.tableau.map((col) => `${col.length}:${col.filter((c) => c.face_up).length}`).join('|'),
  async () => {
    await nextTick()
    recomputeStackOffsets()
  },
)

onMounted(() => {
  // Skip sounds from the initial state snapshot / reconnect
  requestAnimationFrame(() => {
    suppressSounds.value = false
    recomputeStackOffsets()
  })
  if (tableauEl.value && typeof ResizeObserver !== 'undefined') {
    tableauResizeObserver = new ResizeObserver(() => recomputeStackOffsets())
    tableauResizeObserver.observe(tableauEl.value)
  }
  window.addEventListener('resize', recomputeStackOffsets)
})

onUnmounted(() => {
  if (coachMessageTimer) clearTimeout(coachMessageTimer)
  tableauResizeObserver?.disconnect()
  tableauResizeObserver = null
  window.removeEventListener('resize', recomputeStackOffsets)
  cancelFlight()
  if (dragState.value) {
    releaseDragCapture(dragState.value)
  }
  endDragListeners()
  disposeSounds()
})

function isCardSelected(source: string, sourceIndex?: number, cardIndex?: number): boolean {
  if (!selectedCard.value) return false
  if (selectedCard.value.source !== source) return false
  if (sourceIndex !== undefined && selectedCard.value.sourceIndex !== sourceIndex) return false
  if (cardIndex !== undefined && selectedCard.value.cardIndex !== cardIndex) return false
  return true
}

function isInSelectedStack(colIndex: number, cardIndex: number): boolean {
  if (isDragSourceCard(colIndex, cardIndex)) return true
  if (!selectedCard.value) return false
  if (selectedCard.value.source !== 'tableau') return false
  if (selectedCard.value.sourceIndex !== colIndex) return false
  return cardIndex >= (selectedCard.value.cardIndex ?? 0)
}

const dragGhostStyle = computed(() => {
  const drag = dragState.value?.active ? dragState.value : flight.value
  if (!drag) return undefined
  return {
    left: `${drag.x - drag.offsetX}px`,
    top: `${drag.y - drag.offsetY}px`,
  }
})

const ghostCards = computed(() => {
  if (dragState.value?.active) return dragState.value.cards
  return flight.value?.cards ?? []
})

const foundationProgress = computed(() => {
  let total = 0
  for (const foundation of Object.values(board.value.foundations)) {
    total += foundation.count
  }
  return Math.round((total / 52) * 100)
})

const progressBarWidth = computed(() => `${foundationProgress.value}%`)

const cardsInFoundations = computed(() => {
  let total = 0
  for (const foundation of Object.values(board.value.foundations)) {
    total += foundation.count
  }
  return total
})

const wasteFan = computed(() => {
  const fan = board.value.waste_fan
  if (fan?.length) return fan
  return board.value.waste_top ? [board.value.waste_top] : []
})

/** Draw-3 needs a top-row stock/waste fan; Draw-1 keeps the side rail. */
const isDrawThree = computed(() => Number(board.value.settings?.draw_count ?? 1) === 3)

const hasSelection = computed(() => selectedCard.value !== null)

const hintReason = computed(() => {
  if (coachMessage.value) return coachMessage.value
  const h = hint.value
  if (h?.reason && h.type !== 'none') return h.reason
  return ''
})

function isHintSourceWaste(): boolean {
  const h = hint.value
  if (!h) return false
  return h.type === 'move_to_foundation' || h.type === 'move_to_tableau'
    ? h.source === 'waste'
    : false
}

function isHintSourceStock(): boolean {
  const h = hint.value
  return h?.type === 'draw' || h?.type === 'reset_stock'
}

function isHintSourceFoundation(suit: string): boolean {
  const h = hint.value
  if (!h || h.source !== 'foundation' || h.type !== 'move_to_tableau') return false
  return suitOrder[h.source_index ?? -1] === suit
}

function isHintSourceTableau(colIndex: number, cardIndex: number): boolean {
  const h = hint.value
  if (!h || h.source !== 'tableau') return false
  if (h.source_index !== colIndex) return false
  const from = h.card_index ?? 0
  if (h.type === 'move_to_foundation') {
    return cardIndex === board.value.tableau[colIndex].length - 1
  }
  return cardIndex >= from
}

function isHintTargetTableau(colIndex: number): boolean {
  const h = hint.value
  return h?.type === 'move_to_tableau' && h.target_col === colIndex
}

function isHintTargetFoundation(suit: string): boolean {
  const h = hint.value
  if (!h || h.type !== 'move_to_foundation') return false
  if (h.source === 'waste') {
    return board.value.waste_top?.suit === suit
  }
  if (h.source === 'tableau' && h.source_index != null) {
    const col = board.value.tableau[h.source_index]
    const top = col?.[col.length - 1]
    return top?.suit === suit
  }
  return false
}
</script>

<template>
  <div
    ref="boardEl"
    class="solitaire-board"
    :class="{
      'solitaire-board--dragging': isDragging,
      'solitaire-board--autoplay': isAutoplay || isFlightAnimating,
      'solitaire-board--draw3': isDrawThree,
    }"
    :style="boardLayoutStyle"
    @click.self="clearSelection"
  >
    <div class="status-bar">
      <div class="stats-row">
        <div class="stat-item">
          <span class="stat-icon">🎯</span>
          <span class="stat-value">{{ board.moves }}</span>
          <span class="stat-label">moves</span>
        </div>
        <div class="stat-item stat-item--progress">
          <span class="stat-icon">📊</span>
          <div class="progress-wrap">
            <div class="progress-bar">
              <div class="progress-fill" :style="{ width: progressBarWidth }"></div>
            </div>
            <span class="progress-text">{{ cardsInFoundations }}/52</span>
          </div>
        </div>
      </div>
      <div class="status-bar__right">
        <button
          type="button"
          class="sound-toggle"
          :aria-label="soundMuted ? 'Unmute sound' : 'Mute sound'"
          :title="soundMuted ? 'Unmute' : 'Mute'"
          @click="toggleSound"
        >
          {{ soundMuted ? '🔇' : '🔊' }}
        </button>
        <button
          v-if="!isFinished"
          type="button"
          class="btn-action btn-action--hint"
          @click="requestHint"
        >
          <span class="btn-icon">💡</span>
          Hint
        </button>
        <button
          v-if="!isFinished"
          type="button"
          class="btn-action btn-action--watch"
          :class="{ 'btn-action--watch-on': isAutoplay }"
          @click="toggleAutoplay"
        >
          <span class="btn-icon">{{ isAutoplay ? '⏸' : '▶' }}</span>
          {{ isAutoplay ? 'Stop' : 'Watch' }}
        </button>
        <button
          v-if="board.can_auto_complete && !isFinished"
          type="button"
          class="btn-action btn-action--auto"
          @click="autoComplete"
        >
          <span class="btn-icon">✨</span>
          Auto-complete
        </button>
        <button type="button" class="btn-action btn-action--new" @click="newGame">
          <span class="btn-icon">🔄</span>
          New Game
        </button>
      </div>
    </div>

    <p v-if="hintReason" class="coach-banner" role="status">{{ hintReason }}</p>

    <div class="game-area" :class="isDrawThree ? 'game-area--standard' : 'game-area--rail'">
      <!-- Draw-1: side rail for tall cascades. Draw-3: classic top row for the waste fan. -->
      <aside
        :class="isDrawThree ? 'top-row' : 'side-rail'"
        aria-label="Stock and foundations"
      >
        <div class="stock-waste">
          <div
            class="card-slot stock"
            data-slot="stock"
            :class="{ 
              'stock--empty': board.stock_count === 0 && board.waste_count === 0,
              'stock--can-recycle': board.stock_count === 0 && board.waste_count > 0,
              'hint-source': isHintSourceStock(),
              'drag-source': isFlightSourceStock(),
            }"
            @click="drawCard"
          >
            <div v-if="board.stock_count > 0" class="playing-card playing-card--back">
              <div class="card-back">
                <div class="card-back__pattern"></div>
              </div>
              <span class="stock-badge">{{ board.stock_count }}</span>
            </div>
            <div v-else-if="board.waste_count > 0" class="recycle-slot">
              <span class="recycle-icon">↺</span>
              <span class="recycle-label">Reset</span>
            </div>
            <div v-else class="empty-slot empty-slot--stock">
              <span class="empty-icon">✗</span>
            </div>
          </div>

          <div
            class="card-slot waste"
            data-slot="waste"
            :class="{
              selected: isCardSelected('waste'),
              'waste--has-card': wasteFan.length > 0,
              'waste--fan': wasteFan.length > 1,
              'drag-source': (isDragging && dragState?.source.source === 'waste') || isFlightSourceWaste(),
              'hint-source': isHintSourceWaste(),
            }"
            :style="wasteFan.length > 1 ? { '--fan-count': wasteFan.length } : undefined"
            @click="selectWaste"
            @dblclick.stop="onWasteDoubleClick"
            @pointerdown="onWastePointerDown"
          >
            <template v-if="wasteFan.length">
              <div
                v-for="(card, fanIndex) in wasteFan"
                :key="`waste-${fanIndex}-${card.rank}-${card.suit}`"
                class="playing-card waste-fan-card"
                :class="{ red: isRed(card.suit), 'waste-fan-card--top': fanIndex === wasteFan.length - 1 }"
                :style="{ '--fan-index': fanIndex }"
              >
                <span class="corner corner--tl">
                  <span class="corner__rank">{{ card.rank }}</span>
                  <span class="corner__suit">{{ getSuitSymbol(card.suit) }}</span>
                </span>
                <span class="suit suit--center">{{ getSuitSymbol(card.suit) }}</span>
                <span class="corner corner--br">
                  <span class="corner__rank">{{ card.rank }}</span>
                  <span class="corner__suit">{{ getSuitSymbol(card.suit) }}</span>
                </span>
              </div>
            </template>
            <div v-else class="empty-slot empty-slot--waste">
              <span class="empty-label">Waste</span>
            </div>
          </div>
        </div>

        <div class="foundations">
          <div
            v-for="suit in suitOrder"
            :key="suit"
            class="card-slot foundation"
            :class="{
              selected: isCardSelected('foundation', suitOrder.indexOf(suit)),
              complete: board.foundations[suit].count === 13,
              'foundation--has-card': board.foundations[suit].count > 0,
              'drop-target': isDropHighlightFoundation(suit) || isHintTargetFoundation(suit),
              'drag-over': dragOverFoundation === suit && isDropHighlightFoundation(suit),
              'drag-source': (isDragging && dragState?.source.source === 'foundation' && suitOrder[dragState.source.sourceIndex!] === suit) || isFlightSourceFoundation(suit),
              'hint-source': isHintSourceFoundation(suit),
              'hint-target': isHintTargetFoundation(suit),
            }"
            :data-drop="'foundation'"
            :data-suit="suit"
            @click="selectFoundation(suit)"
            @pointerdown="onFoundationPointerDown($event, suit)"
          >
            <div v-if="board.foundations[suit].top" class="playing-card" :class="{ red: isRed(suit) }">
              <span class="corner corner--tl">
                <span class="corner__rank">{{ board.foundations[suit].top?.rank }}</span>
                <span class="corner__suit">{{ getSuitSymbol(suit) }}</span>
              </span>
              <span class="suit suit--center">{{ getSuitSymbol(suit) }}</span>
              <span class="corner corner--br">
                <span class="corner__rank">{{ board.foundations[suit].top?.rank }}</span>
                <span class="corner__suit">{{ getSuitSymbol(suit) }}</span>
              </span>
              <span class="foundation-badge">{{ board.foundations[suit].count }}</span>
            </div>
            <div v-else class="empty-slot foundation-empty">
              <span class="foundation-suit" :class="{ red: isRed(suit) }">{{ getSuitSymbol(suit) }}</span>
              <span class="foundation-hint">A</span>
            </div>
          </div>
        </div>
      </aside>

      <div ref="tableauEl" class="tableau">
        <div
          v-for="(col, colIndex) in board.tableau"
          :key="colIndex"
          class="tableau-column"
          :class="{
            'tableau-column--drop-ok': isDropHighlightTableau(colIndex) || isHintTargetTableau(colIndex),
            'tableau-column--has-selection': hasSelection || isDragging,
            'tableau-column--drag-over': dragOverTableau === colIndex && isDropHighlightTableau(colIndex),
            'tableau-column--hint-target': isHintTargetTableau(colIndex),
          }"
          :style="columnLayoutStyle(colIndex)"
          :data-drop="'tableau'"
          :data-col="colIndex"
          @click.self="hasSelection && moveToTableau(colIndex)"
        >
          <div
            v-if="col.length === 0"
            class="card-slot empty-column"
            :class="{
              'drop-target': isDropHighlightTableau(colIndex) || isHintTargetTableau(colIndex),
              'hint-target': isHintTargetTableau(colIndex),
            }"
            @click="selectEmptyTableau(colIndex)"
          >
            <div class="empty-slot empty-slot--tableau">
              <span class="empty-king">K</span>
            </div>
          </div>
          <div
            v-for="(card, cardIndex) in col"
            :key="`${colIndex}-${cardIndex}`"
            class="tableau-card"
            :class="{
              selected: isInSelectedStack(colIndex, cardIndex),
              'face-down': !card.face_up,
              'tableau-card--top': cardIndex === col.length - 1,
              'drag-source': isDragSourceCard(colIndex, cardIndex),
              'hint-source': isHintSourceTableau(colIndex, cardIndex),
            }"
            :data-slot="'tableau-card'"
            :data-col="colIndex"
            :data-card="cardIndex"
            :style="{
              top: `${cardStackTop(colIndex, col, cardIndex)}px`,
              zIndex: cardIndex === col.length - 1 ? cardIndex + 20 : cardIndex + 1,
            }"
            @click="selectTableauCard(colIndex, cardIndex)"
            @dblclick.stop="onTableauDoubleClick(colIndex, cardIndex)"
            @pointerdown="onTableauPointerDown($event, colIndex, cardIndex)"
          >
            <div v-if="card.face_up" class="playing-card" :class="{ red: isRed(card.suit) }">
              <span class="corner corner--tl">
                <span class="corner__rank">{{ card.rank }}</span>
                <span class="corner__suit">{{ getSuitSymbol(card.suit) }}</span>
              </span>
              <span class="suit suit--center">{{ getSuitSymbol(card.suit) }}</span>
              <span class="corner corner--br">
                <span class="corner__rank">{{ card.rank }}</span>
                <span class="corner__suit">{{ getSuitSymbol(card.suit) }}</span>
              </span>
            </div>
            <div v-else class="playing-card playing-card--back">
              <div class="card-back">
                <div class="card-back__pattern"></div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <Transition name="winner-overlay">
      <div v-if="isFinished" class="winner-overlay">
        <div class="winner-content">
          <div class="confetti" aria-hidden="true">
            <span v-for="n in 20" :key="n" class="confetti-piece" :style="{ '--i': n }"></span>
          </div>
          <div class="winner-card">
            <div class="winner-suits" aria-hidden="true">
              <span class="winner-suit">♠</span>
              <span class="winner-suit red">♥</span>
              <span class="winner-suit">♣</span>
              <span class="winner-suit red">♦</span>
            </div>
            <p class="winner-eyebrow">Congratulations!</p>
            <h2 class="winner-title">You Won!</h2>
            <div class="winner-stats">
              <div class="winner-stat">
                <span class="winner-stat-value">{{ board.moves }}</span>
                <span class="winner-stat-label">moves</span>
              </div>
            </div>
            <button type="button" class="btn-primary play-again-btn" @click="newGame">
              Play Again
            </button>
          </div>
        </div>
      </div>
    </Transition>

    <aside class="controls-hint">
      <div class="hint-item">
        <span class="hint-key">Drag</span>
        <span class="hint-desc">Move cards or piles onto a valid target</span>
      </div>
      <div class="hint-item">
        <span class="hint-key">Hint</span>
        <span class="hint-desc">Highlight a good next move</span>
      </div>
      <div class="hint-item">
        <span class="hint-key">Watch</span>
        <span class="hint-desc">Let the AI play so you can learn</span>
      </div>
    </aside>

    <div
      v-if="ghostCards.length && dragGhostStyle"
      class="solitaire-drag-ghost"
      :class="{ 'solitaire-drag-ghost--flight': isFlightAnimating }"
      :style="dragGhostStyle"
      aria-hidden="true"
    >
      <template v-for="(card, index) in ghostCards" :key="`ghost-${index}-${card.rank}-${card.suit}`">
        <div
          v-if="card.face_up"
          class="playing-card drag-ghost-card"
          :class="{ red: isRed(card.suit) }"
          :style="{ '--ghost-index': index }"
        >
          <span class="corner corner--tl">
            <span class="corner__rank">{{ card.rank }}</span>
            <span class="corner__suit">{{ getSuitSymbol(card.suit) }}</span>
          </span>
          <span class="suit suit--center">{{ getSuitSymbol(card.suit) }}</span>
          <span class="corner corner--br">
            <span class="corner__rank">{{ card.rank }}</span>
            <span class="corner__suit">{{ getSuitSymbol(card.suit) }}</span>
          </span>
        </div>
        <div
          v-else
          class="playing-card playing-card--back drag-ghost-card"
          :style="{ '--ghost-index': index }"
        >
          <div class="card-back">
            <div class="card-back__pattern"></div>
          </div>
        </div>
      </template>
    </div>
  </div>
</template>

<style scoped>
.solitaire-board {
  --card-width: clamp(70px, 10vw, 100px);
  --card-height: calc(var(--card-width) * 1.4);
  --card-gap: clamp(0.4rem, 1vw, 0.75rem);
  /* Overridden dynamically via boardLayoutStyle for tall cascades */
  --card-offset: 28px;
  --card-offset-down: 12px;
  
  width: 100%;
  max-width: 1400px;
  margin: 0 auto;
  padding: 0 1.5rem 1.5rem;
  min-height: calc(100vh - 5.5rem);
  height: calc(100vh - 5.5rem);
  max-height: calc(100vh - 5.5rem);
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
  overflow: hidden;
  background:
    radial-gradient(ellipse 100% 60% at 50% -10%, rgba(34, 139, 34, 0.1) 0%, transparent 50%),
    radial-gradient(ellipse 80% 40% at 50% 110%, rgba(139, 69, 19, 0.08) 0%, transparent 45%);
  touch-action: manipulation;
}

.solitaire-board--dragging {
  cursor: grabbing;
  user-select: none;
  touch-action: none;
}

.solitaire-board--autoplay .game-area {
  pointer-events: none;
}

.solitaire-board--autoplay .status-bar {
  pointer-events: auto;
}

.status-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1rem;
  flex-wrap: wrap;
  padding: 0.75rem 1.25rem;
  background: linear-gradient(135deg, rgba(21, 28, 44, 0.98) 0%, rgba(16, 22, 36, 0.98) 100%);
  border-radius: 14px;
  border: 1px solid rgba(255, 255, 255, 0.08);
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.25);
}

.stats-row {
  display: flex;
  align-items: center;
  gap: 1.25rem;
}

.stat-item {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.stat-icon {
  font-size: 1rem;
}

.stat-value {
  font-size: 1.1rem;
  font-weight: 800;
  color: #fff;
  font-variant-numeric: tabular-nums;
}

.stat-label {
  font-size: 0.8rem;
  color: var(--text-muted);
  text-transform: uppercase;
  letter-spacing: 0.04em;
}

.stat-item--progress {
  gap: 0.65rem;
}

.progress-wrap {
  display: flex;
  align-items: center;
  gap: 0.65rem;
}

.progress-bar {
  width: 100px;
  height: 8px;
  border-radius: 4px;
  background: rgba(255, 255, 255, 0.1);
  overflow: hidden;
  border: 1px solid rgba(255, 255, 255, 0.08);
}

.progress-fill {
  height: 100%;
  border-radius: 3px;
  background: linear-gradient(90deg, #2a8f4e 0%, #4ade80 100%);
  transition: width 0.4s ease;
  box-shadow: 0 0 8px rgba(74, 222, 128, 0.4);
}

.progress-text {
  font-size: 0.82rem;
  font-weight: 700;
  color: #7dffb0;
  font-variant-numeric: tabular-nums;
}

.status-bar__right {
  display: flex;
  align-items: center;
  gap: 0.6rem;
}

.sound-toggle {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 2.25rem;
  height: 2.25rem;
  padding: 0;
  border-radius: 10px;
  border: 1px solid rgba(255, 255, 255, 0.12);
  background: rgba(255, 255, 255, 0.05);
  color: #fff;
  font-size: 1rem;
  line-height: 1;
  cursor: pointer;
  transition: background 0.2s ease, transform 0.15s ease;
  flex-shrink: 0;
}

.sound-toggle:hover {
  background: rgba(255, 255, 255, 0.12);
  transform: translateY(-1px);
}

.btn-action {
  display: inline-flex;
  align-items: center;
  gap: 0.4rem;
  padding: 0.5rem 0.9rem;
  border-radius: 10px;
  font-size: 0.82rem;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s ease;
  border: 1px solid;
}

.btn-action .btn-icon {
  font-size: 0.9rem;
}

.btn-action--auto {
  background: rgba(61, 214, 140, 0.12);
  border-color: rgba(61, 214, 140, 0.35);
  color: #7dffb0;
}

.btn-action--auto:hover {
  background: rgba(61, 214, 140, 0.22);
  transform: translateY(-1px);
  box-shadow: 0 4px 12px rgba(61, 214, 140, 0.2);
}

.btn-action--hint {
  background: rgba(255, 215, 0, 0.1);
  border-color: rgba(255, 215, 0, 0.35);
  color: #ffe08a;
}

.btn-action--hint:hover {
  background: rgba(255, 215, 0, 0.18);
  transform: translateY(-1px);
}

.btn-action--watch {
  background: rgba(91, 156, 255, 0.1);
  border-color: rgba(91, 156, 255, 0.35);
  color: #9ec1ff;
}

.btn-action--watch:hover {
  background: rgba(91, 156, 255, 0.2);
  transform: translateY(-1px);
}

.btn-action--watch-on {
  background: rgba(91, 156, 255, 0.28);
  border-color: rgba(91, 156, 255, 0.55);
  color: #fff;
  box-shadow: 0 0 0 1px rgba(91, 156, 255, 0.25);
}

.btn-action--new {
  background: rgba(255, 255, 255, 0.05);
  border-color: rgba(255, 255, 255, 0.12);
  color: var(--text-muted);
}

.btn-action--new:hover {
  background: rgba(255, 255, 255, 0.1);
  color: #fff;
  transform: translateY(-1px);
}

.coach-banner {
  margin: 0;
  padding: 0.55rem 1rem;
  border-radius: 10px;
  border: 1px solid rgba(255, 215, 0, 0.28);
  background: rgba(255, 215, 0, 0.08);
  color: #ffe08a;
  font-size: 0.9rem;
  font-weight: 600;
  text-align: center;
}

.game-area {
  flex: 1 1 auto;
  display: flex;
  align-items: stretch;
  gap: 0.75rem;
  min-height: 0;
  overflow: hidden;
}

.game-area--rail {
  flex-direction: row;
}

.game-area--standard {
  flex-direction: column;
  gap: 0.65rem;
}

.side-rail {
  flex: 0 0 auto;
  display: flex;
  flex-direction: column;
  gap: 0.55rem;
  width: calc(var(--card-width) * 2 + var(--card-gap));
  max-height: 100%;
  overflow: visible;
  z-index: 2;
}

.top-row {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: var(--card-gap);
  flex-wrap: wrap;
  flex-shrink: 0;
  width: 100%;
  z-index: 2;
}

.stock-waste {
  display: flex;
  flex-direction: row;
  gap: var(--card-gap);
  flex-shrink: 0;
}

.waste--fan {
  /* Reserve horizontal room for the draw-3 fan (peek per buried card) */
  --waste-fan-peek: clamp(22px, calc(var(--card-width) * 0.32), 36px);
  width: calc(var(--card-width) + (var(--fan-count, 1) - 1) * var(--waste-fan-peek));
  z-index: 3;
}

/* Must beat `.playing-card { position: relative }` or cards stack + shift = diagonal */
.playing-card.waste-fan-card {
  position: absolute;
  top: 0;
  left: calc(var(--fan-index, 0) * var(--waste-fan-peek, 28px));
  width: var(--card-width);
  height: var(--card-height);
  pointer-events: none;
  z-index: calc(var(--fan-index, 0) + 1);
}

.playing-card.waste-fan-card--top {
  pointer-events: auto;
}

.side-rail .foundations {
  display: grid;
  grid-template-columns: repeat(2, var(--card-width));
  gap: var(--card-gap);
  flex-shrink: 0;
}

.top-row .foundations {
  display: flex;
  flex-direction: row;
  gap: var(--card-gap);
  flex-shrink: 0;
}

.card-slot {
  width: var(--card-width);
  height: var(--card-height);
  border-radius: calc(var(--card-width) * 0.12);
  cursor: pointer;
  transition: transform 0.2s ease, box-shadow 0.25s ease;
  position: relative;
  flex-shrink: 0;
}

.card-slot:hover {
  transform: translateY(-3px);
}

.card-slot.selected {
  box-shadow: 
    0 0 0 3px #ffd700, 
    0 4px 20px rgba(255, 215, 0, 0.4),
    0 0 30px rgba(255, 215, 0, 0.2);
  transform: translateY(-4px);
}

.empty-slot {
  width: 100%;
  height: 100%;
  border: 2.5px dashed rgba(255, 255, 255, 0.18);
  border-radius: calc(var(--card-width) * 0.12);
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 0.25rem;
  color: rgba(255, 255, 255, 0.25);
  background: rgba(0, 0, 0, 0.25);
  transition: all 0.2s ease;
}

.empty-slot--stock {
  border-color: rgba(255, 255, 255, 0.1);
}

.empty-icon {
  font-size: 1.5rem;
  opacity: 0.5;
}

.empty-label {
  font-size: 0.7rem;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  font-weight: 600;
}

.empty-slot--tableau {
  border-color: rgba(255, 215, 0, 0.25);
  background: rgba(255, 215, 0, 0.05);
}

.empty-king {
  font-size: clamp(1.2rem, calc(var(--card-width) * 0.22), 2rem);
  font-weight: 800;
  color: rgba(255, 215, 0, 0.35);
}

.foundation-empty {
  border-color: rgba(255, 255, 255, 0.25);
  background: rgba(0, 0, 0, 0.3);
}

.foundation-suit {
  font-size: clamp(1.5rem, calc(var(--card-width) * 0.28), 2.5rem);
  opacity: 0.35;
  color: #1a1a1a;
}

.foundation-suit.red {
  color: #c62828;
}

.foundation-hint {
  font-size: 0.75rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.1em;
  color: rgba(255, 255, 255, 0.25);
}

.foundation.complete {
  animation: foundationComplete 0.6s ease;
}

.foundation.complete .playing-card {
  box-shadow:
    0 0 0 2px rgba(74, 222, 128, 0.6),
    0 4px 20px rgba(74, 222, 128, 0.35);
}

@keyframes foundationComplete {
  0%, 100% { transform: scale(1); }
  50% { transform: scale(1.08); }
}

.stock {
  cursor: pointer;
}

.stock--empty {
  cursor: default;
}

.stock--empty:hover {
  transform: none;
}

.stock--can-recycle:hover .recycle-slot {
  background: rgba(91, 156, 255, 0.18);
  border-color: rgba(91, 156, 255, 0.5);
}

.stock-badge {
  position: absolute;
  bottom: 6px;
  right: 6px;
  font-size: 0.72rem;
  font-weight: 800;
  color: #fff;
  background: rgba(0, 0, 0, 0.65);
  padding: 0.15rem 0.4rem;
  border-radius: 6px;
  font-variant-numeric: tabular-nums;
}

.foundation-badge {
  position: absolute;
  bottom: 6px;
  right: 6px;
  font-size: 0.68rem;
  font-weight: 800;
  color: #1a1a1a;
  background: rgba(255, 255, 255, 0.9);
  padding: 0.12rem 0.35rem;
  border-radius: 5px;
  font-variant-numeric: tabular-nums;
}

.recycle-slot {
  width: 100%;
  height: 100%;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 0.3rem;
  border: 2.5px dashed rgba(91, 156, 255, 0.4);
  border-radius: 12px;
  background: rgba(91, 156, 255, 0.1);
  transition: all 0.2s ease;
}

.recycle-icon {
  font-size: clamp(1.5rem, calc(var(--card-width) * 0.28), 2.2rem);
  color: rgba(91, 156, 255, 0.8);
}

.recycle-label {
  font-size: 0.68rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.1em;
  color: rgba(91, 156, 255, 0.7);
}

.playing-card {
  width: 100%;
  height: 100%;
  border-radius: calc(var(--card-width) * 0.12);
  background: linear-gradient(165deg, #fffef9 0%, #f8f4ea 50%, #f0ece2 100%);
  border: 1px solid rgba(0, 0, 0, 0.1);
  position: relative;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #1a1a1a;
  box-shadow:
    0 1px 0 rgba(255, 255, 255, 0.9) inset,
    0 -1px 0 rgba(0, 0, 0, 0.05) inset,
    0 2px 4px rgba(0, 0, 0, 0.18);
  transition: transform 0.15s ease, box-shadow 0.2s ease;
}

.playing-card.red {
  color: #c62828;
}

.playing-card--back {
  background: linear-gradient(150deg, #2a4a8a 0%, #1a3268 50%, #0f2048 100%);
  border: 1px solid rgba(255, 255, 255, 0.1);
  box-shadow:
    0 1px 0 rgba(255, 255, 255, 0.08) inset,
    0 2px 4px rgba(0, 0, 0, 0.25);
}

.card-back {
  width: 86%;
  height: 88%;
  border-radius: 8px;
  border: 2px solid rgba(201, 162, 39, 0.5);
  background: linear-gradient(140deg, #1e4080 0%, #14326a 100%);
  display: flex;
  align-items: center;
  justify-content: center;
  overflow: hidden;
}

.card-back__pattern {
  width: 80%;
  height: 84%;
  border-radius: 5px;
  background:
    repeating-linear-gradient(
      45deg,
      rgba(45, 100, 180, 0.85) 0,
      rgba(45, 100, 180, 0.85) 3px,
      rgba(30, 70, 140, 0.85) 3px,
      rgba(30, 70, 140, 0.85) 6px
    );
  border: 1px solid rgba(255, 215, 0, 0.2);
  box-shadow: inset 0 0 15px rgba(0, 0, 0, 0.2);
}

.corner {
  position: absolute;
  display: flex;
  flex-direction: column;
  align-items: center;
  line-height: 1;
  gap: 0;
}

.corner--tl {
  top: calc(var(--card-width) * 0.06);
  left: calc(var(--card-width) * 0.08);
}

.corner--br {
  bottom: calc(var(--card-width) * 0.06);
  right: calc(var(--card-width) * 0.08);
  transform: rotate(180deg);
}

.corner__rank {
  font-size: clamp(0.7rem, calc(var(--card-width) * 0.14), 1.1rem);
  font-weight: 800;
  letter-spacing: -0.02em;
}

.corner__suit {
  font-size: clamp(0.6rem, calc(var(--card-width) * 0.12), 1rem);
  margin-top: -1px;
}

.suit--center {
  font-size: clamp(1.5rem, calc(var(--card-width) * 0.3), 2.5rem);
  line-height: 1;
  opacity: 0.95;
}

.tableau {
  display: flex;
  gap: var(--card-gap);
  justify-content: space-evenly;
  align-items: stretch;
  flex: 1 1 auto;
  min-width: 0;
  min-height: 0;
  height: 100%;
  overflow: hidden;
}

.game-area--rail .tableau {
  padding-left: 0.15rem;
}

.tableau-column {
  position: relative;
  width: var(--card-width);
  min-height: var(--card-height);
  height: 100%;
  /* Stretch so empty space below short piles is still a drop target */
  align-self: stretch;
}

.empty-column {
  position: absolute;
  top: 0;
  left: 0;
  width: var(--card-width);
  height: var(--card-height);
}

.empty-column.drop-target .empty-slot {
  border-color: rgba(255, 215, 0, 0.6);
  background: rgba(255, 215, 0, 0.12);
}

.tableau-column--drop-ok .tableau-card--top .playing-card,
.foundation.drop-target .playing-card,
.foundation.drop-target .empty-slot {
  box-shadow:
    0 0 0 2px rgba(255, 215, 0, 0.55),
    0 6px 18px rgba(255, 215, 0, 0.2);
}

.tableau-column--drag-over .tableau-card--top .playing-card,
.foundation.drag-over .playing-card,
.foundation.drag-over .empty-slot,
.tableau-column--drag-over .empty-column .empty-slot {
  box-shadow:
    0 0 0 3px #ffd700,
    0 8px 24px rgba(255, 215, 0, 0.35);
  border-color: rgba(255, 215, 0, 0.75);
}

.foundation.drop-target .empty-slot {
  border-color: rgba(255, 215, 0, 0.6);
  background: rgba(255, 215, 0, 0.12);
}

.drag-source {
  opacity: 0.35;
}

.waste.drag-source,
.foundation.drag-source {
  opacity: 0.4;
}

.hint-source .playing-card,
.tableau-card.hint-source .playing-card,
.stock.hint-source .playing-card,
.stock.hint-source .recycle-slot,
.waste.hint-source .playing-card,
.foundation.hint-source .playing-card {
  box-shadow:
    0 0 0 3px #5b9cff,
    0 6px 20px rgba(91, 156, 255, 0.35);
}

.stock.hint-source .recycle-slot,
.stock.hint-source .empty-slot,
.foundation.hint-target .empty-slot,
.empty-column.hint-target .empty-slot {
  border-color: rgba(91, 156, 255, 0.7);
  background: rgba(91, 156, 255, 0.14);
}

.foundation.hint-target .playing-card,
.tableau-column--hint-target .tableau-card--top .playing-card {
  box-shadow:
    0 0 0 3px rgba(91, 156, 255, 0.85),
    0 6px 18px rgba(91, 156, 255, 0.3);
}

.solitaire-drag-ghost {
  position: fixed;
  z-index: 1000;
  width: var(--card-width);
  height: var(--card-height);
  pointer-events: none;
  filter: drop-shadow(0 12px 24px rgba(0, 0, 0, 0.45));
}

.solitaire-drag-ghost--flight {
  z-index: 1200;
  transform: scale(1.04);
  filter: drop-shadow(0 16px 28px rgba(0, 0, 0, 0.55));
}

.drag-ghost-card {
  position: absolute;
  left: 0;
  top: calc(var(--ghost-index, 0) * var(--card-offset));
  width: var(--card-width);
  height: var(--card-height);
}

.waste,
.foundation,
.tableau-card:not(.face-down) {
  touch-action: none;
  cursor: grab;
  user-select: none;
  -webkit-user-select: none;
}

.solitaire-board--dragging .waste,
.solitaire-board--dragging .foundation,
.solitaire-board--dragging .tableau-card {
  cursor: grabbing;
}

.solitaire-board--dragging .playing-card {
  transition: none;
}

.tableau-card {
  position: absolute;
  left: 0;
  /* `top` is set inline from cardStackTop() for mixed face-down/up spacing */
  width: var(--card-width);
  height: var(--card-height);
  cursor: grab;
  z-index: 1;
  background: transparent;
  /* Soft shadow only — hard drop shadows read as black bars between peeks */
  transition: top 0.2s ease, transform 0.2s ease, box-shadow 0.25s ease, opacity 0.15s ease;
}

.solitaire-board--dragging .tableau-card {
  transition: none;
}

/*
  Buried cards keep a short peek hit-box, but overflow is visible so the full
  rounded card paints under the next one (avoids black corner gaps).
*/
.tableau-card:not(.tableau-card--top) {
  height: var(--card-offset);
  overflow: visible;
  background: transparent;
}

.tableau-card.face-down:not(.tableau-card--top) {
  height: var(--card-offset-down);
}

.tableau-card:not(.tableau-card--top) .playing-card {
  height: var(--card-height);
  pointer-events: none;
}

.tableau-card--top {
  height: var(--card-height);
  overflow: visible;
  z-index: 10;
}

.tableau-card:hover:not(.face-down):not(.selected) {
  transform: translateY(-3px);
}

.tableau-card.face-down {
  cursor: default;
}

.tableau-column--has-selection .tableau-card.face-down {
  cursor: pointer;
}

.tableau-card.face-down:hover {
  transform: none;
}

.tableau-card.selected {
  transform: translateY(-8px);
}

.tableau-card.selected .playing-card {
  box-shadow:
    0 0 0 3px #ffd700,
    0 8px 30px rgba(255, 215, 0, 0.4);
}

.winner-overlay {
  position: fixed;
  inset: 0;
  z-index: 100;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(0, 0, 0, 0.8);
  backdrop-filter: blur(10px);
}

.winner-content {
  position: relative;
}

.confetti {
  position: absolute;
  inset: -100px;
  pointer-events: none;
  overflow: hidden;
}

.confetti-piece {
  position: absolute;
  width: 12px;
  height: 12px;
  background: #ffd700;
  opacity: 0;
  animation: confettiFall 3s ease-out infinite;
  animation-delay: calc(var(--i) * 0.15s);
  left: calc(var(--i) * 5%);
  top: -20px;
}

.confetti-piece:nth-child(2n) { background: #ff6b6b; width: 10px; height: 10px; }
.confetti-piece:nth-child(3n) { background: #4ade80; width: 8px; height: 14px; }
.confetti-piece:nth-child(4n) { background: #60a5fa; width: 14px; height: 8px; }
.confetti-piece:nth-child(5n) { background: #f472b6; width: 11px; height: 11px; }

@keyframes confettiFall {
  0% {
    opacity: 1;
    transform: translateY(0) rotate(0deg);
  }
  100% {
    opacity: 0;
    transform: translateY(400px) rotate(720deg);
  }
}

.winner-card {
  text-align: center;
  padding: 2.5rem 3rem;
  border-radius: 24px;
  border: 3px solid rgba(255, 215, 0, 0.7);
  background: linear-gradient(165deg, rgba(35, 25, 8, 0.98) 0%, rgba(12, 28, 18, 0.98) 100%);
  box-shadow:
    0 0 0 1px rgba(255, 215, 0, 0.15),
    0 25px 80px rgba(0, 0, 0, 0.6),
    0 0 60px rgba(255, 215, 0, 0.2);
  animation: winnerPulse 3s ease-in-out infinite;
  position: relative;
  overflow: hidden;
}

.winner-suits {
  display: flex;
  justify-content: center;
  gap: 0.5rem;
  margin-bottom: 1rem;
}

.winner-suit {
  font-size: 1.5rem;
  opacity: 0.6;
}

.winner-suit.red {
  color: #c62828;
}

.winner-eyebrow {
  margin: 0 0 0.5rem;
  font-size: 0.9rem;
  font-weight: 800;
  letter-spacing: 0.18em;
  text-transform: uppercase;
  color: #f0c84b;
}

.winner-title {
  margin: 0;
  font-size: 3rem;
  font-weight: 900;
  color: #fff;
  text-shadow: 0 4px 20px rgba(0, 0, 0, 0.5);
}

.winner-stats {
  display: flex;
  justify-content: center;
  gap: 2rem;
  margin: 1.5rem 0;
}

.winner-stat {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 0.25rem;
}

.winner-stat-value {
  font-size: 2rem;
  font-weight: 900;
  color: #7dffb0;
  font-variant-numeric: tabular-nums;
}

.winner-stat-label {
  font-size: 0.75rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.1em;
  color: rgba(255, 255, 255, 0.5);
}

.play-again-btn {
  font-size: 1.15rem;
  padding: 1rem 2.5rem;
  margin-top: 0.5rem;
}

@keyframes winnerPulse {
  0%, 100% {
    box-shadow:
      0 0 0 1px rgba(255, 215, 0, 0.15),
      0 25px 80px rgba(0, 0, 0, 0.6),
      0 0 50px rgba(255, 215, 0, 0.15);
  }
  50% {
    box-shadow:
      0 0 0 1px rgba(255, 215, 0, 0.3),
      0 25px 80px rgba(0, 0, 0, 0.6),
      0 0 80px rgba(255, 215, 0, 0.35);
  }
}

.winner-overlay-enter-active {
  animation: overlayIn 0.5s ease-out;
}

.winner-overlay-enter-active .winner-card {
  animation: cardIn 0.7s ease-out;
}

@keyframes overlayIn {
  from { opacity: 0; }
  to { opacity: 1; }
}

@keyframes cardIn {
  from {
    opacity: 0;
    transform: scale(0.7) translateY(30px);
  }
  to {
    opacity: 1;
    transform: scale(1) translateY(0);
  }
}

.controls-hint {
  display: flex;
  justify-content: center;
  gap: 2rem;
  padding: 0.65rem 1.25rem;
  background: rgba(21, 28, 44, 0.6);
  border-radius: 12px;
  border: 1px solid rgba(255, 255, 255, 0.06);
  flex-shrink: 0;
}

@media (max-height: 700px) {
  .controls-hint {
    display: none;
  }
}

.hint-item {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.hint-key {
  font-size: 0.75rem;
  font-weight: 700;
  padding: 0.25rem 0.5rem;
  border-radius: 6px;
  background: rgba(255, 255, 255, 0.08);
  border: 1px solid rgba(255, 255, 255, 0.1);
  color: #fff;
}

.hint-desc {
  font-size: 0.8rem;
  color: var(--text-muted);
}

/* Large screens - bigger cards */
@media (min-width: 1200px) {
  .solitaire-board {
    --card-width: clamp(90px, 8vw, 110px);
    --card-offset: clamp(28px, 3.5vh, 36px);
  }
}

@media (min-width: 1600px) {
  .solitaire-board {
    --card-width: clamp(100px, 7vw, 120px);
    --card-offset: clamp(32px, 4vh, 40px);
    max-width: 1600px;
  }
}

@media (max-width: 768px) {
  .solitaire-board {
    --card-width: clamp(48px, 11vw, 60px);
    --card-offset: clamp(18px, 2.8vh, 24px);
    padding: 0 0.5rem 0.75rem;
  }

  .side-rail {
    width: calc(var(--card-width) * 2 + var(--card-gap));
    gap: 0.4rem;
  }

  .top-row {
    flex-direction: column;
    align-items: center;
  }

  .top-row .foundations {
    order: -1;
  }

  .stats-row {
    flex-wrap: wrap;
    gap: 0.75rem;
  }

  .progress-bar {
    width: 70px;
  }
}

@media (max-width: 480px) {
  .solitaire-board {
    --card-width: clamp(42px, 13vw, 50px);
    --card-offset: clamp(16px, 2.5vh, 20px);
    padding: 0 0.35rem 0.75rem;
    gap: 0.5rem;
  }

  .status-bar {
    padding: 0.5rem 0.75rem;
    border-radius: 10px;
    flex-direction: column;
    gap: 0.5rem;
  }

  .stats-row {
    width: 100%;
    justify-content: space-between;
  }

  .status-bar__right {
    width: 100%;
    justify-content: center;
  }

  .stat-value {
    font-size: 0.95rem;
  }

  .stat-label {
    font-size: 0.7rem;
  }

  .progress-bar {
    width: 55px;
    height: 6px;
  }

  .progress-text {
    font-size: 0.72rem;
  }

  .controls-hint {
    display: none;
  }
}

/* Phone landscape mode */
@media (max-height: 500px) and (orientation: landscape) {
  .solitaire-board {
    --card-width: clamp(48px, 14vh, 60px);
    --card-offset: clamp(14px, 2vh, 18px);
    padding: 0.25rem 0.5rem;
    min-height: calc(100vh - 3.5rem);
    gap: 0.35rem;
  }

  .status-bar {
    padding: 0.4rem 0.75rem;
    flex-wrap: nowrap;
    border-radius: 10px;
  }

  .stat-value {
    font-size: 0.95rem;
  }

  .stat-label {
    font-size: 0.65rem;
  }

  .progress-bar {
    width: 60px;
    height: 6px;
  }

  .progress-text {
    font-size: 0.7rem;
  }

  .status-bar__right {
    gap: 0.35rem;
  }

  .btn-action {
    padding: 0.35rem 0.65rem;
    font-size: 0.72rem;
    border-radius: 8px;
  }

  .btn-action .btn-icon {
    font-size: 0.75rem;
  }

  .game-area--rail {
    flex-direction: row;
    gap: 0.4rem;
    flex: 1;
    min-height: 0;
  }

  .game-area--standard {
    flex-direction: column;
    gap: 0.3rem;
  }

  .side-rail {
    width: calc(var(--card-width) * 2 + var(--card-gap));
    gap: 0.3rem;
  }

  .top-row {
    flex-wrap: nowrap;
    gap: 0.35rem;
  }

  .stock-waste {
    flex-direction: row;
    gap: 0.25rem;
  }

  .side-rail .foundations {
    grid-template-columns: repeat(2, var(--card-width));
    gap: 0.25rem;
  }

  .top-row .foundations {
    gap: 0.2rem;
  }

  .tableau {
    flex: 1;
    min-height: 0;
    align-items: stretch;
  }

  .recycle-label {
    font-size: 0.55rem;
  }

  .stock-badge,
  .foundation-badge {
    font-size: 0.55rem;
    padding: 0.08rem 0.25rem;
    bottom: 3px;
    right: 4px;
  }

  .controls-hint {
    display: none;
  }

  .winner-card {
    padding: 1.25rem 1.75rem;
    max-width: 340px;
    border-radius: 18px;
  }

  .winner-title {
    font-size: 2rem;
  }

  .winner-eyebrow {
    font-size: 0.72rem;
  }

  .winner-stat-value {
    font-size: 1.5rem;
  }

  .winner-stats {
    margin: 0.75rem 0;
  }

  .play-again-btn {
    font-size: 0.95rem;
    padding: 0.7rem 1.75rem;
  }
}

/* Very small landscape (iPhone SE landscape, etc.) */
@media (max-height: 400px) and (orientation: landscape) {
  .solitaire-board {
    --card-width: clamp(38px, 12vh, 48px);
    --card-offset: clamp(12px, 1.8vh, 15px);
    padding: 0.15rem 0.35rem;
    gap: 0.25rem;
  }

  .status-bar {
    padding: 0.3rem 0.55rem;
  }

  .stat-value {
    font-size: 0.85rem;
  }

  .stock-waste {
    gap: 0.15rem;
  }

  .side-rail .foundations,
  .top-row .foundations {
    gap: 0.15rem;
  }

  .side-rail {
    gap: 0.2rem;
  }
}
</style>
