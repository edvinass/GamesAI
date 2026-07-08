import type { GoGameState } from '@/types'
import type { GoAiAction } from '../ai'
import { DEFAULT_KOMI, FILES } from '../board'
import type { BoardState, Move, Player } from './katagoTypes'

const BOARD_SIZE = 9

function emptyBoard(): BoardState {
  return Array.from({ length: BOARD_SIZE }, () => Array<null>(BOARD_SIZE).fill(null))
}

function cloneBoard(board: BoardState): BoardState {
  return board.map((row) => row.slice())
}

function toPlayer(color: 'B' | 'W'): Player {
  return color === 'B' ? 'black' : 'white'
}

function boardFromMatrix(matrix: Array<Array<string | null>>): BoardState {
  const board = emptyBoard()
  for (let row = 0; row < BOARD_SIZE; row++) {
    for (let col = 0; col < BOARD_SIZE; col++) {
      const cell = matrix[row]?.[col]
      if (cell === 'B') board[row][col] = 'black'
      else if (cell === 'W') board[row][col] = 'white'
    }
  }
  return board
}

function goMoveToKatagoMove(move: GoGameState['move_history'][number]): Move | null {
  const color = move.color
  if (!color) return null
  const player = toPlayer(color)
  if (move.type === 'pass') return { x: -1, y: -1, player }
  let col = move.col
  let row = move.row
  if ((col === undefined || row === undefined) && move.coord) {
    const normalized = move.coord.trim().toLowerCase()
    if (normalized.length === 2) {
      col = FILES.indexOf(normalized[0])
      row = parseInt(normalized[1], 10) - 1
    }
  }
  if (col === undefined || row === undefined || col < 0 || row < 0) return null
  return { x: col, y: row, player }
}

export function movesFromGameState(state: GoGameState): Move[] {
  const moves: Move[] = []
  for (const entry of state.move_history) {
    const move = goMoveToKatagoMove(entry)
    if (move) moves.push(move)
  }
  return moves
}

function applyMove(board: BoardState, move: Move): BoardState {
  const next = cloneBoard(board)
  if (move.x < 0 || move.y < 0) return next
  next[move.y][move.x] = move.player
  return next
}

function boardAtHistoryIndex(moves: Move[], index: number): BoardState {
  let board = emptyBoard()
  for (let i = 0; i < index; i++) {
    board = applyMove(board, moves[i])
  }
  return board
}

export function legalizeMove(action: GoAiAction, state: GoGameState): GoAiAction {
  const legal = state.legal_plays ?? []
  if (legal.length === 0) return { type: 'pass' }
  if (action.type === 'pass') return { type: 'pass' }
  const coord = action.coord?.toLowerCase()
  if (coord && legal.some((p) => p.coord === coord)) {
    return { type: 'play', coord }
  }
  return { type: 'play', coord: legal[0].coord }
}

export function katagoPositionFromGameState(state: GoGameState, aiColor: 'B' | 'W') {
  const komi = Number(state.settings?.komi ?? DEFAULT_KOMI)
  const board = boardFromMatrix(state.board)
  const moveHistory = movesFromGameState(state)
  const len = moveHistory.length
  const previousBoard = len > 0 ? boardAtHistoryIndex(moveHistory, len - 1) : board
  const previousPreviousBoard = len > 1 ? boardAtHistoryIndex(moveHistory, len - 2) : previousBoard

  return {
    board,
    previousBoard,
    previousPreviousBoard,
    currentPlayer: toPlayer(aiColor),
    moveHistory,
    komi,
    rules: 'chinese' as const,
  }
}
