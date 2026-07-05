import planck from 'planck'
import type { GravityLevel, GravityStaticBody } from './levels'
import {
  strokeCentroid,
  triangulateStroke,
  worldToLocal,
  type Point,
} from './strokeMesh'

type PlanckWorld = planck.World
type PlanckBody = planck.Body

let nextShapeId = 1

export interface DrawnShape {
  id: number
  body: PlanckBody
  /** Full stroke outline — rendered as one filled polygon. */
  localPolygon: Point[]
}

export interface PhysicsWorld {
  world: PlanckWorld
  worldWidth: number
  worldHeight: number
  ballBody: PlanckBody
  targetBody: PlanckBody
  drawnShapes: DrawnShape[]
  ballReleased: boolean
  onWin: () => void
  step: () => void
  cleanup: () => void
}

function attachTriangulatedStroke(body: PlanckBody, mesh: ReturnType<typeof triangulateStroke>): void {
  if (!mesh) return
  for (const [a, b, c] of mesh.triangles) {
    body.createFixture(
      planck.Polygon([planck.Vec2(a.x, a.y), planck.Vec2(b.x, b.y), planck.Vec2(c.x, c.y)]),
      { density: 2.0, friction: 0.85, restitution: 0.12 },
    )
  }
}

/** One rigid body per stroke; outline triangulated into welded triangle fixtures. */
export function addStrokeToWorld(world: PhysicsWorld, stroke: Point[]): DrawnShape | null {
  if (stroke.length < 2) return null

  const center = strokeCentroid(stroke)
  const localCenterline = worldToLocal(center, stroke)
  const mesh = triangulateStroke(localCenterline)
  if (!mesh || mesh.triangles.length === 0) return null

  const body = world.world.createBody({
    type: 'dynamic',
    position: planck.Vec2(center.x, center.y),
    linearDamping: 0.05,
    angularDamping: 0.08,
  })

  attachTriangulatedStroke(body, mesh)

  const shape: DrawnShape = {
    id: nextShapeId++,
    body,
    localPolygon: mesh.outline,
  }
  world.drawnShapes.push(shape)
  return shape
}

export function removeShapeFromWorld(world: PhysicsWorld, shape: DrawnShape): void {
  world.world.destroyBody(shape.body)
  world.drawnShapes = world.drawnShapes.filter((s) => s.id !== shape.id)
}

export function removeAllDrawnShapes(world: PhysicsWorld): void {
  for (const shape of [...world.drawnShapes]) {
    world.world.destroyBody(shape.body)
  }
  world.drawnShapes = []
}

export function getShapeCanvasTransform(shape: DrawnShape) {
  const pos = shape.body.getPosition()
  return {
    x: pos.x,
    y: pos.y,
    angle: shape.body.getAngle(),
  }
}

export function getBallCanvasTransform(world: PhysicsWorld) {
  const pos = world.ballBody.getPosition()
  return { x: pos.x, y: pos.y, angle: world.ballBody.getAngle() }
}

function addStaticBox(
  world: PlanckWorld,
  x: number,
  y: number,
  width: number,
  height: number,
  angle = 0,
): void {
  const body = world.createBody({
    type: 'static',
    position: planck.Vec2(x, y),
    angle,
  })
  body.createFixture(planck.Box(width / 2, height / 2), { friction: 0.9, restitution: 0.05 })
}

function addStaticCircle(world: PlanckWorld, x: number, y: number, radius: number): void {
  const body = world.createBody({ type: 'static', position: planck.Vec2(x, y) })
  body.createFixture(planck.Circle(radius), { friction: 0.9 })
}

function createBoundaries(world: PlanckWorld, width: number, height: number): void {
  const thickness = 24
  addStaticBox(world, width / 2, height + thickness / 2, width, thickness)
  addStaticBox(world, -thickness / 2, height / 2, thickness, height * 2)
  addStaticBox(world, width + thickness / 2, height / 2, thickness, height * 2)
}

function createLevelStatic(world: PlanckWorld, spec: GravityStaticBody): void {
  if (spec.type === 'circle') {
    addStaticCircle(world, spec.x, spec.y, spec.radius ?? 20)
    return
  }
  addStaticBox(world, spec.x, spec.y, spec.width ?? 40, spec.height ?? 16, spec.angle ?? 0)
}

export function createPhysicsWorld(level: GravityLevel, onWin: () => void): PhysicsWorld {
  const world = planck.World({ gravity: planck.Vec2(0, 20) })

  createBoundaries(world, level.world_width, level.world_height)
  for (const spec of level.static_bodies) {
    createLevelStatic(world, spec)
  }

  const ballBody = world.createBody({
    type: 'static',
    position: planck.Vec2(level.ball.x, level.ball.y),
    linearDamping: 0.02,
    angularDamping: 0.02,
  })
  ballBody.createFixture(planck.Circle(level.ball.radius), {
    density: 2.5,
    friction: 0.35,
    restitution: 0.35,
  })

  const targetBody = world.createBody({
    type: 'static',
    position: planck.Vec2(level.target.x, level.target.y),
  })
  targetBody.createFixture(planck.Circle(level.target.radius), { isSensor: true })

  const state: PhysicsWorld = {
    world,
    worldWidth: level.world_width,
    worldHeight: level.world_height,
    ballBody,
    targetBody,
    drawnShapes: [],
    ballReleased: false,
    onWin,
    step: () => {
      world.step(1 / 60)
    },
    cleanup: () => {},
  }

  world.on('begin-contact', (contact) => {
    if (!state.ballReleased) return
    const fixtureA = contact.getFixtureA()
    const fixtureB = contact.getFixtureB()
    const bodyA = fixtureA.getBody()
    const bodyB = fixtureB.getBody()
    const ballTouchesTarget =
      (bodyA === ballBody && bodyB === targetBody) || (bodyB === ballBody && bodyA === targetBody)
    if (ballTouchesTarget) onWin()
  })

  return state
}

export function releaseBall(world: PhysicsWorld): void {
  if (world.ballReleased) return
  world.ballBody.setType('dynamic')
  world.ballReleased = true
}

export function isBallReleased(world: PhysicsWorld): boolean {
  return world.ballReleased
}

export function isBallLost(world: PhysicsWorld): boolean {
  const pos = world.ballBody.getPosition()
  return (
    pos.y > world.worldHeight + 80 ||
    pos.x < -60 ||
    pos.x > world.worldWidth + 60
  )
}

export function isBallSettled(world: PhysicsWorld): boolean {
  const v = world.ballBody.getLinearVelocity()
  const speed = Math.hypot(v.x, v.y)
  return speed < 0.8 && Math.abs(world.ballBody.getAngularVelocity()) < 0.05
}
