<script setup lang="ts">
import { ref, computed, watch, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { usePlayerStore } from '@/stores/player'
import { useRoom } from '@/composables/useRoom'
import { useWebSocket } from '@/composables/useWebSocket'
import CodenamesBoard from '@/games/codenames/CodenamesBoard.vue'
import GameRulesModal from '@/components/GameRulesModal.vue'
import type { Room, GameState } from '@/types'

const route = useRoute()
const router = useRouter()
const playerStore = usePlayerStore()
const { fetchRoom } = useRoom()

const roomId = computed(() => route.params.id as string)
const room = ref<Room | null>(null)
const gameState = ref<GameState | null>(null)
const toast = ref('')
const showRules = ref(false)

const wsToken = computed(() => playerStore.sessionToken)
const { connected, lastMessage, error, send } = useWebSocket(roomId, wsToken)

onMounted(async () => {
  try {
    room.value = await fetchRoom(roomId.value)
  } catch {
    toast.value = 'Room not found'
  }
})

watch(lastMessage, (msg) => {
  if (!msg) return
  if (msg.room) room.value = msg.room
  if (msg.game_state !== undefined) gameState.value = msg.game_state
  if (msg.type === 'returned_to_lobby' && msg.room) {
    router.push(`/room/${roomId.value}`)
  }
  if (msg.type === 'error') {
    toast.value = msg.message ?? 'Error'
    setTimeout(() => (toast.value = ''), 3000)
  }
})

watch(error, (e) => {
  if (e) {
    toast.value = e
    setTimeout(() => (toast.value = ''), 3000)
  }
})

function sendAction(data: Record<string, unknown>) {
  if (!send(data)) {
    toast.value = 'Not connected — try again in a moment'
    setTimeout(() => (toast.value = ''), 3000)
  }
}

function backToLobby() {
  sendAction({ type: 'return_to_lobby' })
}
</script>

<template>
  <div class="game-page">
    <header class="game-header container-wide">
      <div class="header-left">
        <h1>Codenames</h1>
        <div class="header-meta">
          <span class="room-id">Room {{ roomId.slice(0, 8) }}…</span>
          <span class="connection" :class="{ online: connected }">
            <span class="connection-dot" />
            {{ connected ? 'Live' : 'Reconnecting' }}
          </span>
          <span class="av-hint">💬 Voice chat recommended</span>
        </div>
      </div>
      <div class="header-actions">
        <button type="button" class="btn-secondary" @click="backToLobby">Lobby</button>
        <button type="button" class="btn-secondary" @click="showRules = true">Rules</button>
      </div>
    </header>

    <CodenamesBoard
      v-if="gameState && room"
      :game-state="gameState"
      :room="room"
      :player-id="playerStore.playerId"
      @action="sendAction"
    />

    <div v-else class="container-wide loading">
      <div class="loading-spinner" />
      <p>Loading game...</p>
    </div>

    <Transition name="toast">
      <div v-if="toast" class="toast error">{{ toast }}</div>
    </Transition>

    <GameRulesModal
      v-if="showRules"
      :game-type="room?.game_type ?? 'codenames'"
      @close="showRules = false"
    />
  </div>
</template>

<style scoped>
.game-page {
  min-height: 100vh;
  padding-bottom: 1.5rem;
}

.game-header {
  padding-top: 1rem;
  padding-bottom: 0.75rem;
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 1rem;
  border-bottom: 1px solid var(--border);
  margin-bottom: 0.75rem;
  animation: fadeInUp 0.4s var(--ease-smooth);
}

.game-header h1 {
  font-size: 1.35rem;
  font-weight: 700;
}

.header-meta {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 0.65rem;
  margin-top: 0.2rem;
}

.room-id {
  font-size: 0.8rem;
  color: var(--text-muted);
}

.connection {
  display: inline-flex;
  align-items: center;
  gap: 0.35rem;
  font-size: 0.75rem;
  font-weight: 600;
  color: var(--error);
}

.connection.online {
  color: var(--success);
}

.connection-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: currentColor;
}

.connection.online .connection-dot {
  animation: pulse-dot 2s ease-in-out infinite;
}

@keyframes pulse-dot {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.4; }
}

.av-hint {
  font-size: 0.75rem;
  color: var(--text-muted);
}

.header-actions {
  display: flex;
  gap: 0.5rem;
  flex-shrink: 0;
}

.loading {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 1rem;
  padding: 6rem 1rem;
  color: var(--text-muted);
}

.loading-spinner {
  width: 2.5rem;
  height: 2.5rem;
  border: 3px solid var(--border);
  border-top-color: var(--accent);
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

.toast-enter-active {
  animation: toastIn 0.4s var(--ease-bounce);
}

.toast-leave-active {
  animation: toastIn 0.25s reverse;
}
</style>
