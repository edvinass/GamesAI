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
  showRules: []
}>()

const questionText = ref('')
const answerText = ref('')
const selectedTarget = ref('')
const selectedLocation = ref('')
const logRef = ref<HTMLElement | null>(null)
const timeRemaining = ref('')
const locationSearch = ref('')
const showLocationPanel = ref(true)
const roleRevealDismissedFor = ref<string | null>(null)

const me = computed(() => props.room.players.find((p) => p.id === props.playerId))

const isHost = computed(() => props.room.host_player_id === props.playerId)

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

const isSpy = computed(() => props.gameState.is_spy === true)

const isResident = computed(() => props.gameState.is_spy === false)

const showRoleReveal = computed(() => {
  if (isGameOver.value || props.gameState.is_spy == null) return false
  const roundId = props.gameState.round_id
  if (!roundId) return false
  return roleRevealDismissedFor.value !== roundId
})

function dismissRoleReveal() {
  if (props.gameState.round_id) {
    roleRevealDismissedFor.value = props.gameState.round_id
  }
}

watch(
  () => props.gameState.round_id,
  (roundId) => {
    if (roundId && roleRevealDismissedFor.value && roleRevealDismissedFor.value !== roundId) {
      roleRevealDismissedFor.value = null
    }
  },
)

const sortedLocations = computed(() =>
  [...(props.gameState.location_names ?? [])].sort((a, b) => a.localeCompare(b)),
)

const filteredLocations = computed(() => {
  const q = locationSearch.value.trim().toLowerCase()
  if (!q) return sortedLocations.value
  return sortedLocations.value.filter((loc) => loc.toLowerCase().includes(q))
})

function selectLocationForGuess(loc: string) {
  selectedLocation.value = loc
}

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

const phaseHint = computed(() => {
  if (isGameOver.value) return ''
  if (props.gameState.phase === 'voting') {
    return 'Vote for who you think is the Spy. Majority must agree to catch them.'
  }
  if (isMyTurnToAnswer.value) {
    return isSpy.value
      ? 'Bluff with a vague answer — don\'t reveal that you don\'t know the location.'
      : 'Answer in character for your role. Don\'t say the location name.'
  }
  if (isMyTurnToAsk.value) {
    return isSpy.value
      ? 'Ask something vague that fits many locations, or pick up on what others have said.'
      : 'Ask a question that tests whether they really belong here.'
  }
  if (isSpy.value) {
    return 'Watch the conversation and use the location list when you\'re ready to guess.'
  }
  return 'Listen for vague or inconsistent answers — then call an accusation when you\'re ready.'
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

function startNewGame() {
  emit('action', { type: 'start_game' })
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
      <button v-if="isHost" class="btn-primary new-game-btn" @click="startNewGame">
        Play Again
      </button>
      <p v-else class="waiting-host">Waiting for host to start a new game…</p>
    </div>

    <template v-else>
      <Transition name="role-reveal">
        <div v-if="showRoleReveal" class="role-reveal-overlay">
          <div class="role-reveal card" :class="isSpy ? 'spy' : 'resident'">
            <p class="role-reveal-label">Your assignment</p>
            <div v-if="isSpy" class="role-reveal-body">
              <div class="role-reveal-icon">🕵️</div>
              <h2>You are the <span class="highlight">Spy</span></h2>
              <p class="role-reveal-desc">
                You do <strong>not</strong> know the secret location or your role.
                Listen to others, ask vague questions, and guess the location — or try to avoid detection.
              </p>
            </div>
            <div v-else class="role-reveal-body">
              <div class="role-reveal-icon">🏠</div>
              <h2>You are a <span class="highlight">Resident</span></h2>
              <p class="role-reveal-desc">
                You are <strong>not</strong> the spy. Everyone else at the table shares this location with you.
              </p>
              <div class="role-reveal-details">
                <div class="detail-row">
                  <span class="detail-label">Location</span>
                  <span class="detail-value">{{ gameState.viewer_location }}</span>
                </div>
                <div class="detail-row">
                  <span class="detail-label">Your role</span>
                  <span class="detail-value">{{ gameState.viewer_role }}</span>
                </div>
              </div>
            </div>
            <button type="button" class="btn-primary role-reveal-btn" @click="dismissRoleReveal">
              I'm ready — start playing
            </button>
            <button type="button" class="btn-secondary role-rules-btn" @click="emit('showRules')">
              View full rules
            </button>
          </div>
        </div>
      </Transition>

      <div class="play-layout" :class="{ 'has-location-panel': isSpy, dimmed: showRoleReveal }">
        <div class="main-column">
      <div class="top-row">
        <div class="secret-card card" :class="isSpy ? 'spy-card' : 'resident-card'">
          <div class="role-badge" :class="isSpy ? 'spy' : 'resident'">
            {{ isSpy ? '🕵️ Spy' : '🏠 Resident' }}
          </div>
          <h3>Your secret</h3>
          <template v-if="isSpy">
            <p class="spy-label">You don't know the location</p>
            <p class="muted">Blend in and deduce the location — or guess when you're confident.</p>
            <button
              type="button"
              class="btn-secondary toggle-locations-btn"
              @click="showLocationPanel = !showLocationPanel"
            >
              {{ showLocationPanel ? 'Hide' : 'Show' }} all locations ({{ sortedLocations.length }})
            </button>
          </template>
          <template v-else-if="isResident">
            <p class="location-name">{{ gameState.viewer_location }}</p>
            <p class="role-name">Your role: <strong>{{ gameState.viewer_role }}</strong></p>
            <p class="muted resident-note">You are not the spy.</p>
          </template>
          <template v-else>
            <p class="muted">Loading your assignment…</p>
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
          <p v-if="phaseHint" class="phase-hint">{{ phaseHint }}</p>
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

          <div v-if="isSpy" class="action-block spy-guess">
            <h4>Guess location</h4>
            <p v-if="selectedLocation" class="selected-location">
              Selected: <strong>{{ selectedLocation }}</strong>
            </p>
            <select v-model="selectedLocation">
              <option value="" disabled>Select location</option>
              <option v-for="loc in sortedLocations" :key="loc" :value="loc">{{ loc }}</option>
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
        </div>

        <aside v-if="isSpy && showLocationPanel" class="location-panel card">
          <div class="location-panel-header">
            <h3>All locations</h3>
            <span class="location-count">{{ filteredLocations.length }}/{{ sortedLocations.length }}</span>
          </div>
          <input
            v-model="locationSearch"
            type="search"
            class="location-search"
            placeholder="Search locations…"
          />
          <ul class="location-checklist">
            <li v-for="loc in filteredLocations" :key="loc">
              <button
                type="button"
                class="location-item"
                :class="{ selected: selectedLocation === loc }"
                @click="selectLocationForGuess(loc)"
              >
                {{ loc }}
              </button>
            </li>
          </ul>
          <p v-if="!filteredLocations.length" class="muted no-results">No locations match your search.</p>
          <button
            v-if="selectedLocation && gameState.phase === 'questioning'"
            type="button"
            class="btn-primary guess-from-panel-btn"
            @click="guessLocation"
          >
            Guess "{{ selectedLocation }}"
          </button>
        </aside>
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

.play-layout.dimmed {
  pointer-events: none;
  opacity: 0.35;
  filter: blur(2px);
}

.role-reveal-overlay {
  position: fixed;
  inset: 0;
  z-index: 100;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 1.5rem;
  background: rgba(0, 0, 0, 0.65);
  backdrop-filter: blur(4px);
}

.role-reveal {
  max-width: 440px;
  width: 100%;
  text-align: center;
  padding: 2rem 1.75rem;
  border-width: 2px;
}

.role-reveal.spy {
  border-color: var(--warning, #e6a700);
  background: linear-gradient(180deg, rgba(230, 167, 0, 0.12) 0%, var(--surface) 40%);
}

.role-reveal.resident {
  border-color: var(--success);
  background: linear-gradient(180deg, rgba(61, 214, 140, 0.12) 0%, var(--surface) 40%);
}

.role-reveal-label {
  font-size: 0.75rem;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  color: var(--text-muted);
  margin-bottom: 0.75rem;
}

.role-reveal-icon {
  font-size: 3rem;
  margin-bottom: 0.5rem;
}

.role-reveal h2 {
  font-size: 1.75rem;
  font-weight: 700;
  margin-bottom: 0.75rem;
}

.role-reveal h2 .highlight {
  color: var(--accent);
}

.role-reveal.spy h2 .highlight {
  color: var(--warning, #e6a700);
}

.role-reveal.resident h2 .highlight {
  color: var(--success);
}

.role-reveal-desc {
  font-size: 0.95rem;
  color: var(--text-muted);
  line-height: 1.5;
  margin-bottom: 1.25rem;
}

.role-reveal-details {
  text-align: left;
  background: var(--surface-elevated);
  border-radius: var(--radius);
  padding: 1rem 1.25rem;
  margin-bottom: 1.25rem;
}

.detail-row {
  display: flex;
  justify-content: space-between;
  gap: 1rem;
  padding: 0.35rem 0;
}

.detail-row + .detail-row {
  border-top: 1px solid var(--border);
  margin-top: 0.35rem;
  padding-top: 0.65rem;
}

.detail-label {
  font-size: 0.8rem;
  color: var(--text-muted);
  text-transform: uppercase;
  letter-spacing: 0.04em;
}

.detail-value {
  font-weight: 700;
  text-align: right;
}

.role-reveal-btn {
  width: 100%;
  font-size: 1rem;
  padding: 0.85rem;
}

.role-rules-btn {
  width: 100%;
  margin-top: 0.5rem;
  font-size: 0.9rem;
}

.phase-hint {
  font-size: 0.85rem;
  color: var(--text-muted);
  line-height: 1.45;
  margin-top: 0.5rem;
  padding: 0.6rem 0.75rem;
  background: var(--surface-elevated);
  border-radius: var(--radius);
  border-left: 3px solid var(--accent);
}

.role-reveal-enter-active {
  animation: fadeInUp 0.35s var(--ease-smooth);
}

.role-reveal-leave-active {
  animation: fadeInUp 0.2s reverse;
}

.secret-card {
  position: relative;
  overflow: hidden;
}

.secret-card.spy-card {
  border-color: rgba(230, 167, 0, 0.45);
}

.secret-card.resident-card {
  border-color: rgba(61, 214, 140, 0.35);
}

.role-badge {
  display: inline-block;
  font-size: 0.75rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  padding: 0.3rem 0.65rem;
  border-radius: 999px;
  margin-bottom: 0.65rem;
}

.role-badge.spy {
  background: rgba(230, 167, 0, 0.2);
  color: var(--warning, #e6a700);
}

.role-badge.resident {
  background: rgba(61, 214, 140, 0.15);
  color: var(--success);
}

.resident-note {
  margin-top: 0.5rem;
  font-size: 0.85rem;
}

.play-layout {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.play-layout.has-location-panel {
  display: grid;
  grid-template-columns: 1fr 280px;
  gap: 1rem;
  align-items: start;
}

@media (max-width: 960px) {
  .play-layout.has-location-panel {
    grid-template-columns: 1fr;
  }
}

.main-column {
  display: flex;
  flex-direction: column;
  gap: 1rem;
  min-width: 0;
}

.location-panel {
  position: sticky;
  top: 1rem;
  max-height: calc(100vh - 2rem);
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

.location-panel-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.location-panel-header h3 {
  font-size: 0.85rem;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: var(--text-muted);
  margin: 0;
}

.location-count {
  font-size: 0.75rem;
  color: var(--text-muted);
  font-variant-numeric: tabular-nums;
}

.location-search {
  width: 100%;
  font-size: 0.85rem;
}

.location-checklist {
  list-style: none;
  margin: 0;
  padding: 0;
  overflow-y: auto;
  flex: 1;
  min-height: 0;
}

.location-item {
  width: 100%;
  text-align: left;
  padding: 0.45rem 0.6rem;
  border: none;
  border-radius: var(--radius, 6px);
  background: transparent;
  color: inherit;
  font-size: 0.85rem;
  cursor: pointer;
  transition: background 0.15s;
}

.location-item:hover {
  background: var(--surface-elevated);
}

.location-item.selected {
  background: var(--accent-muted);
  color: var(--accent);
  font-weight: 600;
}

.no-results {
  font-size: 0.85rem;
  text-align: center;
}

.guess-from-panel-btn {
  width: 100%;
  font-size: 0.85rem;
}

.toggle-locations-btn {
  margin-top: 0.75rem;
  font-size: 0.85rem;
}

.selected-location {
  font-size: 0.85rem;
  margin-bottom: 0.5rem;
  color: var(--text-muted);
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

.new-game-btn {
  margin-top: 1.25rem;
}

.waiting-host {
  margin-top: 1rem;
  font-size: 0.9rem;
  color: var(--text-muted);
}

.muted {
  color: var(--text-muted);
}
</style>
