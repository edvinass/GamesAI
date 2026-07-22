<script setup lang="ts">
import { ref, onMounted, onUnmounted, computed, watch } from 'vue'
import type { Room, PinballGameState } from '@/types'
import {
  createPinballWorld,
  getBallPosition,
  getFlipperTransforms,
  type PinballWorld,
  type CollisionEvent,
} from './physics'

defineProps<{
  gameState: PinballGameState
  room: Room
  playerId: string
}>()

defineEmits<{
  action: [data: Record<string, unknown>]
}>()

const canvasRef = ref<HTMLCanvasElement | null>(null)
const containerRef = ref<HTMLDivElement | null>(null)
const physicsWorld = ref<PinballWorld | null>(null)
const animationFrame = ref<number | null>(null)
const displayScale = ref(1)

const score = ref(0)
const ballsRemaining = ref(3)
const gameOver = ref(false)
const showLaunchHint = ref(true)
const combo = ref(0)
const lastHitTime = ref(0)
const effects = ref<Array<{ id: number; x: number; y: number; text: string; color: string; createdAt: number }>>([])
let effectId = 0

const highScore = computed(() => {
  const stored = localStorage.getItem('pinball_highscore')
  return stored ? parseInt(stored, 10) : 0
})

function formatScore(n: number): string {
  return n.toLocaleString()
}

function handleCollision(event: CollisionEvent) {
  const now = Date.now()
  if (now - lastHitTime.value < 2000) {
    combo.value++
  } else {
    combo.value = 1
  }
  lastHitTime.value = now

  const multiplier = Math.min(combo.value, 5)
  const points = event.points * multiplier

  if (points > 0) {
    score.value += points
    
    const id = ++effectId
    effects.value.push({
      id,
      x: event.x * displayScale.value,
      y: event.y * displayScale.value,
      text: multiplier > 1 ? `+${formatScore(points)} x${multiplier}` : `+${formatScore(points)}`,
      color: event.type === 'bumper' ? '#ff4757' : event.type === 'target' ? '#5352ed' : '#fff',
      createdAt: now,
    })

    setTimeout(() => {
      effects.value = effects.value.filter((e) => e.id !== id)
    }, 1000)
  }
}

function handleBallLost() {
  combo.value = 0
  if (physicsWorld.value && physicsWorld.value.ballsRemaining <= 0) {
    gameOver.value = true
    if (score.value > highScore.value) {
      localStorage.setItem('pinball_highscore', score.value.toString())
    }
  }
  ballsRemaining.value = physicsWorld.value?.ballsRemaining ?? 0
}

function launchBall() {
  if (physicsWorld.value && !gameOver.value) {
    physicsWorld.value.launchBall()
    showLaunchHint.value = false
    ballsRemaining.value = physicsWorld.value.ballsRemaining
  }
}

function restartGame() {
  if (physicsWorld.value) {
    physicsWorld.value.cleanup()
  }
  physicsWorld.value = createPinballWorld(handleCollision, handleBallLost)
  score.value = 0
  ballsRemaining.value = 3
  gameOver.value = false
  showLaunchHint.value = true
  combo.value = 0
  effects.value = []
}

function handleKeyDown(e: KeyboardEvent) {
  if (!physicsWorld.value || gameOver.value) return

  if (e.code === 'Space' || e.code === 'Enter') {
    e.preventDefault()
    if (!physicsWorld.value.ballInPlay) {
      launchBall()
    }
    return
  }

  if (e.code === 'KeyA' || e.code === 'ArrowLeft' || e.code === 'KeyZ') {
    e.preventDefault()
    physicsWorld.value.activateLeftFlipper(true)
  }
  if (e.code === 'KeyD' || e.code === 'ArrowRight' || e.code === 'Slash' || e.code === 'KeyM') {
    e.preventDefault()
    physicsWorld.value.activateRightFlipper(true)
  }
}

function handleKeyUp(e: KeyboardEvent) {
  if (!physicsWorld.value) return

  if (e.code === 'KeyA' || e.code === 'ArrowLeft' || e.code === 'KeyZ') {
    physicsWorld.value.activateLeftFlipper(false)
  }
  if (e.code === 'KeyD' || e.code === 'ArrowRight' || e.code === 'Slash' || e.code === 'KeyM') {
    physicsWorld.value.activateRightFlipper(false)
  }
}

function handleTouchStart(side: 'left' | 'right') {
  if (!physicsWorld.value || gameOver.value) return
  
  if (!physicsWorld.value.ballInPlay) {
    launchBall()
    return
  }

  if (side === 'left') {
    physicsWorld.value.activateLeftFlipper(true)
  } else {
    physicsWorld.value.activateRightFlipper(true)
  }
}

function handleTouchEnd(side: 'left' | 'right') {
  if (!physicsWorld.value) return

  if (side === 'left') {
    physicsWorld.value.activateLeftFlipper(false)
  } else {
    physicsWorld.value.activateRightFlipper(false)
  }
}

function updateDisplayScale() {
  if (!containerRef.value || !physicsWorld.value) return
  const container = containerRef.value
  const level = physicsWorld.value.level
  const scaleX = container.clientWidth / level.worldWidth
  const scaleY = (container.clientHeight - 120) / level.worldHeight
  displayScale.value = Math.min(scaleX, scaleY, 1.2)
}

function render() {
  const canvas = canvasRef.value
  const world = physicsWorld.value
  if (!canvas || !world) return

  const ctx = canvas.getContext('2d')
  if (!ctx) return

  const level = world.level
  const scale = displayScale.value

  canvas.width = level.worldWidth * scale
  canvas.height = level.worldHeight * scale

  ctx.fillStyle = '#1a1a2e'
  ctx.fillRect(0, 0, canvas.width, canvas.height)

  ctx.save()
  ctx.scale(scale, scale)

  const gradient = ctx.createLinearGradient(0, 0, 0, level.worldHeight)
  gradient.addColorStop(0, '#16213e')
  gradient.addColorStop(1, '#0f0f23')
  ctx.fillStyle = gradient
  ctx.fillRect(0, 0, level.worldWidth, level.worldHeight)

  ctx.strokeStyle = '#4a4a6a'
  ctx.lineWidth = 2
  ctx.strokeRect(10, 10, level.worldWidth - 20, level.worldHeight - 20)

  ctx.strokeStyle = '#3a3a5a'
  ctx.lineWidth = 1
  for (let i = 50; i < level.worldWidth; i += 50) {
    ctx.beginPath()
    ctx.moveTo(i, 10)
    ctx.lineTo(i, level.worldHeight - 10)
    ctx.stroke()
  }
  for (let i = 50; i < level.worldHeight; i += 50) {
    ctx.beginPath()
    ctx.moveTo(10, i)
    ctx.lineTo(level.worldWidth - 10, i)
    ctx.stroke()
  }

  ctx.fillStyle = '#2a2a4a'
  ctx.beginPath()
  ctx.moveTo(10, 530)
  ctx.lineTo(130, 600)
  ctx.lineTo(10, 650)
  ctx.closePath()
  ctx.fill()

  ctx.beginPath()
  ctx.moveTo(level.worldWidth - 10, 530)
  ctx.lineTo(level.worldWidth - 130, 600)
  ctx.lineTo(level.worldWidth - 10, 650)
  ctx.closePath()
  ctx.fill()

  ctx.fillStyle = '#3a3a5a'
  ctx.fillRect(347, 300, 6, 400)

  for (const [body, spec] of world.bumperBodies) {
    const pos = body.getPosition()
    
    const bumperGrad = ctx.createRadialGradient(pos.x, pos.y, 0, pos.x, pos.y, spec.radius)
    bumperGrad.addColorStop(0, spec.color)
    bumperGrad.addColorStop(0.7, spec.color)
    bumperGrad.addColorStop(1, '#000')
    
    ctx.beginPath()
    ctx.arc(pos.x, pos.y, spec.radius, 0, Math.PI * 2)
    ctx.fillStyle = bumperGrad
    ctx.fill()
    
    ctx.strokeStyle = '#fff'
    ctx.lineWidth = 3
    ctx.stroke()

    ctx.beginPath()
    ctx.arc(pos.x - spec.radius * 0.3, pos.y - spec.radius * 0.3, spec.radius * 0.2, 0, Math.PI * 2)
    ctx.fillStyle = 'rgba(255, 255, 255, 0.4)'
    ctx.fill()
  }

  for (const [body, spec] of world.targetBodies) {
    if (world.hitTargets.has(spec.id)) continue
    
    const pos = body.getPosition()
    ctx.save()
    ctx.translate(pos.x, pos.y)
    
    ctx.fillStyle = spec.color
    ctx.shadowColor = spec.color
    ctx.shadowBlur = 10
    ctx.fillRect(-spec.width / 2, -spec.height / 2, spec.width, spec.height)
    
    ctx.strokeStyle = '#fff'
    ctx.lineWidth = 2
    ctx.strokeRect(-spec.width / 2, -spec.height / 2, spec.width, spec.height)
    
    ctx.restore()
  }

  const flippers = getFlipperTransforms(world)
  
  ctx.save()
  ctx.translate(flippers.left.x, flippers.left.y)
  ctx.rotate(flippers.left.angle)
  
  const leftGrad = ctx.createLinearGradient(-level.flipperLength / 2, 0, level.flipperLength / 2, 0)
  leftGrad.addColorStop(0, '#ff6b6b')
  leftGrad.addColorStop(1, '#ee5a5a')
  ctx.fillStyle = leftGrad
  
  ctx.beginPath()
  ctx.moveTo(-level.flipperLength / 2, -level.flipperWidth / 2)
  ctx.lineTo(level.flipperLength / 2, -level.flipperWidth / 3)
  ctx.lineTo(level.flipperLength / 2, level.flipperWidth / 3)
  ctx.lineTo(-level.flipperLength / 2, level.flipperWidth / 2)
  ctx.closePath()
  ctx.fill()
  ctx.strokeStyle = '#fff'
  ctx.lineWidth = 2
  ctx.stroke()
  ctx.restore()

  ctx.save()
  ctx.translate(flippers.right.x, flippers.right.y)
  ctx.rotate(flippers.right.angle)
  
  const rightGrad = ctx.createLinearGradient(-level.flipperLength / 2, 0, level.flipperLength / 2, 0)
  rightGrad.addColorStop(0, '#4ecdc4')
  rightGrad.addColorStop(1, '#3dbdb5')
  ctx.fillStyle = rightGrad
  
  ctx.beginPath()
  ctx.moveTo(level.flipperLength / 2, -level.flipperWidth / 2)
  ctx.lineTo(-level.flipperLength / 2, -level.flipperWidth / 3)
  ctx.lineTo(-level.flipperLength / 2, level.flipperWidth / 3)
  ctx.lineTo(level.flipperLength / 2, level.flipperWidth / 2)
  ctx.closePath()
  ctx.fill()
  ctx.strokeStyle = '#fff'
  ctx.lineWidth = 2
  ctx.stroke()
  ctx.restore()

  const ballPos = getBallPosition(world)
  if (ballPos) {
    const ballGrad = ctx.createRadialGradient(
      ballPos.x - level.ballRadius * 0.3,
      ballPos.y - level.ballRadius * 0.3,
      0,
      ballPos.x,
      ballPos.y,
      level.ballRadius
    )
    ballGrad.addColorStop(0, '#fff')
    ballGrad.addColorStop(0.3, '#e0e0e0')
    ballGrad.addColorStop(1, '#888')
    
    ctx.beginPath()
    ctx.arc(ballPos.x, ballPos.y, level.ballRadius, 0, Math.PI * 2)
    ctx.fillStyle = ballGrad
    ctx.shadowColor = '#fff'
    ctx.shadowBlur = 15
    ctx.fill()
    ctx.shadowBlur = 0
  }

  ctx.restore()
}

function gameLoop() {
  if (physicsWorld.value && !gameOver.value) {
    physicsWorld.value.step()
  }
  render()
  animationFrame.value = requestAnimationFrame(gameLoop)
}

onMounted(() => {
  physicsWorld.value = createPinballWorld(handleCollision, handleBallLost)
  updateDisplayScale()
  
  window.addEventListener('keydown', handleKeyDown)
  window.addEventListener('keyup', handleKeyUp)
  window.addEventListener('resize', updateDisplayScale)
  
  gameLoop()
})

onUnmounted(() => {
  if (animationFrame.value) {
    cancelAnimationFrame(animationFrame.value)
  }
  if (physicsWorld.value) {
    physicsWorld.value.cleanup()
  }
  window.removeEventListener('keydown', handleKeyDown)
  window.removeEventListener('keyup', handleKeyUp)
  window.removeEventListener('resize', updateDisplayScale)
})

watch(displayScale, () => {
  render()
})
</script>

<template>
  <div ref="containerRef" class="pinball-container">
    <div class="pinball-hud">
      <div class="hud-section">
        <span class="hud-label">SCORE</span>
        <span class="hud-value score">{{ formatScore(score) }}</span>
      </div>
      <div class="hud-section">
        <span class="hud-label">HIGH SCORE</span>
        <span class="hud-value">{{ formatScore(highScore) }}</span>
      </div>
      <div class="hud-section balls">
        <span class="hud-label">BALLS</span>
        <div class="ball-indicators">
          <span
            v-for="i in 3"
            :key="i"
            class="ball-indicator"
            :class="{ active: i <= ballsRemaining }"
          />
        </div>
      </div>
      <div v-if="combo > 1" class="combo-display">
        {{ combo }}x COMBO!
      </div>
    </div>

    <div class="game-area">
      <canvas ref="canvasRef" class="pinball-canvas" />
      
      <TransitionGroup name="effect">
        <div
          v-for="effect in effects"
          :key="effect.id"
          class="score-effect"
          :style="{
            left: `${effect.x}px`,
            top: `${effect.y}px`,
            color: effect.color,
          }"
        >
          {{ effect.text }}
        </div>
      </TransitionGroup>

      <div
        v-if="showLaunchHint && !gameOver && ballsRemaining > 0"
        class="launch-hint"
      >
        <span class="hint-text">Press SPACE to launch</span>
        <span class="hint-subtext">or tap the screen</span>
      </div>

      <div v-if="gameOver" class="game-over-overlay">
        <div class="game-over-content">
          <h2>GAME OVER</h2>
          <p class="final-score">Final Score: {{ formatScore(score) }}</p>
          <p v-if="score >= highScore && score > 0" class="new-highscore">NEW HIGH SCORE!</p>
          <button class="restart-btn" @click="restartGame">Play Again</button>
        </div>
      </div>
    </div>

    <div class="touch-controls">
      <button
        class="touch-flipper left"
        @touchstart.prevent="handleTouchStart('left')"
        @touchend.prevent="handleTouchEnd('left')"
        @mousedown.prevent="handleTouchStart('left')"
        @mouseup.prevent="handleTouchEnd('left')"
        @mouseleave="handleTouchEnd('left')"
      >
        <span class="flipper-label">LEFT</span>
        <span class="flipper-key">A / ←</span>
      </button>
      <button
        class="touch-flipper right"
        @touchstart.prevent="handleTouchStart('right')"
        @touchend.prevent="handleTouchEnd('right')"
        @mousedown.prevent="handleTouchStart('right')"
        @mouseup.prevent="handleTouchEnd('right')"
        @mouseleave="handleTouchEnd('right')"
      >
        <span class="flipper-label">RIGHT</span>
        <span class="flipper-key">D / →</span>
      </button>
    </div>
  </div>
</template>

<style scoped>
.pinball-container {
  display: flex;
  flex-direction: column;
  align-items: center;
  height: 100%;
  width: 100%;
  background: linear-gradient(135deg, #0f0f23 0%, #1a1a2e 100%);
  overflow: hidden;
  user-select: none;
}

.pinball-hud {
  display: flex;
  justify-content: center;
  align-items: center;
  gap: 2rem;
  padding: 0.75rem 1.5rem;
  background: linear-gradient(180deg, rgba(0, 0, 0, 0.6) 0%, transparent 100%);
  width: 100%;
  flex-shrink: 0;
}

.hud-section {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 0.2rem;
}

.hud-label {
  font-size: 0.65rem;
  font-weight: 600;
  letter-spacing: 0.1em;
  color: #888;
  text-transform: uppercase;
}

.hud-value {
  font-size: 1.4rem;
  font-weight: 700;
  font-family: 'Courier New', monospace;
  color: #fff;
}

.hud-value.score {
  color: #ffd700;
  text-shadow: 0 0 10px rgba(255, 215, 0, 0.5);
}

.ball-indicators {
  display: flex;
  gap: 0.4rem;
}

.ball-indicator {
  width: 14px;
  height: 14px;
  border-radius: 50%;
  background: #333;
  border: 2px solid #555;
  transition: all 0.3s ease;
}

.ball-indicator.active {
  background: radial-gradient(circle at 30% 30%, #fff, #888);
  border-color: #fff;
  box-shadow: 0 0 8px rgba(255, 255, 255, 0.5);
}

.combo-display {
  position: absolute;
  right: 1rem;
  top: 0.75rem;
  font-size: 1.2rem;
  font-weight: 700;
  color: #ff6b6b;
  text-shadow: 0 0 10px rgba(255, 107, 107, 0.7);
  animation: pulse 0.5s ease-in-out infinite alternate;
}

@keyframes pulse {
  from { transform: scale(1); }
  to { transform: scale(1.1); }
}

.game-area {
  position: relative;
  flex: 1;
  display: flex;
  justify-content: center;
  align-items: center;
  min-height: 0;
}

.pinball-canvas {
  border-radius: 12px;
  box-shadow:
    0 0 30px rgba(0, 0, 0, 0.5),
    inset 0 0 60px rgba(0, 0, 0, 0.3);
}

.score-effect {
  position: absolute;
  font-size: 1.1rem;
  font-weight: 700;
  pointer-events: none;
  text-shadow: 0 0 10px currentColor;
  transform: translate(-50%, -50%);
}

.effect-enter-active {
  animation: scorePopup 1s ease-out forwards;
}

.effect-leave-active {
  animation: scorePopup 1s ease-out forwards reverse;
}

@keyframes scorePopup {
  0% {
    opacity: 1;
    transform: translate(-50%, -50%) scale(0.5);
  }
  50% {
    opacity: 1;
    transform: translate(-50%, -100%) scale(1.2);
  }
  100% {
    opacity: 0;
    transform: translate(-50%, -150%) scale(1);
  }
}

.launch-hint {
  position: absolute;
  bottom: 30%;
  left: 50%;
  transform: translateX(-50%);
  text-align: center;
  animation: bounce 1s ease-in-out infinite;
}

.hint-text {
  display: block;
  font-size: 1.2rem;
  font-weight: 600;
  color: #fff;
  text-shadow: 0 0 10px rgba(255, 255, 255, 0.5);
}

.hint-subtext {
  display: block;
  font-size: 0.8rem;
  color: #888;
  margin-top: 0.3rem;
}

@keyframes bounce {
  0%, 100% { transform: translateX(-50%) translateY(0); }
  50% { transform: translateX(-50%) translateY(-10px); }
}

.game-over-overlay {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(0, 0, 0, 0.8);
  backdrop-filter: blur(4px);
  border-radius: 12px;
  animation: fadeIn 0.3s ease-out;
}

@keyframes fadeIn {
  from { opacity: 0; }
  to { opacity: 1; }
}

.game-over-content {
  text-align: center;
  padding: 2rem;
}

.game-over-content h2 {
  font-size: 2.5rem;
  font-weight: 800;
  color: #ff4757;
  margin: 0 0 1rem;
  text-shadow: 0 0 20px rgba(255, 71, 87, 0.5);
}

.final-score {
  font-size: 1.5rem;
  color: #fff;
  margin: 0 0 0.5rem;
}

.new-highscore {
  font-size: 1.2rem;
  font-weight: 700;
  color: #ffd700;
  margin: 0 0 1.5rem;
  animation: pulse 0.5s ease-in-out infinite alternate;
}

.restart-btn {
  padding: 0.8rem 2rem;
  font-size: 1.1rem;
  font-weight: 600;
  color: #fff;
  background: linear-gradient(135deg, #5352ed, #3742fa);
  border: none;
  border-radius: 8px;
  cursor: pointer;
  transition: transform 0.2s, box-shadow 0.2s;
}

.restart-btn:hover {
  transform: translateY(-2px);
  box-shadow: 0 5px 20px rgba(83, 82, 237, 0.4);
}

.touch-controls {
  display: flex;
  justify-content: space-between;
  width: 100%;
  padding: 0.5rem 1rem 1rem;
  gap: 1rem;
  flex-shrink: 0;
}

.touch-flipper {
  flex: 1;
  max-width: 200px;
  padding: 1rem;
  border: none;
  border-radius: 12px;
  font-weight: 600;
  cursor: pointer;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 0.2rem;
  transition: transform 0.1s, box-shadow 0.1s;
  touch-action: manipulation;
}

.touch-flipper.left {
  background: linear-gradient(135deg, #ff6b6b, #ee5a5a);
}

.touch-flipper.right {
  background: linear-gradient(135deg, #4ecdc4, #3dbdb5);
}

.touch-flipper:active {
  transform: scale(0.95);
  box-shadow: inset 0 2px 8px rgba(0, 0, 0, 0.3);
}

.flipper-label {
  font-size: 1rem;
  color: #fff;
}

.flipper-key {
  font-size: 0.7rem;
  color: rgba(255, 255, 255, 0.7);
}

@media (max-width: 480px) {
  .pinball-hud {
    gap: 1rem;
    padding: 0.5rem 1rem;
  }

  .hud-value {
    font-size: 1.1rem;
  }

  .combo-display {
    font-size: 1rem;
    top: 0.5rem;
    right: 0.5rem;
  }

  .hint-text {
    font-size: 1rem;
  }

  .touch-flipper {
    padding: 0.75rem;
  }

  .flipper-label {
    font-size: 0.9rem;
  }
}
</style>
