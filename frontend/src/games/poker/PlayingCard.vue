<script setup lang="ts">
import { computed } from 'vue'

const props = defineProps<{
  rank?: string
  suit?: string
  faceDown?: boolean
  small?: boolean
  deal?: boolean
  flip?: boolean
}>()

const suitSymbol = computed(() => {
  if (props.faceDown || !props.suit) return ''
  const map: Record<string, string> = {
    hearts: '♥',
    diamonds: '♦',
    clubs: '♣',
    spades: '♠',
  }
  return map[props.suit] ?? ''
})

const rankDisplay = computed(() => {
  if (props.faceDown || !props.rank) return ''
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
      'playing-card--down': faceDown,
      'playing-card--small': small,
      'playing-card--deal': deal,
      'playing-card--flip': flip,
      red: isRed,
      black: !isRed && !faceDown,
    }"
  >
    <template v-if="faceDown">
      <div class="card-back" />
    </template>
    <template v-else>
      <span class="rank">{{ rankDisplay }}</span>
      <span class="suit">{{ suitSymbol }}</span>
    </template>
  </div>
</template>

<style scoped>
.playing-card {
  width: 64px;
  height: 90px;
  border-radius: 8px;
  background: #fff;
  border: 1px solid #ccc;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  font-weight: 700;
  box-shadow: 0 2px 6px rgba(0, 0, 0, 0.25);
  transform-style: preserve-3d;
  backface-visibility: hidden;
}

.playing-card--small {
  width: 48px;
  height: 68px;
  font-size: 0.85rem;
}

.playing-card--deal {
  animation: cardDeal 0.55s ease-out;
}

.playing-card--flip {
  animation: cardFlip 0.65s ease-out;
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

@keyframes cardFlip {
  0% {
    transform: rotateY(90deg) scale(0.9);
    opacity: 0.2;
  }
  100% {
    transform: rotateY(0deg) scale(1);
    opacity: 1;
  }
}

.playing-card--down {
  background: #1a4d8f;
  border-color: #0f3460;
}

.card-back {
  width: 80%;
  height: 80%;
  border-radius: 4px;
  background: repeating-linear-gradient(
    45deg,
    #2563b0,
    #2563b0 4px,
    #1a4d8f 4px,
    #1a4d8f 8px
  );
}

.red {
  color: #c0392b;
}

.black {
  color: #1a1a1a;
}

.rank {
  font-size: 1.1rem;
  line-height: 1;
}

.suit {
  font-size: 1.4rem;
  line-height: 1;
}
</style>
