<script setup lang="ts">
import { computed } from 'vue'

const props = defineProps<{
  rank?: string
  suit?: string
  faceDown?: boolean
  small?: boolean
  deal?: boolean
}>()

const suitSymbol = computed(() => {
  if (!props.suit) return ''
  const map: Record<string, string> = {
    hearts: '♥',
    diamonds: '♦',
    clubs: '♣',
    spades: '♠',
  }
  return map[props.suit] ?? ''
})

const rankDisplay = computed(() => {
  if (!props.rank) return ''
  const map: Record<string, string> = {
    T: '10',
    J: 'J',
    Q: 'Q',
    K: 'K',
    A: 'A',
  }
  return map[props.rank] ?? props.rank
})

const isRed = computed(() => props.suit === 'hearts' || props.suit === 'diamonds')
</script>

<template>
  <div
    class="playing-card"
    :class="{
      'playing-card--small': small,
      'playing-card--deal': deal,
    }"
  >
    <div class="card-inner" :class="{ 'card-inner--face-down': faceDown }">
      <div class="card-face card-face--front" :class="{ red: isRed, black: !isRed }">
        <span class="corner corner--tl">
          <span class="corner__rank">{{ rankDisplay }}</span>
          <span class="corner__suit">{{ suitSymbol }}</span>
        </span>
        <span class="suit suit--center">{{ suitSymbol }}</span>
        <span class="corner corner--br">
          <span class="corner__rank">{{ rankDisplay }}</span>
          <span class="corner__suit">{{ suitSymbol }}</span>
        </span>
      </div>
      <div class="card-face card-face--back">
        <div class="card-back">
          <div class="card-back__inner" />
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.playing-card {
  position: relative;
  width: 64px;
  height: 90px;
  perspective: 900px;
  flex-shrink: 0;
}

.playing-card--small {
  width: 48px;
  height: 68px;
}

.playing-card--deal {
  animation: cardDeal 0.35s ease-out;
}

.card-inner {
  width: 100%;
  height: 100%;
  position: relative;
  transform-style: preserve-3d;
  transform: rotateY(0deg);
  transition: transform 0.6s cubic-bezier(0.4, 0.15, 0.2, 1.05);
}

.card-inner--face-down {
  transform: rotateY(180deg);
}

.card-face {
  position: absolute;
  inset: 0;
  border-radius: 10px;
  backface-visibility: hidden;
  -webkit-backface-visibility: hidden;
  font-size: 1.1rem;
  font-weight: 700;
  box-shadow:
    0 1px 0 rgba(255, 255, 255, 0.8) inset,
    0 2px 4px rgba(0, 0, 0, 0.15),
    0 6px 14px rgba(0, 0, 0, 0.22);
}

.playing-card--small .card-face {
  font-size: 1rem;
  border-radius: 8px;
}

.card-face--front {
  background: linear-gradient(160deg, #fffef9 0%, #f4f0e6 100%);
  border: 1px solid rgba(0, 0, 0, 0.12);
  display: flex;
  align-items: center;
  justify-content: center;
  transform: rotateY(0deg);
}

.card-face--back {
  background: linear-gradient(145deg, #1e3a6e 0%, #0f2448 100%);
  border: 1px solid rgba(255, 255, 255, 0.08);
  transform: rotateY(180deg);
  display: flex;
  align-items: center;
  justify-content: center;
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

.red {
  color: #c62828;
}

.black {
  color: #1a1a1a;
}

.corner {
  position: absolute;
  display: flex;
  flex-direction: column;
  align-items: center;
  line-height: 1;
  gap: 0.05rem;
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
  font-size: 0.95em;
  font-weight: 800;
  letter-spacing: -0.02em;
}

.corner__suit {
  font-size: 0.85em;
}

.suit--center {
  font-size: 2.1em;
  line-height: 1;
  opacity: 0.92;
}

.playing-card--small .corner--tl {
  top: 3px;
  left: 4px;
}

.playing-card--small .corner--br {
  bottom: 3px;
  right: 4px;
}

.playing-card--small .suit--center {
  font-size: 1.75em;
}

.playing-card--small .corner__rank {
  font-size: 0.9em;
}

.playing-card--small .corner__suit {
  font-size: 0.82em;
}

@keyframes cardDeal {
  from {
    opacity: 0;
    transform: translateY(-18px) scale(0.78) rotate(-6deg);
  }
  to {
    opacity: 1;
    transform: translateY(0) scale(1) rotate(0deg);
  }
}

@media (prefers-reduced-motion: reduce) {
  .card-inner {
    transition: none;
  }

  .playing-card--deal {
    animation: none;
  }
}
</style>
