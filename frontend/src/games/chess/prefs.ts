const MOVE_HINTS_KEY = 'chess-move-hints'

export function isMoveHintsEnabled(): boolean {
  try {
    return localStorage.getItem(MOVE_HINTS_KEY) !== '0'
  } catch {
    return true
  }
}

export type BoardView = '2d' | '3d' | 'clay'

export function isBoardView(value: unknown): value is BoardView {
  return value === '2d' || value === '3d' || value === 'clay'
}

const DEFAULT_VIEW_KEY = 'chess-board-view'
const boardViewKey = (roomId: string) => `chess-board-view:${roomId}`

/** Style chosen from the game or the lessons. Null until the player picks one, which means Iso. */
export function getDefaultBoardView(): BoardView | null {
  try {
    const value = localStorage.getItem(DEFAULT_VIEW_KEY)
    return isBoardView(value) ? value : null
  } catch {
    return null
  }
}

export function setDefaultBoardView(value: BoardView): void {
  try {
    localStorage.setItem(DEFAULT_VIEW_KEY, value)
  } catch {
    /* ignore */
  }
}

export function getBoardViewPref(roomId: string): BoardView | null {
  try {
    const value = localStorage.getItem(boardViewKey(roomId))
    return isBoardView(value) ? value : null
  } catch {
    return null
  }
}

export function setBoardViewPref(roomId: string, value: BoardView): void {
  try {
    localStorage.setItem(boardViewKey(roomId), value)
  } catch {
    /* ignore */
  }
}

export function setMoveHintsEnabled(value: boolean): void {
  try {
    localStorage.setItem(MOVE_HINTS_KEY, value ? '1' : '0')
  } catch {
    /* ignore */
  }
}
