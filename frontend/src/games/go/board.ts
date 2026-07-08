/** Go rules engine for 9×9 boards — liberties, capture, ko, and area scoring. */

export const BOARD_SIZE = 9
export const FILES = 'abcdefghi'
export const EMPTY = 0
export const BLACK = 1
export const WHITE = 2
export const DEFAULT_KOMI = 5.5

export const COLOR_CHAR: Record<number, string> = { [BLACK]: 'B', [WHITE]: 'W', [EMPTY]: '.' }
export const CHAR_COLOR: Record<string, number> = { B: BLACK, W: WHITE, '.': EMPTY }
export const OPPONENT: Record<number, number> = { [BLACK]: WHITE, [WHITE]: BLACK }

export interface GoPosition {
  board: number[][]
  turn: 'B' | 'W'
  ko_point: [number, number] | null
  consecutive_passes: number
  captured: { B: number; W: number }
}

export interface GoPlay {
  row: number
  col: number
  coord: string
}

export interface GoScoreResult {
  black_stones: number
  white_stones: number
  black_territory: number
  white_territory: number
  black_score: number
  white_score: number
  komi: number
  winner_color: 'B' | 'W' | null
}

function clonePosition(position: GoPosition): GoPosition {
  return {
    board: position.board.map((row) => [...row]),
    turn: position.turn,
    ko_point: position.ko_point ? [...position.ko_point] as [number, number] : null,
    consecutive_passes: position.consecutive_passes,
    captured: { ...position.captured },
  }
}

export function emptyBoard(): number[][] {
  return Array.from({ length: BOARD_SIZE }, () => Array(BOARD_SIZE).fill(EMPTY))
}

export function coordToRc(coord: string): [number, number] {
  const normalized = coord.trim().toLowerCase()
  if (normalized.length !== 2) throw new Error(`Invalid coordinate: ${coord}`)
  const col = FILES.indexOf(normalized[0])
  const row = parseInt(normalized[1], 10) - 1
  if (row < 0 || row >= BOARD_SIZE) throw new Error(`Invalid coordinate: ${coord}`)
  return [row, col]
}

export function rcToCoord(row: number, col: number): string {
  if (row < 0 || row >= BOARD_SIZE || col < 0 || col >= BOARD_SIZE) {
    throw new Error(`Out of bounds: (${row}, ${col})`)
  }
  return `${FILES[col]}${row + 1}`
}

export function createPosition(turn: 'B' | 'W' = 'B'): GoPosition {
  return {
    board: emptyBoard(),
    turn,
    ko_point: null,
    consecutive_passes: 0,
    captured: { B: 0, W: 0 },
  }
}

export function boardMatrix(position: GoPosition): Array<Array<string | null>> {
  return position.board.map((row) =>
    row.map((cell) => (cell !== EMPTY ? COLOR_CHAR[cell] : null)),
  )
}

export function neighbors(row: number, col: number): Array<[number, number]> {
  const result: Array<[number, number]> = []
  for (const [dr, dc] of [[-1, 0], [1, 0], [0, -1], [0, 1]] as const) {
    const nr = row + dr
    const nc = col + dc
    if (nr >= 0 && nr < BOARD_SIZE && nc >= 0 && nc < BOARD_SIZE) {
      result.push([nr, nc])
    }
  }
  return result
}

export function getGroup(board: number[][], row: number, col: number): Set<string> {
  const color = board[row][col]
  if (color === EMPTY) return new Set()
  const key = (r: number, c: number) => `${r},${c}`
  const stack: Array<[number, number]> = [[row, col]]
  const group = new Set<string>()
  while (stack.length) {
    const [r, c] = stack.pop()!
    const k = key(r, c)
    if (group.has(k) || board[r][c] !== color) continue
    group.add(k)
    for (const [nr, nc] of neighbors(r, c)) {
      if (!group.has(key(nr, nc)) && board[nr][nc] === color) {
        stack.push([nr, nc])
      }
    }
  }
  return group
}

export function groupLiberties(board: number[][], group: Set<string>): Set<string> {
  const libs = new Set<string>()
  for (const key of group) {
    const [r, c] = key.split(',').map(Number)
    for (const [nr, nc] of neighbors(r, c)) {
      if (board[nr][nc] === EMPTY) libs.add(`${nr},${nc}`)
    }
  }
  return libs
}

function removeGroup(board: number[][], group: Set<string>): number {
  for (const key of group) {
    const [r, c] = key.split(',').map(Number)
    board[r][c] = EMPTY
  }
  return group.size
}

export function capturesIfPlayed(
  board: number[][],
  row: number,
  col: number,
  color: number,
): Array<Set<string>> {
  const captured: Array<Set<string>> = []
  const opponent = OPPONENT[color]
  for (const [nr, nc] of neighbors(row, col)) {
    if (board[nr][nc] !== opponent) continue
    const group = getGroup(board, nr, nc)
    if (groupLiberties(board, group).size === 0) captured.push(group)
  }
  return captured
}

export function isLegalPlay(position: GoPosition, row: number, col: number): boolean {
  const board = position.board
  if (board[row][col] !== EMPTY) return false

  const color = CHAR_COLOR[position.turn]
  const ko = position.ko_point
  if (ko && row === ko[0] && col === ko[1]) return false

  const temp = board.map((r) => [...r])
  temp[row][col] = color
  for (const group of capturesIfPlayed(temp, row, col, color)) {
    removeGroup(temp, group)
  }
  const ownGroup = getGroup(temp, row, col)
  return groupLiberties(temp, ownGroup).size > 0
}

export function generateLegalPlays(position: GoPosition): GoPlay[] {
  const plays: GoPlay[] = []
  for (let row = 0; row < BOARD_SIZE; row++) {
    for (let col = 0; col < BOARD_SIZE; col++) {
      if (isLegalPlay(position, row, col)) {
        plays.push({ row, col, coord: rcToCoord(row, col) })
      }
    }
  }
  return plays
}

export function applyPlayRaw(position: GoPosition, row: number, col: number): GoPosition {
  if (!isLegalPlay(position, row, col)) throw new Error('Illegal play')

  const newPos = clonePosition(position)
  const board = newPos.board
  const color = CHAR_COLOR[newPos.turn]
  const colorChar = COLOR_CHAR[color] as 'B' | 'W'

  board[row][col] = color
  let capturedStones = 0
  let koPoint: [number, number] | null = null

  for (const [nr, nc] of neighbors(row, col)) {
    if (board[nr][nc] !== OPPONENT[color]) continue
    const group = getGroup(board, nr, nc)
    if (groupLiberties(board, group).size === 0) {
      let capturedPoint: [number, number] | null = null
      if (group.size === 1) {
        const [kr, kc] = [...group][0].split(',').map(Number)
        capturedPoint = [kr, kc]
      }
      const size = removeGroup(board, group)
      capturedStones += size
      if (size === 1 && groupLiberties(board, getGroup(board, row, col)).size === 1) {
        koPoint = capturedPoint
      }
    }
  }

  newPos.captured[colorChar] += capturedStones
  newPos.ko_point = koPoint
  newPos.consecutive_passes = 0
  newPos.turn = newPos.turn === 'B' ? 'W' : 'B'
  return newPos
}

export function applyPassRaw(position: GoPosition): GoPosition {
  const newPos = clonePosition(position)
  newPos.ko_point = null
  newPos.consecutive_passes += 1
  newPos.turn = newPos.turn === 'B' ? 'W' : 'B'
  return newPos
}

export function gameOverByPasses(position: GoPosition): boolean {
  return position.consecutive_passes >= 2
}

function emptyRegions(board: number[][]): Array<Set<string>> {
  const seen = new Set<string>()
  const regions: Array<Set<string>> = []
  const key = (r: number, c: number) => `${r},${c}`

  for (let row = 0; row < BOARD_SIZE; row++) {
    for (let col = 0; col < BOARD_SIZE; col++) {
      if (board[row][col] !== EMPTY || seen.has(key(row, col))) continue
      const stack: Array<[number, number]> = [[row, col]]
      const region = new Set<string>()
      while (stack.length) {
        const [r, c] = stack.pop()!
        const k = key(r, c)
        if (region.has(k) || board[r][c] !== EMPTY) continue
        region.add(k)
        for (const [nr, nc] of neighbors(r, c)) {
          if (!region.has(key(nr, nc))) stack.push([nr, nc])
        }
      }
      for (const k of region) seen.add(k)
      regions.push(region)
    }
  }
  return regions
}

function regionOwner(board: number[][], region: Set<string>): number | null {
  const adjacent = new Set<number>()
  for (const key of region) {
    const [r, c] = key.split(',').map(Number)
    for (const [nr, nc] of neighbors(r, c)) {
      const stone = board[nr][nc]
      if (stone !== EMPTY) adjacent.add(stone)
    }
  }
  if (adjacent.size === 1 && adjacent.has(BLACK)) return BLACK
  if (adjacent.size === 1 && adjacent.has(WHITE)) return WHITE
  return null
}

export function scorePosition(position: GoPosition, komi = DEFAULT_KOMI): GoScoreResult {
  const board = position.board
  let blackStones = 0
  let whiteStones = 0
  for (const row of board) {
    for (const cell of row) {
      if (cell === BLACK) blackStones++
      else if (cell === WHITE) whiteStones++
    }
  }

  let blackTerritory = 0
  let whiteTerritory = 0
  for (const region of emptyRegions(board)) {
    const owner = regionOwner(board, region)
    if (owner === BLACK) blackTerritory += region.size
    else if (owner === WHITE) whiteTerritory += region.size
  }

  const blackScore = blackStones + blackTerritory
  const whiteScore = whiteStones + whiteTerritory + komi
  let winnerColor: 'B' | 'W' | null = null
  if (blackScore > whiteScore) winnerColor = 'B'
  else if (whiteScore > blackScore) winnerColor = 'W'

  return {
    black_stones: blackStones,
    white_stones: whiteStones,
    black_territory: blackTerritory,
    white_territory: whiteTerritory,
    black_score: blackScore,
    white_score: whiteScore,
    komi,
    winner_color: winnerColor,
  }
}

export function findPlay(position: GoPosition, coord: string): GoPlay | null {
  const [row, col] = coordToRc(coord)
  return generateLegalPlays(position).find((p) => p.row === row && p.col === col) ?? null
}
