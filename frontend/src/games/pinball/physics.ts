import planck from 'planck'

type PlanckWorld = planck.World
type PlanckBody = planck.Body

const FIXED_TIMESTEP = 1 / 60
const PHYSICS_TIME_SCALE = 1.5
/** Arcade gravity — Planck clamps linear speed to ~120, so high g makes launches fail. */
const GRAVITY = 24
/** Sustained plunger speed (at Planck's velocity cap). */
const PLUNGER_SPEED = 110
/** When the ball clears this Y in the shooter lane, gate it into the playfield. */
const LAUNCH_EXIT_Y = 315

/** Flipper rest / raised angles (absolute body angles). */
const LEFT_REST_ANGLE = 0.55
const LEFT_ACTIVE_ANGLE = -0.35
const RIGHT_REST_ANGLE = -0.55
const RIGHT_ACTIVE_ANGLE = 0.35
const FLIPPER_SPEED = 28

export interface BumperSpec {
  x: number
  y: number
  radius: number
  points: number
  color: string
}

export interface TargetSpec {
  x: number
  y: number
  width: number
  height: number
  points: number
  color: string
  id: string
}

export interface PinballLevel {
  worldWidth: number
  worldHeight: number
  ballRadius: number
  launchX: number
  launchY: number
  bumpers: BumperSpec[]
  targets: TargetSpec[]
  flipperLength: number
  flipperWidth: number
}

export interface CollisionEvent {
  type: 'bumper' | 'target' | 'flipper' | 'wall'
  x: number
  y: number
  points: number
  targetId?: string
  intensity: number
}

export interface PinballWorld {
  world: PlanckWorld
  level: PinballLevel
  ballBody: PlanckBody | null
  leftFlipperBody: PlanckBody
  rightFlipperBody: PlanckBody
  bumperBodies: Map<PlanckBody, BumperSpec>
  targetBodies: Map<PlanckBody, TargetSpec>
  hitTargets: Set<string>
  simTime: number
  score: number
  ballsRemaining: number
  ballInPlay: boolean
  ballLaunched: boolean
  leftFlipperActive: boolean
  rightFlipperActive: boolean
  onCollision: (event: CollisionEvent) => void
  onBallLost: () => void
  step: () => void
  launchBall: () => void
  activateLeftFlipper: (active: boolean) => void
  activateRightFlipper: (active: boolean) => void
  resetBall: () => void
  cleanup: () => void
}

const DEFAULT_LEVEL: PinballLevel = {
  worldWidth: 400,
  worldHeight: 700,
  ballRadius: 10,
  launchX: 372,
  launchY: 600,
  flipperLength: 70,
  flipperWidth: 14,
  bumpers: [
    { x: 120, y: 180, radius: 30, points: 100, color: '#ff4757' },
    { x: 280, y: 180, radius: 30, points: 100, color: '#ff4757' },
    { x: 200, y: 120, radius: 35, points: 150, color: '#ffa502' },
    { x: 140, y: 300, radius: 25, points: 75, color: '#2ed573' },
    { x: 260, y: 300, radius: 25, points: 75, color: '#2ed573' },
  ],
  targets: [
    { id: 't1', x: 60, y: 100, width: 40, height: 12, points: 500, color: '#5352ed' },
    { id: 't2', x: 340, y: 100, width: 40, height: 12, points: 500, color: '#5352ed' },
    { id: 't3', x: 80, y: 220, width: 12, height: 50, points: 250, color: '#ff6b81' },
    { id: 't4', x: 320, y: 220, width: 12, height: 50, points: 250, color: '#ff6b81' },
    { id: 't5', x: 200, y: 50, width: 60, height: 12, points: 1000, color: '#eccc68' },
  ],
}

function createWalls(world: PlanckWorld, level: PinballLevel): void {
  const { worldWidth, worldHeight } = level
  const wallThickness = 20

  const leftWallBody = world.createBody({ type: 'static', position: planck.Vec2(0, worldHeight / 2) })
  leftWallBody.createFixture(planck.Box(wallThickness / 2, worldHeight / 2), { friction: 0.3, restitution: 0.4 })

  const rightWallBody = world.createBody({ type: 'static', position: planck.Vec2(worldWidth, worldHeight / 2) })
  rightWallBody.createFixture(planck.Box(wallThickness / 2, worldHeight / 2), { friction: 0.3, restitution: 0.4 })

  const topWallBody = world.createBody({ type: 'static', position: planck.Vec2(worldWidth / 2, 0) })
  topWallBody.createFixture(planck.Box(worldWidth / 2, wallThickness / 2), { friction: 0.3, restitution: 0.6 })

  // Shooter lane wall (top at y≈320). Ball is gated into play above this.
  const launchGuide = world.createBody({ type: 'static', position: planck.Vec2(350, 510) })
  launchGuide.createFixture(planck.Box(3, 190), { friction: 0.1, restitution: 0.2 })

  // Roof over the shooter lane so balls in play cannot fall back into it.
  const laneRoof = world.createBody({ type: 'static', position: planck.Vec2(375, 270) })
  laneRoof.createFixture(planck.Box(22, 4), { friction: 0.2, restitution: 0.3 })

  const leftRamp = world.createBody({ type: 'static', position: planck.Vec2(60, 550), angle: 0.5 })
  leftRamp.createFixture(planck.Box(70, 8), { friction: 0.3, restitution: 0.4 })

  // Keep clear of the shooter lane (x > 350).
  const rightRamp = world.createBody({ type: 'static', position: planck.Vec2(285, 550), angle: -0.5 })
  rightRamp.createFixture(planck.Box(50, 8), { friction: 0.3, restitution: 0.4 })

  const leftOutlane = world.createBody({ type: 'static', position: planck.Vec2(25, 620), angle: 0.3 })
  leftOutlane.createFixture(planck.Box(40, 5), { friction: 0.3, restitution: 0.3 })

  const rightOutlane = world.createBody({ type: 'static', position: planck.Vec2(295, 620), angle: -0.3 })
  rightOutlane.createFixture(planck.Box(28, 5), { friction: 0.3, restitution: 0.3 })
}

function createBumpers(world: PlanckWorld, level: PinballLevel): Map<PlanckBody, BumperSpec> {
  const bumperMap = new Map<PlanckBody, BumperSpec>()

  for (const bumper of level.bumpers) {
    const body = world.createBody({ type: 'static', position: planck.Vec2(bumper.x, bumper.y) })
    body.createFixture(planck.Circle(bumper.radius), { friction: 0.1, restitution: 1.5 })
    bumperMap.set(body, bumper)
  }

  return bumperMap
}

function createTargets(world: PlanckWorld, level: PinballLevel): Map<PlanckBody, TargetSpec> {
  const targetMap = new Map<PlanckBody, TargetSpec>()

  for (const target of level.targets) {
    const body = world.createBody({ type: 'static', position: planck.Vec2(target.x, target.y) })
    body.createFixture(planck.Box(target.width / 2, target.height / 2), { friction: 0.2, restitution: 0.8 })
    targetMap.set(body, target)
  }

  return targetMap
}

function createFlippers(world: PlanckWorld, level: PinballLevel): {
  leftBody: PlanckBody
  rightBody: PlanckBody
} {
  const flipperY = 650
  const leftPivotX = 100
  const rightPivotX = 250

  // Kinematic flippers: infinite effective mass so the ball bounces instead of
  // shoving them. We drive angle via setAngularVelocity each step.
  const leftFlipper = world.createBody({
    type: 'kinematic',
    position: planck.Vec2(leftPivotX, flipperY),
    angle: LEFT_REST_ANGLE,
  })
  leftFlipper.createFixture(
    planck.Polygon([
      planck.Vec2(0, -level.flipperWidth / 2),
      planck.Vec2(level.flipperLength, -level.flipperWidth / 3),
      planck.Vec2(level.flipperLength, level.flipperWidth / 3),
      planck.Vec2(0, level.flipperWidth / 2),
    ]),
    { friction: 0.4, restitution: 0.35 }
  )

  const rightFlipper = world.createBody({
    type: 'kinematic',
    position: planck.Vec2(rightPivotX, flipperY),
    angle: RIGHT_REST_ANGLE,
  })
  rightFlipper.createFixture(
    planck.Polygon([
      planck.Vec2(0, -level.flipperWidth / 2),
      planck.Vec2(-level.flipperLength, -level.flipperWidth / 3),
      planck.Vec2(-level.flipperLength, level.flipperWidth / 3),
      planck.Vec2(0, level.flipperWidth / 2),
    ]),
    { friction: 0.4, restitution: 0.35 }
  )

  return { leftBody: leftFlipper, rightBody: rightFlipper }
}

export function createPinballWorld(
  onCollision: (event: CollisionEvent) => void,
  onBallLost: () => void,
  customLevel?: Partial<PinballLevel>
): PinballWorld {
  const level: PinballLevel = { ...DEFAULT_LEVEL, ...customLevel }
  const world = planck.World({ gravity: planck.Vec2(0, GRAVITY) })

  createWalls(world, level)
  const bumperBodies = createBumpers(world, level)
  const targetBodies = createTargets(world, level)
  const { leftBody, rightBody } = createFlippers(world, level)

  /** True while the plunger is driving the ball up the shooter lane. */
  let plungerActive = false

  const state: PinballWorld = {
    world,
    level,
    ballBody: null,
    leftFlipperBody: leftBody,
    rightFlipperBody: rightBody,
    bumperBodies,
    targetBodies,
    hitTargets: new Set(),
    simTime: 0,
    score: 0,
    ballsRemaining: 3,
    ballInPlay: false,
    ballLaunched: false,
    leftFlipperActive: false,
    rightFlipperActive: false,
    onCollision,
    onBallLost,
    step: () => {
      // Drive kinematic flippers toward rest / active angles.
      const driveFlipper = (body: PlanckBody, active: boolean, rest: number, raised: number) => {
        const target = active ? raised : rest
        const diff = target - body.getAngle()
        if (Math.abs(diff) < 0.01) {
          body.setAngle(target)
          body.setAngularVelocity(0)
        } else {
          body.setAngularVelocity(Math.max(-FLIPPER_SPEED, Math.min(FLIPPER_SPEED, diff * 45)))
        }
      }
      driveFlipper(leftBody, state.leftFlipperActive, LEFT_REST_ANGLE, LEFT_ACTIVE_ANGLE)
      driveFlipper(rightBody, state.rightFlipperActive, RIGHT_REST_ANGLE, RIGHT_ACTIVE_ANGLE)

      for (let i = 0; i < PHYSICS_TIME_SCALE; i++) {
        state.simTime += FIXED_TIMESTEP

        // Planck clamps speed (~120). Re-apply plunger thrust each substep so the
        // ball can climb the shooter lane against gravity, then gate into play.
        if (state.ballBody && plungerActive) {
          const pos = state.ballBody.getPosition()
          if (pos.y > LAUNCH_EXIT_Y) {
            state.ballBody.setLinearVelocity(planck.Vec2(0, -PLUNGER_SPEED))
          }
        }

        world.step(FIXED_TIMESTEP)

        if (state.ballBody && plungerActive) {
          const pos = state.ballBody.getPosition()
          if (pos.y <= LAUNCH_EXIT_Y) {
            state.ballBody.setTransform(planck.Vec2(300, 90), 0)
            state.ballBody.setLinearVelocity(
              planck.Vec2(-45 - Math.random() * 15, 25 + Math.random() * 20)
            )
            plungerActive = false
          }
        }
      }

      if (state.ballBody && state.ballInPlay) {
        const pos = state.ballBody.getPosition()
        if (pos.y > level.worldHeight + 50) {
          state.ballInPlay = false
          state.ballLaunched = false
          plungerActive = false
          world.destroyBody(state.ballBody)
          state.ballBody = null
          state.ballsRemaining--
          onBallLost()
        }
      }
    },
    launchBall: () => {
      if (state.ballInPlay || state.ballsRemaining <= 0) return

      state.ballBody = world.createBody({
        type: 'dynamic',
        position: planck.Vec2(level.launchX, level.launchY),
        bullet: true,
        linearDamping: 0.04,
        angularDamping: 0.15,
      })
      state.ballBody.createFixture(planck.Circle(level.ballRadius), {
        density: 1.0,
        friction: 0.2,
        restitution: 0.5,
      })

      state.ballBody.setLinearVelocity(planck.Vec2(0, -PLUNGER_SPEED))
      plungerActive = true
      state.ballInPlay = true
      state.ballLaunched = true
    },
    activateLeftFlipper: (active: boolean) => {
      state.leftFlipperActive = active
    },
    activateRightFlipper: (active: boolean) => {
      state.rightFlipperActive = active
    },
    resetBall: () => {
      if (state.ballBody) {
        world.destroyBody(state.ballBody)
        state.ballBody = null
      }
      plungerActive = false
      state.ballInPlay = false
      state.ballLaunched = false
    },
    cleanup: () => {
      plungerActive = false
      if (state.ballBody) {
        world.destroyBody(state.ballBody)
      }
    },
  }

  world.on('begin-contact', (contact) => {
    const fixtureA = contact.getFixtureA()
    const fixtureB = contact.getFixtureB()
    const bodyA = fixtureA.getBody()
    const bodyB = fixtureB.getBody()

    if (!state.ballBody) return

    const ballInvolved = bodyA === state.ballBody || bodyB === state.ballBody
    if (!ballInvolved) return

    const otherBody = bodyA === state.ballBody ? bodyB : bodyA

    const bumperSpec = bumperBodies.get(otherBody)
    if (bumperSpec) {
      const vel = state.ballBody.getLinearVelocity()
      const speed = Math.hypot(vel.x, vel.y)

      const pos = otherBody.getPosition()
      const ballPos = state.ballBody.getPosition()
      const dx = ballPos.x - pos.x
      const dy = ballPos.y - pos.y
      const dist = Math.hypot(dx, dy) || 1
      const bounceStrength = 25
      state.ballBody.setLinearVelocity(
        planck.Vec2(
          (dx / dist) * bounceStrength + vel.x * 0.3,
          (dy / dist) * bounceStrength + vel.y * 0.3
        )
      )

      state.score += bumperSpec.points
      onCollision({
        type: 'bumper',
        x: pos.x,
        y: pos.y,
        points: bumperSpec.points,
        intensity: Math.min(1, speed / 30),
      })
      return
    }

    const targetSpec = targetBodies.get(otherBody)
    if (targetSpec && !state.hitTargets.has(targetSpec.id)) {
      state.hitTargets.add(targetSpec.id)
      state.score += targetSpec.points

      const pos = otherBody.getPosition()
      onCollision({
        type: 'target',
        x: pos.x,
        y: pos.y,
        points: targetSpec.points,
        targetId: targetSpec.id,
        intensity: 1,
      })
      return
    }

    if (otherBody === leftBody || otherBody === rightBody) {
      const pos = state.ballBody.getPosition()
      onCollision({
        type: 'flipper',
        x: pos.x,
        y: pos.y,
        points: 0,
        intensity: 0.5,
      })
      return
    }

    // Rail / wall / lane contacts (for SFX).
    {
      const pos = state.ballBody.getPosition()
      const vel = state.ballBody.getLinearVelocity()
      const speed = Math.hypot(vel.x, vel.y)
      if (speed > 8) {
        onCollision({
          type: 'wall',
          x: pos.x,
          y: pos.y,
          points: 0,
          intensity: Math.min(1, speed / 40),
        })
      }
    }
  })

  return state
}


export function getBallPosition(world: PinballWorld): { x: number; y: number } | null {
  if (!world.ballBody) return null
  const pos = world.ballBody.getPosition()
  return { x: pos.x, y: pos.y }
}

export function getFlipperTransforms(world: PinballWorld): {
  left: { x: number; y: number; angle: number }
  right: { x: number; y: number; angle: number }
} {
  const leftPos = world.leftFlipperBody.getPosition()
  const rightPos = world.rightFlipperBody.getPosition()
  return {
    left: { x: leftPos.x, y: leftPos.y, angle: world.leftFlipperBody.getAngle() },
    right: { x: rightPos.x, y: rightPos.y, angle: world.rightFlipperBody.getAngle() },
  }
}
