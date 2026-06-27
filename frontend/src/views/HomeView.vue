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
const games = ref<Array<{ id: string; name: string; description: string }>>([])
const joinRoomId = ref('')
const mode = ref<'create' | 'join'>('create')
const showRules = ref(false)

onMounted(async () => {
  try {
    games.value = await fetchGames()
  } catch {
    games.value = [{ id: 'codenames', name: 'Codenames', description: 'Team word guessing game' }]
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

function startNewGame() {
  mode.value = 'create'
  enterGame()
}

function switchToJoin() {
  mode.value = 'join'
}
</script>

<template>
  <div class="home">
    <div class="hero">
      <h1>GamesAI</h1>
      <p class="tagline">Free online games with friends — and AI players</p>
    </div>

    <div class="card form-card">
      <h2>How to play</h2>
      <ol class="steps">
        <li>Enter your nickname and click <strong>ENTER GAME</strong></li>
        <li>Select your preferred game settings and start the game</li>
        <li>Connect with your friends using your favorite audio or video chat</li>
        <li>Share the room URL with your friends</li>
        <li>Enjoy the game!</li>
      </ol>

      <div class="form">
        <label>
          Nickname
          <input v-model="nickname" placeholder="Your nickname" maxlength="50" @keyup.enter="enterGame" />
        </label>

        <div class="mode-toggle">
          <button
            type="button"
            :class="['mode-btn', { active: mode === 'create' }]"
            :disabled="loading"
            @click="startNewGame"
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

        <p v-if="mode === 'create'" class="hint">Pick a game, then click New Game or ENTER GAME below.</p>
        <p v-else class="hint">Paste the room ID from your friend's link, then click ENTER GAME.</p>

        <template v-if="mode === 'create'">
          <label>
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
        </template>

        <template v-else>
          <label>
            Room ID
            <input v-model="joinRoomId" placeholder="Paste room ID from URL" />
          </label>
        </template>

        <p v-if="error" class="error-msg">{{ error }}</p>

        <button
          type="button"
          class="btn-primary enter-btn"
          :disabled="loading || !nickname.trim() || (mode === 'join' && !joinRoomId.trim())"
          @click="enterGame"
        >
          {{ loading ? 'Please wait...' : mode === 'create' ? 'ENTER GAME' : 'JOIN GAME' }}
        </button>
      </div>
    </div>

    <GameRulesModal v-if="showRules" :game-type="gameType" @close="showRules = false" />
  </div>
</template>

<style scoped>
.home {
  min-height: 100vh;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 2rem 1rem;
  background: radial-gradient(ellipse at top, #1a2744 0%, var(--bg) 60%);
}

.hero {
  text-align: center;
  margin-bottom: 2rem;
}

.hero h1 {
  font-size: 3rem;
  font-weight: 700;
  background: linear-gradient(135deg, var(--accent), #a78bfa);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
}

.tagline {
  color: var(--text-muted);
  font-size: 1.15rem;
  margin-top: 0.5rem;
}

.form-card {
  width: 100%;
  max-width: 480px;
}

.form-card h2 {
  font-size: 1.1rem;
  margin-bottom: 1rem;
  color: var(--text-muted);
}

.steps {
  margin-bottom: 1.5rem;
  padding-left: 1.25rem;
  color: var(--text-muted);
  font-size: 0.9rem;
}

.steps li {
  margin-bottom: 0.4rem;
}

.form {
  display: flex;
  flex-direction: column;
  gap: 1rem;
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
  display: flex;
  gap: 0.5rem;
}

.mode-btn {
  flex: 1;
  padding: 0.6rem;
  background: var(--surface-hover);
  color: var(--text-muted);
  border: 1px solid var(--border);
  border-radius: 8px;
}

.mode-btn.active {
  background: var(--accent);
  color: white;
  border-color: var(--accent);
}

.enter-btn {
  margin-top: 0.5rem;
  width: 100%;
  font-size: 1.1rem;
  letter-spacing: 0.05em;
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
