<script setup lang="ts">
import { computed } from 'vue'
import Chess3DView from './Chess3DView.vue'
import { getIsoPieceSprites } from './isoPieces'
import type { BoardView } from './prefs'

const props = defineProps<{
  board: Array<Array<string | null>>
  fen: string
  flipped: boolean
  interactive: boolean
  side: 'w' | 'b'
  selected: string | null
  targets: string[]
  lastMove: { from: string; to: string } | null
  checkSquare: string | null
  hint?: { from: string; to: string } | null
  inCheck?: boolean
}>()

const view = defineModel<BoardView>('view', { required: true })

const emit = defineEmits<{
  square: [square: string]
  squareClick: [file: string, rankIndex: number]
}>()

const FILES = ['a', 'b', 'c', 'd', 'e', 'f', 'g', 'h'] as const

const PIECE_SVG_MODULES = import.meta.glob('../../assets/chess/pieces/*.svg', {
  eager: true,
  query: '?url',
  import: 'default',
}) as Record<string, string>

const PIECE_SRC: Record<string, string> = Object.fromEntries(
  Object.entries(PIECE_SVG_MODULES).map(([path, url]) => [
    path.split('/').pop()!.replace('.svg', ''),
    url,
  ]),
)

const ISO_PIECE_SRC = getIsoPieceSprites()

const PIECE_NAME: Record<string, string> = {
  k: 'king',
  q: 'queen',
  r: 'rook',
  b: 'bishop',
  n: 'knight',
  p: 'pawn',
}

const is3d = computed(() => view.value === '3d')

const ranks = computed(() => {
  const order = [7, 6, 5, 4, 3, 2, 1, 0]
  return props.flipped ? [...order].reverse() : order
})

const files = computed(() => {
  const order = [...FILES]
  return props.flipped ? [...order].reverse() : order
})

function squareOf(file: string, rankIndex: number): string {
  return `${file}${rankIndex + 1}`
}

function pieceAt(file: string, rankIndex: number): string | null {
  return props.board[rankIndex]?.[FILES.indexOf(file as (typeof FILES)[number])] ?? null
}

function isLightSquare(file: string, rankIndex: number): boolean {
  const fileIndex = FILES.indexOf(file as (typeof FILES)[number])
  return (fileIndex + rankIndex) % 2 === 1
}

function isWhitePiece(piece: string): boolean {
  return piece === piece.toUpperCase()
}

function ownPiece(piece: string | null): boolean {
  if (!piece) return false
  const white = isWhitePiece(piece)
  return props.side === 'w' ? white : !white
}

function pieceSrc(piece: string): string {
  const key = `${isWhitePiece(piece) ? 'w' : 'b'}${piece.toUpperCase()}`
  if (view.value === 'clay' && ISO_PIECE_SRC?.[key]) return ISO_PIECE_SRC[key]
  return PIECE_SRC[key] ?? ''
}

function pieceAlt(piece: string): string {
  return `${isWhitePiece(piece) ? 'White' : 'Black'} ${PIECE_NAME[piece.toLowerCase()] ?? piece}`
}

function isoPieceOrder(file: string, rankIndex: number): number {
  const row = ranks.value.indexOf(rankIndex)
  const col = files.value.indexOf(file as (typeof FILES)[number])
  return 10 + row * 100 + col * 32
}

const targetSet = computed(() => new Set(props.targets))

const hintArrow = computed(() => {
  const hint = props.hint
  if (!hint || is3d.value) return null
  const point = (sq: string) => ({
    x: files.value.indexOf(sq[0] as (typeof FILES)[number]) + 0.5,
    y: ranks.value.indexOf(Number(sq[1]) - 1) + 0.5,
  })
  const from = point(hint.from)
  const to = point(hint.to)
  const len = Math.hypot(to.x - from.x, to.y - from.y) || 1
  const trim = 0.3 / len
  return {
    x1: from.x,
    y1: from.y,
    x2: to.x - (to.x - from.x) * trim,
    y2: to.y - (to.y - from.y) * trim,
  }
})

function emitSquare(file: string, rankIndex: number) {
  if (!props.interactive) return
  emit('square', squareOf(file, rankIndex))
  emit('squareClick', file, rankIndex)
}
</script>

<template>
  <div class="surface" :class="{ 'is-3d': is3d, 'is-clay': view === 'clay' }">
    <Chess3DView
      v-if="is3d"
      :board="board"
      :fen="fen"
      :flipped="flipped"
      :interactive="interactive"
      :selected="selected"
      :targets="targets"
      :last-move="lastMove"
      :check-square="checkSquare"
      :hint="hint"
      @square-click="emitSquare"
    />
    <div
      v-else
      class="board"
      :class="{
        disabled: !interactive,
        check: inCheck,
        clay: view === 'clay',
      }"
    >
      <div class="board-grid">
        <svg class="iso-filters" aria-hidden="true">
          <filter id="iso-outline-w" x="-15%" y="-15%" width="130%" height="130%" color-interpolation-filters="sRGB">
            <feComponentTransfer in="SourceAlpha" result="solid">
              <feFuncA type="discrete" tableValues="0 0 1" />
            </feComponentTransfer>
            <feMorphology in="solid" operator="dilate" radius="1" result="spread" />
            <feFlood flood-color="#2c4158" result="ink" />
            <feComposite in="ink" in2="spread" operator="in" result="line" />
            <feMerge>
              <feMergeNode in="line" />
              <feMergeNode in="SourceGraphic" />
            </feMerge>
          </filter>
          <filter id="iso-outline-b" x="-15%" y="-15%" width="130%" height="130%" color-interpolation-filters="sRGB">
            <feComponentTransfer in="SourceAlpha" result="solid">
              <feFuncA type="discrete" tableValues="0 0 1" />
            </feComponentTransfer>
            <feMorphology in="solid" operator="dilate" radius="1" result="spread" />
            <feFlood flood-color="#e4eef8" result="ink" />
            <feComposite in="ink" in2="spread" operator="in" result="line" />
            <feMerge>
              <feMergeNode in="line" />
              <feMergeNode in="SourceGraphic" />
            </feMerge>
          </filter>
        </svg>
        <div v-for="rankIndex in ranks" :key="rankIndex" class="rank-row">
          <button
            v-for="file in files"
            :key="`${file}${rankIndex}`"
            type="button"
            class="square"
            :class="{
              light: isLightSquare(file, rankIndex),
              dark: !isLightSquare(file, rankIndex),
              selected: selected === squareOf(file, rankIndex),
              target: targetSet.has(squareOf(file, rankIndex)),
              last: lastMove?.from === squareOf(file, rankIndex) || lastMove?.to === squareOf(file, rankIndex),
              capture: targetSet.has(squareOf(file, rankIndex)) && !!pieceAt(file, rankIndex),
              check: checkSquare === squareOf(file, rankIndex),
              'engine-hint': hint?.from === squareOf(file, rankIndex) || hint?.to === squareOf(file, rankIndex),
              movable: interactive && ownPiece(pieceAt(file, rankIndex)),
            }"
            @click="emitSquare(file, rankIndex)"
          >
            <span v-if="file === files[0]" class="coord rank">{{ rankIndex + 1 }}</span>
            <img
              v-if="pieceAt(file, rankIndex)"
              class="piece"
              :class="isWhitePiece(pieceAt(file, rankIndex)!) ? 'is-white' : 'is-black'"
              :src="pieceSrc(pieceAt(file, rankIndex)!)"
              :alt="pieceAlt(pieceAt(file, rankIndex)!)"
              :style="view === 'clay' ? { zIndex: isoPieceOrder(file, rankIndex) } : undefined"
              draggable="false"
            />
            <span
              v-if="targetSet.has(squareOf(file, rankIndex)) && !pieceAt(file, rankIndex)"
              class="target-dot"
            />
            <span v-if="rankIndex === ranks[ranks.length - 1]" class="coord file">{{ file }}</span>
          </button>
        </div>
        <svg v-if="hintArrow" class="engine-arrow" viewBox="0 0 8 8" aria-hidden="true">
          <defs>
            <marker
              id="engine-arrow-head"
              viewBox="0 0 4 4"
              refX="1.2"
              refY="2"
              markerWidth="3"
              markerHeight="3"
              orient="auto"
            >
              <path d="M0,0 L4,2 L0,4 Z" />
            </marker>
          </defs>
          <line
            :x1="hintArrow.x1"
            :y1="hintArrow.y1"
            :x2="hintArrow.x2"
            :y2="hintArrow.y2"
            marker-end="url(#engine-arrow-head)"
          />
        </svg>
      </div>
    </div>
  </div>
</template>

<style scoped>
.surface {
  --wood-light: #f0dcb8;
  --wood-dark: #b3804f;
  --wood-frame: #3d2c1e;
  --wood-frame-hi: #6b4a2e;
  --wood-accent: #c99a62;
  --select: rgba(92, 170, 110, 0.55);
  --last-move: rgba(214, 222, 80, 0.5);
  --target: rgba(40, 70, 40, 0.32);
  --check-glow: rgba(255, 60, 70, 0.85);
  --engine: rgba(64, 156, 255, 0.82);
  width: 100%;
  height: 100%;
  min-height: 0;
  display: grid;
  place-items: center;
  container-type: size;
  position: relative;
}

.surface.is-3d {
  grid-template: minmax(0, 1fr) / minmax(0, 1fr);
  place-items: stretch;
}

.board {
  width: min(100cqw, 100cqh);
  height: min(100cqw, 100cqh);
  aspect-ratio: 1;
  container-type: size;
  box-sizing: border-box;
  display: flex;
  flex-direction: column;
  padding: 1.4cqw;
  border-radius: 14px;
  overflow: hidden;
  background: linear-gradient(145deg, var(--wood-frame-hi), var(--wood-frame) 55%, #2a1e14);
  box-shadow:
    0 20px 56px rgba(0, 0, 0, 0.5),
    0 2px 0 rgba(255, 255, 255, 0.06) inset,
    0 -2px 0 rgba(0, 0, 0, 0.35) inset;
}

@supports not (width: 1cqw) {
  .board {
    width: min(100%, calc(100dvh - 11.5rem));
    height: auto;
    max-height: 100%;
  }
}

.board.check {
  box-shadow:
    0 20px 56px rgba(0, 0, 0, 0.5),
    0 0 0 2px rgba(255, 92, 108, 0.4),
    0 0 32px rgba(255, 92, 108, 0.25);
}

.board.disabled {
  cursor: default;
}

.board-grid {
  position: relative;
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
}

.engine-arrow {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  z-index: 3;
  pointer-events: none;
}

.engine-arrow line {
  stroke: var(--engine);
  stroke-width: 0.18;
  stroke-linecap: round;
}

.engine-arrow path {
  fill: var(--engine);
}

.rank-row {
  display: grid;
  grid-template-columns: repeat(8, 1fr);
  flex: 1;
  min-height: 0;
}

.square {
  position: relative;
  border: none;
  border-radius: 0;
  padding: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: default;
  line-height: 1;
}

.square.light {
  background-color: var(--wood-light);
  background-image: linear-gradient(135deg, rgba(255, 255, 255, 0.16), rgba(0, 0, 0, 0.03));
}

.square.dark {
  background-color: var(--wood-dark);
  background-image: linear-gradient(135deg, rgba(255, 255, 255, 0.08), rgba(0, 0, 0, 0.08));
}

.square.movable,
.square.target {
  cursor: pointer;
}

.square.last {
  background-image: linear-gradient(var(--last-move), var(--last-move));
}

.square.selected {
  background-image: linear-gradient(var(--select), var(--select));
}

.board .square:active {
  transform: none;
}

.square.engine-hint {
  box-shadow: inset 0 0 0 0.45cqw var(--engine);
}

.square.check {
  background-image: radial-gradient(
    circle at center,
    var(--check-glow) 0%,
    rgba(255, 60, 70, 0.45) 45%,
    transparent 78%
  );
}

.square.target:not(.capture):hover {
  background-image: linear-gradient(var(--target), var(--target));
}

.square.target.capture::after {
  content: '';
  position: absolute;
  inset: 0;
  background: radial-gradient(circle, transparent 66%, var(--target) 67%);
  pointer-events: none;
}

.square.target.capture:hover::after {
  background: var(--target);
}

.piece {
  position: relative;
  z-index: 1;
  width: 94%;
  height: 94%;
  object-fit: contain;
  user-select: none;
  -webkit-user-drag: none;
  pointer-events: none;
  filter: drop-shadow(0 0.35cqw 0.35cqw rgba(0, 0, 0, 0.4));
  transition:
    transform 0.14s var(--ease-smooth),
    filter 0.14s var(--ease-smooth);
}

.square.movable:hover .piece {
  transform: translateY(-3%) scale(1.04);
  filter: drop-shadow(0 0.7cqw 0.6cqw rgba(0, 0, 0, 0.45));
}

.square.selected .piece {
  transform: translateY(-4%) scale(1.07);
  filter: drop-shadow(0 0.9cqw 0.7cqw rgba(0, 0, 0, 0.5));
}

.target-dot {
  width: 30%;
  height: 30%;
  border-radius: 50%;
  background: var(--target);
  pointer-events: none;
}

.coord {
  position: absolute;
  z-index: 2;
  font-size: max(0.6rem, min(0.9rem, 1.9cqw));
  font-weight: 800;
  opacity: 0.8;
  pointer-events: none;
  font-family: 'Outfit', 'DM Sans', system-ui, sans-serif;
}

.coord.rank {
  top: 3px;
  left: 4px;
}

.coord.file {
  bottom: 2px;
  right: 4px;
}

.square.light .coord {
  color: var(--wood-dark);
}

.square.dark .coord {
  color: var(--wood-light);
}

.board.clay {
  --wood-light: #d7e0ea;
  --wood-dark: #7f93a8;
  --wood-frame: #1b2836;
  --wood-frame-hi: #3d5166;
  --select: rgba(88, 204, 120, 0.42);
  --last-move: rgba(255, 210, 90, 0.4);
  --target: rgba(18, 36, 54, 0.34);
  padding: 1.05cqw;
  border-radius: 18px;
  overflow: visible;
  isolation: isolate;
  background: linear-gradient(160deg, var(--wood-frame-hi), var(--wood-frame) 58%, #121a24);
}

.iso-filters {
  position: absolute;
  width: 0;
  height: 0;
  overflow: hidden;
}

.board.clay .square {
  height: 100%;
  min-height: 0;
  min-width: 0;
  overflow: visible;
}

.board.clay .piece {
  position: absolute;
  inset: auto;
  left: 50%;
  top: 26%;
  width: 168%;
  height: 168%;
  transform: translate(-50%, -50%);
  z-index: 2;
  transition: transform 0.14s var(--ease-smooth);
}

.board.clay .piece.is-white {
  filter: url(#iso-outline-w);
}

.board.clay .piece.is-black {
  filter: url(#iso-outline-b);
}

.board.clay .engine-arrow {
  z-index: 2000;
}

.board.clay .square.movable:hover .piece.is-white,
.board.clay .square.selected .piece.is-white {
  filter: url(#iso-outline-w);
}

.board.clay .square.movable:hover .piece.is-black,
.board.clay .square.selected .piece.is-black {
  filter: url(#iso-outline-b);
}

.board.clay .square.movable:hover .piece {
  transform: translate(-50%, -54%) scale(1.03);
}

.board.clay .square.selected .piece {
  transform: translate(-50%, -56%) scale(1.04);
}

.board.clay .square.light .coord {
  color: #42566c;
}

.board.clay .square.dark .coord {
  color: #f4f7fb;
}
</style>
