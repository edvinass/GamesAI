export interface GravityStaticBody {
  type: 'rect' | 'circle'
  x: number
  y: number
  width?: number
  height?: number
  radius?: number
  angle?: number
}

export interface GravityLevel {
  id: number
  name: string
  hint: string
  world_width: number
  world_height: number
  max_ink: number
  ball: { x: number; y: number; radius: number }
  target: { x: number; y: number; radius: number }
  static_bodies: GravityStaticBody[]
}

export const GRAVITY_LEVELS: GravityLevel[] = [
  {
    id: 1,
    name: 'First Drop',
    hint: 'Draw shapes — they fall right away. Build a ramp, then drop the ball.',
    world_width: 800,
    world_height: 600,
    max_ink: 420,
    ball: { x: 140, y: 90, radius: 14 },
    target: { x: 660, y: 520, radius: 28 },
    static_bodies: [
      { type: 'rect', x: 400, y: 580, width: 760, height: 24 },
      { type: 'rect', x: 120, y: 420, width: 180, height: 16 },
    ],
  },
  {
    id: 2,
    name: 'The Gap',
    hint: 'Drop as many bridge pieces as you need to cross the gap.',
    world_width: 800,
    world_height: 600,
    max_ink: 380,
    ball: { x: 110, y: 80, radius: 14 },
    target: { x: 690, y: 500, radius: 26 },
    static_bodies: [
      { type: 'rect', x: 400, y: 580, width: 760, height: 24 },
      { type: 'rect', x: 150, y: 360, width: 220, height: 16 },
      { type: 'rect', x: 650, y: 360, width: 220, height: 16 },
    ],
  },
  {
    id: 3,
    name: 'Bounce Pad',
    hint: 'Draw falling platforms to bounce the ball toward the target.',
    world_width: 800,
    world_height: 600,
    max_ink: 360,
    ball: { x: 120, y: 70, radius: 14 },
    target: { x: 700, y: 540, radius: 24 },
    static_bodies: [
      { type: 'rect', x: 400, y: 580, width: 760, height: 24 },
      { type: 'rect', x: 400, y: 460, width: 520, height: 16, angle: -0.18 },
      { type: 'rect', x: 620, y: 320, width: 140, height: 16 },
    ],
  },
  {
    id: 4,
    name: 'Pinball',
    hint: 'Keep drawing walls and ramps while the ball moves.',
    world_width: 800,
    world_height: 600,
    max_ink: 340,
    ball: { x: 400, y: 80, radius: 14 },
    target: { x: 720, y: 520, radius: 22 },
    static_bodies: [
      { type: 'rect', x: 400, y: 580, width: 760, height: 24 },
      { type: 'rect', x: 250, y: 280, width: 120, height: 16, angle: 0.5 },
      { type: 'rect', x: 550, y: 380, width: 120, height: 16, angle: -0.45 },
      { type: 'rect', x: 400, y: 480, width: 80, height: 80 },
    ],
  },
  {
    id: 5,
    name: 'Master Stroke',
    hint: 'Every shape you draw falls — plan carefully, then drop the ball.',
    world_width: 800,
    world_height: 600,
    max_ink: 260,
    ball: { x: 90, y: 100, radius: 13 },
    target: { x: 710, y: 510, radius: 20 },
    static_bodies: [
      { type: 'rect', x: 400, y: 580, width: 760, height: 24 },
      { type: 'rect', x: 160, y: 400, width: 140, height: 14 },
      { type: 'rect', x: 520, y: 320, width: 160, height: 14, angle: 0.35 },
      { type: 'rect', x: 680, y: 440, width: 100, height: 14, angle: -0.25 },
    ],
  },
]

export const STROKE_WIDTH = 10

export function strokeLength(points: { x: number; y: number }[]): number {
  let total = 0
  for (let i = 1; i < points.length; i++) {
    total += Math.hypot(points[i].x - points[i - 1].x, points[i].y - points[i - 1].y)
  }
  return total
}

export function totalInkUsed(strokes: { x: number; y: number }[][]): number {
  return strokes.reduce((sum, stroke) => sum + strokeLength(stroke), 0)
}
