import type { GoAiDifficulty } from './ai'
import type { GoAiAction } from './ai'
import type { GoPosition } from './board'
import type { GoAiWorkerRequest, GoAiWorkerResponse } from './goAi.worker'

let worker: Worker | null = null
let nextId = 0
const pending = new Map<
  number,
  { resolve: (move: GoAiAction) => void; reject: (err: Error) => void }
>()

function getWorker(): Worker {
  if (!worker) {
    worker = new Worker(new URL('./goAi.worker.ts', import.meta.url), { type: 'module' })
    worker.onmessage = (event: MessageEvent<GoAiWorkerResponse>) => {
      const { id, move } = event.data
      const entry = pending.get(id)
      if (!entry) return
      pending.delete(id)
      entry.resolve(move)
    }
    worker.onerror = (event) => {
      const err = new Error(event.message || 'Go AI worker failed')
      for (const [, entry] of pending) entry.reject(err)
      pending.clear()
      worker?.terminate()
      worker = null
    }
  }
  return worker
}

export function chooseGoMoveAsync(
  position: GoPosition,
  aiColor: 'B' | 'W',
  difficulty: GoAiDifficulty,
): Promise<GoAiAction> {
  const id = ++nextId
  const request: GoAiWorkerRequest = { id, position, aiColor, difficulty }
  return new Promise((resolve, reject) => {
    pending.set(id, { resolve, reject })
    getWorker().postMessage(request)
  })
}

export function cancelPendingGoAiRequests(): void {
  pending.clear()
}

export function terminateGoAiWorker(): void {
  cancelPendingGoAiRequests()
  worker?.terminate()
  worker = null
}
