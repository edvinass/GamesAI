import { computed, onUnmounted, watch, type Ref } from 'vue'
import type { GoGameState } from '@/types'
import { chooseGoMoveAsync, cancelPendingGoAiRequests, terminateGoAiWorker } from '@/games/go/goAiClient'
import {
  aiDifficultyFromSettings,
  getAiPlayerId,
  isAiTurn,
  isGoClientSolo,
  positionFromGameState,
} from '@/games/go/stateBridge'

const AI_THINK_MS = 200

export function useGoClientSolo(
  goState: Ref<GoGameState | null>,
  playerId: Ref<string | null>,
  sendAction: (data: Record<string, unknown>) => void,
) {
  let requestGeneration = 0

  const aiTurnKey = computed(() => {
    const state = goState.value
    if (!state || state.phase !== 'playing' || !state.current_actor_id) return null
    if (!isGoClientSolo(state) || !isAiTurn(state)) return null
    return `${state.move_history.length}:${state.current_actor_id}`
  })

  watch(aiTurnKey, (turnKey) => {
    if (!turnKey || !playerId.value) return

    const state = goState.value
    if (!state) return

    const humanId = playerId.value
    const aiId = getAiPlayerId(state)
    if (!aiId || humanId === aiId) return

    const generation = ++requestGeneration
    const position = positionFromGameState(state)
    const aiPlayer = state.players.find((p) => p.id === aiId)
    const aiColor = aiPlayer?.color ?? 'W'
    const difficulty = aiDifficultyFromSettings(state.settings)

    window.setTimeout(() => {
      if (generation !== requestGeneration) return
      chooseGoMoveAsync(position, aiColor, difficulty)
        .then((move) => {
          if (generation !== requestGeneration) return
          sendAction({ type: 'client_ai_move', move })
        })
        .catch(() => {
          if (generation !== requestGeneration) return
        })
    }, AI_THINK_MS)
  })

  onUnmounted(() => {
    requestGeneration++
    cancelPendingGoAiRequests()
    terminateGoAiWorker()
  })
}
