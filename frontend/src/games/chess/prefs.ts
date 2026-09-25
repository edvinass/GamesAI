const MOVE_HINTS_KEY = 'chess-move-hints'

export function isMoveHintsEnabled(): boolean {
  try {
    return localStorage.getItem(MOVE_HINTS_KEY) !== '0'
  } catch {
    return true
  }
}

export type BoardView = '2d' | '3d'

const boardViewKey = (roomId: string) => `chess-board-view:${roomId}`

export function getBoardViewPref(roomId: string): BoardView | null {
  try {
    const value = localStorage.getItem(boardViewKey(roomId))
    return value === '2d' || value === '3d' ? value : null
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
