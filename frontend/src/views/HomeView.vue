<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { useRouter } from 'vue-router'
import { usePlayerStore } from '@/stores/player'
import { useRoom } from '@/composables/useRoom'
import GameRulesModal from '@/components/GameRulesModal.vue'
import {
  getGameMeta,
  listKnownGames,
  GAME_CATEGORIES,
  type GameCategory,
} from '@/games/gameMeta'

const router = useRouter()
const playerStore = usePlayerStore()
const { createRoom, joinRoom, fetchGames, loading, error } = useRoom()

const nickname = ref(playerStore.nickname || '')
const gameType = ref('codenames')
const games = ref(listKnownGames())
const joinRoomId = ref('')
const mode = ref<'create' | 'join'>('create')
const showRules = ref(false)
const categoryFilter = ref<GameCategory | 'all'>('all')

const selectedGameMeta = computed(() => getGameMeta(gameType.value))

const enrichedGames = computed(() =>
  games.value.map((g) => ({
    ...g,
    ...getGameMeta(g.id),
    name: g.name || getGameMeta(g.id).name,
    description: g.description || getGameMeta(g.id).description,
  })),
)

const filteredGames = computed(() => {
  if (categoryFilter.value === 'all') return enrichedGames.value
  return enrichedGames.value.filter((g) => g.category === categoryFilter.value)
})

const gameCountLabel = computed(() => {
  const n = games.value.length
  return `${n} game${n === 1 ? '' : 's'}`
})

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

function selectGame(id: string) {
  gameType.value = id
  if (mode.value !== 'create') mode.value = 'create'
}

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
    <header class="hero">
      <div class="hero-badge">Free · No signup · {{ gameCountLabel }}</div>
      <h1 class="title">
        <span class="title-word">Games</span><span class="title-accent">AI</span>
      </h1>
      <p class="tagline">
        Party nights, classics, and arcade battles — with AI that actually plays.
      </p>
      <div class="feature-chips stagger-in">
        <span class="chip">🤖 AI opponents</span>
        <span class="chip">🔗 Share a link</span>
        <span class="chip">⚡ Instant rooms</span>
      </div>
    </header>

    <section class="picker" aria-label="Choose a game">
      <div class="picker-head">
        <h2 class="picker-title">{{ mode === 'join' ? 'Joining a room' : 'Pick your game' }}</h2>
        <div class="mode-toggle" :class="mode">
          <button
            type="button"
            :class="['mode-btn', { active: mode === 'create' }]"
            :disabled="loading"
            @click="selectCreateMode"
          >
            New Game
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
      </div>

      <div v-show="mode === 'create'" class="create-panel">
        <div class="category-bar" role="tablist" aria-label="Filter by category">
          <button
            v-for="cat in GAME_CATEGORIES"
            :key="cat.id"
            type="button"
            role="tab"
            :aria-selected="categoryFilter === cat.id"
            :class="['cat-chip', { active: categoryFilter === cat.id }]"
            @click="categoryFilter = cat.id"
          >
            {{ cat.label }}
          </button>
        </div>

        <div class="game-grid stagger-in">
          <button
            v-for="(g, i) in filteredGames"
            :key="g.id"
            type="button"
            class="game-tile"
            :class="{ selected: gameType === g.id }"
            :style="{ '--tile-accent': g.accent, '--stagger': `${i * 40}ms` }"
            @click="selectGame(g.id)"
          >
            <span class="tile-emoji" aria-hidden="true">{{ g.emoji }}</span>
            <span class="tile-body">
              <span class="tile-name">{{ g.name }}</span>
              <span class="tile-meta">{{ g.players }}</span>
            </span>
            <span v-if="gameType === g.id" class="tile-check" aria-hidden="true">✓</span>
          </button>
        </div>

        <Transition name="field" mode="out-in">
          <div
            v-if="selectedGameMeta"
            :key="gameType"
            class="selected-banner"
            :style="{ '--tile-accent': selectedGameMeta.accent }"
          >
            <span class="banner-emoji" aria-hidden="true">{{ selectedGameMeta.emoji }}</span>
            <div class="banner-copy">
              <strong>{{ selectedGameMeta.name }}</strong>
              <p>{{ selectedGameMeta.description }}</p>
            </div>
            <button type="button" class="btn-secondary rules-btn" @click="showRules = true">
              Rules
            </button>
          </div>
        </Transition>
      </div>

      <div v-show="mode === 'join'" class="join-panel">
        <p class="hint">Paste the room ID from your friend's link — game type is set by the host.</p>
        <label>
          Room ID
          <input
            v-model="joinRoomId"
            placeholder="Paste room ID from URL"
            @keyup.enter="enterGame"
          />
        </label>
      </div>
    </section>

    <aside class="launch card">
      <label>
        Nickname
        <input
          v-model="nickname"
          placeholder="Your nickname"
          maxlength="50"
          @keyup.enter="enterGame"
        />
      </label>

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
        <template v-if="loading">Please wait...</template>
        <template v-else-if="mode === 'create'">
          <span class="enter-emoji" aria-hidden="true">{{ selectedGameMeta.emoji }}</span>
          Play {{ selectedGameMeta.name }}
        </template>
        <template v-else>Join Game</template>
      </button>
    </aside>

    <GameRulesModal v-if="showRules" :game-type="gameType" @close="showRules = false" />
  </div>
</template>

<style scoped>
.home {
  min-height: 100vh;
  max-width: 960px;
  margin: 0 auto;
  padding: 2.5rem 1.5rem 3rem;
  display: flex;
  flex-direction: column;
  gap: 2rem;
}

.hero {
  animation: fadeInUp 0.6s var(--ease-smooth);
  text-align: center;
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
  margin-bottom: 1rem;
}

.title {
  font-size: clamp(2.75rem, 7vw, 4.25rem);
  font-weight: 800;
  line-height: 1.05;
  margin-bottom: 0.75rem;
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
  font-size: 1.15rem;
  max-width: 480px;
  margin: 0 auto 1.25rem;
}

.feature-chips {
  display: flex;
  flex-wrap: wrap;
  justify-content: center;
  gap: 0.55rem;
}

.chip {
  padding: 0.4rem 0.85rem;
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

.picker {
  animation: fadeInUp 0.55s var(--ease-smooth) 0.08s both;
}

.picker-head {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: 1rem;
  margin-bottom: 1.25rem;
}

.picker-title {
  font-size: 1.35rem;
  font-weight: 700;
}

.mode-toggle {
  position: relative;
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 0;
  padding: 4px;
  min-width: 220px;
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
  left: 50%;
}

.mode-btn {
  position: relative;
  z-index: 1;
  padding: 0.55rem 0.75rem;
  background: transparent;
  color: var(--text-muted);
  border: none;
  border-radius: 9px;
  font-weight: 500;
  font-size: 0.9rem;
}

.mode-btn.active {
  color: var(--text);
  font-weight: 600;
}

.mode-btn:disabled {
  opacity: 0.7;
  cursor: wait;
}

.category-bar {
  display: flex;
  flex-wrap: wrap;
  gap: 0.45rem;
  margin-bottom: 1rem;
}

.cat-chip {
  padding: 0.4rem 0.9rem;
  border-radius: 999px;
  font-size: 0.8rem;
  font-weight: 600;
  background: transparent;
  color: var(--text-muted);
  border: 1px solid var(--border);
}

.cat-chip:hover {
  border-color: var(--accent);
  color: var(--text);
}

.cat-chip.active {
  background: rgba(91, 156, 255, 0.15);
  border-color: rgba(91, 156, 255, 0.45);
  color: var(--accent);
  box-shadow: 0 0 0 1px rgba(91, 156, 255, 0.1);
}

.game-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 0.65rem;
}

@media (min-width: 640px) {
  .game-grid {
    grid-template-columns: repeat(3, 1fr);
    gap: 0.75rem;
  }
}

@media (min-width: 900px) {
  .game-grid {
    grid-template-columns: repeat(4, 1fr);
  }
}

.game-tile {
  position: relative;
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 0.65rem;
  padding: 1rem 0.9rem 0.9rem;
  text-align: left;
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  color: var(--text);
  overflow: hidden;
  animation: tileIn 0.45s var(--ease-smooth) both;
  animation-delay: var(--stagger, 0ms);
  transition:
    transform 0.2s var(--ease-bounce),
    border-color 0.2s,
    box-shadow 0.2s,
    background 0.2s;
}

.game-tile::before {
  content: '';
  position: absolute;
  inset: 0 0 auto 0;
  height: 3px;
  background: var(--tile-accent, var(--accent));
  opacity: 0.55;
  transition: opacity 0.2s, height 0.2s;
}

.game-tile:hover {
  transform: translateY(-3px) scale(1.02);
  border-color: color-mix(in srgb, var(--tile-accent, var(--accent)) 55%, var(--border));
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.3);
  background: var(--surface-hover);
}

.game-tile.selected {
  border-color: var(--tile-accent, var(--accent));
  box-shadow:
    0 0 0 1px var(--tile-accent, var(--accent)),
    0 8px 28px color-mix(in srgb, var(--tile-accent, var(--accent)) 28%, transparent);
  background: color-mix(in srgb, var(--tile-accent, var(--accent)) 10%, var(--surface));
}

.game-tile.selected::before {
  opacity: 1;
  height: 4px;
}

.tile-emoji {
  font-size: 1.75rem;
  line-height: 1;
  filter: drop-shadow(0 2px 6px rgba(0, 0, 0, 0.35));
  transition: transform 0.25s var(--ease-bounce);
}

.game-tile:hover .tile-emoji,
.game-tile.selected .tile-emoji {
  transform: scale(1.12) rotate(-4deg);
}

.tile-body {
  display: flex;
  flex-direction: column;
  gap: 0.15rem;
  min-width: 0;
  width: 100%;
}

.tile-name {
  font-family: 'Outfit', 'DM Sans', system-ui, sans-serif;
  font-weight: 700;
  font-size: 0.95rem;
  line-height: 1.2;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.tile-meta {
  font-size: 0.75rem;
  font-weight: 500;
  color: var(--text-muted);
}

.tile-check {
  position: absolute;
  top: 0.55rem;
  right: 0.55rem;
  width: 1.35rem;
  height: 1.35rem;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 50%;
  font-size: 0.7rem;
  font-weight: 700;
  background: var(--tile-accent, var(--accent));
  color: #0a0e17;
  animation: popIn 0.3s var(--ease-bounce);
}

.selected-banner {
  display: flex;
  align-items: center;
  gap: 0.9rem;
  margin-top: 1rem;
  padding: 0.9rem 1rem;
  border-radius: var(--radius);
  border: 1px solid color-mix(in srgb, var(--tile-accent, var(--accent)) 40%, var(--border));
  background: color-mix(in srgb, var(--tile-accent, var(--accent)) 8%, var(--surface));
}

.banner-emoji {
  font-size: 2rem;
  line-height: 1;
  flex-shrink: 0;
}

.banner-copy {
  flex: 1;
  min-width: 0;
}

.banner-copy strong {
  font-family: 'Outfit', 'DM Sans', system-ui, sans-serif;
  font-size: 1.05rem;
  display: block;
  margin-bottom: 0.15rem;
}

.banner-copy p {
  margin: 0;
  font-size: 0.85rem;
  color: var(--text-muted);
  line-height: 1.4;
}

.rules-btn {
  flex-shrink: 0;
  padding: 0.55rem 0.9rem;
  font-size: 0.85rem;
}

.join-panel {
  display: flex;
  flex-direction: column;
  gap: 1rem;
  padding: 1.25rem;
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius);
}

.hint {
  color: var(--text-muted);
  font-size: 0.9rem;
  margin: 0;
}

.launch {
  animation: fadeInUp 0.5s var(--ease-smooth) 0.16s both;
  display: flex;
  flex-direction: column;
  gap: 0.85rem;
  padding: 1.25rem;
}

@media (min-width: 640px) {
  .launch {
    flex-direction: row;
    align-items: flex-end;
    gap: 1rem;
  }

  .launch label {
    flex: 1;
  }

  .enter-btn {
    flex-shrink: 0;
    width: auto;
    min-width: 220px;
  }
}

label {
  display: flex;
  flex-direction: column;
  gap: 0.4rem;
  font-size: 0.85rem;
  font-weight: 500;
  color: var(--text-muted);
}

.enter-btn {
  width: 100%;
  font-size: 1.05rem;
  letter-spacing: 0.02em;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 0.5rem;
  white-space: nowrap;
}

.enter-emoji {
  font-size: 1.15rem;
  line-height: 1;
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
  margin: 0;
}

@keyframes tileIn {
  from {
    opacity: 0;
    transform: translateY(10px) scale(0.96);
  }
  to {
    opacity: 1;
    transform: translateY(0) scale(1);
  }
}

@keyframes popIn {
  from {
    opacity: 0;
    transform: scale(0.4);
  }
  to {
    opacity: 1;
    transform: scale(1);
  }
}

@media (max-width: 480px) {
  .selected-banner {
    flex-wrap: wrap;
  }

  .rules-btn {
    width: 100%;
  }

  .picker-head {
    flex-direction: column;
    align-items: stretch;
  }

  .mode-toggle {
    min-width: 0;
  }
}
</style>
