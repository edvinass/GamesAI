import planck from 'planck'

type PlanckWorld = planck.World
type PlanckBody = planck.Body

const FIXED_TIMESTEP = 1 / 60
const PHYSICS_TIME_SCALE = 1.5
const GRAVITY = 35

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
  leftFlipperJoint: planck.RevoluteJoint
  rightFlipperJoint: planck.RevoluteJoint
  bumperBodies: Map<PlanckBody, BumperSpec>
  targetBodies: Map<PlanckBody, TargetSpec>
  hitTargets: Set<string>
  simTime: number
  score: number
  ballsRemaining: number
  ballInPlay: boolean
  ballLaunched: boolean
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
  ballRadius: 12,
  launchX: 375,
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

  const launchGuide = world.createBody({ type: 'static', position: planck.Vec2(350, 500) })
  launchGuide.createFixture(planck.Box(3, 200), { friction: 0.2, restitution: 0.3 })

  const leftRamp = world.createBody({ type: 'static', position: planck.Vec2(60, 550), angle: 0.5 })
  leftRamp.createFixture(planck.Box(70, 8), { friction: 0.3, restitution: 0.4 })

  const rightRamp = world.createBody({ type: 'static', position: planck.Vec2(290, 550), angle: -0.5 })
  rightRamp.createFixture(planck.Box(70, 8), { friction: 0.3, restitution: 0.4 })

  const leftOutlane = world.createBody({ type: 'static', position: planck.Vec2(25, 620), angle: 0.3 })
  leftOutlane.createFixture(planck.Box(40, 5), { friction: 0.3, restitution: 0.3 })

  const rightOutlane = world.createBody({ type: 'static', position: planck.Vec2(325, 620), angle: -0.3 })
  rightOutlane.createFixture(planck.Box(40, 5), { friction: 0.3, restitution: 0.3 })
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
  leftJoint: planck.RevoluteJoint
  rightJoint: planck.RevoluteJoint
} {
  const flipperY = 650
  const leftPivotX = 100
  const rightPivotX = 250

  const leftAnchor = world.createBody({ type: 'static', position: planck.Vec2(leftPivotX, flipperY) })
  const rightAnchor = world.createBody({ type: 'static', position: planck.Vec2(rightPivotX, flipperY) })

  const leftFlipper = world.createBody({
    type: 'dynamic',
    position: planck.Vec2(leftPivotX + level.flipperLength / 2 - 10, flipperY),
    angle: 0.4,
    bullet: true,
  })
  leftFlipper.createFixture(
    planck.Polygon([
      planck.Vec2(-level.flipperLength / 2, -level.flipperWidth / 2),
      planck.Vec2(level.flipperLength / 2, -level.flipperWidth / 3),
      planck.Vec2(level.flipperLength / 2, level.flipperWidth / 3),
      planck.Vec2(-level.flipperLength / 2, level.flipperWidth / 2),
    ]),
    { density: 1.5, friction: 0.3, restitution: 0.3 }
  )

  const rightFlipper = world.createBody({
    type: 'dynamic',
    position: planck.Vec2(rightPivotX - level.flipperLength / 2 + 10, flipperY),
    angle: -0.4,
    bullet: true,
  })
  rightFlipper.createFixture(
    planck.Polygon([
      planck.Vec2(level.flipperLength / 2, -level.flipperWidth / 2),
      planck.Vec2(-level.flipperLength / 2, -level.flipperWidth / 3),
      planck.Vec2(-level.flipperLength / 2, level.flipperWidth / 3),
      planck.Vec2(level.flipperLength / 2, level.flipperWidth / 2),
    ]),
    { density: 1.5, friction: 0.3, restitution: 0.3 }
  )

  const leftJoint = planck.RevoluteJoint(
    {
      enableLimit: true,
      lowerAngle: -0.1,
      upperAngle: 0.5,
      enableMotor: true,
      motorSpeed: -15,
      maxMotorTorque: 800,
    },
    leftAnchor,
    leftFlipper,
    planck.Vec2(leftPivotX, flipperY)
  )
  world.createJoint(leftJoint)

  const rightJoint = planck.RevoluteJoint(
    {
      enableLimit: true,
      lowerAngle: -0.5,
      upperAngle: 0.1,
      enableMotor: true,
      motorSpeed: 15,
      maxMotorTorque: 800,
    },
    rightAnchor,
    rightFlipper,
    planck.Vec2(rightPivotX, flipperY)
  )
  world.createJoint(rightJoint)

  return { leftBody: leftFlipper, rightBody: rightFlipper, leftJoint, rightJoint }
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
  const { leftBody, rightBody, leftJoint, rightJoint } = createFlippers(world, level)

  const state: PinballWorld = {
    world,
    level,
    ballBody: null,
    leftFlipperBody: leftBody,
    rightFlipperBody: rightBody,
    leftFlipperJoint: leftJoint,
    rightFlipperJoint: rightJoint,
    bumperBodies,
    targetBodies,
    hitTargets: new Set(),
    simTime: 0,
    score: 0,
    ballsRemaining: 3,
    ballInPlay: false,
    ballLaunched: false,
    onCollision,
    onBallLost,
    step: () => {
      for (let i = 0; i < PHYSICS_TIME_SCALE; i++) {
        state.simTime += FIXED_TIMESTEP
        world.step(FIXED_TIMESTEP)
      }

      if (state.ballBody && state.ballInPlay) {
        const pos = state.ballBody.getPosition()
        if (pos.y > level.worldHeight + 50) {
          state.ballInPlay = false
          state.ballLaunched = false
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
        linearDamping: 0.1,
        angularDamping: 0.2,
      })
      state.ballBody.createFixture(planck.Circle(level.ballRadius), {
        density: 1.2,
        friction: 0.3,
        restitution: 0.5,
      })
      
      const launchPower = 35 + Math.random() * 10
      state.ballBody.setLinearVelocity(planck.Vec2(-2, -launchPower))
      state.ballInPlay = true
      state.ballLaunched = true
    },
    activateLeftFlipper: (active: boolean) => {
      leftJoint.setMotorSpeed(active ? 35 : -15)
    },
    activateRightFlipper: (active: boolean) => {
      rightJoint.setMotorSpeed(active ? -35 : 15)
    },
    resetBall: () => {
      if (state.ballBody) {
        world.destroyBody(state.ballBody)
        state.ballBody = null
      }
      state.ballInPlay = false
      state.ballLaunched = false
    },
    cleanup: () => {
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
      const dist = Math.hypot(dx, dy)
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
