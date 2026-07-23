import planck from 'planck'

type PlanckWorld = planck.World
type PlanckBody = planck.Body

const FIXED_TIMESTEP = 1 / 60
const PHYSICS_TIME_SCALE = 1.5
/** Arcade gravity — Planck clamps linear speed to ~120, so high g makes launches fail. */
const GRAVITY = 18
/** Sustained plunger speed (at Planck's velocity cap). */
const PLUNGER_SPEED = 110
/** Stop forcing plunger thrust once the ball reaches the top curve. */
const PLUNGER_RELEASE_Y = 160

/** Flipper rest / raised angles (absolute body angles). */
const LEFT_REST_ANGLE = 0.55
const LEFT_ACTIVE_ANGLE = -0.4
const RIGHT_REST_ANGLE = -0.55
const RIGHT_ACTIVE_ANGLE = 0.4
const FLIPPER_SPEED = 65
/** Extra kick applied on flipper contact while the flipper is raised/swinging. */
const FLIPPER_KICK_MIN = 55
const FLIPPER_KICK_MAX = 115

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
  /** True once the ball has left the shooter lane and the one-way gate has closed. */
  laneGateClosed: boolean
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

  // Shooter lane wall — opens near the top so the ball can curve into play.
  // Guide spans y≈200..700 (center 450, half-height 250).
  const launchGuide = world.createBody({ type: 'static', position: planck.Vec2(350, 450) })
  launchGuide.createFixture(planck.Box(3, 250), { friction: 0.05, restitution: 0.1 })

  // Top-right curve: sends a launched ball left into the playfield (no teleport).
  const laneCurveA = world.createBody({ type: 'static', position: planck.Vec2(378, 120), angle: 0.95 })
  laneCurveA.createFixture(planck.Box(55, 5), { friction: 0.05, restitution: 0.45 })

  const laneCurveB = world.createBody({ type: 'static', position: planck.Vec2(355, 55), angle: 0.4 })
  laneCurveB.createFixture(planck.Box(35, 5), { friction: 0.05, restitution: 0.4 })

  // Inlanes / outlanes: dead (near-zero restitution) so they guide the ball
  // toward the flippers instead of slingshotting it around weirdly.
  const leftRamp = world.createBody({ type: 'static', position: planck.Vec2(50, 540), angle: 0.6 })
  leftRamp.createFixture(planck.Box(48, 4), { friction: 0.55, restitution: 0.02 })

  const rightRamp = world.createBody({ type: 'static', position: planck.Vec2(300, 540), angle: -0.6 })
  rightRamp.createFixture(planck.Box(40, 4), { friction: 0.55, restitution: 0.02 })

  const leftOutlane = world.createBody({ type: 'static', position: planck.Vec2(22, 625), angle: 0.35 })
  leftOutlane.createFixture(planck.Box(32, 4), { friction: 0.5, restitution: 0.02 })

  const rightOutlane = world.createBody({ type: 'static', position: planck.Vec2(300, 625), angle: -0.35 })
  rightOutlane.createFixture(planck.Box(28, 4), { friction: 0.5, restitution: 0.02 })
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
    { friction: 0.85, restitution: 0.05 }
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
    { friction: 0.85, restitution: 0.05 }
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

  // Classic one-way shooter-lane gate: when closed, extends the lane wall up to
  // the top curves so the ball cannot fall back in from the playfield.
  // Starts open so the plunge can exit left through the curve.
  const laneGate = world.createBody({ type: 'static', position: planck.Vec2(350, 115) })
  laneGate.createFixture(planck.Box(3, 95), { friction: 0.2, restitution: 0.15 })
  laneGate.setActive(false)

  /** True while the plunger is driving the ball up the shooter lane. */
  let plungerActive = false
  /** Queued flipper kick applied after the physics step (solver would overwrite it otherwise). */
  let pendingFlipperKick: { vx: number; vy: number } | null = null

  const openLaneGate = () => {
    laneGate.setActive(false)
    state.laneGateClosed = false
  }
  const closeLaneGate = () => {
    if (state.laneGateClosed) return
    laneGate.setActive(true)
    state.laneGateClosed = true
  }

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
    laneGateClosed: false,
    onCollision,
    onBallLost,
    step: () => {
      // Drive kinematic flippers toward rest / active angles each substep so they
      // don't overshoot when PHYSICS_TIME_SCALE > 1.
      const driveFlipper = (body: PlanckBody, active: boolean, rest: number, raised: number) => {
        const target = active ? raised : rest
        const current = body.getAngle()
        const diff = target - current
        const maxDelta = FLIPPER_SPEED * FIXED_TIMESTEP
        if (Math.abs(diff) <= maxDelta) {
          body.setAngle(target)
          body.setAngularVelocity(0)
        } else {
          const step = Math.sign(diff) * maxDelta
          body.setAngle(current + step)
          // Angular velocity feeds tip speed into ball collisions.
          body.setAngularVelocity(step / FIXED_TIMESTEP)
        }
      }

      for (let i = 0; i < PHYSICS_TIME_SCALE; i++) {
        state.simTime += FIXED_TIMESTEP

        driveFlipper(leftBody, state.leftFlipperActive, LEFT_REST_ANGLE, LEFT_ACTIVE_ANGLE)
        driveFlipper(rightBody, state.rightFlipperActive, RIGHT_REST_ANGLE, RIGHT_ACTIVE_ANGLE)

        // Planck clamps speed (~120). Re-apply plunger thrust while climbing the
        // shooter lane; release near the top curve so the ball rolls into play visibly.
        if (state.ballBody && plungerActive) {
          const pos = state.ballBody.getPosition()
          if (pos.y > PLUNGER_RELEASE_Y && pos.x > 345) {
            state.ballBody.setLinearVelocity(planck.Vec2(0, -PLUNGER_SPEED))
          } else {
            plungerActive = false
          }
        }

        world.step(FIXED_TIMESTEP)

        if (state.ballBody && pendingFlipperKick) {
          const cur = state.ballBody.getLinearVelocity()
          // Don't stack kicks if already rocketing up-table.
          if (cur.y > -85) {
            state.ballBody.setLinearVelocity(
              planck.Vec2(pendingFlipperKick.vx, pendingFlipperKick.vy)
            )
          }
          pendingFlipperKick = null
        }

        // Close the one-way gate only after the ball has crossed left into the
        // playfield (classic pinball: can't fall back in after exiting the lane).
        if (state.ballBody && state.ballLaunched && !plungerActive && !state.laneGateClosed) {
          const pos = state.ballBody.getPosition()
          if (pos.x < 340) closeLaneGate()
        }
      }

      if (state.ballBody && state.ballInPlay) {
        const pos = state.ballBody.getPosition()
        if (pos.y > level.worldHeight + 50) {
          state.ballInPlay = false
          state.ballLaunched = false
          plungerActive = false
          pendingFlipperKick = null
          openLaneGate()
          world.destroyBody(state.ballBody)
          state.ballBody = null
          state.ballsRemaining--
          onBallLost()
        }
      }
    },
    launchBall: () => {
      if (state.ballInPlay || state.ballsRemaining <= 0) return

      openLaneGate()

      state.ballBody = world.createBody({
        type: 'dynamic',
        position: planck.Vec2(level.launchX, level.launchY),
        bullet: true,
        linearDamping: 0.015,
        angularDamping: 0.1,
      })
      state.ballBody.createFixture(planck.Circle(level.ballRadius), {
        density: 0.45,
        friction: 0.08,
        restitution: 0.3,
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
      openLaneGate()
    },
    cleanup: () => {
      plungerActive = false
      openLaneGate()
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
      const isLeft = otherBody === leftBody
      const flipperActive = isLeft ? state.leftFlipperActive : state.rightFlipperActive
      const flipperBody = isLeft ? leftBody : rightBody

      if (flipperActive) {
        const fp = flipperBody.getPosition()
        const ang = flipperBody.getAngle()
        const dx = pos.x - fp.x
        const dy = pos.y - fp.y
        const localX = Math.abs(dx * Math.cos(ang) + dy * Math.sin(ang))
        const along = Math.min(1, Math.max(0.35, localX / level.flipperLength))
        const power = FLIPPER_KICK_MIN + along * (FLIPPER_KICK_MAX - FLIPPER_KICK_MIN)
        // Up-table is -Y. Left flipper also kicks right; right kicks left.
        pendingFlipperKick = {
          vx: (isLeft ? 1 : -1) * (12 + along * 40),
          vy: -power,
        }
      }

      onCollision({
        type: 'flipper',
        x: pos.x,
        y: pos.y,
        points: 0,
        intensity: flipperActive ? 1 : 0.4,
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
