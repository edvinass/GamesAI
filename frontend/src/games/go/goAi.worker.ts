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
  move: GoAiAction
}

self.onmessage = (event: MessageEvent<GoAiWorkerRequest>) => {
  const { id, position, aiColor, difficulty } = event.data
  const move = chooseGoMove(position, aiColor, difficulty)
  const response: GoAiWorkerResponse = { id, move }
  self.postMessage(response)
}
