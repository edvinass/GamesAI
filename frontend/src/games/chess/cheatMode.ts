import { onBeforeUnmount, ref, shallowRef, watch, type Ref } from 'vue'
import type { LocationQuery } from 'vue-router'
import { StockfishClient, type EngineSuggestion } from './stockfish'

/** `?cheat` or `?cheat=1` turns engine suggestions on for this tab; `?cheat=0` turns them off. */
export const CHEAT_QUERY_PARAM = 'cheat'
const CHEAT_SESSION_KEY = 'chess-cheat-mode'
const OFF_VALUES = new Set(['0', 'false', 'off', 'no'])

/**
 * Remember the flag per tab so it survives the in-app hop from the room URL to `/play`,
 * and stays private to whoever opened the URL.
 */
export function captureCheatParam(query: LocationQuery): void {
  if (!(CHEAT_QUERY_PARAM in query)) return
  const raw = query[CHEAT_QUERY_PARAM]
  const value = (Array.isArray(raw) ? raw[0] : raw) ?? ''
  try {
    if (OFF_VALUES.has(value.toLowerCase())) sessionStorage.removeItem(CHEAT_SESSION_KEY)
    else sessionStorage.setItem(CHEAT_SESSION_KEY, '1')
  } catch {
    /* ignore */
  }
}

export function isCheatModeEnabled(): boolean {
  try {
    return sessionStorage.getItem(CHEAT_SESSION_KEY) === '1'
  } catch {
    return false
  }
}

export type CheatEngineStatus = 'off' | 'loading' | 'ready' | 'error'

export function useCheatEngine(options: { enabled: boolean; fen: Ref<string>; active: Ref<boolean> }) {
  const status = ref<CheatEngineStatus>(options.enabled ? 'loading' : 'off')
  const engineLabel = ref<string | null>(null)
  const suggestion = shallowRef<EngineSuggestion | null>(null)
  let client: StockfishClient | null = null

  function sync() {
    if (!client || status.value !== 'ready') return
    if (options.active.value) client.analyze(options.fen.value)
    else client.cancel()
  }

  if (options.enabled) {
    client = new StockfishClient()
    client.onSuggestion = (s) => {
      if (options.active.value && s.fen === options.fen.value) suggestion.value = s
    }
    client
      .init()
      .then((flavor) => {
        engineLabel.value = flavor.label
        status.value = 'ready'
        sync()
      })
      .catch(() => {
        status.value = 'error'
      })

    watch([options.fen, options.active], () => {
      suggestion.value = null
      sync()
    })
  }

  onBeforeUnmount(() => {
    client?.dispose()
    client = null
  })

  return { status, engineLabel, suggestion }
}

export function formatEngineScore(s: Pick<EngineSuggestion, 'scoreCp' | 'mate'>): string {
  if (s.mate !== null) return s.mate > 0 ? `M${s.mate}` : `-M${Math.abs(s.mate)}`
  if (s.scoreCp === null) return '—'
  const pawns = s.scoreCp / 100
  return `${pawns > 0 ? '+' : ''}${pawns.toFixed(2)}`
}
