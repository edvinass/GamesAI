<script setup lang="ts">
import { computed } from 'vue'
import { Chess } from 'chess.js'
import ChessSurface from '../ChessSurface.vue'
import type { BoardView } from '../prefs'

const props = defineProps<{
  fen: string
  selected: string | null
  targets: string[]
  lastMove: { from: string; to: string } | null
  hint: { from: string; to: string } | null
  checkSquare: string | null
  disabled: boolean
  shake: boolean
}>()

const emit = defineEmits<{
  square: [square: string]
}>()

const view = defineModel<BoardView>('view', { required: true })

const matrix = computed(() => {
  const rows = new Chess(props.fen).board()
  const board: Array<Array<string | null>> = []
  for (let rank = 0; rank < 8; rank += 1) {
    const row = rows[7 - rank] ?? []
    board[rank] = row.map((piece) => {
      if (!piece) return null
      return piece.color === 'w' ? piece.type.toUpperCase() : piece.type
    })
  }
  return board
})
</script>

<template>
  <div class="learn-board" :class="{ shake, iso: view === 'clay' }">
    <div class="stage">
      <ChessSurface
        v-model:view="view"
        :board="matrix"
        :fen="fen"
        :flipped="false"
        side="w"
        :interactive="!disabled"
        :selected="selected"
        :targets="targets"
        :last-move="lastMove"
        :check-square="checkSquare"
        :hint="hint"
        :in-check="!!checkSquare"
        @square="emit('square', $event)"
      />
    </div>
  </div>
</template>

<style scoped>
.learn-board {
  flex: 1 1 auto;
  align-self: stretch;
  min-height: 0;
  width: 100%;
  display: grid;
  place-items: start center;
  container-type: size;
}

.learn-board.shake .stage {
  animation: shake 0.4s ease;
}

.stage {
  width: min(100cqw, 100cqh);
  height: min(100cqw, 100cqh);
  min-height: 0;
}

.learn-board.iso .stage {
  width: min(100cqw, calc(100cqh - 2.6rem));
  height: min(100cqw, calc(100cqh - 2.6rem));
  margin-bottom: 2.6rem;
}

.stage :deep(.surface) {
  width: 100%;
  height: 100%;
}

@keyframes shake {
  0%,
  100% {
    transform: translateX(0);
  }
  25% {
    transform: translateX(-6px);
  }
  75% {
    transform: translateX(6px);
  }
}
</style>
