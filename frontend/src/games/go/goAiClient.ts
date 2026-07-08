import type { GoGameState } from '@/types'
import type { GoAiDifficulty } from './ai'
import type { GoAiAction } from './ai'
import type { GoPosition } from './board'
import type { GoAiWorkerRequest, GoAiWorkerResponse } from './goAi.worker'
import { chooseKataGoMove, terminateKataGoClient } from './katago/katagoGoClient'

const HEURISTIC_TIMEOUT_MS = 20_000

let worker: Worker | null = null
let nextId = 0
const pending = new Map<
  number,
  { resolve: (move: GoAiAction) => void; reject: (err: Error) => void; timer: ReturnType<typeof setTimeout> }
>()

function rejectAllPending(err: Error): void {
  for (const [, entry] of pending) {
    clearTimeout(entry.timer)
    entry.reject(err)
  }
  pending.clear()
}

function getWorker(): Worker {
  if (!worker) {
    worker = new Worker(new URL('./goAi.worker.ts', import.meta.url), { type: 'module' })
    worker.onmessage = (event: MessageEvent<GoAiWorkerResponse>) => {
      const { id, move, error } = event.data
      const entry = pending.get(id)
      if (!entry) return
      clearTimeout(entry.timer)
      pending.delete(id)
      if (error) {
        entry.reject(new Error(error))
        return
      }
      if (!move) {
        entry.reject(new Error('Go AI returned no move'))
        return
      }
      entry.resolve(move)
    }
    worker.onerror = (event) => {
      const err = new Error(event.message || 'Go AI worker failed')
      rejectAllPending(err)
      worker?.terminate()
      worker = null
    }
  }
  return worker
}

function chooseHeuristicMoveAsync(
  position: GoPosition,
  aiColor: 'B' | 'W',
  difficulty: GoAiDifficulty,
): Promise<GoAiAction> {
  const id = ++nextId
  const request: GoAiWorkerRequest = { id, position, aiColor, difficulty }
  return new Promise((resolve, reject) => {
    const timer = setTimeout(() => {
      pending.delete(id)
      reject(new Error('Go AI timed out'))
    }, HEURISTIC_TIMEOUT_MS)
    pending.set(id, { resolve, reject, timer })
    getWorker().postMessage(request)
  })
}

export function chooseGoMoveAsync(
  position: GoPosition,
  aiColor: 'B' | 'W',
  difficulty: GoAiDifficulty,
  gameState?: GoGameState,
): Promise<GoAiAction> {
  if (difficulty === 'hard' && gameState) {
    return chooseKataGoMove(gameState, aiColor).catch((err) => {
      console.warn('[go-ai] KataGo failed, using heuristic MCTS', err)
      return chooseHeuristicMoveAsync(position, aiColor, 'hard')
    })
  }
  return chooseHeuristicMoveAsync(position, aiColor, difficulty)
}

export function cancelPendingGoAiRequests(): void {
  rejectAllPending(new Error('Go AI request cancelled'))
}

export function terminateGoAiWorker(): void {
  cancelPendingGoAiRequests()
  worker?.terminate()
  worker = null
  terminateKataGoClient()
}
