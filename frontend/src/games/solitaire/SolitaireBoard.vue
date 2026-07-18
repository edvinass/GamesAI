<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import type { Room, SolitaireGameState } from '@/types'

const props = defineProps<{
  gameState: SolitaireGameState
  room: Room
  playerId: string
}>()

const emit = defineEmits<{
  action: [data: Record<string, unknown>]
}>()

const selectedCard = ref<{
  source: 'waste' | 'tableau' | 'foundation'
  sourceIndex?: number
  cardIndex?: number
} | null>(null)

const lastMoveTime = ref(Date.now())

watch(() => props.gameState.moves, () => {
  lastMoveTime.value = Date.now()
})

const isFinished = computed(() => props.gameState.phase === 'finished')

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

function getSelectedMovingCard(): { rank: string | null; suit: string | null } | null {
  if (!selectedCard.value) return null
  if (selectedCard.value.source === 'waste') {
    return props.gameState.waste_top
  }
  if (selectedCard.value.source === 'tableau') {
    const col = props.gameState.tableau[selectedCard.value.sourceIndex!]
    return col?.[selectedCard.value.cardIndex ?? 0] ?? null
  }
  if (selectedCard.value.source === 'foundation') {
    const suit = suitOrder[selectedCard.value.sourceIndex!]
    return props.gameState.foundations[suit]?.top ?? null
  }
  return null
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
  const moving = getSelectedMovingCard()
  if (!moving || !selectedCard.value) return false
  if (
    selectedCard.value.source === 'tableau' &&
    selectedCard.value.sourceIndex === targetCol
  ) {
    return false
  }
  const target = props.gameState.tableau[targetCol]
  if (!target.length) return moving.rank === 'K'
  const top = target[target.length - 1]
  if (!top.face_up) return false
  return canStackOnTableau(moving, top)
}

function canMoveSelectionToFoundation(): boolean {
  if (!selectedCard.value) return false
  if (selectedCard.value.source === 'waste') {
    const card = props.gameState.waste_top
    return Boolean(card?.suit && canStackOnFoundation(card, card.suit))
  }
  if (selectedCard.value.source === 'tableau') {
    const col = props.gameState.tableau[selectedCard.value.sourceIndex!]
    if (!col?.length) return false
    if (selectedCard.value.cardIndex !== col.length - 1) return false
    const card = col[col.length - 1]
    return Boolean(card.suit && canStackOnFoundation(card, card.suit))
  }
  return false
}

function drawCard() {
  if (isFinished.value) return
  if (props.gameState.stock_count > 0) {
    emit('action', { type: 'draw' })
  } else if (props.gameState.waste_count > 0) {
    emit('action', { type: 'reset_stock' })
  }
  clearSelection()
}

function selectWaste() {
  if (isFinished.value || !props.gameState.waste_top) return

  if (selectedCard.value?.source === 'waste') {
    clearSelection()
    return
  }

  selectedCard.value = { source: 'waste' }
}

function selectTableauCard(colIndex: number, cardIndex: number) {
  if (isFinished.value) return
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
  if (isFinished.value) return
  if (selectedCard.value) {
    moveToTableau(colIndex)
  }
}

function selectFoundation(suit: string) {
  if (isFinished.value) return
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

function moveToTableau(targetCol: number) {
  if (!selectedCard.value || isFinished.value) return

  if (
    selectedCard.value.source === 'tableau' &&
    selectedCard.value.sourceIndex === targetCol
  ) {
    clearSelection()
    return
  }

  if (!canMoveSelectionToTableau(targetCol)) return

  emit('action', {
    type: 'move_to_tableau',
    source: selectedCard.value.source,
    source_index: selectedCard.value.sourceIndex ?? null,
    card_index: selectedCard.value.cardIndex ?? 0,
    target_col: targetCol,
  })
  clearSelection()
}

function onTableauDoubleClick(colIndex: number, cardIndex: number) {
  if (isFinished.value) return
  const col = props.gameState.tableau[colIndex]
  if (cardIndex !== col.length - 1 || !col[cardIndex]?.face_up) return
  selectedCard.value = { source: 'tableau', sourceIndex: colIndex, cardIndex }
  sendToFoundation('tableau', colIndex)
}

function onWasteDoubleClick() {
  if (isFinished.value || !props.gameState.waste_top) return
  selectedCard.value = { source: 'waste' }
  sendToFoundation('waste')
}

function autoComplete() {
  emit('action', { type: 'auto_complete' })
}

function newGame() {
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
    clearSelection()
  },
)

function isCardSelected(source: string, sourceIndex?: number, cardIndex?: number): boolean {
  if (!selectedCard.value) return false
  if (selectedCard.value.source !== source) return false
  if (sourceIndex !== undefined && selectedCard.value.sourceIndex !== sourceIndex) return false
  if (cardIndex !== undefined && selectedCard.value.cardIndex !== cardIndex) return false
  return true
}

function isInSelectedStack(colIndex: number, cardIndex: number): boolean {
  if (!selectedCard.value) return false
  if (selectedCard.value.source !== 'tableau') return false
  if (selectedCard.value.sourceIndex !== colIndex) return false
  return cardIndex >= (selectedCard.value.cardIndex ?? 0)
}

const foundationProgress = computed(() => {
  let total = 0
  for (const foundation of Object.values(props.gameState.foundations)) {
    total += foundation.count
  }
  return Math.round((total / 52) * 100)
})

const progressBarWidth = computed(() => `${foundationProgress.value}%`)

const cardsInFoundations = computed(() => {
  let total = 0
  for (const foundation of Object.values(props.gameState.foundations)) {
    total += foundation.count
  }
  return total
})

const wasteFan = computed(() => {
  const fan = props.gameState.waste_fan
  if (fan?.length) return fan
  return props.gameState.waste_top ? [props.gameState.waste_top] : []
})

const hasSelection = computed(() => selectedCard.value !== null)
</script>

<template>
  <div class="solitaire-board" @click.self="clearSelection">
    <div class="status-bar">
      <div class="stats-row">
        <div class="stat-item">
          <span class="stat-icon">🎯</span>
          <span class="stat-value">{{ gameState.moves }}</span>
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
          v-if="gameState.can_auto_complete && !isFinished"
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

    <div class="game-area">
      <div class="top-row">
        <div class="stock-waste">
          <div
            class="card-slot stock"
            :class="{ 
              'stock--empty': gameState.stock_count === 0 && gameState.waste_count === 0,
              'stock--can-recycle': gameState.stock_count === 0 && gameState.waste_count > 0
            }"
            @click="drawCard"
          >
            <div v-if="gameState.stock_count > 0" class="playing-card playing-card--back">
              <div class="card-back">
                <div class="card-back__pattern"></div>
              </div>
              <span class="stock-badge">{{ gameState.stock_count }}</span>
            </div>
            <div v-else-if="gameState.waste_count > 0" class="recycle-slot">
              <span class="recycle-icon">↺</span>
              <span class="recycle-label">Reset</span>
            </div>
            <div v-else class="empty-slot empty-slot--stock">
              <span class="empty-icon">✗</span>
            </div>
          </div>

          <div
            class="card-slot waste"
            :class="{
              selected: isCardSelected('waste'),
              'waste--has-card': wasteFan.length > 0,
              'waste--fan': wasteFan.length > 1,
            }"
            :style="wasteFan.length > 1 ? { '--fan-count': wasteFan.length } : undefined"
            @click="selectWaste"
            @dblclick.stop="onWasteDoubleClick"
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
              complete: gameState.foundations[suit].count === 13,
              'foundation--has-card': gameState.foundations[suit].count > 0,
              'drop-target': hasSelection && canMoveSelectionToFoundation() && getSelectedMovingCard()?.suit === suit,
            }"
            @click="selectFoundation(suit)"
          >
            <div v-if="gameState.foundations[suit].top" class="playing-card" :class="{ red: isRed(suit) }">
              <span class="corner corner--tl">
                <span class="corner__rank">{{ gameState.foundations[suit].top?.rank }}</span>
                <span class="corner__suit">{{ getSuitSymbol(suit) }}</span>
              </span>
              <span class="suit suit--center">{{ getSuitSymbol(suit) }}</span>
              <span class="corner corner--br">
                <span class="corner__rank">{{ gameState.foundations[suit].top?.rank }}</span>
                <span class="corner__suit">{{ getSuitSymbol(suit) }}</span>
              </span>
              <span class="foundation-badge">{{ gameState.foundations[suit].count }}</span>
            </div>
            <div v-else class="empty-slot foundation-empty">
              <span class="foundation-suit" :class="{ red: isRed(suit) }">{{ getSuitSymbol(suit) }}</span>
              <span class="foundation-hint">A</span>
            </div>
          </div>
        </div>
      </div>

      <div class="tableau">
        <div
          v-for="(col, colIndex) in gameState.tableau"
          :key="colIndex"
          class="tableau-column"
          :class="{
            'tableau-column--drop-ok': hasSelection && canMoveSelectionToTableau(colIndex),
            'tableau-column--has-selection': hasSelection,
          }"
          @click.self="hasSelection && moveToTableau(colIndex)"
        >
          <div
            v-if="col.length === 0"
            class="card-slot empty-column"
            :class="{ 'drop-target': hasSelection && canMoveSelectionToTableau(colIndex) }"
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
            }"
            :style="{
              '--card-index': cardIndex,
              zIndex: cardIndex === col.length - 1 ? cardIndex + 20 : cardIndex + 1,
            }"
            @click="selectTableauCard(colIndex, cardIndex)"
            @dblclick.stop="onTableauDoubleClick(colIndex, cardIndex)"
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
                <span class="winner-stat-value">{{ gameState.moves }}</span>
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
        <span class="hint-key">Click</span>
        <span class="hint-desc">Select a card or pile, then click a target</span>
      </div>
      <div class="hint-item">
        <span class="hint-key">Double-click</span>
        <span class="hint-desc">Send a top card to its foundation</span>
      </div>
    </aside>
  </div>
</template>

<style scoped>
.solitaire-board {
  --card-width: clamp(70px, 10vw, 100px);
  --card-height: calc(var(--card-width) * 1.4);
  --card-gap: clamp(0.4rem, 1vw, 0.75rem);
  --card-offset: clamp(24px, 3.5vh, 32px);
  
  width: 100%;
  max-width: 1400px;
  margin: 0 auto;
  padding: 0 1.5rem 1.5rem;
  min-height: calc(100vh - 5.5rem);
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
  background:
    radial-gradient(ellipse 100% 60% at 50% -10%, rgba(34, 139, 34, 0.1) 0%, transparent 50%),
    radial-gradient(ellipse 80% 40% at 50% 110%, rgba(139, 69, 19, 0.08) 0%, transparent 45%);
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

.game-area {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 1rem;
  min-height: 0;
}

.top-row {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: var(--card-gap);
  flex-wrap: wrap;
}

.stock-waste {
  display: flex;
  gap: var(--card-gap);
}

.waste--fan {
  width: calc(var(--card-width) + (var(--fan-count, 1) - 1) * var(--card-offset));
}

.waste-fan-card {
  position: absolute;
  top: 0;
  left: calc(var(--fan-index, 0) * var(--card-offset));
  width: var(--card-width);
  height: var(--card-height);
  pointer-events: none;
}

.waste-fan-card--top {
  pointer-events: auto;
}

.foundations {
  display: flex;
  gap: var(--card-gap);
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
    0 3px 6px rgba(0, 0, 0, 0.12),
    0 8px 20px rgba(0, 0, 0, 0.18);
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
    0 3px 6px rgba(0, 0, 0, 0.2),
    0 8px 20px rgba(0, 0, 0, 0.3);
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
  justify-content: center;
  flex: 1;
  min-height: calc(var(--card-height) + var(--card-offset) * 12);
}

.tableau-column {
  position: relative;
  width: var(--card-width);
  min-height: var(--card-height);
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

.foundation.drop-target .empty-slot {
  border-color: rgba(255, 215, 0, 0.6);
  background: rgba(255, 215, 0, 0.12);
}

.tableau-card {
  position: absolute;
  left: 0;
  top: calc(var(--card-index, 0) * var(--card-offset));
  width: var(--card-width);
  height: var(--card-height);
  cursor: pointer;
  transition: transform 0.2s ease, box-shadow 0.25s ease;
}

/*
  Buried cards only expose a peek for hit-testing. The peek box itself is the
  click target (children are non-interactive) so full-size faces can't steal
  clicks from the top card.
*/
.tableau-card:not(.tableau-card--top) {
  height: var(--card-offset);
  overflow: hidden;
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
  padding: 0.85rem 1.25rem;
  background: rgba(21, 28, 44, 0.6);
  border-radius: 12px;
  border: 1px solid rgba(255, 255, 255, 0.06);
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
    --card-width: clamp(52px, 12vw, 65px);
    --card-offset: clamp(18px, 2.8vh, 24px);
    padding: 0 0.75rem 1rem;
  }

  .top-row {
    flex-direction: column;
    align-items: center;
  }

  .foundations {
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

  .game-area {
    flex-direction: row;
    gap: 0.5rem;
    flex: 1;
    min-height: 0;
  }

  .top-row {
    flex-direction: column;
    justify-content: flex-start;
    gap: 0.4rem;
    flex-shrink: 0;
    width: auto;
  }

  .stock-waste {
    flex-direction: column;
    gap: 0.3rem;
  }

  .foundations {
    flex-direction: column;
    gap: 0.2rem;
  }

  .tableau {
    flex: 1;
    min-height: 0;
    align-items: flex-start;
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
    gap: 0.2rem;
  }

  .foundations {
    gap: 0.15rem;
  }
}
</style>
