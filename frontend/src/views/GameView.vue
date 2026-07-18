<script setup lang="ts">
import { computed, ref, watch, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { usePlayerStore } from '@/stores/player'
import { useRoom } from '@/composables/useRoom'
import { useWebSocket } from '@/composables/useWebSocket'
import CodenamesBoard from '@/games/codenames/CodenamesBoard.vue'
import SpyfallBoard from '@/games/spyfall/SpyfallBoard.vue'
import SnakeBoard from '@/games/snake/SnakeBoard.vue'
import DuelBoard from '@/games/duel/DuelBoard.vue'
import TetrisBoard from '@/games/tetris/TetrisBoard.vue'
import GravityMasterBoard from '@/games/gravity_master/GravityMasterBoard.vue'
import PokerBoard from '@/games/poker/PokerBoard.vue'
import ChessBoard from '@/games/chess/ChessBoard.vue'
import GoBoard from '@/games/go/GoBoard.vue'
import RoboRallyBoard from '@/games/roborally/RoboRallyBoard.vue'
import Connect4Board from '@/games/connect4/Connect4Board.vue'
import BattleshipBoard from '@/games/battleship/BattleshipBoard.vue'
import SolitaireBoard from '@/games/solitaire/SolitaireBoard.vue'
import { useGoClientSolo } from '@/composables/useGoClientSolo'
import GameRulesModal from '@/components/GameRulesModal.vue'
import PokerHandsModal from '@/games/poker/PokerHandsModal.vue'
import type { PokerReaction } from '@/games/poker/reactions'
import { pokerReactionSet } from '@/games/poker/reactions'
import type { Room, GameState, CodenamesGameState, SpyfallGameState, SnakeGameState, DuelGameState, TetrisGameState, GravityMasterGameState, PokerGameState, ChessGameState, GoGameState, RoboRallyGameState, Connect4GameState, BattleshipGameState, SolitaireGameState } from '@/types'
import { isCodenamesState, isSpyfallState, isSnakeState, isDuelState, isTetrisState, isGravityMasterState, isPokerState, isChessState, isGoState, isRoboRallyState, isConnect4State, isBattleshipState, isSolitaireState } from '@/types'

const route = useRoute()
const router = useRouter()
const playerStore = usePlayerStore()
const { fetchRoom } = useRoom()

const roomId = computed(() => route.params.id as string)
const room = ref<Room | null>(null)
const gameState = ref<GameState | null>(null)
const toast = ref('')
const showRules = ref(false)
const showPokerHands = ref(false)
const pokerReactions = ref<PokerReaction[]>([])

const wsToken = computed(() => playerStore.sessionToken)
const { connected, lastMessage, error, send } = useWebSocket(roomId, wsToken)

const gameTitle = computed(() => {
  const type = room.value?.game_type
  if (type === 'spyfall') return 'Spyfall'
  if (type === 'codenames') return 'Codenames'
  if (type === 'snake') return 'Multiplayer Snake'
  if (type === 'duel') return 'Side Duel'
  if (type === 'tetris') return 'Multiplier Tetris'
  if (type === 'gravity_master') return 'Gravity Master'
  if (type === 'poker') return 'Poker'
  if (type === 'chess') return 'Chess'
  if (type === 'go') return 'Go'
  if (type === 'roborally') return 'RoboRally'
  if (type === 'connect4') return 'Connect Four'
  if (type === 'battleship') return 'Battleship'
  if (type === 'solitaire') return 'Solitaire'
  return type ?? 'Game'
})

const codenamesState = computed(() =>
  gameState.value && isCodenamesState(gameState.value) ? gameState.value as CodenamesGameState : null,
)

const spyfallState = computed(() =>
  gameState.value && isSpyfallState(gameState.value) ? gameState.value as SpyfallGameState : null,
)

const snakeState = computed(() =>
  gameState.value && isSnakeState(gameState.value) ? gameState.value as SnakeGameState : null,
)

const duelState = computed(() =>
  gameState.value && isDuelState(gameState.value) ? gameState.value as DuelGameState : null,
)

const duelInputSuspended = computed(() => showRules.value || showPokerHands.value)

const tetrisState = computed(() =>
  gameState.value && isTetrisState(gameState.value) ? gameState.value as TetrisGameState : null,
)

const gravityMasterState = computed(() =>
  gameState.value && isGravityMasterState(gameState.value) ? gameState.value as GravityMasterGameState : null,
)

const pokerState = computed(() =>
  gameState.value && isPokerState(gameState.value) ? gameState.value as PokerGameState : null,
)

const chessState = computed(() =>
  gameState.value && isChessState(gameState.value) ? gameState.value as ChessGameState : null,
)

const goState = computed(() =>
  gameState.value && isGoState(gameState.value) ? gameState.value as GoGameState : null,
)

const roborallyState = computed(() =>
  gameState.value && isRoboRallyState(gameState.value) ? gameState.value as RoboRallyGameState : null,
)

const connect4State = computed(() =>
  gameState.value && isConnect4State(gameState.value) ? gameState.value as Connect4GameState : null,
)

const battleshipState = computed(() =>
  gameState.value && isBattleshipState(gameState.value) ? gameState.value as BattleshipGameState : null,
)

const solitaireState = computed(() =>
  gameState.value && isSolitaireState(gameState.value) ? gameState.value as SolitaireGameState : null,
)

const playerId = computed(() => playerStore.playerId)

const isPoker = computed(() => room.value?.game_type === 'poker')

const isRoboRally = computed(() => room.value?.game_type === 'roborally')

const isFullscreenGame = computed(() =>
  Boolean(snakeState.value || duelState.value || tetrisState.value || gravityMasterState.value || chessState.value || goState.value || roborallyState.value || connect4State.value || battleshipState.value || solitaireState.value),
)

const loadingMessage = computed(() => {
  if (!room.value) return 'Loading room...'
  if (room.value.status === 'playing' && !gameState.value) {
    return connected.value ? 'Waiting for game state...' : 'Connecting...'
  }
  return 'Loading game...'
})

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
  if (msg.type === 'game_started' && msg.room) {
    room.value = msg.room
  }
  if (msg.type === 'returned_to_lobby' && msg.room) {
    router.push(`/room/${roomId.value}`)
  }
  if (msg.type === 'error') {
    toast.value = msg.message ?? 'Error'
    setTimeout(() => (toast.value = ''), 3000)
  }
  if (msg.type === 'reaction' && msg.player_id && msg.emoji && pokerReactionSet.has(msg.emoji)) {
    const reaction: PokerReaction = {
      id: `${msg.player_id}-${Date.now()}-${Math.random().toString(36).slice(2, 7)}`,
      playerId: msg.player_id,
      nickname: msg.nickname ?? 'Player',
      emoji: msg.emoji,
    }
    pokerReactions.value = [...pokerReactions.value, reaction]
    setTimeout(() => {
      pokerReactions.value = pokerReactions.value.filter((entry) => entry.id !== reaction.id)
    }, 2400)
  }
}, { immediate: true })

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

useGoClientSolo(goState, playerId, sendAction)

function sendReaction(emoji: string) {
  sendAction({ type: 'reaction', emoji })
}

function backToLobby() {
  sendAction({ type: 'return_to_lobby' })
}
</script>

<template>
  <div
    class="game-page"
    :class="{
      'game-page--snake': isFullscreenGame,
      'game-page--poker': isPoker,
      'game-page--roborally': isRoboRally,
    }"
  >
    <header
      class="game-header"
      :class="{
        'game-header--snake': isFullscreenGame,
        'game-header--poker': isPoker,
        'game-header--roborally': isRoboRally,
      }"
    >
      <div class="header-left">
        <h1>{{ gameTitle }}</h1>
        <div class="header-meta">
          <span class="room-id">Room {{ roomId.slice(0, 8) }}…</span>
          <span class="connection" :class="{ online: connected }">
            <span class="connection-dot" />
            {{ connected ? 'Live' : 'Reconnecting' }}
          </span>
          <span v-if="room?.game_type !== 'duel' && room?.game_type !== 'roborally'" class="av-hint">💬 Voice chat optional — text Q&amp;A built in</span>
        </div>
      </div>
      <div class="header-actions">
        <button type="button" class="btn-secondary" @click="backToLobby">Lobby</button>
        <button v-if="isPoker" type="button" class="btn-secondary header-btn--compact" @click="showPokerHands = true">
          <span class="header-btn__full">Hand rankings</span>
          <span class="header-btn__short" aria-hidden="true">Hands</span>
        </button>
        <button type="button" class="btn-secondary" @click="showRules = true">Rules</button>
      </div>
    </header>

    <CodenamesBoard
      v-if="codenamesState && room"
      :game-state="codenamesState"
      :room="room"
      :player-id="playerStore.playerId"
      @action="sendAction"
    />

    <SpyfallBoard
      v-else-if="spyfallState && room"
      :game-state="spyfallState"
      :room="room"
      :player-id="playerStore.playerId"
      @action="sendAction"
      @show-rules="showRules = true"
    />

    <SnakeBoard
      v-else-if="snakeState && room"
      :game-state="snakeState"
      :room="room"
      :player-id="playerStore.playerId"
      @action="sendAction"
    />

    <DuelBoard
      v-else-if="duelState && room"
      :game-state="duelState"
      :room="room"
      :player-id="playerStore.playerId"
      :input-suspended="duelInputSuspended"
      @action="sendAction"
      @lobby="backToLobby"
      @show-rules="showRules = true"
    />

    <TetrisBoard
      v-else-if="tetrisState && room"
      :game-state="tetrisState"
      :room="room"
      :player-id="playerStore.playerId"
      @action="sendAction"
    />

    <GravityMasterBoard
      v-else-if="gravityMasterState && room"
      :game-state="gravityMasterState"
      :room="room"
      :player-id="playerStore.playerId"
      @action="sendAction"
    />

    <PokerBoard
      v-else-if="pokerState && room"
      :game-state="pokerState"
      :room="room"
      :player-id="playerStore.playerId"
      :reactions="pokerReactions"
      @action="sendAction"
      @reaction="sendReaction"
    />

    <ChessBoard
      v-else-if="chessState && room"
      :game-state="chessState"
      :room="room"
      :player-id="playerStore.playerId"
      @action="sendAction"
    />

    <GoBoard
      v-else-if="goState && room"
      :game-state="goState"
      :room="room"
      :player-id="playerStore.playerId"
      @action="sendAction"
    />

    <RoboRallyBoard
      v-else-if="roborallyState && room"
      :game-state="roborallyState"
      :room="room"
      :player-id="playerStore.playerId"
      @action="sendAction"
    />

    <Connect4Board
      v-else-if="connect4State && room"
      :game-state="connect4State"
      :room="room"
      :player-id="playerStore.playerId"
      @action="sendAction"
    />

    <BattleshipBoard
      v-else-if="battleshipState && room"
      :game-state="battleshipState"
      :room="room"
      :player-id="playerStore.playerId"
      @action="sendAction"
    />

    <SolitaireBoard
      v-else-if="solitaireState && room"
      :game-state="solitaireState"
      :room="room"
      :player-id="playerStore.playerId"
      @action="sendAction"
    />

    <div v-else class="container-wide loading">
      <div class="loading-spinner" />
      <p>{{ loadingMessage }}</p>
    </div>

    <Transition name="toast">
      <div v-if="toast" class="toast error">{{ toast }}</div>
    </Transition>

    <GameRulesModal
      v-if="showRules"
      :game-type="room?.game_type ?? 'codenames'"
      @close="showRules = false"
    />

    <PokerHandsModal v-if="showPokerHands" @close="showPokerHands = false" />
  </div>
</template>

<style scoped>
.game-page {
  min-height: 100vh;
  padding-bottom: 1.5rem;
}

.game-page--snake {
  display: flex;
  flex-direction: column;
  height: 100vh;
  min-height: 100vh;
  padding-bottom: 0;
  overflow: hidden;
}

.game-page--snake .game-header {
  flex-shrink: 0;
  margin-bottom: 0;
  padding: 0.75rem 1rem;
  border-bottom: 1px solid var(--border);
}

.game-page--roborally .game-header {
  padding: 0.35rem 0.75rem;
  border-bottom: 2px solid #c9a24a;
}

.game-page--roborally .game-header h1 {
  font-size: 1rem;
  letter-spacing: 0.04em;
  text-transform: uppercase;
}

.game-header--roborally .header-meta {
  margin-top: 0;
}

.game-header--roborally .header-meta .room-id,
.game-header--roborally .header-meta .connection {
  font-size: 0.75rem;
}

.game-page--roborally .av-hint {
  display: none;
}

.game-page--roborally .header-actions .btn-secondary {
  padding: 0.3rem 0.65rem;
  font-size: 0.78rem;
}

.game-header--snake {
  max-width: none;
  margin: 0;
}

.game-header:not(.game-header--snake) {
  padding-left: 1.5rem;
  padding-right: 1.5rem;
  max-width: 1440px;
  margin-left: auto;
  margin-right: auto;
  width: 100%;
}

.game-header {
  padding-top: 1rem;
  padding-bottom: 0.75rem;
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 1rem;
  animation: fadeInUp 0.4s var(--ease-smooth);
}

.game-header:not(.game-header--snake) {
  border-bottom: 1px solid var(--border);
  margin-bottom: 0.75rem;
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

.game-page--poker {
  padding-bottom: 0;
}

.game-header--poker {
  max-width: 1440px;
  margin-left: auto;
  margin-right: auto;
  width: 100%;
}

.header-btn__short {
  display: none;
}

@media (max-width: 640px) {
  .game-page--poker {
    padding-bottom: 0;
  }

  .game-header--poker {
    flex-wrap: wrap;
    align-items: flex-start;
    padding-top: 0.65rem;
    padding-bottom: 0.55rem;
    padding-inline: 0.75rem;
    gap: 0.55rem;
    margin-bottom: 0.35rem;
  }

  .game-header--poker h1 {
    font-size: 1.1rem;
  }

  .game-header--poker .header-meta {
    gap: 0.45rem;
  }

  .game-header--poker .av-hint {
    display: none;
  }

  .game-header--poker .header-actions {
    width: 100%;
    justify-content: stretch;
  }

  .game-header--poker .header-actions .btn-secondary {
    flex: 1;
    min-width: 0;
    padding: 0.45rem 0.5rem;
    font-size: 0.82rem;
    touch-action: manipulation;
  }

  .game-header--poker .header-btn__full {
    display: none;
  }

  .game-header--poker .header-btn__short {
    display: inline;
  }
}
</style>
