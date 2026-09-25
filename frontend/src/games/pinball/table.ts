/** Static geometry for the classic pinball table (world units, y grows downward). */

export interface Vec {
  x: number
  y: number
}

export type SegmentKind = 'wall' | 'rubber' | 'sling' | 'gate' | 'drop' | 'standup'

export interface Segment {
  a: Vec
  b: Vec
  kind: SegmentKind
  restitution: number
  id?: string
  /** Solid only when approached from the (b - a) rotated side: normal = (d.y, -d.x). */
  oneWay?: boolean
}

export interface CircleObstacle {
  c: Vec
  r: number
  kind: 'post' | 'bumper'
  restitution: number
  id: string
  color?: string
}

export type SensorKind = 'rollover' | 'inlane' | 'outlane'

export interface Sensor {
  c: Vec
  r: number
  kind: SensorKind
  id: string
}

export interface FlipperSpec {
  side: 'left' | 'right'
  pivot: Vec
  length: number
  /** Radius at the pivot end. */
  r0: number
  /** Radius at the tip. */
  r1: number
  restAngle: number
  activeAngle: number
}

export interface SlingSpec {
  id: string
  points: [Vec, Vec, Vec]
}

export interface TableLayout {
  width: number
  height: number
  ballRadius: number
  playLeft: number
  playRight: number
  laneRight: number
  domeCenter: Vec
  domeRadius: number
  segments: Segment[]
  circles: CircleObstacle[]
  sensors: Sensor[]
  flippers: FlipperSpec[]
  slings: SlingSpec[]
  dropTargets: { id: string; a: Vec; b: Vec }[]
  standups: { id: string; a: Vec; b: Vec }[]
  saucer: { c: Vec; r: number }
  plunger: { x0: number; x1: number; restY: number; maxPull: number }
  laneGuides: number[]
  rollovers: Vec[]
  drainY: number
}

const W = 446
const H = 880
const PLAY_LEFT = 14
const PLAY_RIGHT = 404
const LANE_RIGHT = 432
const CX = (PLAY_LEFT + PLAY_RIGHT) / 2
const DOME_C = { x: (PLAY_LEFT + LANE_RIGHT) / 2, y: 223 }
const DOME_R = (LANE_RIGHT - PLAY_LEFT) / 2

const WALL_E = 0.35
const RUBBER_E = 0.72

const v = (x: number, y: number): Vec => ({ x, y })
const mirror = (p: Vec): Vec => ({ x: 2 * CX - p.x, y: p.y })

function polyline(points: Vec[], kind: SegmentKind, restitution: number): Segment[] {
  const out: Segment[] = []
  for (let i = 0; i < points.length - 1; i++) {
    out.push({ a: points[i], b: points[i + 1], kind, restitution })
  }
  return out
}

function domePoints(steps: number): Vec[] {
  const pts: Vec[] = []
  for (let i = 0; i <= steps; i++) {
    const t = Math.PI + (Math.PI * i) / steps
    pts.push(v(DOME_C.x + Math.cos(t) * DOME_R, DOME_C.y + Math.sin(t) * DOME_R))
  }
  return pts
}

export function buildTable(): TableLayout {
  const segments: Segment[] = []
  const circles: CircleObstacle[] = []

  // Outer cabinet: left wall, dome, right wall of the shooter lane.
  segments.push(
    ...polyline([v(PLAY_LEFT, H + 40), ...domePoints(72), v(LANE_RIGHT, H + 40)], 'wall', WALL_E),
  )

  // Shooter lane divider and the one-way gate at its top.
  const gateY = 212
  const gateEndY = 199
  const gateEndX = DOME_C.x + Math.sqrt(DOME_R ** 2 - (gateEndY - DOME_C.y) ** 2)
  segments.push({ a: v(PLAY_RIGHT, H + 40), b: v(PLAY_RIGHT, gateY), kind: 'wall', restitution: WALL_E })
  segments.push({ a: v(PLAY_RIGHT, gateY), b: v(gateEndX, gateEndY), kind: 'gate', restitution: 0.2, oneWay: true })

  // Side pockets housing the drop targets (left) and standups (right).
  const leftPocket = [v(PLAY_LEFT, 262), v(34, 282), v(34, 396), v(PLAY_LEFT, 416)]
  segments.push(...polyline(leftPocket, 'wall', WALL_E))
  segments.push(...polyline(leftPocket.map(mirror), 'wall', WALL_E))

  // Top rollover lane guides.
  const laneGuides = [CX - 60, CX - 20, CX + 20, CX + 60]
  for (const x of laneGuides) {
    segments.push({ a: v(x, 72), b: v(x, 112), kind: 'wall', restitution: WALL_E })
    circles.push({ c: v(x, 72), r: 3, kind: 'post', restitution: 0.5, id: `guide-${x}` })
  }
  const rollovers = [v(CX - 40, 95), v(CX, 95), v(CX + 40, 95)]

  // Pop bumpers.
  const bumperColors = ['#ff3b4a', '#ffb020', '#2fa8ff']
  ;[v(CX - 40, 175), v(CX + 40, 175), v(CX, 235)].forEach((c, i) => {
    circles.push({ c, r: 22, kind: 'bumper', restitution: 0.6, id: `bumper${i}`, color: bumperColors[i] })
  })

  // Lower playfield: outlane dividers, inlane guides, slingshots (left, then mirrored).
  const slings: SlingSpec[] = []
  for (const side of ['left', 'right'] as const) {
    const m = side === 'left' ? (p: Vec) => p : mirror
    const dividerTop = m(v(38, 610))
    const dividerBottom = m(v(38, 700))
    const guideEnd = m(v(122, 770))
    segments.push({ a: dividerTop, b: dividerBottom, kind: 'wall', restitution: WALL_E })
    segments.push({ a: dividerBottom, b: guideEnd, kind: 'wall', restitution: WALL_E })
    circles.push({ c: dividerTop, r: 4, kind: 'post', restitution: RUBBER_E, id: `divider-${side}` })

    const A = m(v(66, 608))
    const B = m(v(66, 690))
    const C = m(v(112, 722))
    const id = side === 'left' ? 'slingL' : 'slingR'
    slings.push({ id, points: [A, B, C] })
    segments.push({ a: A, b: C, kind: 'sling', restitution: RUBBER_E, id })
    segments.push({ a: A, b: B, kind: 'rubber', restitution: RUBBER_E })
    segments.push({ a: B, b: C, kind: 'rubber', restitution: RUBBER_E })
    circles.push({ c: A, r: 5, kind: 'post', restitution: RUBBER_E, id: `${id}-top` })
    circles.push({ c: C, r: 5, kind: 'post', restitution: RUBBER_E, id: `${id}-bottom` })
  }

  // Drop target bank (left) — kept separate so the engine can toggle them.
  const dropTargets = [298, 324, 350, 376].map((y, i) => ({
    id: `drop${i}`,
    a: v(41, y - 11),
    b: v(41, y + 11),
  }))
  // Standup targets (right).
  const standups = [305, 339, 373].map((y, i) => ({
    id: `standup${i}`,
    a: v(2 * CX - 41, y - 13),
    b: v(2 * CX - 41, y + 13),
  }))

  const sensors: Sensor[] = [
    ...rollovers.map((c, i) => ({ c, r: 10, kind: 'rollover' as const, id: `lane${i}` })),
    { c: v(52, 655), r: 10, kind: 'inlane', id: 'inlaneL' },
    { c: mirror(v(52, 655)), r: 10, kind: 'inlane', id: 'inlaneR' },
    { c: v(26, 760), r: 10, kind: 'outlane', id: 'outlaneL' },
    { c: mirror(v(26, 760)), r: 10, kind: 'outlane', id: 'outlaneR' },
  ]

  const flipperY = 780
  const flippers: FlipperSpec[] = [
    {
      side: 'left',
      pivot: v(CX - 78, flipperY),
      length: 70,
      r0: 11,
      r1: 6,
      restAngle: 0.52,
      activeAngle: -0.52,
    },
    {
      side: 'right',
      pivot: v(CX + 78, flipperY),
      length: 70,
      r0: 11,
      r1: 6,
      restAngle: Math.PI - 0.52,
      activeAngle: Math.PI + 0.52,
    },
  ]

  return {
    width: W,
    height: H,
    ballRadius: 9,
    playLeft: PLAY_LEFT,
    playRight: PLAY_RIGHT,
    laneRight: LANE_RIGHT,
    domeCenter: DOME_C,
    domeRadius: DOME_R,
    segments,
    circles,
    sensors,
    flippers,
    slings,
    dropTargets,
    standups,
    saucer: { c: v(CX, 350), r: 13 },
    plunger: { x0: PLAY_RIGHT, x1: LANE_RIGHT, restY: 840, maxPull: 42 },
    laneGuides,
    rollovers,
    drainY: H + 12,
  }
}
