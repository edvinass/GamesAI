import type { GoGameState } from '@/types'
import { BLACK, WHITE, EMPTY, type GoPosition } from './board'

export function positionFromGameState(state: GoGameState): GoPosition {
  return {
    board: state.board.map((row) =>
      row.map((cell) => {
        if (cell === 'B') return BLACK
        if (cell === 'W') return WHITE
        return EMPTY
      }),
    ),
    turn: state.current_color,
    ko_point: state.ko_point ?? null,
    consecutive_passes: state.consecutive_passes,
    captured: { ...state.captured },
  }
}

export function isGoClientSolo(state: GoGameState): boolean {
  return Boolean(state.settings?.solo_practice && state.settings?.client_side_ai)
}

export function getAiPlayerId(state: GoGameState): string | null {
  const ai = state.players.find((p) => p.is_ai)
  return ai?.id ?? null
}

export function isAiTurn(state: GoGameState): boolean {
  if (state.phase !== 'playing' || !state.current_actor_id) return false
  const actor = state.players.find((p) => p.id === state.current_actor_id)
  return Boolean(actor?.is_ai)
}

export function aiDifficultyFromSettings(settings: Record<string, unknown>): 'easy' | 'medium' | 'hard' {
  const raw = String(settings.ai_difficulty ?? 'medium').toLowerCase()
  if (raw === 'easy' || raw === 'hard') return raw
  return 'medium'
}
