import earcut from 'earcut'
import { STROKE_WIDTH } from './levels'

export type Point = { x: number; y: number }

function tangentAt(points: Point[], index: number): Point {
  const prev = points[Math.max(0, index - 1)]
  const next = points[Math.min(points.length - 1, index + 1)]
  const dx = next.x - prev.x
  const dy = next.y - prev.y
  const len = Math.hypot(dx, dy)
  if (len < 0.001) return { x: 1, y: 0 }
  return { x: dx / len, y: dy / len }
}

/** Closed polygon around a thick stroke (round caps). */
export function strokeOutline(points: Point[], halfWidth: number): Point[] {
  if (points.length < 2) return []

  const left: Point[] = []
  const right: Point[] = []
  for (let i = 0; i < points.length; i++) {
    const t = tangentAt(points, i)
    const nx = -t.y
    const ny = t.x
    left.push({ x: points[i].x + nx * halfWidth, y: points[i].y + ny * halfWidth })
    right.push({ x: points[i].x - nx * halfWidth, y: points[i].y - ny * halfWidth })
  }

  const start = points[0]
  const end = points[points.length - 1]
  const startAngle = Math.atan2(tangentAt(points, 0).y, tangentAt(points, 0).x)
  const endAngle = Math.atan2(
    tangentAt(points, points.length - 1).y,
    tangentAt(points, points.length - 1).x,
  )

  const outline: Point[] = [...left]
  const capSteps = 8
  for (let i = 1; i < capSteps; i++) {
    const a = endAngle + Math.PI / 2 - (Math.PI * i) / capSteps
    outline.push({ x: end.x + Math.cos(a) * halfWidth, y: end.y + Math.sin(a) * halfWidth })
  }
  outline.push(...right.reverse())
  for (let i = 1; i < capSteps; i++) {
    const a = startAngle - Math.PI / 2 - (Math.PI * i) / capSteps
    outline.push({ x: start.x + Math.cos(a) * halfWidth, y: start.y + Math.sin(a) * halfWidth })
  }
  return outline
}

export interface StrokeMesh {
  outline: Point[]
  triangles: [Point, Point, Point][]
}

/** Triangulate stroke outline into convex triangles for one welded rigid body. */
export function triangulateStroke(localCenterline: Point[], strokeWidth = STROKE_WIDTH): StrokeMesh | null {
  if (localCenterline.length < 2) return null

  const outline = strokeOutline(localCenterline, strokeWidth / 2)
  if (outline.length < 3) return null

  const flat: number[] = []
  for (const p of outline) {
    flat.push(p.x, p.y)
  }

  const indices = earcut(flat)
  if (indices.length < 3) return null

  const triangles: [Point, Point, Point][] = []
  for (let i = 0; i < indices.length; i += 3) {
    triangles.push([
      outline[indices[i]],
      outline[indices[i + 1]],
      outline[indices[i + 2]],
    ])
  }

  return { outline, triangles }
}

export function strokeCentroid(points: Point[]): Point {
  let x = 0
  let y = 0
  for (const p of points) {
    x += p.x
    y += p.y
  }
  return { x: x / points.length, y: y / points.length }
}

export function worldToLocal(origin: Point, points: Point[]): Point[] {
  return points.map((p) => ({ x: p.x - origin.x, y: p.y - origin.y }))
}
