import type { BattleshipShip } from '@/types'

export type ShipSegmentRole = 'bow' | 'mid' | 'stern'

export interface ShipSegment {
  shipId: string
  role: ShipSegmentRole
  horizontal: boolean
  index: number
  length: number
  sunk: boolean
  /** Mid-forward cell gets the bridge/funnel. */
  hasBridge: boolean
}

/** Map "row,col" → ship segment for drawing hull pieces. */
export function buildShipSegmentMap(
  ships: BattleshipShip[],
): Map<string, ShipSegment> {
  const map = new Map<string, ShipSegment>()
  for (const ship of ships) {
    if (!ship.cells?.length) continue
    const cells = [...ship.cells].sort((a, b) => a[0] - b[0] || a[1] - b[1])
    const horizontal = cells[0][0] === cells[cells.length - 1][0]
    const length = cells.length
    const bridgeIndex = Math.min(length - 1, Math.max(1, Math.floor(length * 0.55)))

    cells.forEach(([row, col], index) => {
      let role: ShipSegmentRole = 'mid'
      if (index === length - 1) role = 'bow'
      else if (index === 0) role = 'stern'
      map.set(`${row},${col}`, {
        shipId: ship.id,
        role,
        horizontal,
        index,
        length,
        sunk: Boolean(ship.sunk),
        hasBridge: index === bridgeIndex,
      })
    })
  }
  return map
}

export function previewSegments(
  row: number,
  col: number,
  length: number,
  horizontal: boolean,
): Map<string, ShipSegment> {
  const map = new Map<string, ShipSegment>()
  const bridgeIndex = Math.min(length - 1, Math.max(1, Math.floor(length * 0.55)))
  for (let i = 0; i < length; i++) {
    const r = horizontal ? row : row + i
    const c = horizontal ? col + i : col
    let role: ShipSegmentRole = 'mid'
    if (i === length - 1) role = 'bow'
    else if (i === 0) role = 'stern'
    map.set(`${r},${c}`, {
      shipId: 'preview',
      role,
      horizontal,
      index: i,
      length,
      sunk: false,
      hasBridge: i === bridgeIndex,
    })
  }
  return map
}
