import type { GoGameState } from '@/types'
import type { GoAiAction } from '../ai'
import { FILES } from '../board'
import { getKataGoEngineClient, resetKataGoEngineClientForTests } from './engine/client'
import {
  KATAGO_9X9_MODEL_NAME,
  KATAGO_9X9_MODEL_URL,
  KATAGO_HARD_MAX_TIME_MS,
  KATAGO_HARD_VISITS,
} from './modelConfig'
import { katagoPositionFromGameState, legalizeMove } from './positionBridge'

const INIT_TIMEOUT_MS = 90_000
const ANALYZE_TIMEOUT_MS = KATAGO_HARD_MAX_TIME_MS + 20_000

let initPromise: Promise<void> | null = null
let katagoDisabled = false
let consecutiveFailures = 0

function withTimeout<T>(promise: Promise<T>, ms: number, label: string): Promise<T> {
  return new Promise((resolve, reject) => {
    const timer = window.setTimeout(() => reject(new Error(`${label} timed out after ${ms}ms`)), ms)
    promise
      .then(resolve, reject)
      .finally(() => window.clearTimeout(timer))
  })
}

function resetKataGoWorker(): void {
  try {
    getKataGoEngineClient().abortAllPending()
  } catch {
    // Worker may not exist yet.
  }
  resetKataGoEngineClientForTests()
  initPromise = null
}

function ensureKataGoReady(): Promise<void> {
  if (katagoDisabled) {
    return Promise.reject(new Error('KataGo disabled after repeated failures'))
  }
  if (!initPromise) {
    const client = getKataGoEngineClient()
    initPromise = withTimeout(
      client.init(KATAGO_9X9_MODEL_URL, 'wasm'),
      INIT_TIMEOUT_MS,
      'KataGo model load',
    ).catch((err) => {
      initPromise = null
      throw err
    })
  }
  return initPromise
}

function moveToAction(x: number, y: number): GoAiAction {
  if (x < 0 || y < 0) return { type: 'pass' }
  return { type: 'play', coord: `${FILES[x]}${y + 1}` }
}

export async function chooseKataGoMove(state: GoGameState, aiColor: 'B' | 'W'): Promise<GoAiAction> {
  if (katagoDisabled) {
    throw new Error('KataGo disabled after repeated failures')
  }

  await ensureKataGoReady()
  const client = getKataGoEngineClient()
  const position = katagoPositionFromGameState(state, aiColor)
  const positionId = `go-${state.move_history.length}-${state.current_actor_id}`

  try {
    const analysis = await withTimeout(
      client.analyze({
        analysisGroup: 'interactive',
        positionId,
        modelUrl: KATAGO_9X9_MODEL_URL,
        board: position.board,
        previousBoard: position.previousBoard,
        previousPreviousBoard: position.previousPreviousBoard,
        currentPlayer: position.currentPlayer,
        moveHistory: position.moveHistory,
        komi: position.komi,
        rules: position.rules,
        maxTimeMs: KATAGO_HARD_MAX_TIME_MS,
        visits: KATAGO_HARD_VISITS,
        topK: 5,
        conservativePass: true,
        reuseTree: false,
        nnRandomize: false,
        wideRootNoise: 0,
        maxChildren: 120,
      }),
      ANALYZE_TIMEOUT_MS,
      'KataGo analysis',
    )

    consecutiveFailures = 0
    const best = analysis.moves.find((m) => m.order === 0) ?? analysis.moves[0]
    if (!best) return legalizeMove({ type: 'pass' }, state)
    return legalizeMove(moveToAction(best.x, best.y), state)
  } catch (err) {
    consecutiveFailures++
    console.warn('[go-ai] KataGo move failed', err)
    resetKataGoWorker()
    if (consecutiveFailures >= 2) {
      katagoDisabled = true
      console.warn('[go-ai] KataGo disabled for this session; using heuristic MCTS')
    }
    throw err
  }
}

export function cancelKataGoRequests(): void {
  resetKataGoWorker()
}

export function terminateKataGoClient(): void {
  katagoDisabled = false
  consecutiveFailures = 0
  resetKataGoWorker()
}

export function getKataGoModelLabel(): string {
  return KATAGO_9X9_MODEL_NAME
}

/** Start loading the KataGo model early (e.g. when Hard is selected in lobby). */
export function preloadKataGo(): Promise<void> {
  return ensureKataGoReady()
}
