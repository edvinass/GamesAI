<script setup lang="ts">
import { computed, ref } from 'vue'
import type { Room, SolitaireGameState, SolitaireCard } from '@/types'

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

const isHost = computed(() => props.room.host_player_id === props.playerId)
const isFinished = computed(() => props.gameState.phase === 'finished')

const suitSymbols: Record<string, string> = {
  hearts: '♥',
  diamonds: '♦',
  clubs: '♣',
  spades: '♠',
}

const suitOrder = ['hearts', 'diamonds', 'clubs', 'spades']

function getSuitSymbol(suit: string | null): string {
  return suit ? suitSymbols[suit] ?? '' : ''
}

function isRed(suit: string | null): boolean {
  return suit === 'hearts' || suit === 'diamonds'
}

function drawCard() {
  if (props.gameState.stock_count > 0) {
    emit('action', { type: 'draw' })
  } else if (props.gameState.waste_count > 0) {
    emit('action', { type: 'reset_stock' })
  }
  clearSelection()
}

function selectWaste() {
  if (!props.gameState.waste_top) return

  if (selectedCard.value?.source === 'waste') {
    tryMoveToFoundation('waste')
    return
  }

  selectedCard.value = { source: 'waste' }
}

function selectTableauCard(colIndex: number, cardIndex: number) {
  const col = props.gameState.tableau[colIndex]
  if (!col[cardIndex]?.face_up) return

  if (
    selectedCard.value?.source === 'tableau' &&
    selectedCard.value.sourceIndex === colIndex &&
    selectedCard.value.cardIndex === cardIndex
  ) {
    tryMoveToFoundation('tableau', colIndex)
    return
  }

  if (selectedCard.value) {
    moveToTableau(colIndex)
  } else {
    selectedCard.value = { source: 'tableau', sourceIndex: colIndex, cardIndex }
  }
}

function selectEmptyTableau(colIndex: number) {
  if (selectedCard.value) {
    moveToTableau(colIndex)
  }
}

function selectFoundation(suit: string) {
  const foundation = props.gameState.foundations[suit]

  if (selectedCard.value) {
    tryMoveSelectedToFoundation(suit)
  } else if (foundation.count > 0) {
    const suitIndex = suitOrder.indexOf(suit)
    selectedCard.value = { source: 'foundation', sourceIndex: suitIndex }
  }
}

function tryMoveToFoundation(source: 'waste' | 'tableau', sourceIndex?: number) {
  emit('action', {
    type: 'move_to_foundation',
    source,
    source_index: sourceIndex,
  })
  clearSelection()
}

function tryMoveSelectedToFoundation(targetSuit: string) {
  if (!selectedCard.value) return

  if (selectedCard.value.source === 'waste') {
    emit('action', { type: 'move_to_foundation', source: 'waste' })
  } else if (selectedCard.value.source === 'tableau') {
    const col = props.gameState.tableau[selectedCard.value.sourceIndex!]
    if (selectedCard.value.cardIndex === col.length - 1) {
      emit('action', {
        type: 'move_to_foundation',
        source: 'tableau',
        source_index: selectedCard.value.sourceIndex,
      })
    }
  }
  clearSelection()
}

function moveToTableau(targetCol: number) {
  if (!selectedCard.value) return

  emit('action', {
    type: 'move_to_tableau',
    source: selectedCard.value.source,
    source_index: selectedCard.value.sourceIndex,
    card_index: selectedCard.value.cardIndex ?? 0,
    target_col: targetCol,
  })
  clearSelection()
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
</script>

<template>
  <div class="solitaire-board" @click.self="clearSelection">
    <div class="status-bar card">
      <div class="status-pills">
        <span class="status-pill status-pill--moves">
          Moves: <strong>{{ gameState.moves }}</strong>
        </span>
        <span class="status-pill status-pill--progress">
          {{ foundationProgress }}% complete
        </span>
      </div>
      <div class="status-bar__right">
        <button
          v-if="gameState.can_auto_complete && !isFinished"
          type="button"
          class="btn-secondary btn-auto"
          @click="autoComplete"
        >
          Auto-complete
        </button>
        <button type="button" class="btn-secondary" @click="newGame">New Game</button>
      </div>
    </div>

    <div class="game-area">
      <div class="top-row">
        <div class="stock-waste">
          <div
            class="card-slot stock"
            :class="{ 'stock--empty': gameState.stock_count === 0 && gameState.waste_count === 0 }"
            @click="drawCard"
          >
            <div v-if="gameState.stock_count > 0" class="playing-card playing-card--back">
              <div class="card-back">
                <div class="card-back__inner" />
              </div>
              <span class="stock-count">{{ gameState.stock_count }}</span>
            </div>
            <div v-else-if="gameState.waste_count > 0" class="recycle-icon">↺</div>
            <div v-else class="empty-slot" />
          </div>

          <div
            class="card-slot waste"
            :class="{ selected: isCardSelected('waste') }"
            @click="selectWaste"
          >
            <div v-if="gameState.waste_top" class="playing-card" :class="{ red: isRed(gameState.waste_top.suit) }">
              <span class="corner corner--tl">
                <span class="corner__rank">{{ gameState.waste_top.rank }}</span>
                <span class="corner__suit">{{ getSuitSymbol(gameState.waste_top.suit) }}</span>
              </span>
              <span class="suit suit--center">{{ getSuitSymbol(gameState.waste_top.suit) }}</span>
              <span class="corner corner--br">
                <span class="corner__rank">{{ gameState.waste_top.rank }}</span>
                <span class="corner__suit">{{ getSuitSymbol(gameState.waste_top.suit) }}</span>
              </span>
            </div>
            <div v-else class="empty-slot" />
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
              <span class="foundation-count">{{ gameState.foundations[suit].count }}/13</span>
            </div>
            <div v-else class="empty-slot foundation-empty">
              <span class="foundation-suit" :class="{ red: isRed(suit) }">{{ getSuitSymbol(suit) }}</span>
            </div>
          </div>
        </div>
      </div>

      <div class="tableau">
        <div v-for="(col, colIndex) in gameState.tableau" :key="colIndex" class="tableau-column">
          <div
            v-if="col.length === 0"
            class="card-slot empty-column"
            :class="{ 'drop-target': selectedCard !== null }"
            @click="selectEmptyTableau(colIndex)"
          >
            <div class="empty-slot">K</div>
          </div>
          <div
            v-for="(card, cardIndex) in col"
            :key="`${colIndex}-${cardIndex}`"
            class="tableau-card"
            :class="{
              selected: isInSelectedStack(colIndex, cardIndex),
              'face-down': !card.face_up,
            }"
            :style="{ top: `${cardIndex * 28}px`, zIndex: cardIndex + 1 }"
            @click="selectTableauCard(colIndex, cardIndex)"
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
                <div class="card-back__inner" />
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <Transition name="winner-overlay">
      <div v-if="isFinished" class="winner-overlay">
        <div class="winner-banner">
          <p class="winner-banner__eyebrow">Congratulations!</p>
          <h2 class="winner-banner__title">You Won!</h2>
          <p class="winner-banner__stats">Completed in {{ gameState.moves }} moves</p>
          <button type="button" class="btn-primary play-again-btn" @click="newGame">
            Play Again
          </button>
        </div>
      </div>
    </Transition>

    <aside class="controls-hint">
      <p><strong>Click</strong> a card to select it, then click a destination to move.</p>
      <p><strong>Double-click</strong> a card to auto-move to foundation.</p>
    </aside>
  </div>
</template>

<style scoped>
.solitaire-board {
  max-width: 1200px;
  margin: 0 auto;
  padding: 0 1rem 1.5rem;
  min-height: calc(100vh - 5.5rem);
  display: flex;
  flex-direction: column;
  gap: 1rem;
  background:
    radial-gradient(ellipse 80% 50% at 50% 0%, rgba(34, 139, 34, 0.08) 0%, transparent 50%),
    radial-gradient(ellipse 60% 40% at 50% 100%, rgba(139, 69, 19, 0.06) 0%, transparent 45%);
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

.status-pill--moves {
  color: var(--text);
  background: rgba(91, 156, 255, 0.1);
  border-color: rgba(91, 156, 255, 0.22);
}

.status-pill--moves strong {
  color: #fff;
  font-weight: 800;
}

.status-pill--progress {
  color: #7dffb0;
  background: rgba(61, 214, 140, 0.1);
  border-color: rgba(61, 214, 140, 0.25);
}

.status-bar__right {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.btn-auto {
  background: rgba(61, 214, 140, 0.15);
  border-color: rgba(61, 214, 140, 0.4);
  color: #7dffb0;
}

.btn-auto:hover {
  background: rgba(61, 214, 140, 0.25);
}

.game-area {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 1.5rem;
}

.top-row {
  display: flex;
  justify-content: space-between;
  gap: 1rem;
  flex-wrap: wrap;
}

.stock-waste {
  display: flex;
  gap: 0.75rem;
}

.foundations {
  display: flex;
  gap: 0.5rem;
}

.card-slot {
  width: 80px;
  height: 112px;
  border-radius: 10px;
  cursor: pointer;
  transition: transform 0.15s ease, box-shadow 0.2s ease;
  position: relative;
}

.card-slot:hover {
  transform: translateY(-2px);
}

.card-slot.selected {
  box-shadow: 0 0 0 3px #ffd700, 0 4px 16px rgba(255, 215, 0, 0.35);
}

.empty-slot {
  width: 100%;
  height: 100%;
  border: 2px dashed rgba(255, 255, 255, 0.15);
  border-radius: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: rgba(255, 255, 255, 0.2);
  font-size: 1.5rem;
  font-weight: 700;
  background: rgba(0, 0, 0, 0.2);
}

.foundation-empty {
  border-color: rgba(255, 255, 255, 0.25);
}

.foundation-suit {
  font-size: 2rem;
  opacity: 0.4;
}

.foundation-suit.red {
  color: #c62828;
}

.foundation.complete {
  animation: foundationComplete 0.5s ease;
}

@keyframes foundationComplete {
  0%, 100% { transform: scale(1); }
  50% { transform: scale(1.05); }
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

.stock-count {
  position: absolute;
  bottom: 4px;
  right: 6px;
  font-size: 0.7rem;
  font-weight: 700;
  color: rgba(255, 255, 255, 0.8);
  background: rgba(0, 0, 0, 0.5);
  padding: 0.1rem 0.35rem;
  border-radius: 4px;
}

.foundation-count {
  position: absolute;
  bottom: 4px;
  right: 6px;
  font-size: 0.65rem;
  font-weight: 700;
  color: rgba(0, 0, 0, 0.6);
  background: rgba(255, 255, 255, 0.8);
  padding: 0.1rem 0.3rem;
  border-radius: 4px;
}

.recycle-icon {
  width: 100%;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 2.5rem;
  color: rgba(91, 156, 255, 0.6);
  border: 2px dashed rgba(91, 156, 255, 0.4);
  border-radius: 10px;
  background: rgba(91, 156, 255, 0.08);
  transition: all 0.2s ease;
}

.recycle-icon:hover {
  color: rgba(91, 156, 255, 0.9);
  background: rgba(91, 156, 255, 0.15);
}

.playing-card {
  width: 100%;
  height: 100%;
  border-radius: 10px;
  background: linear-gradient(160deg, #fffef9 0%, #f4f0e6 100%);
  border: 1px solid rgba(0, 0, 0, 0.12);
  position: relative;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #1a1a1a;
  box-shadow:
    0 1px 0 rgba(255, 255, 255, 0.8) inset,
    0 2px 4px rgba(0, 0, 0, 0.15),
    0 6px 14px rgba(0, 0, 0, 0.22);
  transition: transform 0.15s ease;
}

.playing-card.red {
  color: #c62828;
}

.playing-card--back {
  background: linear-gradient(145deg, #1e3a6e 0%, #0f2448 100%);
  border: 1px solid rgba(255, 255, 255, 0.08);
  box-shadow:
    0 1px 0 rgba(255, 255, 255, 0.06) inset,
    0 4px 12px rgba(0, 0, 0, 0.35);
}

.card-back {
  width: 88%;
  height: 90%;
  border-radius: 6px;
  border: 2px solid rgba(201, 162, 39, 0.55);
  background: linear-gradient(135deg, #1a4d8f 0%, #0d2d5c 100%);
  display: flex;
  align-items: center;
  justify-content: center;
  overflow: hidden;
}

.card-back__inner {
  width: 78%;
  height: 82%;
  border-radius: 4px;
  border: 1px solid rgba(255, 215, 0, 0.2);
  background:
    repeating-linear-gradient(
      45deg,
      rgba(37, 99, 176, 0.9) 0,
      rgba(37, 99, 176, 0.9) 3px,
      rgba(26, 77, 143, 0.9) 3px,
      rgba(26, 77, 143, 0.9) 6px
    ),
    radial-gradient(circle at center, rgba(255, 215, 0, 0.12) 0%, transparent 65%);
}

.corner {
  position: absolute;
  display: flex;
  flex-direction: column;
  align-items: center;
  line-height: 1;
  gap: 0.02rem;
}

.corner--tl {
  top: 5px;
  left: 6px;
}

.corner--br {
  bottom: 5px;
  right: 6px;
  transform: rotate(180deg);
}

.corner__rank {
  font-size: 0.95rem;
  font-weight: 800;
  letter-spacing: -0.02em;
}

.corner__suit {
  font-size: 0.85rem;
}

.suit--center {
  font-size: 2rem;
  line-height: 1;
  opacity: 0.92;
}

.tableau {
  display: flex;
  gap: 0.5rem;
  justify-content: center;
  flex: 1;
  min-height: 400px;
}

.tableau-column {
  position: relative;
  width: 80px;
  min-height: 112px;
}

.empty-column {
  position: absolute;
  top: 0;
  left: 0;
}

.empty-column.drop-target {
  border-color: rgba(255, 215, 0, 0.5);
  background: rgba(255, 215, 0, 0.08);
}

.tableau-card {
  position: absolute;
  left: 0;
  width: 80px;
  height: 112px;
  cursor: pointer;
  transition: transform 0.15s ease, box-shadow 0.2s ease;
}

.tableau-card:hover {
  transform: translateY(-3px);
  z-index: 100 !important;
}

.tableau-card.face-down {
  cursor: default;
}

.tableau-card.face-down:hover {
  transform: none;
}

.tableau-card.selected {
  transform: translateY(-8px);
  z-index: 100 !important;
}

.tableau-card.selected .playing-card {
  box-shadow:
    0 0 0 3px #ffd700,
    0 8px 24px rgba(255, 215, 0, 0.35);
}

.winner-overlay {
  position: fixed;
  inset: 0;
  z-index: 100;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(0, 0, 0, 0.75);
  backdrop-filter: blur(8px);
}

.winner-banner {
  text-align: center;
  max-width: 400px;
  padding: 2rem 2.5rem;
  border-radius: 20px;
  border: 3px solid rgba(255, 215, 0, 0.75);
  background: linear-gradient(160deg, rgba(28, 18, 4, 0.98) 0%, rgba(8, 24, 14, 0.98) 100%);
  box-shadow:
    0 0 0 1px rgba(255, 215, 0, 0.2),
    0 20px 60px rgba(0, 0, 0, 0.6),
    0 0 50px rgba(255, 215, 0, 0.25);
  animation: winnerGlow 2.5s ease-in-out infinite;
}

.winner-banner__eyebrow {
  margin: 0 0 0.5rem;
  font-size: 0.85rem;
  font-weight: 800;
  letter-spacing: 0.16em;
  text-transform: uppercase;
  color: #f0c84b;
}

.winner-banner__title {
  margin: 0;
  font-size: 2.5rem;
  font-weight: 900;
  color: #fff;
  text-shadow: 0 2px 16px rgba(0, 0, 0, 0.5);
}

.winner-banner__stats {
  margin: 1rem 0 1.5rem;
  font-size: 1.1rem;
  color: #7dffb0;
  font-weight: 600;
}

.play-again-btn {
  font-size: 1.1rem;
  padding: 0.85rem 2rem;
}

@keyframes winnerGlow {
  0%, 100% {
    box-shadow:
      0 0 0 1px rgba(255, 215, 0, 0.2),
      0 20px 60px rgba(0, 0, 0, 0.6),
      0 0 40px rgba(255, 215, 0, 0.2);
  }
  50% {
    box-shadow:
      0 0 0 1px rgba(255, 215, 0, 0.4),
      0 20px 60px rgba(0, 0, 0, 0.6),
      0 0 60px rgba(255, 215, 0, 0.4);
  }
}

.winner-overlay-enter-active {
  animation: overlayIn 0.5s ease-out;
}

.winner-overlay-enter-active .winner-banner {
  animation: bannerIn 0.6s ease-out;
}

@keyframes overlayIn {
  from { opacity: 0; }
  to { opacity: 1; }
}

@keyframes bannerIn {
  from {
    opacity: 0;
    transform: scale(0.8) translateY(20px);
  }
  to {
    opacity: 1;
    transform: scale(1) translateY(0);
  }
}

.controls-hint {
  text-align: center;
  padding: 0.75rem;
  background: var(--surface);
  border-radius: 8px;
  border: 1px solid var(--border);
}

.controls-hint p {
  margin: 0.25rem 0;
  font-size: 0.85rem;
  color: var(--text-muted);
}

.controls-hint strong {
  color: var(--text);
}

@media (max-width: 768px) {
  .card-slot {
    width: 56px;
    height: 78px;
  }

  .tableau-column {
    width: 56px;
  }

  .tableau-card {
    width: 56px;
    height: 78px;
  }

  .tableau-card {
    top: calc(var(--index) * 20px);
  }

  .corner__rank {
    font-size: 0.75rem;
  }

  .corner__suit {
    font-size: 0.65rem;
  }

  .suit--center {
    font-size: 1.4rem;
  }

  .corner--tl {
    top: 3px;
    left: 4px;
  }

  .corner--br {
    bottom: 3px;
    right: 4px;
  }

  .foundation-suit {
    font-size: 1.4rem;
  }

  .recycle-icon {
    font-size: 1.8rem;
  }

  .empty-slot {
    font-size: 1rem;
  }

  .top-row {
    flex-direction: column;
    align-items: center;
  }

  .foundations {
    order: -1;
  }
}

@media (max-width: 480px) {
  .solitaire-board {
    padding: 0 0.5rem 1rem;
  }

  .card-slot {
    width: 44px;
    height: 62px;
    border-radius: 6px;
  }

  .tableau-column {
    width: 44px;
  }

  .tableau-card {
    width: 44px;
    height: 62px;
  }

  .tableau {
    gap: 0.25rem;
  }

  .foundations {
    gap: 0.35rem;
  }

  .stock-waste {
    gap: 0.5rem;
  }

  .playing-card {
    border-radius: 6px;
  }

  .corner__rank {
    font-size: 0.65rem;
  }

  .corner__suit {
    font-size: 0.55rem;
  }

  .suit--center {
    font-size: 1.1rem;
  }

  .status-bar {
    padding: 0.5rem 0.75rem;
  }

  .status-pill {
    font-size: 0.7rem;
    padding: 0.25rem 0.5rem;
  }

  .controls-hint {
    display: none;
  }
}
</style>
