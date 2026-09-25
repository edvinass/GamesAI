/**
 * Browser Stockfish 19 (stockfish.js by Nathan Rugg / Chess.com, GPL-3.0) driven over UCI in a Web Worker.
 * Engine files are copied into `public/stockfish/` by `scripts/copy-stockfish.mjs`.
 */

export interface EngineFlavor {
  id: 'full-mt' | 'full' | 'lite'
  label: string
  script: string
  multiThreaded: boolean
}

const FLAVORS: EngineFlavor[] = [
  { id: 'full-mt', label: 'Stockfish 19 NNUE (multi-thread)', script: '/stockfish/stockfish-19.js', multiThreaded: true },
  { id: 'full', label: 'Stockfish 19 NNUE', script: '/stockfish/stockfish-19-single.js', multiThreaded: false },
  { id: 'lite', label: 'Stockfish 19 lite', script: '/stockfish/stockfish-19-lite-single.js', multiThreaded: false },
]

/** The full builds fetch a ~99 MB network, so allow a slow first download. */
const LOAD_TIMEOUT_MS = 180_000
const SEARCH_MOVETIME_MS = 5_000
const MAX_THREADS = 16
const HASH_MB = 256

export interface EngineSuggestion {
  fen: string
  from: string
  to: string
  promotion: string | null
  uci: string
  depth: number
  /** Centipawns from the side to move's point of view. */
  scoreCp: number | null
  /** Moves to mate; negative means the side to move is getting mated. */
  mate: number | null
  pv: string[]
  final: boolean
}

function parseUciMove(fen: string, uci: string): Pick<EngineSuggestion, 'fen' | 'from' | 'to' | 'promotion' | 'uci'> {
  return {
    fen,
    uci,
    from: uci.slice(0, 2),
    to: uci.slice(2, 4),
    promotion: uci.length > 4 ? uci[4] : null,
  }
}

function parseInfo(line: string): { depth: number; scoreCp: number | null; mate: number | null; pv: string[] } | null {
  const tokens = line.split(/\s+/)
  const pvAt = tokens.indexOf('pv')
  const depthAt = tokens.indexOf('depth')
  const scoreAt = tokens.indexOf('score')
  if (pvAt < 0 || depthAt < 0 || scoreAt < 0) return null
  const multipvAt = tokens.indexOf('multipv')
  if (multipvAt >= 0 && tokens[multipvAt + 1] !== '1') return null
  if (tokens.includes('lowerbound') || tokens.includes('upperbound')) return null

  const kind = tokens[scoreAt + 1]
  const value = Number(tokens[scoreAt + 2])
  return {
    depth: Number(tokens[depthAt + 1]),
    scoreCp: kind === 'cp' ? value : null,
    mate: kind === 'mate' ? value : null,
    pv: tokens.slice(pvAt + 1),
  }
}

export class StockfishClient {
  flavor: EngineFlavor | null = null
  onSuggestion: ((suggestion: EngineSuggestion) => void) | null = null

  private worker: Worker | null = null
  private listeners = new Set<(line: string) => void>()
  private searching = false
  private stopping = false
  private searchFen: string | null = null
  private pendingFen: string | null = null
  private latest: EngineSuggestion | null = null
  private disposed = false

  async init(): Promise<EngineFlavor> {
    const candidates = FLAVORS.filter((f) => !f.multiThreaded || globalThis.crossOriginIsolated)
    let lastError: unknown = null
    for (const flavor of candidates) {
      if (this.disposed) break
      try {
        await this.boot(flavor)
        this.flavor = flavor
        return flavor
      } catch (err) {
        lastError = err
        this.worker?.terminate()
        this.worker = null
      }
    }
    throw lastError ?? new Error('Stockfish could not be started')
  }

  private boot(flavor: EngineFlavor): Promise<void> {
    const worker = new Worker(flavor.script)
    this.worker = worker
    worker.onmessage = (e: MessageEvent) => {
      const line = typeof e.data === 'string' ? e.data : String(e.data ?? '')
      for (const listener of this.listeners) listener(line)
      this.handleLine(line)
    }

    return new Promise<void>((resolve, reject) => {
      const timer = window.setTimeout(() => fail(new Error(`${flavor.label} timed out while loading`)), LOAD_TIMEOUT_MS)
      const cleanup = () => {
        window.clearTimeout(timer)
        this.listeners.delete(onLine)
        worker.onerror = null
      }
      const fail = (err: unknown) => {
        cleanup()
        reject(err)
      }
      const onLine = (line: string) => {
        if (line === 'uciok') {
          if (flavor.multiThreaded) {
            const threads = Math.max(1, Math.min(MAX_THREADS, (navigator.hardwareConcurrency || 4) - 1))
            this.send(`setoption name Threads value ${threads}`)
          }
          this.send(`setoption name Hash value ${HASH_MB}`)
          this.send('setoption name UCI_LimitStrength value false')
          this.send('setoption name Skill Level value 20')
          this.send('isready')
        } else if (line === 'readyok') {
          cleanup()
          resolve()
        }
      }
      this.listeners.add(onLine)
      worker.onerror = (e) => fail(new Error(e.message || `${flavor.label} failed to load`))
      this.send('uci')
    })
  }

  private send(cmd: string) {
    this.worker?.postMessage(cmd)
  }

  /** Search `fen`, superseding any search already running. */
  analyze(fen: string) {
    if (!this.worker || !this.flavor) return
    if (this.searching) {
      if (this.searchFen === fen && !this.stopping) return
      this.pendingFen = fen
      if (!this.stopping) {
        this.stopping = true
        this.send('stop')
      }
      return
    }
    this.start(fen)
  }

  cancel() {
    this.pendingFen = null
    if (this.searching && !this.stopping) {
      this.stopping = true
      this.send('stop')
    }
  }

  private start(fen: string) {
    this.searching = true
    this.stopping = false
    this.searchFen = fen
    this.latest = null
    this.send(`position fen ${fen}`)
    this.send(`go movetime ${SEARCH_MOVETIME_MS}`)
  }

  private handleLine(line: string) {
    if (!this.searching || !this.searchFen) return

    if (line.startsWith('info ')) {
      if (this.stopping) return
      const info = parseInfo(line)
      if (!info || info.pv.length === 0) return
      this.latest = { ...parseUciMove(this.searchFen, info.pv[0]), ...info, final: false }
      this.onSuggestion?.(this.latest)
      return
    }

    if (line.startsWith('bestmove')) {
      const move = line.split(/\s+/)[1]
      const wasStopped = this.stopping
      this.searching = false
      this.stopping = false
      if (!wasStopped && move && move !== '(none)') {
        const base = this.latest?.uci === move ? this.latest : null
        this.onSuggestion?.({
          ...parseUciMove(this.searchFen, move),
          depth: base?.depth ?? 0,
          scoreCp: base?.scoreCp ?? null,
          mate: base?.mate ?? null,
          pv: base?.pv ?? [move],
          final: true,
        })
      }
      const next = this.pendingFen
      this.pendingFen = null
      if (next) this.start(next)
    }
  }

  dispose() {
    this.disposed = true
    this.onSuggestion = null
    this.listeners.clear()
    if (this.worker) {
      this.send('quit')
      this.worker.terminate()
      this.worker = null
    }
  }
}
