/** Go AI — heuristic-guided MCTS with policy playouts. */

import {
  BLACK,
  EMPTY,
  OPPONENT,
  CHAR_COLOR,
  getGroup,
  groupLiberties,
  type GoPlay,
  type GoPosition,
  applyPassRaw,
  applyPlayRaw,
  capturesIfPlayed,
  gameOverByPasses,
  generateLegalPlays,
  scorePosition,
} from './board'

export type GoAiDifficulty = 'easy' | 'medium' | 'hard'

/** Wall-clock budget in the worker — keeps Hard responsive. */
export const DIFFICULTY_BUDGET_MS: Record<GoAiDifficulty, number> = {
  easy: 0,
  medium: 4000,
  hard: 8000,
}

/** Safety cap so fast devices do not over-search. */
export const DIFFICULTY_MAX_SIMS: Record<GoAiDifficulty, number> = {
  easy: 0,
  medium: 6400,
  hard: 10000,
}

const OPENING_POINTS = new Set(['2,2', '2,6', '6,2', '6,6', '4,4'])
const NEIGHBOR_DELTAS: ReadonlyArray<readonly [number, number]> = [
  [-1, 0],
  [1, 0],
  [0, -1],
  [0, 1],
]

function cloneBoard(board: number[][]): number[][] {
  const out = new Array<number[]>(9)
  for (let r = 0; r < 9; r++) out[r] = board[r].slice()
  return out
}

function clonePosition(position: GoPosition): GoPosition {
  return {
    board: cloneBoard(position.board),
    turn: position.turn,
    ko_point: position.ko_point,
    consecutive_passes: position.consecutive_passes,
    captured: { B: position.captured.B, W: position.captured.W },
  }
}

function countStones(board: number[][]): number {
  let n = 0
  for (let r = 0; r < 9; r++) {
    for (let c = 0; c < 9; c++) {
      if (board[r][c] !== EMPTY) n++
    }
  }
  return n
}

function heuristicScore(position: GoPosition, row: number, col: number, color: number): number {
  const board = position.board
  let score = 0
  const temp = cloneBoard(board)
  temp[row][col] = color

  for (const group of capturesIfPlayed(temp, row, col, color)) {
    score += group.size * 20
  }

  for (const [dr, dc] of NEIGHBOR_DELTAS) {
    const nr = row + dr
    const nc = col + dc
    if (nr < 0 || nr > 8 || nc < 0 || nc > 8) continue
    const stone = board[nr][nc]
    if (stone === color) {
      score += 4
      const group = getGroup(board, nr, nc)
      if (groupLiberties(board, group).size === 1) score += 8
    } else if (stone === OPPONENT[color]) {
      score += 2
    }
  }

  for (const [dr, dc] of NEIGHBOR_DELTAS) {
    const nr = row + dr
    const nc = col + dc
    if (nr < 0 || nr > 8 || nc < 0 || nc > 8) continue
    if (temp[nr][nc] !== OPPONENT[color]) continue
    const group = getGroup(temp, nr, nc)
    if (groupLiberties(temp, group).size === 1) score += 7
  }

  const stones = countStones(board)
  if (OPENING_POINTS.has(`${row},${col}`) && stones < 14) score += 4
  const dist = Math.abs(row - 4) + Math.abs(col - 4)
  if (stones < 20 && dist <= 2) score += 2
  if (stones < 16 && (row === 0 || row === 8 || col === 0 || col === 8)) score -= 2

  return score
}

function quickHeuristic(board: number[][], row: number, col: number, color: number): number {
  let score = 0
  for (const [dr, dc] of NEIGHBOR_DELTAS) {
    const nr = row + dr
    const nc = col + dc
    if (nr < 0 || nr > 8 || nc < 0 || nc > 8) continue
    const stone = board[nr][nc]
    if (stone === color) score += 3
    else if (stone === OPPONENT[color]) score += 1.5
    else score += 0.4
  }
  const dist = Math.abs(row - 4) + Math.abs(col - 4)
  if (dist <= 2) score += 0.5
  return score
}

function topPlays(position: GoPosition, color: number, limit: number): GoPlay[] {
  const legal = generateLegalPlays(position)
  if (legal.length <= limit) return legal
  const scored = legal.map((p) => ({
    p,
    s: heuristicScore(position, p.row, p.col, color),
  }))
  scored.sort((a, b) => b.s - a.s)
  return scored.slice(0, limit).map((x) => x.p)
}

function quickPickPlay(position: GoPosition, color: number): GoPlay | null {
  const legal = generateLegalPlays(position)
  if (legal.length === 0) return null
  let bestScore = -Infinity
  let picks: GoPlay[] = []
  const board = position.board
  for (const p of legal) {
    const s = quickHeuristic(board, p.row, p.col, color)
    if (s > bestScore) {
      bestScore = s
      picks = [p]
    } else if (s === bestScore) {
      picks.push(p)
    }
  }
  return picks[Math.floor(Math.random() * picks.length)]
}

function policyPlayout(from: GoPosition, maxMoves = 55): number {
  let state = clonePosition(from)
  let passes = 0

  for (let i = 0; i < maxMoves; i++) {
    if (gameOverByPasses(state)) break
    const legal = generateLegalPlays(state)
    const lateGame = countStones(state.board) > 55

    if (legal.length === 0) {
      state = applyPassRaw(state)
      passes++
      if (passes >= 2) break
      continue
    }

    if (lateGame && passes === 0 && Math.random() < 0.1) {
      state = applyPassRaw(state)
      passes++
      continue
    }

    passes = 0
    const play = quickPickPlay(state, CHAR_COLOR[state.turn])
    if (!play) break
    state = applyPlayRaw(state, play.row, play.col)
  }

  if (!gameOverByPasses(state)) {
    state = applyPassRaw(state)
    if (!gameOverByPasses(state)) state = applyPassRaw(state)
  }

  const result = scorePosition(state)
  if (result.winner_color === 'B') return 1
  if (result.winner_color === 'W') return -1
  return 0
}

class MCTSNode {
  move: GoPlay | null
  parent: MCTSNode | null
  children = new Map<string, MCTSNode>()
  untried: GoPlay[]
  visits = 0
  value = 0

  constructor(move: GoPlay | null, parent: MCTSNode | null, untried: GoPlay[]) {
    this.move = move
    this.parent = parent
    this.untried = untried
  }

  uctScore(exploration: number): number {
    if (this.visits === 0) return Infinity
    return (
      this.value / this.visits +
      exploration * Math.sqrt(Math.log(this.parent!.visits) / this.visits)
    )
  }

  bestChild(): MCTSNode {
    let best: MCTSNode | null = null
    let bestScore = -Infinity
    for (const child of this.children.values()) {
      const score = child.uctScore(1.25)
      if (score > bestScore) {
        bestScore = score
        best = child
      }
    }
    return best!
  }
}

function mctsBestPlay(
  position: GoPosition,
  aiColor: number,
  budgetMs: number,
  maxSims: number,
): GoPlay | null {
  const rootPlays = generateLegalPlays(position)
  if (rootPlays.length === 0) return null

  const orderedRoot = topPlays(position, aiColor, 22)
  const root = new MCTSNode(null, null, [...orderedRoot])
  root.visits = 1
  const deadline = performance.now() + budgetMs
  let sims = 0

  while (sims < maxSims && performance.now() < deadline) {
    let node = root
    let state = clonePosition(position)
    const path: MCTSNode[] = [root]

    while (node.untried.length === 0 && node.children.size > 0) {
      node = node.bestChild()
      if (node.move) state = applyPlayRaw(state, node.move.row, node.move.col)
      path.push(node)
    }

    if (node.untried.length > 0) {
      const move = node.untried.shift()!
      state = applyPlayRaw(state, move.row, move.col)
      const nextColor = CHAR_COLOR[state.turn]
      const child = new MCTSNode(move, node, topPlays(state, nextColor, 14))
      node.children.set(move.coord, child)
      node = child
      path.push(node)
    }

    const outcome = policyPlayout(state)
    const aiSign = aiColor === BLACK ? 1 : -1
    const result = outcome * aiSign
    for (const n of path) {
      n.visits++
      n.value += result
    }
    sims++
  }

  if (root.children.size === 0) return orderedRoot[0] ?? rootPlays[0]
  let best: MCTSNode | null = null
  for (const child of root.children.values()) {
    if (!best || child.visits > best.visits) best = child
  }
  return best!.move
}

export interface GoAiAction {
  type: 'play' | 'pass'
  coord?: string
}

export function chooseGoMove(
  position: GoPosition,
  aiColor: 'B' | 'W',
  difficulty: GoAiDifficulty = 'medium',
): GoAiAction {
  const legal = generateLegalPlays(position)
  const diff = difficulty in DIFFICULTY_BUDGET_MS ? difficulty : 'medium'
  const colorInt = CHAR_COLOR[aiColor]

  if (diff === 'easy') {
    if (Math.random() < 0.35 && legal.length > 0) {
      return { type: 'play', coord: legal[Math.floor(Math.random() * legal.length)].coord }
    }
    const ordered = topPlays(position, colorInt, 12)
    if (ordered.length > 0) {
      const top = ordered.slice(0, Math.max(3, Math.floor(ordered.length / 4)))
      return { type: 'play', coord: top[Math.floor(Math.random() * top.length)].coord }
    }
    return { type: 'pass' }
  }

  const play = mctsBestPlay(
    position,
    colorInt,
    DIFFICULTY_BUDGET_MS[diff],
    DIFFICULTY_MAX_SIMS[diff],
  )
  if (play) return { type: 'play', coord: play.coord }
  return { type: 'pass' }
}
