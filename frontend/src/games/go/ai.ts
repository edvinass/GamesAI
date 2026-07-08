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
  neighbors,
  scorePosition,
} from './board'

export type GoAiDifficulty = 'easy' | 'medium' | 'hard'

/** Client-side solo can afford more sims than the old server budget. */
export const DIFFICULTY_SIMULATIONS: Record<GoAiDifficulty, number> = {
  easy: 0,
  medium: 400,
  hard: 1500,
}

const OPENING_POINTS = new Set(['2,2', '2,6', '6,2', '6,6', '4,4'])

function clonePosition(position: GoPosition): GoPosition {
  return {
    board: position.board.map((row) => [...row]),
    turn: position.turn,
    ko_point: position.ko_point ? [...position.ko_point] as [number, number] : null,
    consecutive_passes: position.consecutive_passes,
    captured: { ...position.captured },
  }
}

function stoneCount(position: GoPosition): number {
  return position.board.reduce((n, row) => n + row.filter((c) => c !== EMPTY).length, 0)
}

function heuristicScore(position: GoPosition, row: number, col: number, color: number): number {
  const board = position.board
  let score = 0
  const temp = board.map((r) => [...r])
  temp[row][col] = color

  for (const group of capturesIfPlayed(temp, row, col, color)) {
    score += group.size * 20
  }

  for (const [nr, nc] of neighbors(row, col)) {
    const stone = board[nr][nc]
    if (stone === color) {
      score += 4
      const group = getGroup(board, nr, nc)
      if (groupLiberties(board, group).size === 1) score += 8
    } else if (stone === OPPONENT[color]) {
      score += 2
    }
  }

  for (const [nr, nc] of neighbors(row, col)) {
    if (temp[nr][nc] !== OPPONENT[color]) continue
    const group = getGroup(temp, nr, nc)
    const libs = groupLiberties(temp, group)
    if (libs.size === 1) score += 7
  }

  const stones = stoneCount(position)
  if (OPENING_POINTS.has(`${row},${col}`) && stones < 14) score += 4
  const dist = Math.abs(row - 4) + Math.abs(col - 4)
  if (stones < 20 && dist <= 2) score += 2
  if (stones < 16 && (row === 0 || row === 8 || col === 0 || col === 8)) score -= 2

  return score
}

function orderPlays(position: GoPosition, color: number): GoPlay[] {
  const plays = generateLegalPlays(position)
  return [...plays].sort(
    (a, b) =>
      heuristicScore(position, b.row, b.col, color) -
      heuristicScore(position, a.row, a.col, color),
  )
}

function weightedPickPlay(
  position: GoPosition,
  color: number,
  topK = 8,
): GoPlay | null {
  const ordered = orderPlays(position, color)
  if (ordered.length === 0) return null
  const pool = ordered.slice(0, Math.min(topK, ordered.length))
  const weights = pool.map((p) =>
    Math.max(0.5, heuristicScore(position, p.row, p.col, color)),
  )
  const total = weights.reduce((sum, w) => sum + w, 0)
  let roll = Math.random() * total
  for (let i = 0; i < pool.length; i++) {
    roll -= weights[i]
    if (roll <= 0) return pool[i]
  }
  return pool[pool.length - 1]
}

function policyPlayout(from: GoPosition, maxMoves = 100): number {
  let state = clonePosition(from)
  let passes = 0
  const colorToMove = () => CHAR_COLOR[state.turn]

  for (let i = 0; i < maxMoves; i++) {
    if (gameOverByPasses(state)) break
    const legal = generateLegalPlays(state)
    const lateGame = stoneCount(state) > 55

    if (legal.length === 0) {
      state = applyPassRaw(state)
      passes++
      if (passes >= 2) break
      continue
    }

    if (lateGame && passes === 0 && Math.random() < 0.12) {
      state = applyPassRaw(state)
      passes++
      continue
    }

    passes = 0
    const play = weightedPickPlay(state, colorToMove(), 6)
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
}

function mctsBestPlay(
  position: GoPosition,
  aiColor: number,
  simulations: number,
): GoPlay | null {
  const rootPlays = generateLegalPlays(position)
  if (rootPlays.length === 0) return null

  const orderedRoot = orderPlays(position, aiColor)
  const root = new MCTSNode(null, null, [...orderedRoot])
  root.visits = 1

  for (let i = 0; i < simulations; i++) {
    let node = root
    let state = clonePosition(position)
    const path: MCTSNode[] = [root]

    while (node.untried.length === 0 && node.children.size > 0) {
      node = [...node.children.values()].reduce((best, n) =>
        n.uctScore(1.25) > best.uctScore(1.25) ? n : best,
      )
      if (node.move) state = applyPlayRaw(state, node.move.row, node.move.col)
      path.push(node)
    }

    if (node.untried.length > 0) {
      const move = node.untried.shift()!
      state = applyPlayRaw(state, move.row, move.col)
      const nextColor = CHAR_COLOR[state.turn]
      const child = new MCTSNode(move, node, orderPlays(state, nextColor))
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
  }

  if (root.children.size === 0) return orderedRoot[0] ?? rootPlays[0]
  return [...root.children.values()].reduce((best, n) =>
    n.visits > best.visits ? n : best,
  ).move
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
  const diff = difficulty in DIFFICULTY_SIMULATIONS ? difficulty : 'medium'
  const colorInt = CHAR_COLOR[aiColor]

  if (diff === 'easy') {
    if (Math.random() < 0.35 && legal.length > 0) {
      return { type: 'play', coord: legal[Math.floor(Math.random() * legal.length)].coord }
    }
    const ordered = orderPlays(position, colorInt)
    if (ordered.length > 0) {
      const top = ordered.slice(0, Math.max(3, Math.floor(ordered.length / 4)))
      return { type: 'play', coord: top[Math.floor(Math.random() * top.length)].coord }
    }
    return { type: 'pass' }
  }

  const play = mctsBestPlay(position, colorInt, DIFFICULTY_SIMULATIONS[diff])
  if (play) return { type: 'play', coord: play.coord }
  return { type: 'pass' }
}
