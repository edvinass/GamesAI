<script setup lang="ts">
import { computed, ref, watch, onMounted, onUnmounted } from 'vue'
import type { Room, SpyfallGameState } from '@/types'

const props = defineProps<{
  gameState: SpyfallGameState
  room: Room
  playerId: string
}>()

const emit = defineEmits<{
  action: [data: Record<string, unknown>]
}>()

const questionText = ref('')
const answerText = ref('')
const selectedTarget = ref('')
const selectedLocation = ref('')
const logRef = ref<HTMLElement | null>(null)
const timeRemaining = ref('')

const me = computed(() => props.room.players.find((p) => p.id === props.playerId))

const isGameOver = computed(() => props.gameState.phase === 'finished' || Boolean(props.gameState.winner))

const currentActor = computed(() => {
  const pending = props.gameState.pending_question
  if (pending) {
    return props.room.players.find((p) => p.id === pending.to_id)
  }
  if (props.gameState.phase === 'questioning') {
    return props.room.players.find((p) => p.id === props.gameState.current_turn_player_id)
  }
  if (props.gameState.phase === 'voting') {
    return props.room.players.find((p) => !props.gameState.votes[p.id])
  }
  return undefined
})

const isAiTurn = computed(() => !isGameOver.value && Boolean(currentActor.value?.is_ai))

const isMyTurnToAsk = computed(() => {
  if (!me.value || props.gameState.phase !== 'questioning') return false
  if (props.gameState.pending_question) return false
  return props.gameState.current_turn_player_id === props.playerId
})

const isMyTurnToAnswer = computed(() => {
  if (!me.value || !props.gameState.pending_question) return false
  return props.gameState.pending_question.to_id === props.playerId
})

const hasVoted = computed(() => {
  if (!me.value) return false
  return props.playerId in props.gameState.votes
})

const otherPlayers = computed(() =>
  props.room.players.filter((p) => p.id !== props.playerId),
)

const statusMessage = computed(() => {
  if (isGameOver.value) return 'Game over'
  if (props.gameState.phase === 'voting') {
    if (isAiTurn.value) return 'AI is voting…'
    if (!hasVoted.value) return 'Cast your vote'
    return `Waiting for votes (${props.gameState.votes_cast_count}/${props.gameState.votes_total})`
  }
  if (props.gameState.pending_question) {
    const pending = props.gameState.pending_question
    const asker = props.room.players.find((p) => p.id === pending.from_id)
    if (isAiTurn.value) return `${asker?.nickname ?? 'Someone'} is waiting for an answer…`
    if (isMyTurnToAnswer.value) return 'Answer the question'
    return `${asker?.nickname ?? 'Someone'} asked a question`
  }
  if (isAiTurn.value) return 'AI is thinking…'
  if (isMyTurnToAsk.value) return 'Your turn — ask a question'
  const actor = currentActor.value
  return actor ? `Waiting for ${actor.nickname}` : 'Waiting…'
})

const winMessage = computed(() => {
  const reason = props.gameState.win_reason
  const winner = props.gameState.winner
  if (reason === 'location_guessed') return 'The Spy guessed the location!'
  if (reason === 'wrong_location_guess') return 'The Spy guessed wrong!'
  if (reason === 'spy_voted_out') return 'The Spy was voted out!'
  if (reason === 'vote_failed') return 'Wrong vote — the Spy escapes!'
  if (reason === 'timer_expired') return 'Time ran out!'
  return winner === 'spy' ? 'Spy wins!' : 'Residents win!'
})

function askQuestion() {
  if (!selectedTarget.value || !questionText.value.trim()) return
  emit('action', {
    type: 'ask_question',
    target_player_id: selectedTarget.value,
    question: questionText.value.trim(),
  })
  questionText.value = ''
  selectedTarget.value = ''
}

function answerQuestion() {
  if (!answerText.value.trim()) return
  emit('action', {
    type: 'answer_question',
    answer: answerText.value.trim(),
  })
  answerText.value = ''
}

function callAccusation(targetId: string) {
  emit('action', { type: 'call_accusation', accused_player_id: targetId })
}

function castVote(targetId: string | null) {
  emit('action', { type: 'cast_vote', vote_for_player_id: targetId })
}

function guessLocation() {
  if (!selectedLocation.value) return
  emit('action', { type: 'spy_guess_location', location_name: selectedLocation.value })
  selectedLocation.value = ''
}

function playerLabel(id: string) {
  return props.room.players.find((p) => p.id === id)?.nickname ?? '?'
}

function updateTimer() {
  const ends = props.gameState.timer_ends_at
  if (!ends || isGameOver.value) {
    timeRemaining.value = ''
    return
  }
  const diff = new Date(ends).getTime() - Date.now()
  if (diff <= 0) {
    timeRemaining.value = '0:00'
    return
  }
  const mins = Math.floor(diff / 60000)
  const secs = Math.floor((diff % 60000) / 1000)
  timeRemaining.value = `${mins}:${secs.toString().padStart(2, '0')}`
}

let timerInterval: ReturnType<typeof setInterval> | null = null

onMounted(() => {
  updateTimer()
  timerInterval = setInterval(updateTimer, 1000)
})

onUnmounted(() => {
  if (timerInterval) clearInterval(timerInterval)
})

watch(
  () => props.gameState.question_log.length,
  () => {
    if (logRef.value) {
      logRef.value.scrollTop = logRef.value.scrollHeight
    }
  },
)
</script>

<template>
  <div class="spyfall-board container-wide">
    <div v-if="isGameOver" class="game-over card">
      <div class="winner-badge" :class="gameState.winner">
        {{ gameState.winner === 'spy' ? '🕵️ Spy wins!' : '🏠 Residents win!' }}
      </div>
      <p class="win-reason">{{ winMessage }}</p>
      <div class="reveal-block">
        <p><strong>Location:</strong> {{ gameState.revealed_location }}</p>
        <p>
          <strong>Spy:</strong>
          {{ playerLabel(gameState.revealed_spy_id ?? '') }}
        </p>
        <ul v-if="gameState.revealed_assignments" class="role-list">
          <li v-for="(info, pid) in gameState.revealed_assignments" :key="pid">
            {{ playerLabel(pid) }} —
            {{ info.is_spy ? 'Spy' : info.role }}
          </li>
        </ul>
      </div>
    </div>

    <template v-else>
      <div class="top-row">
        <div class="secret-card card">
          <h3>Your secret</h3>
          <template v-if="gameState.is_spy">
            <p class="spy-label">You are the <strong>Spy</strong></p>
            <p class="muted">Guess the location from the list below.</p>
            <div v-if="gameState.location_names" class="location-list">
              <span v-for="loc in gameState.location_names" :key="loc" class="loc-chip">{{ loc }}</span>
            </div>
          </template>
          <template v-else>
            <p class="location-name">{{ gameState.viewer_location }}</p>
            <p class="role-name">Role: <strong>{{ gameState.viewer_role }}</strong></p>
          </template>
        </div>

        <div class="status-card card">
          <div class="status-bar">
            <span class="phase-tag">{{ gameState.phase }}</span>
            <span v-if="timeRemaining" class="timer">⏱ {{ timeRemaining }}</span>
          </div>
          <p class="status-text" :class="{ 'ai-thinking': isAiTurn }">
            <span v-if="isAiTurn" class="ai-icon">🤖</span>
            {{ statusMessage }}
          </p>
          <div v-if="gameState.pending_question" class="pending-q card-inner">
            <p class="q-label">Pending question</p>
            <p>
              <strong>{{ playerLabel(gameState.pending_question.from_id) }}</strong>
              asked
              <strong>{{ playerLabel(gameState.pending_question.to_id) }}</strong>:
            </p>
            <p class="question-text">"{{ gameState.pending_question.question }}"</p>
          </div>
        </div>
      </div>

      <div class="player-strip card">
        <div
          v-for="player in room.players"
          :key="player.id"
          class="player-chip"
          :class="{
            active: currentActor?.id === player.id,
            self: player.id === playerId,
            voted: gameState.phase === 'voting' && player.id in gameState.votes,
          }"
        >
          <span class="nickname">{{ player.nickname }}</span>
          <span v-if="player.is_ai" class="ai-badge">AI</span>
          <span v-if="player.id === gameState.current_turn_player_id && gameState.phase === 'questioning' && !gameState.pending_question" class="turn-badge">Ask</span>
        </div>
      </div>

      <div ref="logRef" class="question-log card">
        <h3>Conversation</h3>
        <p v-if="!gameState.question_log.length" class="muted empty-log">No questions yet — start probing!</p>
        <div v-for="(entry, i) in gameState.question_log" :key="i" class="log-entry">
          <p class="log-q">
            <strong>{{ entry.from_nickname }}</strong> → {{ entry.to_nickname }}:
            "{{ entry.question }}"
          </p>
          <p class="log-a">"{{ entry.answer }}"</p>
        </div>
      </div>

      <div class="action-panel card">
        <template v-if="gameState.phase === 'questioning'">
          <div v-if="isMyTurnToAnswer" class="action-block">
            <h4>Your answer</h4>
            <textarea v-model="answerText" rows="2" placeholder="Answer in character…" maxlength="200" />
            <button class="btn-primary" :disabled="!answerText.trim()" @click="answerQuestion">Submit answer</button>
          </div>

          <div v-else-if="isMyTurnToAsk" class="action-block">
            <h4>Ask a question</h4>
            <select v-model="selectedTarget">
              <option value="" disabled>Select player</option>
              <option v-for="p in otherPlayers" :key="p.id" :value="p.id">{{ p.nickname }}</option>
            </select>
            <textarea v-model="questionText" rows="2" placeholder="Your question…" maxlength="120" />
            <button class="btn-primary" :disabled="!selectedTarget || !questionText.trim()" @click="askQuestion">
              Ask
            </button>
          </div>

          <div v-if="gameState.is_spy" class="action-block spy-guess">
            <h4>Guess location</h4>
            <select v-model="selectedLocation">
              <option value="" disabled>Select location</option>
              <option v-for="loc in gameState.location_names ?? []" :key="loc" :value="loc">{{ loc }}</option>
            </select>
            <button class="btn-secondary" :disabled="!selectedLocation" @click="guessLocation">Guess location</button>
          </div>

          <div v-if="!isMyTurnToAsk && !isMyTurnToAnswer" class="action-block accuse-block">
            <h4>Call accusation</h4>
            <div class="accuse-buttons">
              <button
                v-for="p in otherPlayers"
                :key="p.id"
                class="btn-secondary accuse-btn"
                @click="callAccusation(p.id)"
              >
                Accuse {{ p.nickname }}
              </button>
            </div>
          </div>
        </template>

        <template v-if="gameState.phase === 'voting'">
          <div v-if="!hasVoted" class="action-block">
            <h4>Vote for the Spy</h4>
            <div class="vote-buttons">
              <button
                v-for="p in room.players"
                :key="p.id"
                class="btn-secondary vote-btn"
                :disabled="p.id === playerId"
                @click="castVote(p.id)"
              >
                {{ p.nickname }}
              </button>
              <button class="btn-secondary vote-btn abstain" @click="castVote(null)">Abstain</button>
            </div>
          </div>
          <p v-else class="muted">Vote cast — waiting for others ({{ gameState.votes_cast_count }}/{{ gameState.votes_total }})</p>
        </template>
      </div>
    </template>
  </div>
</template>

<style scoped>
.spyfall-board {
  display: flex;
  flex-direction: column;
  gap: 1rem;
  padding-bottom: 2rem;
}

.top-row {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 1rem;
}

@media (max-width: 768px) {
  .top-row {
    grid-template-columns: 1fr;
  }
}

.secret-card h3,
.question-log h3 {
  font-size: 0.85rem;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: var(--text-muted);
  margin-bottom: 0.5rem;
}

.location-name {
  font-size: 1.5rem;
  font-weight: 700;
}

.role-name {
  margin-top: 0.25rem;
  color: var(--text-muted);
}

.spy-label {
  font-size: 1.25rem;
}

.location-list {
  display: flex;
  flex-wrap: wrap;
  gap: 0.35rem;
  margin-top: 0.75rem;
  max-height: 8rem;
  overflow-y: auto;
}

.loc-chip {
  font-size: 0.7rem;
  padding: 0.2rem 0.5rem;
  background: var(--surface-elevated);
  border-radius: 999px;
  border: 1px solid var(--border);
}

.status-bar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 0.5rem;
}

.phase-tag {
  font-size: 0.75rem;
  font-weight: 600;
  text-transform: uppercase;
  padding: 0.2rem 0.6rem;
  border-radius: 999px;
  background: var(--accent-muted);
  color: var(--accent);
}

.timer {
  font-size: 0.85rem;
  font-weight: 600;
  font-variant-numeric: tabular-nums;
}

.status-text {
  font-weight: 600;
}

.status-text.ai-thinking {
  color: var(--accent);
}

.ai-icon {
  margin-right: 0.25rem;
}

.pending-q {
  margin-top: 0.75rem;
  padding: 0.75rem;
  background: var(--surface-elevated);
  border-radius: var(--radius);
}

.q-label {
  font-size: 0.75rem;
  color: var(--text-muted);
  margin-bottom: 0.25rem;
}

.question-text {
  font-style: italic;
  margin-top: 0.25rem;
}

.player-strip {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
}

.player-chip {
  display: flex;
  align-items: center;
  gap: 0.35rem;
  padding: 0.4rem 0.75rem;
  border-radius: 999px;
  border: 1px solid var(--border);
  font-size: 0.85rem;
}

.player-chip.active {
  border-color: var(--accent);
  background: var(--accent-muted);
}

.player-chip.self {
  font-weight: 700;
}

.player-chip.voted {
  opacity: 0.6;
}

.ai-badge,
.turn-badge {
  font-size: 0.65rem;
  padding: 0.1rem 0.35rem;
  border-radius: 4px;
  background: var(--surface-elevated);
}

.turn-badge {
  background: var(--accent);
  color: white;
}

.question-log {
  max-height: 280px;
  overflow-y: auto;
}

.empty-log {
  font-size: 0.9rem;
}

.log-entry {
  padding: 0.6rem 0;
  border-bottom: 1px solid var(--border);
}

.log-entry:last-child {
  border-bottom: none;
}

.log-q {
  font-size: 0.9rem;
}

.log-a {
  font-size: 0.85rem;
  color: var(--text-muted);
  margin-top: 0.2rem;
  padding-left: 1rem;
}

.action-panel {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.action-block h4 {
  font-size: 0.85rem;
  margin-bottom: 0.5rem;
  color: var(--text-muted);
}

.action-block select,
.action-block textarea {
  width: 100%;
  margin-bottom: 0.5rem;
}

.accuse-buttons,
.vote-buttons {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
}

.game-over {
  text-align: center;
  padding: 2rem;
}

.winner-badge {
  font-size: 1.5rem;
  font-weight: 700;
  margin-bottom: 0.5rem;
}

.winner-badge.spy {
  color: var(--warning, #e6a700);
}

.winner-badge.residents {
  color: var(--success);
}

.win-reason {
  color: var(--text-muted);
  margin-bottom: 1rem;
}

.reveal-block {
  text-align: left;
  max-width: 400px;
  margin: 0 auto;
}

.role-list {
  margin-top: 0.75rem;
  list-style: none;
  font-size: 0.9rem;
}

.role-list li {
  padding: 0.25rem 0;
}

.muted {
  color: var(--text-muted);
}
</style>
