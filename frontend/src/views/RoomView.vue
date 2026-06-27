<script setup lang="ts">
import { ref, computed, watch, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { usePlayerStore } from '@/stores/player'
import { useRoom } from '@/composables/useRoom'
import { useWebSocket } from '@/composables/useWebSocket'
import { useLeaveRoom } from '@/composables/useLeaveRoom'
import GameRulesModal from '@/components/GameRulesModal.vue'
import LobbyTeamPanel from '@/components/lobby/LobbyTeamPanel.vue'
import { validateLobby } from '@/games/codenames/lobbyValidation'
import type { Room } from '@/types'

const route = useRoute()
const router = useRouter()
const playerStore = usePlayerStore()
const { fetchRoom, joinRoom, loading: joinLoading } = useRoom()

const roomId = computed(() => route.params.id as string)
const room = ref<Room | null>(null)
const joinNickname = ref(playerStore.nickname || '')
const needsJoin = ref(false)
const copied = ref(false)
const toast = ref('')
const showRules = ref(false)

const wsToken = ref(playerStore.sessionToken)
const { connected, lastMessage, send, disconnect } = useWebSocket(roomId, wsToken)
const { leaveRoom } = useLeaveRoom()

onMounted(async () => {
  try {
    room.value = await fetchRoom(roomId.value)
    if (room.value.status === 'playing') {
      router.replace(`/room/${roomId.value}/play`)
      return
    }
    if (!playerStore.sessionToken || playerStore.roomId !== roomId.value) {
      needsJoin.value = true
      wsToken.value = ''
    } else {
      wsToken.value = playerStore.sessionToken
    }
  } catch {
    toast.value = 'Room not found'
  }
})

watch(lastMessage, (msg) => {
  if (!msg) return
  if (msg.room) room.value = msg.room
  if (msg.type === 'game_started' && msg.room) {
    router.push(`/room/${roomId.value}/play`)
  }
  if (msg.type === 'error') {
    toast.value = msg.message ?? 'Error'
    setTimeout(() => (toast.value = ''), 3000)
  }
})

const roomUrl = computed(() => `${window.location.origin}/room/${roomId.value}`)
const isHost = computed(() => room.value?.host_player_id === playerStore.playerId)

const lobbyValidation = computed(() =>
  room.value ? validateLobby(room.value) : { valid: false, message: '', issues: [] },
)

const soloPractice = computed({
  get: () => Boolean(room.value?.settings?.solo_practice),
  set: (val: boolean) => updateSettings({ solo_practice: val }),
})

async function handleJoin() {
  if (!joinNickname.value.trim()) return
  const result = await joinRoom(roomId.value, joinNickname.value.trim())
  playerStore.saveSession({
    nickname: joinNickname.value.trim(),
    sessionToken: result.session_token,
    playerId: result.player_id,
    roomId: result.room_id,
  })
  needsJoin.value = false
  wsToken.value = result.session_token
  room.value = await fetchRoom(roomId.value)
}

function updateSettings(settings: Record<string, unknown>) {
  send({ type: 'update_settings', settings })
}

function addAi(team: string, role: string) {
  send({ type: 'add_ai_player', team, role })
}

function removePlayer(id: string) {
  send({ type: 'remove_player', player_id: id })
}

function assignPlayer(
  playerId: string,
  team: 'red' | 'blue',
  role: 'spymaster' | 'operative',
) {
  send({ type: 'update_player', player_id: playerId, team, role })
}

function startGame() {
  send({ type: 'start_game' })
}

async function copyUrl() {
  await navigator.clipboard.writeText(roomUrl.value)
  copied.value = true
  setTimeout(() => (copied.value = false), 2000)
}
</script>

<template>
  <div class="container lobby">
    <div v-if="needsJoin" class="card join-card">
      <h2>Join Room</h2>
      <p class="muted">Enter your nickname to join this room.</p>
      <input v-model="joinNickname" placeholder="Nickname" maxlength="50" @keyup.enter="handleJoin" />
      <button class="btn-primary" :disabled="joinLoading || !joinNickname.trim()" @click="handleJoin">
        Join
      </button>
    </div>

    <template v-else-if="room">
      <header class="lobby-header">
        <div>
          <h1>Lobby</h1>
          <p class="muted">{{ room.game_type }} · {{ room.players.length }} players</p>
        </div>
        <div class="header-actions">
          <button type="button" class="btn-secondary" @click="leaveRoom(disconnect)">Leave Room</button>
          <button type="button" class="btn-secondary" @click="showRules = true">Rules</button>
          <div class="connection" :class="{ online: connected }">
            {{ connected ? 'Connected' : 'Reconnecting...' }}
          </div>
        </div>
      </header>

      <div class="av-callout card">
        <strong>Tip:</strong> Connect with your friends using your favorite audio or video chat (Discord, Zoom, etc.)
      </div>

      <div class="share-row card">
        <input :value="roomUrl" readonly class="url-input" />
        <button class="btn-secondary" @click="copyUrl">
          {{ copied ? 'Copied!' : 'Copy URL' }}
        </button>
      </div>

      <div class="settings card" v-if="isHost">
        <h3>Settings</h3>
        <label class="checkbox-label">
          <input type="checkbox" v-model="soloPractice" />
          Solo practice (play against AI teams)
        </label>
      </div>

      <div v-if="soloPractice" class="solo-notice card">
        <p>Solo practice auto-builds teams when you start. You will play as the red operative against AI.</p>
      </div>

      <template v-else>
        <p v-if="isHost" class="arrange-hint">
          Assign each team one spymaster and at least one operative. Use the slot buttons to move players, change roles, or fill gaps with AI.
        </p>

        <div class="teams">
          <LobbyTeamPanel
            team="red"
            :players="room.players"
            :is-host="isHost"
            :current-player-id="playerStore.playerId"
            :host-player-id="room.host_player_id"
            @assign="assignPlayer"
            @add-ai="addAi"
            @remove="removePlayer"
          />
          <LobbyTeamPanel
            team="blue"
            :players="room.players"
            :is-host="isHost"
            :current-player-id="playerStore.playerId"
            :host-player-id="room.host_player_id"
            @assign="assignPlayer"
            @add-ai="addAi"
            @remove="removePlayer"
          />
        </div>

        <div
          class="validation-banner card"
          :class="{ valid: lobbyValidation.valid, invalid: !lobbyValidation.valid }"
        >
          <span class="validation-icon">{{ lobbyValidation.valid ? '✓' : '!' }}</span>
          <div>
            <p class="validation-message">{{ lobbyValidation.message }}</p>
            <ul v-if="!lobbyValidation.valid && lobbyValidation.issues.length > 1" class="validation-issues">
              <li v-for="issue in lobbyValidation.issues" :key="issue">{{ issue }}</li>
            </ul>
          </div>
        </div>
      </template>

      <button
        v-if="isHost"
        class="btn-primary start-btn"
        :disabled="!lobbyValidation.valid"
        @click="startGame"
      >
        Start Game
      </button>
    </template>

    <div v-if="toast" class="toast error">{{ toast }}</div>

    <GameRulesModal
      v-if="showRules && room"
      :game-type="room.game_type"
      @close="showRules = false"
    />
  </div>
</template>

<style scoped>
.lobby {
  padding-top: 2rem;
  padding-bottom: 3rem;
}

.join-card {
  max-width: 400px;
  margin: 4rem auto;
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.lobby-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 1.5rem;
}

.lobby-header h1 {
  font-size: 1.75rem;
}

.header-actions {
  display: flex;
  align-items: center;
  gap: 0.75rem;
}

.muted {
  color: var(--text-muted);
  font-size: 0.9rem;
}

.connection {
  font-size: 0.85rem;
  color: var(--error);
  padding: 0.35rem 0.75rem;
  border-radius: 20px;
  background: rgba(231, 76, 92, 0.1);
}

.connection.online {
  color: var(--success);
  background: rgba(46, 204, 113, 0.1);
}

.av-callout {
  margin-bottom: 1rem;
  font-size: 0.9rem;
  color: var(--text-muted);
  border-left: 3px solid var(--accent);
}

.share-row {
  display: flex;
  gap: 0.75rem;
  margin-bottom: 1rem;
}

.url-input {
  flex: 1;
  font-size: 0.85rem;
}

.settings {
  margin-bottom: 1rem;
}

.settings h3 {
  margin-bottom: 0.75rem;
  font-size: 1rem;
}

.checkbox-label {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  cursor: pointer;
  font-size: 0.9rem;
}

.solo-notice {
  margin-bottom: 1rem;
  font-size: 0.9rem;
  color: var(--text-muted);
  border-left: 3px solid var(--accent);
}

.arrange-hint {
  margin-bottom: 1rem;
  font-size: 0.85rem;
  color: var(--text-muted);
}

.teams {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 1rem;
  margin-bottom: 1rem;
}

@media (max-width: 768px) {
  .teams {
    grid-template-columns: 1fr;
  }
}

.validation-banner {
  display: flex;
  gap: 0.75rem;
  align-items: flex-start;
  margin-bottom: 1.5rem;
  padding: 1rem 1.25rem;
}

.validation-banner.valid {
  border-color: rgba(46, 204, 113, 0.4);
  background: rgba(46, 204, 113, 0.08);
}

.validation-banner.invalid {
  border-color: rgba(231, 76, 92, 0.35);
  background: rgba(231, 76, 92, 0.08);
}

.validation-icon {
  width: 1.5rem;
  height: 1.5rem;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: 700;
  font-size: 0.85rem;
  flex-shrink: 0;
}

.validation-banner.valid .validation-icon {
  background: rgba(46, 204, 113, 0.2);
  color: var(--success);
}

.validation-banner.invalid .validation-icon {
  background: rgba(231, 76, 92, 0.2);
  color: var(--error);
}

.validation-message {
  font-size: 0.9rem;
}

.validation-issues {
  margin-top: 0.5rem;
  padding-left: 1.1rem;
  font-size: 0.85rem;
  color: var(--text-muted);
}

.validation-issues li {
  margin-bottom: 0.2rem;
}

.start-btn {
  width: 100%;
  font-size: 1.1rem;
  padding: 1rem;
}
</style>
