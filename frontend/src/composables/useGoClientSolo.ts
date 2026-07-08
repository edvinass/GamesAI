import { ref, watch, type Ref } from 'vue'
import type { GoGameState } from '@/types'
import { chooseGoMove } from '@/games/go/ai'
import {
  aiDifficultyFromSettings,
  getAiPlayerId,
  isAiTurn,
  isGoClientSolo,
  positionFromGameState,
} from '@/games/go/stateBridge'

const AI_THINK_MS = 650

export function useGoClientSolo(
  goState: Ref<GoGameState | null>,
  playerId: Ref<string | null>,
  sendAction: (data: Record<string, unknown>) => void,
) {
  const aiPending = ref(false)

  watch(
    goState,
    (state) => {
      if (!state || !playerId.value || aiPending.value) return
      if (!isGoClientSolo(state)) return
      if (!isAiTurn(state)) return

      const humanId = playerId.value
      const aiId = getAiPlayerId(state)
      if (!aiId || humanId === aiId) return

      aiPending.value = true
      const position = positionFromGameState(state)
      const aiPlayer = state.players.find((p) => p.id === aiId)
      const aiColor = aiPlayer?.color ?? 'W'
      const difficulty = aiDifficultyFromSettings(state.settings)

      window.setTimeout(() => {
        try {
          const move = chooseGoMove(position, aiColor, difficulty)
          sendAction({ type: 'client_ai_move', move })
        } finally {
          window.setTimeout(() => {
            aiPending.value = false
          }, 200)
        }
      }, AI_THINK_MS)
    },
    { deep: true },
  )

  return { aiPending }
}
