import { onBeforeUnmount, ref, shallowRef, watch, type Ref } from 'vue'
import type { CodenamesGameState } from '@/types'
import { isCheatModeEnabled } from '@/games/chess/cheatMode'
import { usePlayerStore } from '@/stores/player'

export { isCheatModeEnabled }

/** Same shape as the backend `codenames_position_key`. */
export function codenamesPositionKey(state: CodenamesGameState): string {
  const revealed = [...state.cards]
    .sort((a, b) => a.index - b.index)
    .filter((card) => card.revealed)
    .map((card) => card.index)
    .join(',')
  const word = state.current_clue?.word ?? ''
  const number = state.current_clue?.number
  const numberText = number === undefined || number === null ? '' : String(number)
  return [
    state.phase,
    state.current_team,
    word,
    numberText,
    String(state.guesses_remaining ?? 0),
    revealed,
  ].join('|')
}

export interface CodenamesClueSuggestion {
  kind: 'clue'
  word: string
  number: number
  targets: string[]
}

export interface CodenamesGuessSuggestion {
  kind: 'guess'
  guesses: { index: number; word: string }[]
}

export type CodenamesSuggestion = CodenamesClueSuggestion | CodenamesGuessSuggestion

export type CodenamesCheatStatus = 'off' | 'loading' | 'ready' | 'error'

const SUGGEST_TIMEOUT_MS = 180_000

/**
 * Ask for a clue or guess without touching the game socket.
 * In-flight requests are aborted when the position changes, so play never waits on them.
 */
export function useCodenamesCheat(options: {
  enabled: boolean
  roomId: Ref<string>
  gameState: Ref<CodenamesGameState>
  active: Ref<boolean>
}) {
  const status = ref<CodenamesCheatStatus>(options.enabled ? 'loading' : 'off')
  const modelLabel = ref<string | null>(null)
  const suggestion = shallowRef<CodenamesSuggestion | null>(null)
  let controller: AbortController | null = null
  let requestId = 0

  async function sync() {
    controller?.abort()
    controller = null
    if (!options.enabled) return

    if (!options.active.value || options.gameState.value.winner) {
      suggestion.value = null
      status.value = 'ready'
      return
    }

    const keyAtStart = codenamesPositionKey(options.gameState.value)
    const id = ++requestId
    const ac = new AbortController()
    controller = ac
    suggestion.value = null
    status.value = 'loading'
    const timer = setTimeout(() => ac.abort(), SUGGEST_TIMEOUT_MS)

    try {
      const token = usePlayerStore().sessionToken
      const res = await fetch(`/api/rooms/${options.roomId.value}/codenames/suggest`, {
        method: 'POST',
        headers: { 'X-Session-Token': token },
        signal: ac.signal,
      })
      if (id !== requestId) return
      if (!options.active.value) return
      if (!res.ok) throw new Error(`suggest failed (${res.status})`)
      const data = (await res.json()) as {
        position_key?: string
        model_label?: string
        suggestion?: { kind?: string }
      }
      if (data.position_key !== codenamesPositionKey(options.gameState.value)) return
      if (data.position_key !== keyAtStart) return
      modelLabel.value = data.model_label ?? null
      const next = data.suggestion
      if (next?.kind === 'clue' || next?.kind === 'guess') {
        suggestion.value = next as CodenamesSuggestion
      } else {
        suggestion.value = null
      }
      status.value = 'ready'
    } catch (error) {
      if (id !== requestId || ac.signal.aborted) return
      if (error instanceof DOMException && error.name === 'AbortError') return
      status.value = 'error'
      suggestion.value = null
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
          Boolean(options.gameState.value.winner),
          codenamesPositionKey(options.gameState.value),
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

  return { status, modelLabel, suggestion }
}
