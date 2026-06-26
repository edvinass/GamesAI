<script setup lang="ts">
import { ref, computed, watch, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { usePlayerStore } from '@/stores/player'
import { useRoom } from '@/composables/useRoom'
import { useWebSocket } from '@/composables/useWebSocket'
import type { Room, Player } from '@/types'

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

const wsToken = ref(playerStore.sessionToken)
const { connected, lastMessage, send } = useWebSocket(roomId, wsToken)

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

const redPlayers = computed(() => room.value?.players.filter((p) => p.team === 'red') ?? [])
const bluePlayers = computed(() => room.value?.players.filter((p) => p.team === 'blue') ?? [])

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

function startGame() {
  send({ type: 'start_game' })
}

async function copyUrl() {
  await navigator.clipboard.writeText(roomUrl.value)
  copied.value = true
  setTimeout(() => (copied.value = false), 2000)
}

function playerLabel(p: Player) {
  const role = p.role === 'spymaster' ? 'Spymaster' : 'Operative'
  return `${p.nickname} (${role})`
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
        <div class="connection" :class="{ online: connected }">
          {{ connected ? 'Connected' : 'Reconnecting...' }}
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

      <div class="teams">
        <div class="team-panel card red">
          <h3>Red Team</h3>
          <ul>
            <li v-for="p in redPlayers" :key="p.id" class="player-row">
              <span>
                {{ playerLabel(p) }}
                <span v-if="p.is_ai" class="badge badge-ai">AI</span>
                <span v-if="!p.is_connected" class="badge badge-disconnected">Offline</span>
              </span>
              <button
                v-if="isHost && p.is_ai"
                class="btn-small btn-secondary"
                @click="removePlayer(p.id)"
              >Remove</button>
            </li>
          </ul>
          <div v-if="isHost && !soloPractice" class="ai-buttons">
            <button class="btn-secondary btn-small" @click="addAi('red', 'spymaster')">+ AI Spymaster</button>
            <button class="btn-secondary btn-small" @click="addAi('red', 'operative')">+ AI Operative</button>
          </div>
        </div>

        <div class="team-panel card blue">
          <h3>Blue Team</h3>
          <ul>
            <li v-for="p in bluePlayers" :key="p.id" class="player-row">
              <span>
                {{ playerLabel(p) }}
                <span v-if="p.is_ai" class="badge badge-ai">AI</span>
                <span v-if="!p.is_connected" class="badge badge-disconnected">Offline</span>
              </span>
              <button
                v-if="isHost && p.is_ai"
                class="btn-small btn-secondary"
                @click="removePlayer(p.id)"
              >Remove</button>
            </li>
          </ul>
          <div v-if="isHost && !soloPractice" class="ai-buttons">
            <button class="btn-secondary btn-small" @click="addAi('blue', 'spymaster')">+ AI Spymaster</button>
            <button class="btn-secondary btn-small" @click="addAi('blue', 'operative')">+ AI Operative</button>
          </div>
        </div>
      </div>

      <button v-if="isHost" class="btn-primary start-btn" @click="startGame">
        Start Game
      </button>
    </template>

    <div v-if="toast" class="toast error">{{ toast }}</div>
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

.teams {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 1rem;
  margin-bottom: 1.5rem;
}

@media (max-width: 640px) {
  .teams {
    grid-template-columns: 1fr;
  }
}

.team-panel h3 {
  margin-bottom: 0.75rem;
}

.team-panel.red h3 { color: var(--red-team); }
.team-panel.blue h3 { color: var(--blue-team); }

.team-panel ul {
  list-style: none;
  margin-bottom: 0.75rem;
}

.player-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0.4rem 0;
  font-size: 0.9rem;
}

.ai-buttons {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
}

.btn-small {
  font-size: 0.75rem;
  padding: 0.35rem 0.65rem;
}

.start-btn {
  width: 100%;
  font-size: 1.1rem;
  padding: 1rem;
}
</style>
