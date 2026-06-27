<script setup lang="ts">
import { ref, computed, watch, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { useLeaveRoom } from '@/composables/useLeaveRoom'
import { usePlayerStore } from '@/stores/player'
import { useRoom } from '@/composables/useRoom'
import { useWebSocket } from '@/composables/useWebSocket'
import CodenamesBoard from '@/games/codenames/CodenamesBoard.vue'
import GameRulesModal from '@/components/GameRulesModal.vue'
import type { Room, GameState } from '@/types'

const route = useRoute()
const playerStore = usePlayerStore()
const { fetchRoom } = useRoom()

const roomId = computed(() => route.params.id as string)
const room = ref<Room | null>(null)
const gameState = ref<GameState | null>(null)
const toast = ref('')
const showRules = ref(false)

const wsToken = computed(() => playerStore.sessionToken)
const { connected, lastMessage, error, send, disconnect } = useWebSocket(roomId, wsToken)
const { leave } = useLeaveRoom()

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

const playerId = computed(() => playerStore.playerId)
</script>

<template>
  <div class="game-page">
    <header class="game-header container">
      <div>
        <h1>Codenames</h1>
        <p class="muted">
          Room {{ roomId.slice(0, 8) }}...
          <span class="connection" :class="{ online: connected }">
            {{ connected ? '· Connected' : '· Reconnecting...' }}
          </span>
        </p>
      </div>
      <div class="header-actions">
        <button type="button" class="btn-secondary" @click="leave(disconnect)">Leave</button>
        <button type="button" class="btn-secondary" @click="showRules = true">Rules</button>
      </div>
    </header>

    <div class="av-callout container">
      <div class="card av-inner">
        Use your favorite audio or video chat to talk with teammates.
      </div>
    </div>

    <CodenamesBoard
      v-if="gameState && room"
      :game-state="gameState"
      :room="room"
      :player-id="playerId"
      @action="send"
    />

    <div v-else class="container loading">
      <p>Loading game...</p>
    </div>

    <div v-if="toast" class="toast error">{{ toast }}</div>

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
  padding-bottom: 2rem;
}

.game-header {
  padding-top: 1.5rem;
  margin-bottom: 1rem;
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 1rem;
}

.game-header h1 {
  font-size: 1.5rem;
}

.header-actions {
  display: flex;
  gap: 0.5rem;
}

.muted {
  color: var(--text-muted);
  font-size: 0.85rem;
}

.connection {
  color: var(--error);
}

.connection.online {
  color: var(--success);
}

.av-callout {
  margin-bottom: 1rem;
}

.av-inner {
  font-size: 0.85rem;
  color: var(--text-muted);
  text-align: center;
  padding: 0.75rem;
}

.loading {
  text-align: center;
  padding: 4rem;
  color: var(--text-muted);
}
</style>
