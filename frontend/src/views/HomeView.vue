<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { usePlayerStore } from '@/stores/player'
import { useRoom } from '@/composables/useRoom'
import GameRulesModal from '@/components/GameRulesModal.vue'

const router = useRouter()
const playerStore = usePlayerStore()
const { createRoom, joinRoom, fetchGames, loading, error } = useRoom()

const nickname = ref(playerStore.nickname || '')
const gameType = ref('codenames')
const games = ref<Array<{ id: string; name: string; description: string }>>([
  { id: 'codenames', name: 'Codenames', description: 'Team word guessing game' },
])
const joinRoomId = ref('')
const mode = ref<'create' | 'join'>('create')
const showRules = ref(false)

onMounted(async () => {
  try {
    const fetched = await fetchGames()
    if (Array.isArray(fetched) && fetched.length > 0) {
      games.value = fetched
      if (!fetched.some((g) => g.id === gameType.value)) {
        gameType.value = fetched[0].id
      }
    }
  } catch {
    // keep default games list
  }
})

async function enterGame() {
  if (!nickname.value.trim()) {
    error.value = 'Enter a nickname first'
    return
  }

  try {
    playerStore.setNickname(nickname.value.trim())

    if (mode.value === 'join') {
      if (!joinRoomId.value.trim()) {
        error.value = 'Enter a room ID to join'
        return
      }
      const result = await joinRoom(joinRoomId.value.trim(), nickname.value.trim())
      playerStore.saveSession({
        nickname: nickname.value.trim(),
        sessionToken: result.session_token,
        playerId: result.player_id,
        roomId: result.room_id,
      })
      await router.push(`/room/${result.room_id}`)
    } else {
      const result = await createRoom(gameType.value, nickname.value.trim())
      playerStore.saveSession({
        nickname: nickname.value.trim(),
        sessionToken: result.session_token,
        playerId: result.player_id,
        roomId: result.room_id,
      })
      await router.push(`/room/${result.room_id}`)
    }
  } catch {
    // error message shown via useRoom.error
  }
}

function selectCreateMode() {
  mode.value = 'create'
}

function switchToJoin() {
  mode.value = 'join'
}
</script>

<template>
  <div class="home">
    <div class="home-grid">
      <section class="hero">
        <div class="hero-badge">Free · No signup</div>
        <h1 class="title">
          <span class="title-word">Games</span><span class="title-accent">AI</span>
        </h1>
        <p class="tagline">Online party games with friends — and AI teammates that actually play.</p>

        <div class="feature-chips stagger-in">
          <span class="chip">🎯 Codenames</span>
          <span class="chip">🤖 AI players</span>
          <span class="chip">🔗 Share a link</span>
        </div>

        <ol class="steps stagger-in">
          <li><span class="step-num">1</span> Pick a nickname</li>
          <li><span class="step-num">2</span> Create or join a room</li>
          <li><span class="step-num">3</span> Voice chat with friends</li>
          <li><span class="step-num">4</span> Play!</li>
        </ol>
      </section>

      <div class="card form-card card-interactive">
        <h2>Jump in</h2>

        <div class="form">
          <label>
            Nickname
            <input v-model="nickname" placeholder="Your nickname" maxlength="50" @keyup.enter="enterGame" />
          </label>

          <div class="mode-toggle" :class="mode">
            <button
              type="button"
              :class="['mode-btn', { active: mode === 'create' }]"
              :disabled="loading"
              @click="selectCreateMode"
            >
              {{ loading && mode === 'create' ? 'Creating...' : 'New Game' }}
            </button>
            <button
              type="button"
              :class="['mode-btn', { active: mode === 'join' }]"
              :disabled="loading"
              @click="switchToJoin"
            >
              Join Room
            </button>
          </div>

          <p v-if="mode === 'create'" class="hint">Pick a game, then hit ENTER GAME below.</p>
          <p v-else class="hint">Paste the room ID from your friend's link.</p>

          <div class="field-area">
            <label v-show="mode === 'create'">
              Game
              <div class="game-select-row">
                <select v-model="gameType">
                  <option v-for="g in games" :key="g.id" :value="g.id">
                    {{ g.name }}
                  </option>
                </select>
                <button type="button" class="btn-secondary" @click="showRules = true">
                  Rules
                </button>
              </div>
            </label>
            <label v-show="mode === 'join'">
              Room ID
              <input v-model="joinRoomId" placeholder="Paste room ID from URL" />
            </label>
          </div>

          <Transition name="field">
            <p v-if="error" class="error-msg">{{ error }}</p>
          </Transition>

          <button
            type="button"
            class="btn-primary enter-btn"
            :disabled="loading || !nickname.trim() || (mode === 'join' && !joinRoomId.trim())"
            @click="enterGame"
          >
            <span v-if="loading" class="btn-spinner" />
            {{ loading ? 'Please wait...' : mode === 'create' ? 'ENTER GAME' : 'JOIN GAME' }}
          </button>
        </div>
      </div>
    </div>

    <GameRulesModal v-if="showRules" :game-type="gameType" @close="showRules = false" />
  </div>
</template>

<style scoped>
.home {
  min-height: 100vh;
  display: flex;
  align-items: center;
  padding: 2rem 1.5rem;
}

.home-grid {
  width: 100%;
  max-width: 1100px;
  margin: 0 auto;
  display: grid;
  grid-template-columns: 1fr;
  gap: 2.5rem;
  align-items: center;
}

@media (min-width: 900px) {
  .home-grid {
    grid-template-columns: 1fr 420px;
    gap: 4rem;
  }
}

.hero {
  animation: fadeInUp 0.6s var(--ease-smooth);
}

.hero-badge {
  display: inline-block;
  padding: 0.35rem 0.85rem;
  border-radius: 999px;
  font-size: 0.75rem;
  font-weight: 600;
  letter-spacing: 0.04em;
  text-transform: uppercase;
  background: rgba(91, 156, 255, 0.12);
  border: 1px solid rgba(91, 156, 255, 0.25);
  color: var(--accent);
  margin-bottom: 1.25rem;
}

.title {
  font-size: clamp(2.75rem, 6vw, 4.5rem);
  font-weight: 800;
  line-height: 1.05;
  margin-bottom: 1rem;
}

.title-word {
  color: var(--text);
}

.title-accent {
  background: linear-gradient(135deg, var(--accent) 0%, #a78bfa 50%, #ff6b9d 100%);
  background-size: 200% auto;
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
  animation: shimmer 4s linear infinite;
}

.tagline {
  color: var(--text-muted);
  font-size: 1.2rem;
  max-width: 420px;
  margin-bottom: 1.75rem;
}

.feature-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 0.6rem;
  margin-bottom: 2rem;
}

.chip {
  padding: 0.45rem 0.9rem;
  border-radius: 999px;
  font-size: 0.85rem;
  font-weight: 500;
  background: var(--surface);
  border: 1px solid var(--border);
  transition: transform 0.2s var(--ease-bounce), border-color 0.2s;
}

.chip:hover {
  transform: translateY(-2px) scale(1.02);
  border-color: var(--accent);
}

.steps {
  list-style: none;
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 0.75rem;
}

@media (min-width: 900px) {
  .steps {
    grid-template-columns: repeat(2, minmax(0, 1fr));
    max-width: 480px;
  }
}

.steps li {
  display: flex;
  align-items: center;
  gap: 0.65rem;
  font-size: 0.9rem;
  color: var(--text-muted);
}

.step-num {
  flex-shrink: 0;
  width: 1.75rem;
  height: 1.75rem;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 8px;
  font-size: 0.8rem;
  font-weight: 700;
  background: var(--surface);
  border: 1px solid var(--border);
  color: var(--accent);
}

.form-card {
  animation: slideUp 0.5s var(--ease-smooth) 0.1s both;
}

@keyframes slideUp {
  from {
    transform: translateY(12px);
  }
  to {
    transform: translateY(0);
  }
}

.form-card h2 {
  font-size: 1.35rem;
  margin-bottom: 1.25rem;
}

.form {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.field-area {
  display: grid;
}

.field-area > label {
  grid-area: 1 / 1;
}

.game-select-row {
  display: flex;
  gap: 0.5rem;
}

.game-select-row select {
  flex: 1;
}

label {
  display: flex;
  flex-direction: column;
  gap: 0.4rem;
  font-size: 0.85rem;
  font-weight: 500;
  color: var(--text-muted);
}

.mode-toggle {
  position: relative;
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 0;
  padding: 4px;
  background: var(--bg);
  border-radius: 12px;
  border: 1px solid var(--border);
  isolation: isolate;
}

.mode-toggle::before {
  content: '';
  position: absolute;
  top: 4px;
  bottom: 4px;
  left: 4px;
  width: calc(50% - 4px);
  background: linear-gradient(135deg, var(--accent), #7c6cf0);
  border-radius: 9px;
  box-shadow: 0 2px 12px var(--accent-glow);
  transition: left 0.3s var(--ease-bounce);
  z-index: 0;
}

.mode-toggle.join::before {
  left: calc(50%);
}

.mode-btn {
  position: relative;
  z-index: 1;
  padding: 0.65rem;
  background: transparent;
  color: var(--text-muted);
  border: none;
  border-radius: 9px;
  font-weight: 500;
}

.mode-btn.active {
  color: var(--text);
  font-weight: 600;
}

.enter-btn {
  margin-top: 0.25rem;
  width: 100%;
  font-size: 1.05rem;
  letter-spacing: 0.06em;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 0.5rem;
}

.btn-spinner {
  width: 1rem;
  height: 1rem;
  border: 2px solid rgba(255, 255, 255, 0.3);
  border-top-color: white;
  border-radius: 50%;
  animation: spin 0.7s linear infinite;
}

.error-msg {
  color: var(--error);
  font-size: 0.9rem;
}

.hint {
  color: var(--text-muted);
  font-size: 0.85rem;
  margin: -0.25rem 0 0;
}

.mode-btn:disabled {
  opacity: 0.7;
  cursor: wait;
}
</style>
