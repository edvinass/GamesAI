import planck from 'planck'
import type { CollisionEvent } from './effects'
import type {
  GravityBouncer,
  GravityGear,
  GravityLevel,
  GravityMagnet,
  GravityMovingPlatform,
  GravitySeesaw,
  GravityStaticBody,
} from './levels'
import { DESIGN_HEIGHT, scaledStrokeWidth } from './levels'
import {
  strokeCentroid,
  triangulateStroke,
  worldToLocal,
  type Point,
} from './strokeMesh'

export type { CollisionEvent }

type PlanckWorld = planck.World
type PlanckBody = planck.Body

let nextShapeId = 1

const FIXED_TIMESTEP = 1 / 60
/** Simulated seconds advanced per animation frame (1 = real-time at 60fps). */
const PHYSICS_TIME_SCALE = 2
const GRAVITY = 20
/** Gravity multiplier for the ball when released. */
const FALL_GRAVITY_SCALE = 2.2
/** Stronger gravity for drawn shapes so they settle quickly after each stroke. */
const SHAPE_GRAVITY_SCALE = 5.2
/** Minimal drag so shapes keep accelerating as they fall. */
const SHAPE_LINEAR_DAMPING = 0.005

export interface DrawnShape {
  id: number
  body: PlanckBody
  /** Full stroke outline — rendered as one filled polygon. */
  localPolygon: Point[]
}

export interface GearInstance {
  spec: GravityGear
  body: PlanckBody
  teeth: number
}

export interface MovingPlatformInstance {
  spec: GravityMovingPlatform
  body: PlanckBody
}

export interface BouncerInstance {
  spec: GravityBouncer
}

export interface SeesawInstance {
  spec: GravitySeesaw
  plankBody: PlanckBody
  pivotX: number
  pivotY: number
}

export interface PhysicsWorld {
  world: PlanckWorld
  worldWidth: number
  worldHeight: number
  strokeWidth: number
  layoutScale: number
  ballRadius: number
  ballBody: PlanckBody
  targetBody: PlanckBody
  drawnShapes: DrawnShape[]
  gears: GearInstance[]
  movingPlatforms: MovingPlatformInstance[]
  bouncers: BouncerInstance[]
  seesaws: SeesawInstance[]
  magnets: GravityMagnet[]
  simTime: number
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
      { density: 2.0, friction: 0.18, restitution: 0.2 },
    )
  }
}

/** One rigid body per stroke; outline triangulated into welded triangle fixtures. */
export function addStrokeToWorld(world: PhysicsWorld, stroke: Point[]): DrawnShape | null {
  if (stroke.length < 2) return null

  const center = strokeCentroid(stroke)
  const localCenterline = worldToLocal(center, stroke)
  const mesh = triangulateStroke(localCenterline, world.strokeWidth)
  if (!mesh || mesh.triangles.length === 0) return null

  const body = world.world.createBody({
    type: 'dynamic',
    position: planck.Vec2(center.x, center.y),
    gravityScale: SHAPE_GRAVITY_SCALE,
    linearDamping: SHAPE_LINEAR_DAMPING,
    angularDamping: 0.03,
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

export function getGearCanvasTransform(gear: GearInstance) {
  const pos = gear.body.getPosition()
  return {
    x: pos.x,
    y: pos.y,
    angle: gear.body.getAngle(),
    radius: gear.spec.radius,
    teeth: gear.teeth,
  }
}

export function getMovingPlatformTransform(platform: MovingPlatformInstance) {
  const pos = platform.body.getPosition()
  return {
    x: pos.x,
    y: pos.y,
    width: platform.spec.width,
    height: platform.spec.height,
    axis: platform.spec.axis,
    travel: platform.spec.travel,
  }
}

export function getSeesawTransform(seesaw: SeesawInstance) {
  const pos = seesaw.plankBody.getPosition()
  return {
    x: pos.x,
    y: pos.y,
    angle: seesaw.plankBody.getAngle(),
    width: seesaw.spec.width,
    height: seesaw.spec.height ?? 12,
    pivotX: seesaw.pivotX,
    pivotY: seesaw.pivotY,
  }
}

function addGear(world: PlanckWorld, spec: GravityGear): GearInstance {
  const teeth = spec.teeth ?? 12
  const body = world.createBody({
    type: 'kinematic',
    position: planck.Vec2(spec.x, spec.y),
    angularVelocity: spec.angular_velocity,
  })
  body.createFixture(planck.Circle(spec.radius), {
    friction: 0.85,
    restitution: 0.15,
  })
  return { spec, body, teeth }
}

function addMovingPlatform(world: PlanckWorld, spec: GravityMovingPlatform): MovingPlatformInstance {
  const body = world.createBody({
    type: 'kinematic',
    position: planck.Vec2(spec.x, spec.y),
  })
  body.createFixture(planck.Box(spec.width / 2, spec.height / 2), {
    friction: 0.9,
    restitution: 0.08,
  })
  return { spec, body }
}

function addBouncer(world: PlanckWorld, spec: GravityBouncer): BouncerInstance {
  const body = world.createBody({
    type: 'static',
    position: planck.Vec2(spec.x, spec.y),
    angle: spec.angle ?? 0,
  })
  body.createFixture(planck.Box(spec.width / 2, spec.height / 2), {
    friction: 0.15,
    restitution: spec.restitution ?? 0.92,
  })
  return { spec }
}

function addSeesaw(world: PlanckWorld, spec: GravitySeesaw): SeesawInstance {
  const height = spec.height ?? 12
  const pivot = world.createBody({
    type: 'static',
    position: planck.Vec2(spec.x, spec.y),
  })
  const plank = world.createBody({
    type: 'dynamic',
    position: planck.Vec2(spec.x, spec.y),
    angle: spec.angle ?? 0,
    angularDamping: 0.04,
    linearDamping: 0.02,
  })
  plank.createFixture(planck.Box(spec.width / 2, height / 2), {
    density: 1.8,
    friction: 0.75,
    restitution: 0.06,
  })
  world.createJoint(
    planck.RevoluteJoint(
      {
        enableLimit: true,
        lowerAngle: -0.8,
        upperAngle: 0.8,
      },
      pivot,
      plank,
      planck.Vec2(spec.x, spec.y),
    ),
  )
  return { spec, plankBody: plank, pivotX: spec.x, pivotY: spec.y }
}

function updateMovingPlatforms(platforms: MovingPlatformInstance[], time: number): void {
  for (const platform of platforms) {
    const { spec, body } = platform
    const phase = spec.phase ?? 0
    const offset = (spec.travel / 2) * Math.sin(spec.speed * time + phase)
    const velocity = (spec.travel / 2) * spec.speed * Math.cos(spec.speed * time + phase)
    if (spec.axis === 'x') {
      body.setTransform(planck.Vec2(spec.x + offset, spec.y), 0)
      body.setLinearVelocity(planck.Vec2(velocity, 0))
    } else {
      body.setTransform(planck.Vec2(spec.x, spec.y + offset), 0)
      body.setLinearVelocity(planck.Vec2(0, velocity))
    }
  }
}

function applyMagnetForces(
  magnets: GravityMagnet[],
  bodies: PlanckBody[],
  layoutScale: number,
): void {
  for (const magnet of magnets) {
    for (const body of bodies) {
      const pos = body.getPosition()
      const dx = magnet.x - pos.x
      const dy = magnet.y - pos.y
      const dist = Math.hypot(dx, dy)
      if (dist < 2 || dist > magnet.radius) continue
      const falloff = 1 - dist / magnet.radius
      const force = magnet.strength * falloff * falloff * layoutScale
      body.applyForceToCenter(planck.Vec2((force * dx) / dist, (force * dy) / dist), true)
    }
  }
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

function createLevelStatic(world: PlanckWorld, spec: GravityStaticBody): void {
  if (spec.type === 'circle') {
    addStaticCircle(world, spec.x, spec.y, spec.radius ?? 20)
    return
  }
  addStaticBox(world, spec.x, spec.y, spec.width ?? 40, spec.height ?? 16, spec.angle ?? 0)
}

const BALL_COLLISION_SPEED = 3.5
const SHAPE_COLLISION_SPEED = 2.8
/** Cap for normalizing collision intensity. */
const MAX_IMPACT_SPEED = 18

function contactPoint(contact: planck.Contact): { x: number; y: number } | null {
  const manifold = contact.getWorldManifold(null)
  if (!manifold || manifold.pointCount === 0) return null
  const p = manifold.points[0]
  return { x: p.x, y: p.y }
}

function relativeImpactSpeed(bodyA: PlanckBody, bodyB: PlanckBody): number {
  const velA = bodyA.getLinearVelocity()
  const velB = bodyB.getLinearVelocity()
  return Math.hypot(velA.x - velB.x, velA.y - velB.y)
}

export function createPhysicsWorld(
  level: GravityLevel,
  onWin: () => void,
  onCollision?: (event: CollisionEvent) => void,
): PhysicsWorld {
  const layoutScale = level.layout_scale ?? 1
  const heightScale = level.world_height / DESIGN_HEIGHT
  const world = planck.World({ gravity: planck.Vec2(0, GRAVITY * heightScale) })

  for (const spec of level.static_bodies) {
    createLevelStatic(world, spec)
  }

  const gears: GearInstance[] = (level.gears ?? []).map((spec) => addGear(world, spec))
  const movingPlatforms: MovingPlatformInstance[] = (level.moving_platforms ?? []).map((spec) =>
    addMovingPlatform(world, spec),
  )
  const bouncers: BouncerInstance[] = (level.bouncers ?? []).map((spec) => addBouncer(world, spec))
  const seesaws: SeesawInstance[] = (level.seesaws ?? []).map((spec) => addSeesaw(world, spec))
  const magnets: GravityMagnet[] = level.magnets ?? []

  const ballBody = world.createBody({
    type: 'static',
    position: planck.Vec2(level.ball.x, level.ball.y),
    gravityScale: FALL_GRAVITY_SCALE,
    linearDamping: 0.02,
    angularDamping: 0.05,
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
    strokeWidth: scaledStrokeWidth(level),
    layoutScale,
    ballRadius: level.ball.radius,
    ballBody,
    targetBody,
    drawnShapes: [],
    gears,
    movingPlatforms,
    bouncers,
    seesaws,
    magnets,
    simTime: 0,
    ballReleased: false,
    onWin,
    step: () => {
      for (let i = 0; i < PHYSICS_TIME_SCALE; i++) {
        state.simTime += FIXED_TIMESTEP
        updateMovingPlatforms(movingPlatforms, state.simTime)
        const magnetTargets: PlanckBody[] = [
          state.ballBody,
          ...state.drawnShapes.map((shape) => shape.body),
        ]
        if (state.ballReleased) {
          applyMagnetForces(magnets, magnetTargets, state.layoutScale)
        } else {
          applyMagnetForces(
            magnets,
            state.drawnShapes.map((shape) => shape.body),
            state.layoutScale,
          )
        }
        world.step(FIXED_TIMESTEP)
      }
    },
    cleanup: () => {},
  }

  world.on('begin-contact', (contact) => {
    const fixtureA = contact.getFixtureA()
    const fixtureB = contact.getFixtureB()
    const bodyA = fixtureA.getBody()
    const bodyB = fixtureB.getBody()

    const ballTouchesTarget =
      (bodyA === ballBody && bodyB === targetBody) || (bodyB === ballBody && bodyA === targetBody)
    if (ballTouchesTarget && state.ballReleased) {
      onWin()
      return
    }

    if (!onCollision) return

    const point = contactPoint(contact)
    if (!point) return

    const impact = relativeImpactSpeed(bodyA, bodyB)
    const involvesBall = bodyA === ballBody || bodyB === ballBody
    const involvesDrawnShape = state.drawnShapes.some(
      (s) => s.body === bodyA || s.body === bodyB,
    )

    if (involvesBall && state.ballReleased && impact >= BALL_COLLISION_SPEED) {
      onCollision({
        x: point.x,
        y: point.y,
        intensity: Math.min(1, impact / MAX_IMPACT_SPEED),
        kind: 'ball',
      })
      return
    }

    if (
      involvesDrawnShape &&
      impact >= SHAPE_COLLISION_SPEED &&
      (bodyA.getType() === 'dynamic' || bodyB.getType() === 'dynamic')
    ) {
      onCollision({
        x: point.x,
        y: point.y,
        intensity: Math.min(1, impact / (MAX_IMPACT_SPEED * 0.75)),
        kind: 'shape',
      })
    }
  })

  return state
}

export function releaseBall(world: PhysicsWorld): void {
  if (world.ballReleased) return
  world.ballBody.setType('dynamic')
  world.ballReleased = true
}

export function restoreBallMotion(
  world: PhysicsWorld,
  state: {
    position: { x: number; y: number }
    velocity: { x: number; y: number }
    angle: number
    angularVelocity: number
  },
): void {
  world.ballBody.setPosition(planck.Vec2(state.position.x, state.position.y))
  world.ballBody.setLinearVelocity(planck.Vec2(state.velocity.x, state.velocity.y))
  world.ballBody.setAngle(state.angle)
  world.ballBody.setAngularVelocity(state.angularVelocity)
}

export function isBallReleased(world: PhysicsWorld): boolean {
  return world.ballReleased
}

export function isBallLost(world: PhysicsWorld): boolean {
  if (!world.ballReleased) return false
  const pos = world.ballBody.getPosition()
  const r = world.ballRadius
  return (
    pos.x < -r ||
    pos.x > world.worldWidth + r ||
    pos.y < -r ||
    pos.y > world.worldHeight + r
  )
}

export function isBallSettled(world: PhysicsWorld): boolean {
  const v = world.ballBody.getLinearVelocity()
  const speed = Math.hypot(v.x, v.y)
  const settleSpeed = 0.8 * PHYSICS_TIME_SCALE
  const settleSpin = 0.05 * PHYSICS_TIME_SCALE
  return speed < settleSpeed && Math.abs(world.ballBody.getAngularVelocity()) < settleSpin
}
