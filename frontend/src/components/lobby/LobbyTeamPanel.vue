<script setup lang="ts">
import { computed } from 'vue'
import type { Player } from '@/types'
import { teamOperatives, teamSpymaster } from '@/games/codenames/lobbyValidation'

const props = defineProps<{
  team: 'red' | 'blue'
  players: Player[]
  isHost: boolean
  currentPlayerId: string
  hostPlayerId: string | null
}>()

const emit = defineEmits<{
  assign: [playerId: string, team: 'red' | 'blue', role: 'spymaster' | 'operative']
  addAi: [team: 'red' | 'blue', role: 'spymaster' | 'operative']
  remove: [playerId: string]
}>()

const otherTeam = computed(() => (props.team === 'red' ? 'blue' : 'red'))
const spymaster = computed(() => teamSpymaster(props.players, props.team))
const operatives = computed(() => teamOperatives(props.players, props.team))

function isYou(player: Player) {
  return player.id === props.currentPlayerId
}

function isHost(player: Player) {
  return player.id === props.hostPlayerId
}

function moveToOtherTeam(player: Player) {
  emit('assign', player.id, otherTeam.value, player.role ?? 'operative')
}

function setRole(player: Player, role: 'spymaster' | 'operative') {
  emit('assign', player.id, props.team, role)
}

function displayName(player: Player) {
  if (player.is_ai && player.role) {
    return player.role === 'spymaster' ? '🤖 AI Spymaster' : '🤖 AI Operative'
  }
  return player.nickname
}
</script>

<template>
  <section :class="['team-board', team]">
    <header class="team-header">
      <h3>{{ team === 'red' ? '🔴 Red' : '🔵 Blue' }} Team</h3>
      <span class="team-count">{{ players.filter((p) => p.team === team).length }} players</span>
    </header>

    <div class="slot-section">
      <p class="slot-label">Spymaster</p>
      <div class="player-slot" :class="spymaster ? 'filled' : 'empty'">
        <template v-if="spymaster">
          <div class="player-info">
            <span class="player-name">{{ displayName(spymaster) }}</span>
            <span class="badges">
              <span v-if="isYou(spymaster)" class="badge badge-you">You</span>
              <span v-if="isHost(spymaster)" class="badge badge-host">Host</span>
              <span v-if="spymaster.is_ai" class="badge badge-ai">AI</span>
              <span v-if="!spymaster.is_connected" class="badge badge-disconnected">Offline</span>
            </span>
          </div>
          <div v-if="isHost" class="slot-actions">
            <button
              type="button"
              class="action-btn"
              :title="`Move to ${otherTeam} team`"
              @click="moveToOtherTeam(spymaster)"
            >
              To {{ otherTeam === 'red' ? 'Red' : 'Blue' }}
            </button>
            <button
              type="button"
              class="action-btn"
              title="Set as operative"
              @click="setRole(spymaster, 'operative')"
            >
              Operative
            </button>
            <button
              v-if="spymaster.is_ai"
              type="button"
              class="action-btn danger"
              title="Remove AI"
              @click="emit('remove', spymaster.id)"
            >
              ×
            </button>
          </div>
        </template>
        <template v-else>
          <span class="empty-text">No spymaster yet</span>
          <button
            v-if="isHost"
            type="button"
            class="add-ai-btn"
            @click="emit('addAi', team, 'spymaster')"
          >
            + AI Spymaster
          </button>
        </template>
      </div>
    </div>

    <div class="slot-section">
      <p class="slot-label">Operatives</p>
      <ul v-if="operatives.length" class="operative-list">
        <li v-for="player in operatives" :key="player.id" class="player-slot filled">
          <div class="player-info">
            <span class="player-name">{{ displayName(player) }}</span>
            <span class="badges">
              <span v-if="isYou(player)" class="badge badge-you">You</span>
              <span v-if="isHost(player)" class="badge badge-host">Host</span>
              <span v-if="player.is_ai" class="badge badge-ai">AI</span>
              <span v-if="!player.is_connected" class="badge badge-disconnected">Offline</span>
            </span>
          </div>
          <div v-if="isHost" class="slot-actions">
            <button
              type="button"
              class="action-btn"
              :title="`Move to ${otherTeam} team`"
              @click="moveToOtherTeam(player)"
            >
              To {{ otherTeam === 'red' ? 'Red' : 'Blue' }}
            </button>
            <button
              type="button"
              class="action-btn"
              title="Make spymaster"
              @click="setRole(player, 'spymaster')"
            >
              Spymaster
            </button>
            <button
              v-if="player.is_ai"
              type="button"
              class="action-btn danger"
              title="Remove AI"
              @click="emit('remove', player.id)"
            >
              ×
            </button>
          </div>
        </li>
      </ul>
      <div v-else class="player-slot empty operative-empty">
        <span class="empty-text">No operatives yet</span>
        <button
          v-if="isHost"
          type="button"
          class="add-ai-btn"
          @click="emit('addAi', team, 'operative')"
        >
          + AI Operative
        </button>
      </div>
      <button
        v-if="isHost && operatives.length > 0"
        type="button"
        class="add-ai-btn secondary"
        @click="emit('addAi', team, 'operative')"
      >
        + AI Operative
      </button>
    </div>
  </section>
</template>

<style scoped>
.team-board {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 1.25rem;
  box-shadow: var(--shadow);
  display: flex;
  flex-direction: column;
  gap: 1.25rem;
  transition: transform 0.25s var(--ease-smooth), box-shadow 0.25s;
}

.team-board:hover {
  transform: translateY(-2px);
}

.team-board.red {
  border-top: 4px solid var(--red-team);
  background: linear-gradient(180deg, var(--red-team-bg) 0%, var(--surface) 100px);
}

.team-board.blue {
  border-top: 4px solid var(--blue-team);
  background: linear-gradient(180deg, var(--blue-team-bg) 0%, var(--surface) 100px);
}

.team-header {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 0.5rem;
}

.team-header h3 {
  font-size: 1.15rem;
}

.team-board.red .team-header h3 {
  color: var(--red-team);
}

.team-board.blue .team-header h3 {
  color: var(--blue-team);
}

.team-count {
  font-size: 0.8rem;
  color: var(--text-muted);
}

.slot-section {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.slot-label {
  font-size: 0.75rem;
  font-weight: 600;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  color: var(--text-muted);
}

.player-slot {
  border: 1px solid var(--border);
  border-radius: 10px;
  padding: 0.75rem;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.75rem;
  min-height: 3.25rem;
  transition: transform 0.2s var(--ease-bounce), border-color 0.2s, background 0.2s;
}

.player-slot.filled {
  background: rgba(0, 0, 0, 0.15);
}

.player-slot.filled:hover {
  border-color: rgba(255, 255, 255, 0.15);
  transform: translateX(2px);
}

.player-slot.empty {
  border-style: dashed;
  background: transparent;
  flex-direction: column;
  align-items: stretch;
  text-align: center;
  gap: 0.5rem;
}

.player-slot.empty:not(.operative-empty) {
  animation: pulse-empty 3s ease-in-out infinite;
}

@keyframes pulse-empty {
  0%, 100% { border-color: var(--border); }
  50% { border-color: rgba(91, 156, 255, 0.3); }
}

.empty-text {
  color: var(--text-muted);
  font-size: 0.85rem;
}

.operative-list {
  list-style: none;
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.player-info {
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
  min-width: 0;
}

.player-name {
  font-size: 0.95rem;
  font-weight: 600;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.badges {
  display: flex;
  flex-wrap: wrap;
  gap: 0.35rem;
}

.badge-you {
  background: rgba(91, 156, 255, 0.2);
  color: var(--accent);
}

.badge-host {
  background: rgba(61, 214, 140, 0.15);
  color: var(--success);
}

.slot-actions {
  display: flex;
  flex-shrink: 0;
  gap: 0.35rem;
}

.action-btn {
  padding: 0.35rem 0.5rem;
  font-size: 0.7rem;
  font-weight: 600;
  background: var(--surface-hover);
  color: var(--text-muted);
  border: 1px solid var(--border);
  border-radius: 6px;
}

.action-btn:hover:not(:disabled) {
  background: var(--border);
  color: var(--text);
  transform: translateY(-1px);
}

.action-btn.danger:hover:not(:disabled) {
  background: rgba(255, 92, 108, 0.2);
  color: var(--error);
  border-color: var(--error);
}

.add-ai-btn {
  padding: 0.5rem 0.75rem;
  font-size: 0.8rem;
  background: var(--surface-hover);
  color: var(--text);
  border: 1px dashed var(--border);
  border-radius: 8px;
  transition: border-color 0.2s, color 0.2s, transform 0.2s var(--ease-bounce);
}

.add-ai-btn:hover:not(:disabled) {
  border-color: var(--accent);
  color: var(--accent);
  transform: scale(1.02);
}

.add-ai-btn.secondary {
  align-self: flex-start;
}
</style>
