import { onBeforeUnmount, ref, shallowRef, watch, type Ref } from 'vue'
import type { ScrabbleGameState } from '@/types'
import { isCheatModeEnabled } from '@/games/chess/cheatMode'
import { usePlayerStore } from '@/stores/player'

export { isCheatModeEnabled }

/** Same shape as the backend `scrabble_position_key`. */
export function scrabblePositionKey(state: ScrabbleGameState): string {
  const rack = state.rack
    .map((tile) => tile.id)
    .sort()
    .join(',')
  return `${state.turn_index}|${state.current_actor_id ?? ''}|${rack}`
}

export interface ScrabbleSuggestedPlacement {
  row: number
  col: number
  tile_id: string
  letter: string
  blank: boolean
}

export interface ScrabbleSuggestedMove {
  score: number
  bingo: boolean
  words: { word: string; score: number }[]
  placements: ScrabbleSuggestedPlacement[]
}

export type ScrabbleCheatStatus = 'off' | 'loading' | 'ready' | 'error'

const SUGGEST_TIMEOUT_MS = 30_000

/**
 * Ask for the best plays for this player's rack without touching the game socket.
 * In-flight requests are aborted when the position changes, so play never waits on them.
 */
export function useScrabbleCheat(options: {
  enabled: boolean
  roomId: Ref<string>
  gameState: Ref<ScrabbleGameState>
  active: Ref<boolean>
}) {
  const status = ref<ScrabbleCheatStatus>(options.enabled ? 'loading' : 'off')
  const modelLabel = ref<string | null>(null)
  const moves = shallowRef<ScrabbleSuggestedMove[]>([])
  let controller: AbortController | null = null
  let requestId = 0

  async function sync() {
    controller?.abort()
    controller = null
    if (!options.enabled) return

    if (!options.active.value) {
      moves.value = []
      status.value = 'ready'
      return
    }

    const keyAtStart = scrabblePositionKey(options.gameState.value)
    const id = ++requestId
    const ac = new AbortController()
    controller = ac
    moves.value = []
    status.value = 'loading'
    const timer = setTimeout(() => ac.abort(), SUGGEST_TIMEOUT_MS)

    try {
      const token = usePlayerStore().sessionToken
      const res = await fetch(`/api/rooms/${options.roomId.value}/scrabble/suggest`, {
        method: 'POST',
        headers: { 'X-Session-Token': token },
        signal: ac.signal,
      })
      if (id !== requestId || !options.active.value) return
      if (!res.ok) throw new Error(`suggest failed (${res.status})`)
      const data = (await res.json()) as {
        position_key?: string
        model_label?: string
        moves?: ScrabbleSuggestedMove[]
      }
      if (data.position_key !== keyAtStart) return
      if (data.position_key !== scrabblePositionKey(options.gameState.value)) return
      modelLabel.value = data.model_label ?? null
      moves.value = Array.isArray(data.moves) ? data.moves : []
      status.value = 'ready'
    } catch (error) {
      if (id !== requestId || ac.signal.aborted) return
      if (error instanceof DOMException && error.name === 'AbortError') return
      status.value = 'error'
      moves.value = []
    } finally {
      clearTimeout(timer)
    }
  }

  if (options.enabled) {
    watch(
      () =>
        [
          options.roomId.value,
          options.active.value,
          scrabblePositionKey(options.gameState.value),
        ] as const,
      () => {
        void sync()
      },
      { immediate: true },
    )
  }

  onBeforeUnmount(() => {
    requestId += 1
    controller?.abort()
    controller = null
  })

  return { status, modelLabel, moves }
}
