import { Chess, type Move, type PieceSymbol, type Square } from 'chess.js'

export const PIECE_VALUE: Record<PieceSymbol, number> = {
  p: 1,
  n: 3,
  b: 3,
  r: 5,
  q: 9,
  k: 0,
}

export type OscarStyle = 'gentle' | 'sharp'

function play(chess: Chess, move: Move): Chess {
  const next = new Chess(chess.fen())
  next.move({ from: move.from, to: move.to, promotion: move.promotion })
  return next
}

function scoreMove(chess: Chess, move: Move): number {
  let score = 0
  if (move.isCapture() && move.captured) score += PIECE_VALUE[move.captured]
  if (move.promotion) score += PIECE_VALUE[move.promotion]
  const next = play(chess, move)
  if (next.isCheckmate()) return 500
  if (next.isStalemate()) score -= 4
  else if (next.isDraw()) score -= 1
  if (next.isCheck()) score += 0.35

  const mover = PIECE_VALUE[move.promotion ?? move.piece]
  const attackers = next.attackers(move.to, next.turn())
  if (attackers.length > 0) {
    let cheapest = 9
    for (const square of attackers) {
      const piece = next.get(square)
      if (piece) cheapest = Math.min(cheapest, PIECE_VALUE[piece.type])
    }
    const defenders = next.attackers(move.to, move.color).length
    if (defenders === 0) score -= mover
    else if (cheapest < mover) score -= mover - cheapest
  }
  return score
}

function ranked(chess: Chess): { move: Move; score: number }[] {
  return chess
    .moves({ verbose: true })
    .map((move) => ({ move, score: scoreMove(chess, move) }))
    .sort((a, b) => b.score - a.score)
}

/** Material-aware move with deliberate mistakes so early lessons stay winnable. */
export function pickOscarMove(chess: Chess, style: OscarStyle): string | null {
  const moves = ranked(chess).filter(({ move }) => {
    const next = play(chess, move)
    return !next.isStalemate()
  })
  const pool = moves.length > 0 ? moves : ranked(chess)
  if (pool.length === 0) return null
  const best = pool[0].score
  const slack = style === 'gentle' ? 3 : 1
  let choices = pool.filter((entry) => entry.score >= best - slack)
  const blunder = style === 'gentle' ? 0.35 : 0.1
  if (Math.random() < blunder) choices = pool
  const choice = choices[Math.floor(Math.random() * choices.length)]
  return choice.move.lan
}

export function bestSafeMove(chess: Chess): string | null {
  const moves = ranked(chess)
  return moves[0]?.move.lan ?? null
}

function mostValuableWhite(chess: Chess): Square | null {
  let best: Square | null = null
  let bestValue = 0
  for (const row of chess.board()) {
    for (const piece of row) {
      if (!piece || piece.color !== 'w' || piece.type === 'k') continue
      const value = PIECE_VALUE[piece.type]
      if (value > bestValue) {
        bestValue = value
        best = piece.square
      }
    }
  }
  return best
}

function squareDistance(a: Square, b: Square): number {
  return Math.abs(a.charCodeAt(0) - b.charCodeAt(0)) + Math.abs(Number(a[1]) - Number(b[1]))
}

/**
 * Mini-match opponent. Captures the best white piece it can reach, even when
 * that piece is protected, which is how the Duolingo drills let you trap a queen.
 */
export function pickGreedyCapture(chess: Chess): string | null {
  const all = chess.moves({ verbose: true })
  if (all.length === 0) return null
  const withoutKing = all.filter((move) => move.piece !== 'k')
  const moves = withoutKing.length > 0 ? withoutKing : all
  const captures = moves.filter((move) => move.isCapture() && move.captured)
  if (captures.length > 0) {
    captures.sort((a, b) => {
      const taken = PIECE_VALUE[b.captured!] - PIECE_VALUE[a.captured!]
      if (taken !== 0) return taken
      return PIECE_VALUE[a.piece] - PIECE_VALUE[b.piece]
    })
    return captures[0].lan
  }
  const prey = mostValuableWhite(chess)
  if (!prey) return moves[Math.floor(Math.random() * moves.length)].lan
  let best = moves[0]
  let bestDistance = squareDistance(best.to, prey)
  for (const move of moves) {
    const distance = squareDistance(move.to, prey)
    if (distance < bestDistance) {
      best = move
      bestDistance = distance
    }
  }
  return best.lan
}

const SPAWN_BAG: PieceSymbol[] = ['q', 'q', 'q', 'r', 'b', 'n', 'p']

function shuffle<T>(items: T[]): T[] {
  const copy = [...items]
  for (let i = copy.length - 1; i > 0; i -= 1) {
    const j = Math.floor(Math.random() * (i + 1))
    const swap = copy[i]
    copy[i] = copy[j]
    copy[j] = swap
  }
  return copy
}

export function blackPieceCount(chess: Chess): number {
  let count = 0
  for (const row of chess.board()) {
    for (const piece of row) {
      if (piece?.color === 'b' && piece.type !== 'k') count += 1
    }
  }
  return count
}

export function whiteAttackersCount(chess: Chess): number {
  let count = 0
  for (const row of chess.board()) {
    for (const piece of row) {
      if (piece?.color === 'w' && piece.type !== 'k') count += 1
    }
  }
  return count
}

/** Drop another black piece on the far side so a 90 second drill does not run dry. */
export function spawnTarget(chess: Chess): boolean {
  if (blackPieceCount(chess) >= 6) return false
  const files = 'abcdefgh'
  const squares: Square[] = []
  for (let rank = 4; rank <= 8; rank += 1) {
    for (const file of files) squares.push(`${file}${rank}` as Square)
  }
  for (const type of shuffle(SPAWN_BAG)) {
    for (const square of shuffle(squares)) {
      if (chess.get(square)) continue
      if (type === 'p' && (square.endsWith('1') || square.endsWith('8'))) continue
      if (!chess.put({ type, color: 'b' }, square)) continue
      if (chess.isCheck()) {
        chess.remove(square)
        continue
      }
      return true
    }
  }
  return false
}
