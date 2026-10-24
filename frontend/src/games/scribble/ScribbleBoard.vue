<script setup lang="ts">
import { computed, nextTick, onMounted, onUnmounted, ref, watch } from 'vue'
import type { ScribbleGameState, ScribbleStroke } from '@/types'

const props = defineProps<{
  gameState: ScribbleGameState
  playerId: string
}>()

const emit = defineEmits<{
  action: [data: Record<string, unknown>]
}>()

const COLORS = ['#1c1917', '#e11d48', '#f97316', '#eab308', '#16a34a', '#0284c7', '#4f46e5', '#9333ea', '#92400e']
const SIZES = [8, 16, 28, 46]
const PAPER = '#f6f1e7'

const canvasRef = ref<HTMLCanvasElement | null>(null)
const chatRef = ref<HTMLElement | null>(null)
const color = ref(COLORS[1])
const size = ref(16)
const erasing = ref(false)
const guess = ref('')
const now = ref(Date.now())
const drawing = ref(false)
const livePoints = ref<number[][]>([])

let clock: ReturnType<typeof setInterval> | undefined
let resizeObserver: ResizeObserver | undefined

const isDrawer = computed(() => props.gameState.viewer_is_drawer)
const phase = computed(() => props.gameState.phase)
const canDraw = computed(() => isDrawer.value && phase.value === 'drawing')
const canGuess = computed(
  () => phase.value === 'drawing' && !isDrawer.value && !props.gameState.viewer_has_guessed,
)

const secondsLeft = computed(() => {
  const ends = props.gameState.phase_ends_at
  if (!ends || phase.value === 'finished') return 0
  return Math.max(0, Math.ceil((Date.parse(ends) - now.value) / 1000))
})

const ranked = computed(() =>
  [...props.gameState.players].sort((a, b) => b.score - a.score || a.nickname.localeCompare(b.nickname)),
)

const maskChars = computed(() => (props.gameState.word_mask || '').split(' '))

const brushColor = computed(() => (erasing.value ? PAPER : color.value))

const statusLine = computed(() => {
  const drawer = props.gameState.players.find((player) => player.is_drawer)
  const name = drawer?.nickname ?? 'Someone'
  if (phase.value === 'choosing') {
    return isDrawer.value ? 'Pick a word to draw' : `${name} is choosing a word`
  }
  if (phase.value === 'drawing') {
    return isDrawer.value ? 'Draw it. They are guessing.' : `${name} is drawing`
  }
  if (phase.value === 'reveal') return 'Word revealed'
  if (props.gameState.winner === 'tie') return 'Tie game'
  const winner = props.gameState.players.find((player) => player.id === props.gameState.winner)
  return winner ? `${winner.nickname} wins` : 'Game over'
})

function pointsLabel(difficulty: string) {
  if (difficulty === 'hard') return '300 pts'
  if (difficulty === 'medium') return '200 pts'
  return '100 pts'
}

function choose(index: number) {
  emit('action', { type: 'choose_word', index })
}

function submitGuess() {
  const text = guess.value.trim()
  if (!text || !canGuess.value) return
  emit('action', { type: 'guess', text })
  guess.value = ''
}

function undo() {
  if (canDraw.value) emit('action', { type: 'undo' })
}

function clearCanvas() {
  if (canDraw.value) emit('action', { type: 'clear' })
}

function endTurn() {
  if (canDraw.value) emit('action', { type: 'end_turn' })
}

function canvasPoint(event: PointerEvent): [number, number] {
  const canvas = canvasRef.value
  if (!canvas) return [0, 0]
  const rect = canvas.getBoundingClientRect()
  const width = props.gameState.canvas_width || 1000
  const height = props.gameState.canvas_height || 700
  const x = ((event.clientX - rect.left) / rect.width) * width
  const y = ((event.clientY - rect.top) / rect.height) * height
  return [
    Math.max(0, Math.min(width, x)),
    Math.max(0, Math.min(height, y)),
  ]
}

function onPointerDown(event: PointerEvent) {
  if (!canDraw.value) return
  event.preventDefault()
  const canvas = canvasRef.value
  canvas?.setPointerCapture(event.pointerId)
  drawing.value = true
  livePoints.value = [canvasPoint(event)]
  paint()
}

function onPointerMove(event: PointerEvent) {
  if (!drawing.value) return
  const next = canvasPoint(event)
  const prev = livePoints.value[livePoints.value.length - 1]
  if (prev) {
    const dx = next[0] - prev[0]
    const dy = next[1] - prev[1]
    if (dx * dx + dy * dy < 16) return
  }
  livePoints.value = [...livePoints.value, next]
  paint()
}

function onPointerUp(event: PointerEvent) {
  if (!drawing.value) return
  drawing.value = false
  const canvas = canvasRef.value
  if (canvas?.hasPointerCapture(event.pointerId)) canvas.releasePointerCapture(event.pointerId)
  const points = livePoints.value
  livePoints.value = []
  paint()
  if (points.length === 0) return
  emit('action', {
    type: 'stroke',
    color: brushColor.value,
    size: size.value,
    points: points.map(([x, y]) => [Math.round(x), Math.round(y)]),
  })
}

function paintStroke(ctx: CanvasRenderingContext2D, stroke: ScribbleStroke, scale: number) {
  const pts = stroke.points
  if (!pts.length) return
  ctx.beginPath()
  ctx.strokeStyle = stroke.color
  ctx.lineWidth = Math.max(1.5, stroke.size * scale)
  ctx.lineCap = 'round'
  ctx.lineJoin = 'round'
  ctx.moveTo(pts[0][0], pts[0][1])
  for (const point of pts.slice(1)) ctx.lineTo(point[0], point[1])
  if (pts.length === 1) ctx.lineTo(pts[0][0] + 0.5, pts[0][1] + 0.5)
  ctx.stroke()
}

function paint() {
  const canvas = canvasRef.value
  if (!canvas) return
  const ctx = canvas.getContext('2d')
  if (!ctx) return
  const width = props.gameState.canvas_width || 1000
  const height = props.gameState.canvas_height || 700
  ctx.clearRect(0, 0, width, height)
  ctx.fillStyle = PAPER
  ctx.fillRect(0, 0, width, height)
  const scale = 1
  for (const stroke of props.gameState.strokes) paintStroke(ctx, stroke, scale)
  if (livePoints.value.length) {
    paintStroke(
      ctx,
      { color: brushColor.value, size: size.value, points: livePoints.value },
      scale,
    )
  }
}

function fitCanvas() {
  const canvas = canvasRef.value
  if (!canvas) return
  const width = props.gameState.canvas_width || 1000
  const height = props.gameState.canvas_height || 700
  const dpr = Math.min(window.devicePixelRatio || 1, 2)
  const rect = canvas.getBoundingClientRect()
  const pixelWidth = Math.max(1, Math.round(rect.width * dpr))
  const pixelHeight = Math.max(1, Math.round(rect.height * dpr))
  if (canvas.width !== pixelWidth || canvas.height !== pixelHeight) {
    canvas.width = pixelWidth
    canvas.height = pixelHeight
  }
  const ctx = canvas.getContext('2d')
  if (!ctx) return
  ctx.setTransform((pixelWidth / width), 0, 0, (pixelHeight / height), 0, 0)
  paint()
}

function messageText(kind: string, nickname: string, text: string) {
  if (kind === 'system') return text
  if (kind === 'correct') return `${nickname} ${text}`
  if (kind === 'close') return `${nickname}: ${text} · close`
  return `${nickname}: ${text}`
}

watch(
  () => props.gameState.strokes,
  () => {
    if (!drawing.value) paint()
  },
)

watch(
  () => props.gameState.messages.length,
  async () => {
    await nextTick()
    const el = chatRef.value
    if (el) el.scrollTop = el.scrollHeight
  },
)

onMounted(() => {
  clock = setInterval(() => {
    now.value = Date.now()
  }, 200)
  const canvas = canvasRef.value
  if (canvas && typeof ResizeObserver !== 'undefined') {
    resizeObserver = new ResizeObserver(() => fitCanvas())
    resizeObserver.observe(canvas)
  }
  fitCanvas()
})

onUnmounted(() => {
  if (clock) clearInterval(clock)
  resizeObserver?.disconnect()
})
</script>

<template>
  <div class="scribble">
    <header class="topbar">
      <div class="round">
        <span>Round {{ gameState.round }} / {{ gameState.rounds }}</span>
        <strong>{{ statusLine }}</strong>
      </div>
      <div class="prompt" :class="{ secret: Boolean(gameState.word) && phase !== 'reveal' && phase !== 'finished' }">
        <p v-if="gameState.word" class="secret-word">{{ gameState.word }}</p>
        <div v-else-if="maskChars.some((ch) => ch)" class="mask" aria-label="Word hint">
          <span
            v-for="(ch, index) in maskChars"
            :key="index"
            class="letter"
            :class="{ blank: ch === '_', gap: ch === '' }"
          >{{ ch === '_' || ch === '' ? '' : ch }}</span>
        </div>
        <p v-else class="waiting">{{ phase === 'choosing' ? 'Word hidden' : 'Get ready' }}</p>
      </div>
      <div class="timer" :class="{ low: secondsLeft <= 10 && phase !== 'finished' }">
        {{ phase === 'finished' ? 'End' : `${secondsLeft}s` }}
      </div>
    </header>

    <aside class="scores">
      <h2>Scores</h2>
      <ol>
        <li
          v-for="player in ranked"
          :key="player.id"
          :class="{ drawer: player.is_drawer, me: player.id === playerId, got: player.guessed }"
        >
          <span class="who">
            <span class="name">{{ player.nickname }}</span>
            <span v-if="player.is_drawer" class="tag">Drawing</span>
            <span v-else-if="player.guessed" class="tag ok">Got it</span>
          </span>
          <strong>{{ player.score }}</strong>
        </li>
      </ol>
    </aside>

    <section class="stage">
      <div class="canvas-frame" :class="{ drawable: canDraw }">
        <canvas
          ref="canvasRef"
          :width="gameState.canvas_width"
          :height="gameState.canvas_height"
          @pointerdown="onPointerDown"
          @pointermove="onPointerMove"
          @pointerup="onPointerUp"
          @pointercancel="onPointerUp"
        />
        <div v-if="phase === 'choosing' && isDrawer" class="overlay choices">
          <p>Choose a word</p>
          <button
            v-for="(option, index) in gameState.word_options || []"
            :key="option.text"
            type="button"
            class="word-choice"
            @click="choose(index)"
          >
            <span>{{ option.text }}</span>
            <small>{{ option.difficulty }} · {{ pointsLabel(option.difficulty) }}</small>
          </button>
        </div>
        <div v-else-if="phase === 'choosing'" class="overlay dim">
          Waiting for a word
        </div>
        <div v-else-if="phase === 'reveal'" class="overlay reveal">
          <p class="reveal-word">{{ gameState.word }}</p>
          <ul v-if="gameState.last_awards.length">
            <li v-for="award in gameState.last_awards" :key="award.player_id">
              {{ award.nickname }} +{{ award.points }}
            </li>
          </ul>
          <p v-else>Nobody scored this turn</p>
        </div>
        <div v-else-if="phase === 'finished'" class="overlay reveal">
          <p class="reveal-word">{{ statusLine }}</p>
          <p>Highest score takes the room.</p>
        </div>
      </div>

      <div v-if="canDraw" class="tools">
        <div class="swatches">
          <button
            v-for="swatch in COLORS"
            :key="swatch"
            type="button"
            class="swatch"
            :class="{ active: !erasing && color === swatch }"
            :style="{ background: swatch }"
            :aria-label="`Color ${swatch}`"
            @click="color = swatch; erasing = false"
          />
          <button type="button" class="swatch eraser" :class="{ active: erasing }" @click="erasing = true">
            Erase
          </button>
        </div>
        <div class="sizes">
          <button
            v-for="brush in SIZES"
            :key="brush"
            type="button"
            :class="{ active: size === brush }"
            @click="size = brush"
          >
            <i :style="{ width: `${Math.max(4, brush / 4)}px`, height: `${Math.max(4, brush / 4)}px` }" />
          </button>
        </div>
        <button type="button" class="btn-secondary" @click="undo">Undo</button>
        <button type="button" class="btn-secondary" @click="clearCanvas">Clear</button>
        <button type="button" class="btn-secondary" @click="endTurn">End turn</button>
      </div>
    </section>

    <aside class="chat">
      <div ref="chatRef" class="log">
        <p
          v-for="message in gameState.messages"
          :key="message.id"
          :class="message.kind"
        >
          {{ messageText(message.kind, message.nickname, message.text) }}
        </p>
      </div>
      <form v-if="phase === 'drawing'" class="guess" @submit.prevent="submitGuess">
        <input
          v-model="guess"
          :disabled="!canGuess"
          :placeholder="isDrawer ? 'You are drawing' : gameState.viewer_has_guessed ? 'You got it' : 'Type a guess'"
          maxlength="40"
          autocomplete="off"
        />
        <button type="submit" class="btn-primary" :disabled="!canGuess">Guess</button>
      </form>
    </aside>
  </div>
</template>

<style scoped>
.scribble {
  flex: 1;
  min-height: 0;
  display: grid;
  grid-template-columns: 200px minmax(0, 1fr) 280px;
  grid-template-rows: auto minmax(0, 1fr);
  gap: 0.75rem;
  padding: 0.75rem;
  color: var(--text);
}

.topbar {
  grid-column: 1 / -1;
  display: grid;
  grid-template-columns: minmax(140px, 1fr) minmax(0, 2fr) 88px;
  gap: 0.75rem;
  align-items: center;
}

.round {
  display: flex;
  flex-direction: column;
  gap: 0.15rem;
}

.round span,
.waiting {
  color: var(--text-muted);
  font-size: 0.82rem;
}

.round strong {
  font-size: 0.95rem;
}

.prompt {
  min-height: 52px;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 0.4rem 0.6rem;
  border-radius: 14px;
  background: rgba(246, 241, 231, 0.08);
  border: 1px solid var(--border);
}

.prompt.secret {
  background: rgba(225, 29, 72, 0.12);
  border-color: rgba(225, 29, 72, 0.35);
}

.secret-word {
  margin: 0;
  font-size: 1.35rem;
  letter-spacing: 0.04em;
  text-transform: lowercase;
}

.mask {
  display: flex;
  flex-wrap: wrap;
  gap: 0.35rem;
  justify-content: center;
}

.letter {
  min-width: 1.4rem;
  height: 1.8rem;
  display: grid;
  place-items: center;
  border-bottom: 2px solid var(--text);
  font-weight: 700;
}

.letter.blank {
  color: transparent;
}

.letter.gap {
  min-width: 0.8rem;
  border-bottom: none;
}

.timer {
  justify-self: end;
  font-variant-numeric: tabular-nums;
  font-size: 1.6rem;
  font-weight: 700;
}

.timer.low {
  color: #e11d48;
}

.scores,
.chat,
.stage {
  min-height: 0;
}

.scores,
.chat {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 0.8rem;
  display: flex;
  flex-direction: column;
  gap: 0.6rem;
}

.scores h2 {
  margin: 0;
  font-size: 0.82rem;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  color: var(--text-muted);
}

.scores ol {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 0.45rem;
  overflow: auto;
}

.scores li {
  display: flex;
  justify-content: space-between;
  gap: 0.5rem;
  align-items: center;
  padding: 0.4rem 0.45rem;
  border-radius: 10px;
}

.scores li.drawer {
  background: rgba(225, 29, 72, 0.12);
}

.scores li.me {
  outline: 1px solid rgba(91, 156, 255, 0.45);
}

.who {
  display: flex;
  flex-direction: column;
  min-width: 0;
}

.name {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.tag {
  font-size: 0.68rem;
  color: var(--text-muted);
}

.tag.ok {
  color: #3dd68c;
}

.stage {
  display: flex;
  flex-direction: column;
  gap: 0.55rem;
}

.canvas-frame {
  position: relative;
  flex: 1;
  min-height: 180px;
  border-radius: 16px;
  overflow: hidden;
  background: #f6f1e7;
  border: 1px solid rgba(28, 25, 23, 0.16);
}

.canvas-frame canvas {
  width: 100%;
  height: 100%;
  display: block;
  touch-action: none;
  cursor: default;
}

.canvas-frame.drawable canvas {
  cursor: crosshair;
}

.overlay {
  position: absolute;
  inset: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 0.6rem;
  padding: 1rem;
  background: rgba(10, 14, 23, 0.45);
  color: white;
  text-align: center;
}

.overlay.dim {
  background: rgba(246, 241, 231, 0.72);
  color: #1c1917;
}

.choices {
  background: rgba(10, 14, 23, 0.62);
}

.word-choice {
  min-width: min(280px, 90%);
  border: none;
  border-radius: 12px;
  background: #f6f1e7;
  color: #1c1917;
  padding: 0.7rem 0.9rem;
  display: flex;
  justify-content: space-between;
  gap: 1rem;
  align-items: center;
}

.word-choice small {
  color: #78716c;
}

.reveal-word {
  margin: 0;
  font-size: 2rem;
  text-transform: lowercase;
}

.reveal ul {
  list-style: none;
  margin: 0;
  padding: 0;
}

.tools {
  display: flex;
  flex-wrap: wrap;
  gap: 0.45rem;
  align-items: center;
}

.swatches,
.sizes {
  display: flex;
  gap: 0.35rem;
  align-items: center;
}

.swatch {
  width: 26px;
  height: 26px;
  border-radius: 50%;
  border: 2px solid transparent;
  padding: 0;
}

.swatch.active,
.sizes button.active {
  border-color: white;
  box-shadow: 0 0 0 2px #e11d48;
}

.eraser {
  width: auto;
  border-radius: 999px;
  padding: 0.2rem 0.55rem;
  background: #f6f1e7;
  color: #1c1917;
  font-size: 0.75rem;
}

.sizes button {
  width: 32px;
  height: 32px;
  border-radius: 10px;
  border: 1px solid var(--border);
  background: var(--surface);
  display: grid;
  place-items: center;
}

.sizes i {
  display: block;
  border-radius: 50%;
  background: var(--text);
}

.log {
  flex: 1;
  overflow: auto;
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
}

.log p {
  margin: 0;
  font-size: 0.9rem;
  line-height: 1.35;
}

.log .system {
  color: var(--text-muted);
}

.log .correct {
  color: #3dd68c;
}

.log .close {
  color: #f0a060;
}

.guess {
  display: flex;
  gap: 0.4rem;
}

.guess input {
  flex: 1;
  min-width: 0;
}

@media (max-width: 980px) {
  .scribble {
    grid-template-columns: 1fr;
    grid-template-rows: auto auto minmax(280px, 1fr) auto;
    overflow: auto;
  }

  .scores {
    order: 4;
    max-height: 180px;
  }

  .topbar {
    grid-template-columns: 1fr auto;
  }

  .prompt {
    grid-column: 1 / -1;
    order: 3;
  }
}
</style>
