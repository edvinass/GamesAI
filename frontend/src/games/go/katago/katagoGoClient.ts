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
import { katagoPositionFromGameState } from './positionBridge'

const INIT_TIMEOUT_MS = 90_000
const ANALYZE_TIMEOUT_MS = 45_000

let initPromise: Promise<void> | null = null

function withTimeout<T>(promise: Promise<T>, ms: number, label: string): Promise<T> {
  return new Promise((resolve, reject) => {
    const timer = window.setTimeout(() => reject(new Error(`${label} timed out after ${ms}ms`)), ms)
    promise
      .then(resolve, reject)
      .finally(() => window.clearTimeout(timer))
  })
}

function ensureKataGoReady(): Promise<void> {
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
  await ensureKataGoReady()
  const client = getKataGoEngineClient()
  const position = katagoPositionFromGameState(state, aiColor)

  const analysis = await withTimeout(
    client.analyze({
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
      topK: 1,
      conservativePass: true,
    }),
    ANALYZE_TIMEOUT_MS,
    'KataGo analysis',
  )

  const best = analysis.moves.find((m) => m.order === 0) ?? analysis.moves[0]
  if (!best) return { type: 'pass' }
  return moveToAction(best.x, best.y)
}

export function cancelKataGoRequests(): void {
  // Worker queue drains between requests; next analyze replaces in-flight work.
}

export function terminateKataGoClient(): void {
  initPromise = null
  resetKataGoEngineClientForTests()
}

export function getKataGoModelLabel(): string {
  return KATAGO_9X9_MODEL_NAME
}

/** Start loading the KataGo model early (e.g. when Hard is selected in lobby). */
export function preloadKataGo(): Promise<void> {
  return ensureKataGoReady()
}
