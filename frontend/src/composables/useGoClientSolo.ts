import { onUnmounted, ref, watch, type Ref } from 'vue'
import type { GoGameState } from '@/types'
import { chooseGoMoveAsync, cancelPendingGoAiRequests, terminateGoAiWorker } from '@/games/go/goAiClient'
import {
  aiDifficultyFromSettings,
  getAiPlayerId,
  isAiTurn,
  isGoClientSolo,
  positionFromGameState,
} from '@/games/go/stateBridge'

const AI_THINK_MS = 400

export function useGoClientSolo(
  goState: Ref<GoGameState | null>,
  playerId: Ref<string | null>,
  sendAction: (data: Record<string, unknown>) => void,
) {
  const aiPending = ref(false)
  let requestGeneration = 0

  watch(
    goState,
    (state) => {
      if (!state || !playerId.value || aiPending.value) return
      if (!isGoClientSolo(state)) return
      if (!isAiTurn(state)) return

      const humanId = playerId.value
      const aiId = getAiPlayerId(state)
      if (!aiId || humanId === aiId) return

      const generation = ++requestGeneration
      aiPending.value = true
      const position = positionFromGameState(state)
      const aiPlayer = state.players.find((p) => p.id === aiId)
      const aiColor = aiPlayer?.color ?? 'W'
      const difficulty = aiDifficultyFromSettings(state.settings)

      window.setTimeout(() => {
        chooseGoMoveAsync(position, aiColor, difficulty)
          .then((move) => {
            if (generation !== requestGeneration) return
            sendAction({ type: 'client_ai_move', move })
          })
          .catch(() => {
            if (generation !== requestGeneration) return
          })
          .finally(() => {
            if (generation !== requestGeneration) return
            window.setTimeout(() => {
              if (generation === requestGeneration) aiPending.value = false
            }, 150)
          })
      }, AI_THINK_MS)
    },
    { deep: true },
  )

  onUnmounted(() => {
    requestGeneration++
    cancelPendingGoAiRequests()
    terminateGoAiWorker()
  })

  return { aiPending }
}
