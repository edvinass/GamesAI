import { chooseGoMove, type GoAiDifficulty } from './ai'
import type { GoPosition } from './board'
import type { GoAiAction } from './ai'

export interface GoAiWorkerRequest {
  id: number
  position: GoPosition
  aiColor: 'B' | 'W'
  difficulty: GoAiDifficulty
}

export interface GoAiWorkerResponse {
  id: number
  move?: GoAiAction
  error?: string
}

self.onmessage = (event: MessageEvent<GoAiWorkerRequest>) => {
  const { id, position, aiColor, difficulty } = event.data
  try {
    const move = chooseGoMove(position, aiColor, difficulty)
    const response: GoAiWorkerResponse = { id, move }
    self.postMessage(response)
  } catch (err) {
    const response: GoAiWorkerResponse = {
      id,
      error: err instanceof Error ? err.message : 'Go AI worker failed',
    }
    self.postMessage(response)
  }
}
