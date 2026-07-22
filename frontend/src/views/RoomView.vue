<script setup lang="ts">
import { ref, computed, watch, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { usePlayerStore } from '@/stores/player'
import { useRoom } from '@/composables/useRoom'
import { useWebSocket } from '@/composables/useWebSocket'
import { useLeaveRoom } from '@/composables/useLeaveRoom'
import GameRulesModal from '@/components/GameRulesModal.vue'
import ShareInvite from '@/components/ShareInvite.vue'
import PokerHandsModal from '@/games/poker/PokerHandsModal.vue'
import LobbyTeamPanel from '@/components/lobby/LobbyTeamPanel.vue'
import SpyfallLobby from '@/games/spyfall/SpyfallLobby.vue'
import SnakeLobby from '@/games/snake/SnakeLobby.vue'
import BombermanLobby from '@/games/bomberman/BombermanLobby.vue'
import DuelLobby from '@/games/duel/DuelLobby.vue'
import TetrisLobby from '@/games/tetris/TetrisLobby.vue'
import GravityMasterLobby from '@/games/gravity_master/GravityMasterLobby.vue'
import PokerLobby from '@/games/poker/PokerLobby.vue'
import ChessLobby from '@/games/chess/ChessLobby.vue'
import GoLobby from '@/games/go/GoLobby.vue'
import RoboRallyLobby from '@/games/roborally/RoboRallyLobby.vue'
import Connect4Lobby from '@/games/connect4/Connect4Lobby.vue'
import BattleshipLobby from '@/games/battleship/BattleshipLobby.vue'
import SolitaireLobby from '@/games/solitaire/SolitaireLobby.vue'
import { validateLobby as validateCodenamesLobby, teamOperatives, teamSpymaster } from '@/games/codenames/lobbyValidation'
import { validateLobby as validateSpyfallLobby } from '@/games/spyfall/lobbyValidation'
import { validateLobby as validateSnakeLobby } from '@/games/snake/lobbyValidation'
import { validateLobby as validateBombermanLobby } from '@/games/bomberman/lobbyValidation'
import { validateLobby as validateDuelLobby } from '@/games/duel/lobbyValidation'
import { validateLobby as validateTetrisLobby } from '@/games/tetris/lobbyValidation'
import { validateLobby as validateGravityMasterLobby } from '@/games/gravity_master/lobbyValidation'
import { validateLobby as validatePokerLobby } from '@/games/poker/lobbyValidation'
import { validateLobby as validateChessLobby } from '@/games/chess/lobbyValidation'
import { validateLobby as validateGoLobby } from '@/games/go/lobbyValidation'
import { validateLobby as validateRoboRallyLobby } from '@/games/roborally/lobbyValidation'
import { validateLobby as validateConnect4Lobby } from '@/games/connect4/lobbyValidation'
import { validateLobby as validateBattleshipLobby } from '@/games/battleship/lobbyValidation'
import { validateLobby as validateSolitaireLobby } from '@/games/solitaire/lobbyValidation'
import { getGameMeta } from '@/games/gameMeta'
import type { Room } from '@/types'

const route = useRoute()
const router = useRouter()
const playerStore = usePlayerStore()
const { fetchRoom, joinRoom, loading: joinLoading } = useRoom()

const room = ref<Room | null>(null)
const joinNickname = ref(playerStore.nickname || '')
const needsJoin = ref(false)
const toast = ref('')
const showRules = ref(false)
const showPokerHands = ref(false)

/** Route may be a short code (`/r/ABC123`) or UUID (`/room/<uuid>`). */
const roomRef = computed(
  () => (route.params.code as string | undefined) ?? (route.params.id as string),
)
/** WebSocket + play routes always use the canonical UUID. */
const roomUuid = computed(() => room.value?.id ?? '')

const wsToken = ref(playerStore.sessionToken)
const { connected, lastMessage, send, disconnect } = useWebSocket(roomUuid, wsToken)
const { leaveRoom } = useLeaveRoom()

onMounted(async () => {
  try {
    room.value = await fetchRoom(roomRef.value)
    if (room.value.status === 'playing') {
      router.replace(`/room/${room.value.id}/play`)
      return
    }
    if (!playerStore.sessionToken || playerStore.roomId !== room.value.id) {
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
    router.push(`/room/${msg.room.id}/play`)
  }
  if (msg.type === 'error') {
    toast.value = msg.message ?? 'Error'
    setTimeout(() => (toast.value = ''), 3000)
  }
})

// Refresh RoboRally map catalog for lobbies created before available_maps existed.
watch(
  () => [room.value, connected.value] as const,
  ([r, isConnected]) => {
    if (!isConnected || !r || r.game_type !== 'roborally' || r.status !== 'lobby') return
    if (r.host_player_id !== playerStore.playerId) return
    const maps = r.settings?.available_maps
    if (Array.isArray(maps) && maps.length > 0) return
    send({
      type: 'update_settings',
      settings: { map_id: String(r.settings?.map_id ?? 'factory_floor') },
    })
  },
)

const isHost = computed(() => room.value?.host_player_id === playerStore.playerId)

const isSpyfall = computed(() => room.value?.game_type === 'spyfall')
const isSnake = computed(() => room.value?.game_type === 'snake')
const isBomberman = computed(() => room.value?.game_type === 'bomberman')
const isDuel = computed(() => room.value?.game_type === 'duel')
const isTetris = computed(() => room.value?.game_type === 'tetris')
const isGravityMaster = computed(() => room.value?.game_type === 'gravity_master')
const isPoker = computed(() => room.value?.game_type === 'poker')
const isChess = computed(() => room.value?.game_type === 'chess')
const isGo = computed(() => room.value?.game_type === 'go')
const isRoboRally = computed(() => room.value?.game_type === 'roborally')
const isConnect4 = computed(() => room.value?.game_type === 'connect4')
const isBattleship = computed(() => room.value?.game_type === 'battleship')
const isSolitaire = computed(() => room.value?.game_type === 'solitaire')
const isCodenames = computed(() => room.value?.game_type === 'codenames')

const gameMeta = computed(() => getGameMeta(room.value?.game_type ?? ''))

const lobbyValidation = computed(() => {
  if (!room.value) return { valid: false, message: '', issues: [] }
  if (room.value.game_type === 'spyfall') return validateSpyfallLobby(room.value)
  if (room.value.game_type === 'snake') return validateSnakeLobby(room.value)
  if (room.value.game_type === 'bomberman') return validateBombermanLobby(room.value)
  if (room.value.game_type === 'duel') return validateDuelLobby(room.value)
  if (room.value.game_type === 'tetris') return validateTetrisLobby(room.value)
  if (room.value.game_type === 'gravity_master') return validateGravityMasterLobby(room.value)
  if (room.value.game_type === 'poker') return validatePokerLobby(room.value)
  if (room.value.game_type === 'chess') return validateChessLobby(room.value)
  if (room.value.game_type === 'go') return validateGoLobby(room.value)
  if (room.value.game_type === 'roborally') return validateRoboRallyLobby(room.value)
  if (room.value.game_type === 'connect4') return validateConnect4Lobby(room.value)
  if (room.value.game_type === 'battleship') return validateBattleshipLobby(room.value)
  if (room.value.game_type === 'solitaire') return validateSolitaireLobby(room.value)
  return validateCodenamesLobby(room.value)
})

const soloPractice = computed({
  get: () => Boolean(room.value?.settings?.solo_practice),
  set: (val: boolean) =>
    updateSettings({
      solo_practice: val,
      ...(val ? { single_player: false, same_room: false } : {}),
    }),
})

const sameRoom = computed({
  get: () => Boolean(room.value?.settings?.same_room),
  set: (val: boolean) =>
    updateSettings({
      same_room: val,
      ...(val ? { solo_practice: false } : {}),
    }),
})

const singlePlayer = computed({
  get: () => Boolean(room.value?.settings?.single_player),
  set: (val: boolean) => updateSettings({ single_player: val, ...(val ? { solo_practice: false } : {}) }),
})

const tickMs = computed({
  get: () =>
    Number(
      room.value?.settings?.tick_ms ??
        (room.value?.game_type === 'duel' ? 75 : room.value?.game_type === 'snake' ? 130 : room.value?.game_type === 'bomberman' ? 150 : 150),
    ),
  set: (val: number) => updateSettings({ tick_ms: val }),
})

const duelMatchFormat = computed({
  get: () => String(room.value?.settings?.match_format ?? 'best_of_5'),
  set: (val: string) => updateSettings({ match_format: val }),
})

const baseDropTicks = computed({
  get: () => Number(room.value?.settings?.base_drop_ticks ?? 20),
  set: (val: number) => updateSettings({ base_drop_ticks: val }),
})

const startingChips = computed({
  get: () => Number(room.value?.settings?.starting_chips ?? 1000),
  set: (val: number) => updateSettings({ starting_chips: val }),
})

const smallBlind = computed({
  get: () => Number(room.value?.settings?.small_blind ?? 5),
  set: (val: number) => updateSettings({ small_blind: val }),
})

const bigBlind = computed({
  get: () => Number(room.value?.settings?.big_blind ?? 10),
  set: (val: number) => updateSettings({ big_blind: val }),
})

const aiDifficulty = computed({
  get: () => String(room.value?.settings?.ai_difficulty ?? 'medium'),
  set: (val: string) => updateSettings({ ai_difficulty: val }),
})

const mapId = computed({
  get: () => String(room.value?.settings?.map_id ?? 'factory_floor'),
  set: (val: string) => updateSettings({ map_id: val }),
})

const registerSize = computed({
  get: () => Number(room.value?.settings?.register_size ?? 5),
  set: (val: number) => updateSettings({ register_size: val }),
})

const drawCount = computed({
  get: () => Number(room.value?.settings?.draw_count ?? 1),
  set: (val: number) => updateSettings({ draw_count: val }),
})

const soloAiDifficulties = computed({
  get: () => {
    const raw = room.value?.settings?.solo_ai_difficulties
    const isPokerRoom = room.value?.game_type === 'poker'
    const defaultLevel = isPokerRoom ? 'medium' : 'normal'
    const maxAi = isPokerRoom
      ? 2
      : Math.max(0, Number(room.value?.settings?.max_players ?? 4) - 1)
    if (Array.isArray(raw) && raw.length >= maxAi) {
      return raw.slice(0, maxAi).map(String)
    }
    return Array.from({ length: maxAi }, () => defaultLevel)
  },
  set: (val: string[]) => {
    const isPokerRoom = room.value?.game_type === 'poker'
    const maxAi = isPokerRoom
      ? 2
      : Math.max(0, Number(room.value?.settings?.max_players ?? 4) - 1)
    updateSettings({ solo_ai_difficulties: val.slice(0, maxAi) })
  },
})

async function handleJoin() {
  if (!joinNickname.value.trim()) return
  const result = await joinRoom(roomRef.value, joinNickname.value.trim())
  playerStore.saveSession({
    nickname: joinNickname.value.trim(),
    sessionToken: result.session_token,
    playerId: result.player_id,
    roomId: result.room_id,
  })
  needsJoin.value = false
  wsToken.value = result.session_token
  room.value = await fetchRoom(result.room_id)
}

function updateSettings(settings: Record<string, unknown>) {
  send({ type: 'update_settings', settings })
}

function setAiDifficulty(playerId: string, difficulty: string) {
  const current = (room.value?.settings?.ai_difficulties ?? {}) as Record<string, string>
  updateSettings({
    ai_difficulties: { ...current, [playerId]: difficulty },
  })
}

function addAi(team?: string, role?: string) {
  if (team && role) {
    send({ type: 'add_ai_player', team, role })
  } else {
    send({ type: 'add_ai_player' })
  }
}

function fillCodenamesWithAi() {
  if (!room.value) return
  const players = room.value.players
  if (!teamSpymaster(players, 'blue')) addAi('blue', 'spymaster')
  if (teamOperatives(players, 'red').length === 0) addAi('red', 'operative')
  if (teamOperatives(players, 'blue').length === 0) addAi('blue', 'operative')
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
        <div class="header-title">
          <h1>Lobby</h1>
          <div class="meta-row">
            <span class="game-tag">{{ gameMeta.emoji }} {{ gameMeta.name }}</span>
            <span class="player-count">{{ room.players.length }} players</span>
            <span class="connection" :class="{ online: connected }">
              <span class="connection-dot" />
              {{ connected ? 'Connected' : 'Reconnecting...' }}
            </span>
          </div>
        </div>
        <div class="header-actions">
          <button type="button" class="btn-secondary" @click="leaveRoom(disconnect)">Leave</button>
          <button v-if="isPoker" type="button" class="btn-secondary" @click="showPokerHands = true">
            Hand rankings
          </button>
          <button type="button" class="btn-secondary" @click="showRules = true">Rules</button>
        </div>
      </header>

      <p class="lobby-game-hint">{{ gameMeta.lobbyHint }}</p>

      <div class="toolbar card">
        <div class="share-block">
          <ShareInvite v-if="room.code" :code="room.code" :game-name="gameMeta.name" />
        </div>
        <div v-if="isHost && isCodenames" class="settings-block">
          <span class="toolbar-label">Host settings</span>
          <label class="checkbox-label">
            <input type="checkbox" v-model="soloPractice" />
            Solo practice (play against AI)
          </label>
        </div>
        <p v-else-if="!isHost" class="av-tip">
          💬 Use Discord, Zoom, or your favorite chat while you play
        </p>
      </div>

      <SpyfallLobby
        v-if="isSpyfall"
        v-model:solo-practice="soloPractice"
        v-model:same-room="sameRoom"
        :room="room"
        :is-host="isHost"
        :current-player-id="playerStore.playerId"
        :host-player-id="room.host_player_id"
        :validation-message="lobbyValidation.message"
        :validation-valid="lobbyValidation.valid"
        :validation-issues="lobbyValidation.issues"
        @add-ai="addAi()"
        @remove="removePlayer"
      />

      <SnakeLobby
        v-else-if="isSnake"
        v-model:solo-practice="soloPractice"
        v-model:tick-ms="tickMs"
        :room="room"
        :is-host="isHost"
        :current-player-id="playerStore.playerId"
        :host-player-id="room.host_player_id"
        :validation-message="lobbyValidation.message"
        :validation-valid="lobbyValidation.valid"
        :validation-issues="lobbyValidation.issues"
        @add-ai="addAi()"
        @remove="removePlayer"
      />

      <BombermanLobby
        v-else-if="isBomberman"
        v-model:solo-practice="soloPractice"
        v-model:tick-ms="tickMs"
        :room="room"
        :is-host="isHost"
        :current-player-id="playerStore.playerId"
        :host-player-id="room.host_player_id"
        :validation-message="lobbyValidation.message"
        :validation-valid="lobbyValidation.valid"
        :validation-issues="lobbyValidation.issues"
        @add-ai="addAi()"
        @remove="removePlayer"
      />

      <DuelLobby
        v-else-if="isDuel"
        v-model:solo-practice="soloPractice"
        v-model:match-format="duelMatchFormat"
        v-model:ai-difficulty="aiDifficulty"
        :room="room"
        :is-host="isHost"
        :current-player-id="playerStore.playerId"
        :host-player-id="room.host_player_id"
        :validation-message="lobbyValidation.message"
        :validation-valid="lobbyValidation.valid"
        :validation-issues="lobbyValidation.issues"
        @add-ai="addAi()"
        @remove="removePlayer"
      />

      <TetrisLobby
        v-else-if="isTetris"
        v-model:solo-practice="soloPractice"
        v-model:single-player="singlePlayer"
        v-model:base-drop-ticks="baseDropTicks"
        v-model:solo-ai-difficulties="soloAiDifficulties"
        :room="room"
        :is-host="isHost"
        :current-player-id="playerStore.playerId"
        :host-player-id="room.host_player_id"
        :validation-message="lobbyValidation.message"
        :validation-valid="lobbyValidation.valid"
        :validation-issues="lobbyValidation.issues"
        @add-ai="addAi()"
        @remove="removePlayer"
        @set-ai-difficulty="setAiDifficulty"
      />

      <PokerLobby
        v-else-if="isPoker"
        v-model:solo-practice="soloPractice"
        v-model:starting-chips="startingChips"
        v-model:small-blind="smallBlind"
        v-model:big-blind="bigBlind"
        v-model:ai-difficulty="aiDifficulty"
        v-model:solo-ai-difficulties="soloAiDifficulties"
        :room="room"
        :is-host="isHost"
        :current-player-id="playerStore.playerId"
        :host-player-id="room.host_player_id"
        :validation-message="lobbyValidation.message"
        :validation-valid="lobbyValidation.valid"
        :validation-issues="lobbyValidation.issues"
        @add-ai="addAi()"
        @remove="removePlayer"
        @set-ai-difficulty="setAiDifficulty"
      />

      <ChessLobby
        v-else-if="isChess"
        v-model:solo-practice="soloPractice"
        v-model:ai-difficulty="aiDifficulty"
        :room="room"
        :is-host="isHost"
        :current-player-id="playerStore.playerId"
        :host-player-id="room.host_player_id"
        :validation-message="lobbyValidation.message"
        :validation-valid="lobbyValidation.valid"
        :validation-issues="lobbyValidation.issues"
        @add-ai="addAi()"
        @remove="removePlayer"
      />

      <GoLobby
        v-else-if="isGo"
        v-model:solo-practice="soloPractice"
        v-model:ai-difficulty="aiDifficulty"
        :room="room"
        :is-host="isHost"
        :current-player-id="playerStore.playerId"
        :host-player-id="room.host_player_id"
        :validation-message="lobbyValidation.message"
        :validation-valid="lobbyValidation.valid"
        :validation-issues="lobbyValidation.issues"
        @add-ai="addAi()"
        @remove="removePlayer"
      />

      <RoboRallyLobby
        v-else-if="isRoboRally"
        v-model:solo-practice="soloPractice"
        v-model:map-id="mapId"
        v-model:register-size="registerSize"
        v-model:ai-difficulty="aiDifficulty"
        :room="room"
        :is-host="isHost"
        :current-player-id="playerStore.playerId"
        :host-player-id="room.host_player_id"
        :validation-message="lobbyValidation.message"
        :validation-valid="lobbyValidation.valid"
        :validation-issues="lobbyValidation.issues"
        @add-ai="addAi()"
        @remove="removePlayer"
      />

      <Connect4Lobby
        v-else-if="isConnect4"
        v-model:solo-practice="soloPractice"
        v-model:ai-difficulty="aiDifficulty"
        :room="room"
        :is-host="isHost"
        :current-player-id="playerStore.playerId"
        :host-player-id="room.host_player_id"
        :validation-message="lobbyValidation.message"
        :validation-valid="lobbyValidation.valid"
        :validation-issues="lobbyValidation.issues"
        @add-ai="addAi()"
        @remove="removePlayer"
      />

      <BattleshipLobby
        v-else-if="isBattleship"
        v-model:solo-practice="soloPractice"
        v-model:ai-difficulty="aiDifficulty"
        :room="room"
        :is-host="isHost"
        :current-player-id="playerStore.playerId"
        :host-player-id="room.host_player_id"
        :validation-message="lobbyValidation.message"
        :validation-valid="lobbyValidation.valid"
        :validation-issues="lobbyValidation.issues"
        @add-ai="addAi()"
        @remove="removePlayer"
      />

      <GravityMasterLobby
        v-else-if="isGravityMaster"
        :room="room"
        :is-host="isHost"
        :current-player-id="playerStore.playerId"
        :host-player-id="room.host_player_id"
        :validation-message="lobbyValidation.message"
        :validation-valid="lobbyValidation.valid"
        :validation-issues="lobbyValidation.issues"
      />

      <SolitaireLobby
        v-else-if="isSolitaire"
        v-model:draw-count="drawCount"
        :room="room"
        :is-host="isHost"
        :current-player-id="playerStore.playerId"
        :host-player-id="room.host_player_id"
        :validation-message="lobbyValidation.message"
        :validation-valid="lobbyValidation.valid"
        :validation-issues="lobbyValidation.issues"
      />

      <template v-else-if="isCodenames">
        <div v-if="soloPractice" class="solo-notice card">
          <p>Solo practice auto-builds teams when you start. You will play as the red operative against AI.</p>
        </div>

        <template v-else>
          <p v-if="isHost" class="arrange-hint">
            You're set as Red Spymaster. Tap <em>Fill empty slots with AI</em> or use the per-slot buttons on each team.
          </p>

          <button
            v-if="isHost"
            type="button"
            class="btn-secondary fill-ai-btn"
            @click="fillCodenamesWithAi"
          >
            Fill empty slots with AI
          </button>

          <div class="teams stagger-in">
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
      </template>

      <button
        v-if="isHost"
        class="btn-primary start-btn"
        :class="{ ready: lobbyValidation.valid }"
        :disabled="!lobbyValidation.valid"
        @click="startGame"
      >
        Start Game →
      </button>
    </template>

    <Transition name="toast">
      <div v-if="toast" class="toast error">{{ toast }}</div>
    </Transition>

    <GameRulesModal
      v-if="showRules && room"
      :game-type="room.game_type"
      @close="showRules = false"
    />

    <PokerHandsModal v-if="showPokerHands" @close="showPokerHands = false" />
  </div>
</template>

<style scoped>
.lobby {
  padding-top: 1.5rem;
  padding-bottom: 3rem;
  max-width: 1280px;
}

.join-card {
  max-width: 400px;
  margin: 4rem auto;
  display: flex;
  flex-direction: column;
  gap: 1rem;
  animation: fadeInUp 0.5s var(--ease-smooth);
}

.lobby-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 1rem;
  margin-bottom: 1.25rem;
  animation: fadeInUp 0.4s var(--ease-smooth);
}

.lobby-header h1 {
  font-size: 2rem;
  font-weight: 700;
}

.lobby-game-hint {
  font-size: 0.9rem;
  color: var(--text-muted);
  margin: -0.5rem 0 1rem;
  line-height: 1.5;
}

.meta-row {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 0.6rem;
  margin-top: 0.35rem;
}

.game-tag {
  padding: 0.2rem 0.6rem;
  border-radius: 6px;
  font-size: 0.75rem;
  font-weight: 600;
  text-transform: uppercase;
  background: rgba(91, 156, 255, 0.15);
  color: var(--accent);
}

.player-count {
  font-size: 0.85rem;
  color: var(--text-muted);
}

.header-actions {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  flex-shrink: 0;
}

.muted {
  color: var(--text-muted);
  font-size: 0.9rem;
}

.connection {
  display: inline-flex;
  align-items: center;
  gap: 0.4rem;
  font-size: 0.8rem;
  color: var(--error);
  padding: 0.25rem 0.65rem;
  border-radius: 999px;
  background: rgba(255, 92, 108, 0.1);
}

.connection.online {
  color: var(--success);
  background: rgba(61, 214, 140, 0.1);
}

.connection-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: currentColor;
  animation: pulse-dot 2s ease-in-out infinite;
}

.connection.online .connection-dot {
  animation: pulse-dot 2s ease-in-out infinite;
}

@keyframes pulse-dot {
  0%, 100% { opacity: 1; transform: scale(1); }
  50% { opacity: 0.5; transform: scale(0.85); }
}

.toolbar {
  display: grid;
  grid-template-columns: 1fr;
  gap: 1rem;
  margin-bottom: 1.25rem;
  padding: 1.25rem;
  animation: fadeInUp 0.4s var(--ease-smooth) 0.05s backwards;
}

@media (min-width: 768px) {
  .toolbar {
    grid-template-columns: 1.4fr 1fr;
    align-items: end;
  }
}

.toolbar-label {
  display: block;
  font-size: 0.7rem;
  font-weight: 600;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  color: var(--text-muted);
  margin-bottom: 0.5rem;
}

.av-tip {
  font-size: 0.85rem;
  color: var(--text-muted);
  align-self: center;
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
  animation: fadeInUp 0.4s var(--ease-smooth);
}

.arrange-hint {
  margin-bottom: 1rem;
  font-size: 0.85rem;
  color: var(--text-muted);
}

.fill-ai-btn {
  margin-bottom: 1rem;
  width: 100%;
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
  padding: 1rem 1.25rem;
  transition: border-color 0.3s, background 0.3s, transform 0.3s var(--ease-bounce);
}

.validation-banner.valid {
  border-color: rgba(61, 214, 140, 0.4);
  background: rgba(61, 214, 140, 0.08);
}

.validation-banner.invalid {
  border-color: rgba(255, 92, 108, 0.35);
  background: rgba(255, 92, 108, 0.08);
}

.validation-icon {
  width: 1.75rem;
  height: 1.75rem;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: 700;
  font-size: 0.85rem;
  flex-shrink: 0;
  transition: transform 0.3s var(--ease-bounce);
}

.validation-banner.valid .validation-icon {
  background: rgba(61, 214, 140, 0.2);
  color: var(--success);
  animation: celebrate 0.5s var(--ease-bounce);
}

.validation-banner.invalid .validation-icon {
  background: rgba(255, 92, 108, 0.2);
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
  margin-top: 1.25rem;
  font-size: 1.15rem;
  padding: 1rem;
  transition: transform 0.2s, box-shadow 0.3s;
}

.start-btn.ready {
  animation: glowPulse 2.5s ease-in-out infinite;
}

.start-btn.ready:hover:not(:disabled) {
  transform: translateY(-3px) scale(1.01);
}

.toast-enter-active {
  animation: toastIn 0.4s var(--ease-bounce);
}

.toast-leave-active {
  animation: toastIn 0.25s reverse;
}
</style>
