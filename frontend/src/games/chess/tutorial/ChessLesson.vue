<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Chess, type Move, type PieceSymbol, type Square } from 'chess.js'
import { HEARTS, lessonById, lessons } from './course'
import OscarBubble from './OscarBubble.vue'
import TutorialBoard from './TutorialBoard.vue'
import { pieceSrc } from './pieces'
import {
  PIECE_VALUE,
  bestSafeMove,
  blackPieceCount,
  pickGreedyCapture,
  pickOscarMove,
  spawnTarget,
  whiteAttackersCount,
} from './oscarAi'
import { applyStars, isUnlocked, loadProgress, miniStars, saveProgress, skipMatch, starsForHearts } from './progress'
import { StockfishClient } from '../stockfish'
import { getDefaultBoardView, setDefaultBoardView, type BoardView } from '../prefs'

const boardView = ref<BoardView>(getDefaultBoardView() ?? '2d')
watch(boardView, setDefaultBoardView)

const boardStyles = [
  { id: '2d', label: '2D' },
  { id: 'clay', label: 'Iso' },
  { id: '3d', label: '3D' },
] as const satisfies ReadonlyArray<{ id: BoardView; label: string }>

const route = useRoute()
const router = useRouter()
const lesson = lessonById(String(route.params.lessonId))
const lessonIndex = lessons.findIndex((item) => item.id === lesson?.id)

const mood = ref<'idle' | 'happy' | 'sad' | 'think'>('idle')
const coach = ref('Loading the lesson.')
const status = ref<'play' | 'wait' | 'wrong' | 'explain' | 'hearts' | 'complete' | 'mini-over' | 'match-over'>('wait')
const fen = ref('rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1')
const selected = ref<string | null>(null)
const lastMove = ref<{ from: string; to: string } | null>(null)
const hint = ref<{ from: string; to: string } | null>(null)
const hintNote = ref('')
const shake = ref(false)
const wrongText = ref('')
const hearts = ref(HEARTS)
const drillIndex = ref(0)
const stepIndex = ref(0)
const explainFinal = ref(false)
const pending = ref<{ from: string; to: string } | null>(null)
const points = ref(0)
const remainingMs = ref(0)
const whiteMs = ref(0)
const blackMs = ref(0)
const resultStars = ref(0)
const xpGained = ref(0)
const resultLine = ref('')
const engineNote = ref('')
const resignArmed = ref(false)
const locked = ref(false)

let board = new Chess()
let epoch = 0
let ended = false
let engine: StockfishClient | null = null
const timers: number[] = []

const usesHearts = computed(
  () => lesson?.kind === 'theory' || lesson?.kind === 'puzzle' || lesson?.kind === 'review',
)
const nextLesson = computed(() => (lessonIndex >= 0 ? lessons[lessonIndex + 1] : undefined))

const targets = computed(() => {
  fen.value
  if (status.value !== 'play' || !selected.value) return []
  const moves = board.moves({ square: selected.value as Square, verbose: true })
  return [...new Set(moves.map((move) => move.to))]
})

const checkSquare = computed(() => {
  fen.value
  if (!board.isCheck()) return null
  return board.findPiece({ type: 'k', color: board.turn() })[0] ?? null
})

const boardDisabled = computed(() => locked.value || status.value !== 'play')

function sync() {
  fen.value = board.fen()
}

function later(ms: number, fn: () => void) {
  const token = epoch
  window.setTimeout(() => {
    if (token !== epoch) return
    fn()
  }, ms)
}

function every(ms: number, fn: () => void) {
  const id = window.setInterval(fn, ms)
  timers.push(id)
}

function stopTimers() {
  epoch += 1
  for (const id of timers) window.clearInterval(id)
  timers.length = 0
}

function clockLabel(ms: number) {
  const total = Math.max(0, Math.ceil(ms / 1000))
  return `${Math.floor(total / 60)}:${String(total % 60).padStart(2, '0')}`
}

function uciParts(uci: string) {
  return {
    from: uci.slice(0, 2) as Square,
    to: uci.slice(2, 4) as Square,
    promotion: (uci.length > 4 ? uci[4] : undefined) as PieceSymbol | undefined,
  }
}

function currentStep() {
  return lesson?.drills[drillIndex.value]?.steps[stepIndex.value]
}

function shakeBoard() {
  shake.value = true
  later(420, () => {
    shake.value = false
  })
}

function reject(message: string, penalize: boolean) {
  wrongText.value = message
  coach.value = 'Not quite.'
  mood.value = 'sad'
  selected.value = null
  pending.value = null
  shakeBoard()
  if (penalize) {
    hearts.value -= 1
    status.value = hearts.value <= 0 ? 'hearts' : 'wrong'
    return
  }
  status.value = 'wrong'
}

function resume() {
  if (!lesson) return
  const step = currentStep()
  coach.value = step?.prompt ?? coach.value
  mood.value = 'idle'
  status.value = 'play'
}

function loadDrill() {
  if (!lesson) return
  const drill = lesson.drills[drillIndex.value]
  board = new Chess(drill.fen)
  stepIndex.value = 0
  selected.value = null
  pending.value = null
  lastMove.value = null
  hint.value = null
  hintNote.value = ''
  explainFinal.value = false
  sync()
  coach.value = drill.steps[0].prompt
  mood.value = 'idle'
  status.value = 'play'
}

function finishScored(stars: number, line = 'Lesson complete.') {
  if (!lesson) return
  stopTimers()
  resultStars.value = stars
  resultLine.value = line
  const applied = applyStars(loadProgress(), lesson.id, stars)
  xpGained.value = applied.gained * 10
  saveProgress(applied.progress)
  status.value = 'complete'
  mood.value = 'happy'
  coach.value = line
}

function advance() {
  if (!lesson) return
  const drill = lesson.drills[drillIndex.value]
  if (stepIndex.value + 1 < drill.steps.length) {
    stepIndex.value += 1
    coach.value = drill.steps[stepIndex.value].prompt
    mood.value = 'idle'
    status.value = 'play'
    return
  }
  const more = drillIndex.value + 1 < lesson.drills.length
  if (drill.explain) {
    explainFinal.value = !more
    coach.value = drill.explain
    mood.value = 'happy'
    status.value = 'explain'
    return
  }
  if (more) {
    drillIndex.value += 1
    loadDrill()
    return
  }
  finishScored(starsForHearts(hearts.value, HEARTS))
}

function continueExplain() {
  if (!lesson) return
  if (explainFinal.value) {
    finishScored(starsForHearts(hearts.value, HEARTS), 'Lesson complete.')
    return
  }
  drillIndex.value += 1
  loadDrill()
}

function isMate(uci: string) {
  const next = new Chess(board.fen())
  const parts = uciParts(uci)
  next.move(parts)
  return next.isCheckmate()
}

function afterCorrect(stepSuccess?: string, reply?: string) {
  mood.value = 'happy'
  if (reply) {
    status.value = 'wait'
    coach.value = stepSuccess ?? 'Watch the reply.'
    later(560, () => {
      const replyMove = board.moves({ verbose: true }).find((move) => move.lan === reply)
      if (!replyMove) return
      board.move({ from: replyMove.from, to: replyMove.to, promotion: replyMove.promotion })
      lastMove.value = { from: replyMove.from, to: replyMove.to }
      sync()
      advance()
    })
    return
  }
  if (stepSuccess && lesson && stepIndex.value + 1 < lesson.drills[drillIndex.value].steps.length) {
    status.value = 'wait'
    coach.value = stepSuccess
    later(700, advance)
    return
  }
  advance()
}

function playDrill(move: Move) {
  const step = currentStep()
  if (!step) return
  const correct = step.accept.includes(move.lan) || Boolean(step.anyMate && isMate(move.lan))
  if (!correct) {
    reject(step.wrong ?? 'That is legal, but it is not the move this lesson wants.', true)
    return
  }
  board.move({ from: move.from, to: move.to, promotion: move.promotion })
  lastMove.value = { from: move.from, to: move.to }
  sync()
  afterCorrect(step.success, step.reply)
}

function endMini(line: string) {
  if (ended || !lesson) return
  ended = true
  stopTimers()
  const stars = miniStars(points.value)
  resultStars.value = stars
  resultLine.value = line
  if (stars > 0) {
    const applied = applyStars(loadProgress(), lesson.id, stars)
    xpGained.value = applied.gained * 10
    saveProgress(applied.progress)
  } else {
    xpGained.value = 0
  }
  status.value = 'mini-over'
  mood.value = stars > 0 ? 'happy' : 'sad'
  coach.value = line
}

function topUp() {
  if (blackPieceCount(board) < 5) spawnTarget(board)
}

function playMini(move: Move) {
  if (move.piece === 'k' && board.moves({ verbose: true }).some((candidate) => candidate.piece !== 'k')) {
    reject('The king sits this drill out.', false)
    return
  }
  board.move({ from: move.from, to: move.to, promotion: move.promotion })
  lastMove.value = { from: move.from, to: move.to }
  points.value += capturePoints(move)
  sync()
  if (board.isCheckmate()) {
    points.value += 9
    board = new Chess(lesson!.mini!.fen)
    sync()
    coach.value = 'Checkmate. A fresh set of pieces.'
    mood.value = 'happy'
    return
  }
  if (board.isGameOver()) {
    board = new Chess(lesson!.mini!.fen)
    sync()
    return
  }
  topUp()
  sync()
  status.value = 'wait'
  mood.value = 'think'
  later(420, () => {
    const lan = pickGreedyCapture(board)
    if (lan) {
      const reply = board.moves({ verbose: true }).find((candidate) => candidate.lan === lan)
      if (reply) {
        board.move({ from: reply.from, to: reply.to, promotion: reply.promotion })
        lastMove.value = { from: reply.from, to: reply.to }
      }
    }
    sync()
    if (board.isCheckmate() || whiteAttackersCount(board) === 0) {
      endMini('Your pieces are gone. That is the score.')
      return
    }
    if (board.isGameOver()) {
      board = new Chess(lesson!.mini!.fen)
      sync()
    }
    status.value = 'play'
    mood.value = 'idle'
  })
}

function finishMatch(outcome: 'win' | 'draw' | 'loss', line: string) {
  if (ended || !lesson) return
  ended = true
  stopTimers()
  const stars = outcome === 'win' ? 3 : outcome === 'draw' ? 1 : 0
  resultStars.value = stars
  resultLine.value = line
  if (stars > 0) {
    const applied = applyStars(loadProgress(), lesson.id, stars)
    xpGained.value = applied.gained * 10
    saveProgress(applied.progress)
  } else {
    xpGained.value = 0
  }
  status.value = 'match-over'
  mood.value = outcome === 'loss' ? 'sad' : 'happy'
  coach.value = line
}

function matchResultLine(): string | null {
  if (board.isCheckmate()) {
    return board.turn() === 'b' ? 'Checkmate. That is the point of the game.' : 'Oscar found a mate. Look at the last move, then try again.'
  }
  if (board.isStalemate()) {
    return 'Stalemate. The king is not in check, so this is a draw. Keep a check in the mating net next time.'
  }
  if (board.isDraw()) return 'This one is a draw.'
  return null
}

function playMatch(move: Move) {
  board.move({ from: move.from, to: move.to, promotion: move.promotion })
  lastMove.value = { from: move.from, to: move.to }
  sync()
  const done = matchResultLine()
  if (done) {
    const outcome = board.isCheckmate() ? (board.turn() === 'b' ? 'win' : 'loss') : 'draw'
    finishMatch(outcome, done)
    return
  }
  status.value = 'wait'
  mood.value = 'think'
  coach.value = 'Oscar is thinking.'
  later(480, () => {
    const lan = pickOscarMove(board, lesson!.match!.oscar)
    if (lan) {
      const reply = board.moves({ verbose: true }).find((candidate) => candidate.lan === lan)
      if (reply) {
        board.move({ from: reply.from, to: reply.to, promotion: reply.promotion })
        lastMove.value = { from: reply.from, to: reply.to }
        sync()
      }
    }
    const after = matchResultLine()
    if (after) {
      const outcome = board.isCheckmate() ? 'loss' : 'draw'
      finishMatch(outcome, after)
      return
    }
    status.value = 'play'
    mood.value = 'idle'
    coach.value = 'Your move.'
  })
}

function capturePoints(move: Move) {
  let scored = 0
  if (move.isCapture() && move.captured) scored += PIECE_VALUE[move.captured]
  if (move.promotion === 'n' || move.promotion === 'b') scored += 2
  if (move.promotion === 'r') scored += 4
  if (move.promotion === 'q') scored += 8
  return scored
}

function commit(move: Move) {
  selected.value = null
  pending.value = null
  hint.value = null
  hintNote.value = ''
  resignArmed.value = false
  if (!lesson) return
  if (lesson.kind === 'mini') playMini(move)
  else if (lesson.kind === 'match') playMatch(move)
  else playDrill(move)
}

function onSquare(square: string) {
  if (status.value !== 'play') return
  if (selected.value && targets.value.includes(square as Square)) {
    const options = board
      .moves({ square: selected.value as Square, verbose: true })
      .filter((move) => move.to === square)
    if (options.length === 0) {
      selected.value = null
      return
    }
    const promotions = [...new Set(options.map((move) => move.promotion).filter(Boolean))]
    if (promotions.length > 1) {
      pending.value = { from: selected.value, to: square }
      return
    }
    commit(options[0])
    return
  }
  const piece = board.get(square as Square)
  if (piece && piece.color === 'w' && board.turn() === 'w') {
    selected.value = square
    return
  }
  selected.value = null
}

function choosePromotion(type: string) {
  if (!pending.value) return
  const move = board
    .moves({ square: pending.value.from as Square, verbose: true })
    .find((candidate) => candidate.to === pending.value?.to && candidate.promotion === type)
  if (move) commit(move)
}

function showLessonHint() {
  const step = currentStep()
  if (!step) return
  const parts = uciParts(step.accept[0])
  hint.value = { from: parts.from, to: parts.to }
  hintNote.value = 'The glowing squares are the move this lesson wants.'
  mood.value = 'think'
}

async function showEngineHint() {
  const safe = bestSafeMove(board)
  if (safe) {
    const parts = uciParts(safe)
    hint.value = { from: parts.from, to: parts.to }
  }
  engineNote.value = 'Asking the engine.'
  if (!engine) engine = new StockfishClient()
  try {
    if (!engine.flavor) await engine.init({ lite: true })
    engine.onSuggestion = (suggestion) => {
      if (!suggestion.final || suggestion.fen !== board.fen()) return
      hint.value = { from: suggestion.from, to: suggestion.to }
      engineNote.value = 'Engine hint. Oscar the opponent will not play this well.'
      mood.value = 'think'
    }
    engine.analyze(board.fen(), { movetimeMs: 700 })
  } catch {
    engineNote.value = safe
      ? 'The engine did not start. This highlight is a sound material move.'
      : 'The engine did not start.'
  }
}

function resign() {
  if (!resignArmed.value) {
    resignArmed.value = true
    return
  }
  finishMatch('loss', 'You resigned. Oscar takes the point.')
}

function skipThisMatch() {
  if (!lesson) return
  saveProgress(skipMatch(loadProgress(), lesson.id))
  router.push('/chess/learn')
}

function startMini() {
  if (!lesson?.mini) return
  ended = false
  points.value = 0
  board = new Chess(lesson.mini.fen)
  sync()
  remainingMs.value = lesson.mini.seconds * 1000
  const endsAt = Date.now() + remainingMs.value
  status.value = 'play'
  mood.value = 'idle'
  coach.value =
    'Capture what you can before the clock ends. Black grabs your best piece even if you protect it. Five points is a star, twenty is two, forty is three.'
  every(200, () => {
    remainingMs.value = Math.max(0, endsAt - Date.now())
    if (remainingMs.value === 0) endMini('Time. Here is the score.')
  })
  every(4000, () => {
    if (status.value !== 'play' || board.turn() !== 'w') return
    if (blackPieceCount(board) >= 4) return
    spawnTarget(board)
    sync()
  })
}

function startMatch() {
  if (!lesson?.match) return
  ended = false
  board = new Chess()
  sync()
  const ms = lesson.match.minutes * 60 * 1000
  whiteMs.value = ms
  blackMs.value = ms
  let anchor = Date.now()
  status.value = 'play'
  mood.value = 'idle'
  coach.value =
    lesson.match.oscar === 'gentle'
      ? 'Oscar goes easy. He takes free pieces and misses a lot. Checkmate wins. You can skip this match from the path.'
      : 'Oscar is sharper this time, and he still slips. Checkmate wins.'
  every(200, () => {
    const now = Date.now()
    const delta = now - anchor
    anchor = now
    if (status.value !== 'play' && status.value !== 'wait') return
    if (board.turn() === 'w') whiteMs.value -= delta
    else blackMs.value -= delta
    if (whiteMs.value <= 0) finishMatch('loss', 'Time. Oscar wins this one.')
    else if (blackMs.value <= 0) finishMatch('win', 'Oscar ran out of time.')
  })
}

function begin() {
  if (!lesson) return
  stopTimers()
  ended = false
  hearts.value = HEARTS
  drillIndex.value = 0
  stepIndex.value = 0
  points.value = 0
  hint.value = null
  hintNote.value = ''
  engineNote.value = ''
  resignArmed.value = false
  selected.value = null
  pending.value = null
  lastMove.value = null
  if (locked.value) {
    coach.value = 'Finish the previous lesson first.'
    mood.value = 'idle'
    status.value = 'wait'
    return
  }
  if (lesson.kind === 'mini') startMini()
  else if (lesson.kind === 'match') startMatch()
  else loadDrill()
}

function retry() {
  begin()
}

onMounted(() => {
  if (!lesson) {
    router.replace('/chess/learn')
    return
  }
  locked.value = !isUnlocked(loadProgress(), lessonIndex)
  begin()
})

onUnmounted(() => {
  stopTimers()
  engine?.dispose()
  engine = null
})
</script>

<template>
  <div v-if="lesson" class="lesson">
    <header class="top">
      <button type="button" class="btn-secondary back" @click="router.push('/chess/learn')">Path</button>
      <div class="title-block">
        <p class="kicker">{{ lesson.kind }}</p>
        <h1>{{ lesson.title }}</h1>
      </div>
      <div v-if="usesHearts" class="hearts" aria-label="Hearts">
        <span v-for="n in HEARTS" :key="n" :class="{ spent: n > hearts }">♥</span>
      </div>
      <div v-else-if="lesson.kind === 'mini'" class="hud">
        <strong>{{ points }} pts</strong>
        <span>{{ clockLabel(remainingMs) }}</span>
      </div>
      <div v-else-if="lesson.kind === 'match'" class="hud">
        <span>You {{ clockLabel(whiteMs) }}</span>
        <span>Oscar {{ clockLabel(blackMs) }}</span>
      </div>
    </header>

    <div v-if="usesHearts && lesson.drills.length > 1" class="pips" aria-hidden="true">
      <span
        v-for="(_, index) in lesson.drills"
        :key="index"
        :class="{ done: index < drillIndex, now: index === drillIndex }"
      />
    </div>

    <OscarBubble :mood="mood" :text="coach" />

    <TutorialBoard
      v-model:view="boardView"
      :fen="fen"
      :selected="selected"
      :targets="targets"
      :last-move="lastMove"
      :hint="hint"
      :check-square="checkSquare"
      :disabled="boardDisabled"
      :shake="shake"
      @square="onSquare"
    />

    <p v-if="hintNote" class="note">{{ hintNote }}</p>
    <p v-if="engineNote" class="note">{{ engineNote }}</p>

    <div v-if="status === 'play' && !locked" class="actions">
      <button v-if="usesHearts" type="button" class="btn-secondary" @click="showLessonHint">Hint</button>
      <button v-if="lesson.kind === 'match'" type="button" class="btn-secondary" @click="showEngineHint">
        Engine hint
      </button>
      <button v-if="lesson.kind === 'match'" type="button" class="btn-secondary" @click="resign">
        {{ resignArmed ? 'Confirm resign' : 'Resign' }}
      </button>
      <button v-if="lesson.kind === 'match'" type="button" class="btn-secondary" @click="skipThisMatch">
        Skip match
      </button>
    </div>

    <div class="view-switch" role="radiogroup" aria-label="Board style">
      <span class="view-switch-label">Board</span>
      <button
        v-for="option in boardStyles"
        :key="option.id"
        type="button"
        class="view-option"
        :class="{ active: boardView === option.id }"
        role="radio"
        :aria-checked="boardView === option.id"
        @click="boardView = option.id"
      >
        {{ option.label }}
      </button>
    </div>

    <div v-if="pending" class="promo">
      <p>Promote to</p>
      <div class="promo-row">
        <button
          v-for="type in ['q', 'r', 'b', 'n']"
          :key="type"
          type="button"
          @click="choosePromotion(type)"
        >
          <img :src="pieceSrc('w', type)" alt="" />
        </button>
      </div>
    </div>

    <aside v-if="status === 'wrong'" class="sheet bad">
      <h2>Try again</h2>
      <p>{{ wrongText }}</p>
      <button type="button" class="btn-primary" @click="resume">Continue</button>
    </aside>
    <aside v-else-if="status === 'hearts'" class="sheet bad">
      <h2>Out of hearts</h2>
      <p>Oscar resets the lesson. Nothing is saved until you finish with a heart left.</p>
      <button type="button" class="btn-primary" @click="retry">Try the lesson again</button>
    </aside>
    <aside v-else-if="status === 'explain'" class="sheet good">
      <h2>Nice</h2>
      <p>{{ coach }}</p>
      <button type="button" class="btn-primary" @click="continueExplain">Continue</button>
    </aside>
    <aside v-else-if="status === 'complete'" class="sheet good">
      <h2>Lesson complete</h2>
      <p class="stars" aria-label="Stars">
        <span v-for="n in 3" :key="n" :class="{ on: n <= resultStars }">★</span>
      </p>
      <p>{{ xpGained > 0 ? `+${xpGained} XP` : 'Best score kept.' }}</p>
      <div class="sheet-actions">
        <button type="button" class="btn-secondary" @click="router.push('/chess/learn')">Path</button>
        <button
          v-if="nextLesson && resultStars > 0"
          type="button"
          class="btn-primary"
          @click="router.push(`/chess/learn/${nextLesson.id}`)"
        >
          Next
        </button>
      </div>
    </aside>
    <aside v-else-if="status === 'mini-over'" class="sheet" :class="resultStars > 0 ? 'good' : 'bad'">
      <h2>{{ resultStars > 0 ? 'Drill complete' : 'Need five points' }}</h2>
      <p>{{ points }} points</p>
      <p class="stars" aria-label="Stars">
        <span v-for="n in 3" :key="n" :class="{ on: n <= resultStars }">★</span>
      </p>
      <p>{{ resultLine }}</p>
      <div class="sheet-actions">
        <button type="button" class="btn-secondary" @click="router.push('/chess/learn')">Path</button>
        <button v-if="resultStars === 0" type="button" class="btn-primary" @click="retry">Try again</button>
        <button
          v-else-if="nextLesson"
          type="button"
          class="btn-primary"
          @click="router.push(`/chess/learn/${nextLesson.id}`)"
        >
          Next
        </button>
      </div>
    </aside>
    <aside v-else-if="status === 'match-over'" class="sheet" :class="resultStars > 0 ? 'good' : 'bad'">
      <h2>{{ resultStars === 3 ? 'You won' : resultStars === 1 ? 'Draw' : 'Oscar won' }}</h2>
      <p>{{ resultLine }}</p>
      <p v-if="xpGained > 0">+{{ xpGained }} XP</p>
      <div class="sheet-actions">
        <button type="button" class="btn-secondary" @click="router.push('/chess/learn')">Path</button>
        <button type="button" class="btn-secondary" @click="retry">Rematch</button>
        <button
          v-if="nextLesson && resultStars > 0"
          type="button"
          class="btn-primary"
          @click="router.push(`/chess/learn/${nextLesson.id}`)"
        >
          Next
        </button>
      </div>
    </aside>
    <aside v-else-if="locked" class="sheet bad">
      <h2>Locked</h2>
      <p>Finish the previous lesson to open this one. Matches can be skipped.</p>
      <button type="button" class="btn-primary" @click="router.push('/chess/learn')">Back to the path</button>
    </aside>
  </div>
</template>

<style scoped>
.lesson {
  width: 100%;
  height: 100dvh;
  margin: 0 auto;
  padding: 0.75rem 1.25rem 0.85rem;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 0.65rem;
  overflow: hidden;
}

.top,
.pips,
.note,
.actions,
.view-switch,
.promo {
  width: min(100%, 720px);
  flex-shrink: 0;
}

.lesson :deep(.oscar) {
  width: min(100%, 720px);
  flex-shrink: 0;
}

.top {
  display: flex;
  align-items: center;
  gap: 0.75rem;
}

.title-block {
  flex: 1;
  min-width: 0;
}

.title-block h1 {
  font-size: 1.25rem;
  line-height: 1.2;
}

.kicker {
  margin: 0;
  color: var(--text-muted);
  font-size: 0.72rem;
  letter-spacing: 0.06em;
  text-transform: uppercase;
}

.back {
  padding: 0.45rem 0.7rem;
}

.hearts {
  color: #ff5c6c;
  letter-spacing: 0.12em;
  font-size: 1.05rem;
}

.hearts .spent {
  opacity: 0.28;
}

.hud {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  font-variant-numeric: tabular-nums;
  color: var(--text-muted);
  font-size: 0.92rem;
}

.hud strong {
  color: var(--text);
}

.pips {
  display: flex;
  gap: 0.35rem;
}

.pips span {
  width: 0.7rem;
  height: 0.7rem;
  border-radius: 50%;
  background: rgba(255, 255, 255, 0.16);
}

.pips .done,
.pips .now {
  background: var(--success);
}

.note {
  margin: 0;
  text-align: center;
  color: var(--text-muted);
  font-size: 0.92rem;
}

.actions {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
  justify-content: center;
}

.view-switch {
  display: flex;
  align-items: center;
  align-self: center;
  gap: 0.3rem;
  padding: 0.3rem 0.3rem 0.3rem 0.6rem;
  border-radius: 10px;
  border: 1px solid var(--border);
  background: rgba(10, 14, 23, 0.35);
}

.view-switch-label {
  font-size: 0.82rem;
  font-weight: 600;
  margin-right: 0.15rem;
}

.view-option {
  min-width: 2.6rem;
  padding: 0.3rem 0.55rem;
  border-radius: 7px;
  border: 1px solid transparent;
  background: transparent;
  color: var(--text-muted);
  font-size: 0.78rem;
  font-weight: 700;
  cursor: pointer;
}

.view-option.active {
  background: rgba(201, 154, 98, 0.2);
  border-color: rgba(201, 154, 98, 0.45);
  color: #c99a62;
}

.promo {
  text-align: center;
}

.promo-row {
  display: flex;
  justify-content: center;
  gap: 0.5rem;
  margin-top: 0.4rem;
}

.promo-row button {
  width: 3.2rem;
  height: 3.2rem;
  background: var(--surface);
  border: 1px solid var(--border);
}

.promo-row img {
  width: 100%;
  height: 100%;
  object-fit: contain;
}

.sheet {
  position: fixed;
  left: 50%;
  bottom: 0;
  transform: translateX(-50%);
  width: min(720px, 100%);
  padding: 1.1rem 1.1rem 1.3rem;
  border-radius: 18px 18px 0 0;
  background: var(--surface);
  border: 1px solid var(--border);
  box-shadow: 0 -12px 40px rgba(0, 0, 0, 0.35);
  animation: rise 0.35s var(--ease-bounce);
  z-index: 5;
}

.sheet.bad {
  background: #3a1820;
  border-color: rgba(255, 92, 108, 0.45);
}

.sheet.good {
  background: #143228;
  border-color: rgba(61, 214, 140, 0.4);
}

.sheet h2 {
  margin-bottom: 0.35rem;
}

.sheet p {
  margin: 0.25rem 0 0.75rem;
}

.sheet-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
}

.stars {
  font-size: 1.4rem;
  letter-spacing: 0.15em;
  color: rgba(255, 255, 255, 0.28);
}

.stars .on {
  color: #f0c14d;
}

@keyframes rise {
  from {
    transform: translate(-50%, 24px);
    opacity: 0;
  }
  to {
    transform: translate(-50%, 0);
    opacity: 1;
  }
}
</style>
