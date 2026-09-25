<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref, watch } from 'vue'
import * as THREE from 'three'
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js'
import { RoomEnvironment } from 'three/examples/jsm/environments/RoomEnvironment.js'
import {
  createPieceMaterials,
  createPieceMesh,
  disposePieceGeometries,
  woodTexture,
  type PieceKind,
} from './chessPieces3d'

const props = defineProps<{
  board: Array<Array<string | null>>
  fen: string
  flipped: boolean
  interactive: boolean
  selected: string | null
  targets: string[]
  lastMove: { from: string; to: string } | null
  checkSquare: string | null
  hint?: { from: string; to: string } | null
}>()

const emit = defineEmits<{
  squareClick: [file: string, rankIndex: number]
}>()

const FILES = ['a', 'b', 'c', 'd', 'e', 'f', 'g', 'h'] as const
const FRAME_SIZE = 9.2
const BOARD_TOP = 0.1
const PIECE_SCALE = 0.8
const KNIGHT_TURN = Math.PI / 3
const SELECT_LIFT = 0.18
const MOVE_MS = 280
const CLICK_SLOP_PX = 6

const container = ref<HTMLDivElement | null>(null)
const webglFailed = ref(false)

let renderer: THREE.WebGLRenderer | null = null
let camera: THREE.PerspectiveCamera | null = null
let controls: OrbitControls | null = null
let resizeObserver: ResizeObserver | null = null
let frameId = 0
let pointerDown: { x: number; y: number } | null = null
let moveAnim: {
  mesh: THREE.Object3D
  from: THREE.Vector3
  to: THREE.Vector3
  start: number
} | null = null

const scene = new THREE.Scene()
const piecesGroup = new THREE.Group()
const highlightGroup = new THREE.Group()
const squareMeshes: THREE.Mesh[] = []
const pieceBySquare = new Map<string, THREE.Object3D>()
const raycaster = new THREE.Raycaster()
const disposables: Array<{ dispose(): void }> = []

function track<T extends { dispose(): void }>(resource: T): T {
  disposables.push(resource)
  return resource
}

const pieceMaterials = track(createPieceMaterials())

function overlayMaterial(color: number, opacity: number) {
  return track(
    new THREE.MeshBasicMaterial({ color, opacity, transparent: true, depthWrite: false }),
  )
}

const selectedMat = overlayMaterial(0xf0c14b, 0.6)
const lastMoveMat = overlayMaterial(0xf6e05e, 0.38)
const checkMat = overlayMaterial(0xff5c6c, 0.6)
const targetMat = overlayMaterial(0x141414, 0.32)
const hintMat = overlayMaterial(0x409cff, 0.55)

const squareOverlayGeo = track(new THREE.PlaneGeometry(1, 1).rotateX(-Math.PI / 2))
const targetDotGeo = track(new THREE.CircleGeometry(0.14, 32).rotateX(-Math.PI / 2))
const captureRingGeo = track(new THREE.RingGeometry(0.38, 0.46, 40).rotateX(-Math.PI / 2))

function squarePosition(square: string, y = BOARD_TOP): THREE.Vector3 {
  const fileIndex = FILES.indexOf(square[0] as (typeof FILES)[number])
  const rankIndex = Number(square[1]) - 1
  return new THREE.Vector3(fileIndex - 3.5, y, 3.5 - rankIndex)
}

function buildLabelTexture(frameWood: THREE.CanvasTexture): THREE.CanvasTexture {
  const size = 1024
  const canvas = document.createElement('canvas')
  canvas.width = size
  canvas.height = size
  const ctx = canvas.getContext('2d')!
  ctx.drawImage(frameWood.image as HTMLCanvasElement, 0, 0, size, size)
  ctx.fillStyle = '#ecd9b8'
  ctx.shadowColor = 'rgba(0, 0, 0, 0.55)'
  ctx.shadowBlur = 4
  ctx.shadowOffsetY = 2
  ctx.font = `700 ${Math.round(size * 0.036)}px Outfit, "DM Sans", system-ui, sans-serif`
  ctx.textAlign = 'center'
  ctx.textBaseline = 'middle'

  const toCanvas = (world: number) => ((world + FRAME_SIZE / 2) / FRAME_SIZE) * size

  const drawLabel = (text: string, x: number, z: number, upsideDown: boolean) => {
    ctx.save()
    ctx.translate(toCanvas(x), toCanvas(z))
    if (upsideDown) ctx.rotate(Math.PI)
    ctx.fillText(text, 0, 0)
    ctx.restore()
  }

  const edge = 4 + (FRAME_SIZE / 2 - 4) / 2
  for (let i = 0; i < 8; i++) {
    const offset = i - 3.5
    drawLabel(FILES[i], offset, edge, false)
    drawLabel(FILES[i], offset, -edge, true)
    drawLabel(String(i + 1), -edge, -offset, false)
    drawLabel(String(i + 1), edge, -offset, true)
  }

  const texture = new THREE.CanvasTexture(canvas)
  texture.colorSpace = THREE.SRGBColorSpace
  texture.anisotropy = 4
  return track(texture)
}

function buildBoard() {
  const lacquered = (map: THREE.Texture, clearcoat: number) =>
    track(
      new THREE.MeshPhysicalMaterial({ map, roughness: 0.45, clearcoat, clearcoatRoughness: 0.2 }),
    )

  const frameWood = track(woodTexture('#4a3020', '#1f130b', '#6b4a33', 37))
  frameWood.repeat.set(3, 1)
  const frame = new THREE.Mesh(
    track(new THREE.BoxGeometry(FRAME_SIZE, 0.4, FRAME_SIZE)),
    lacquered(frameWood, 0.6),
  )
  frame.position.y = -0.2
  frame.receiveShadow = true
  scene.add(frame)

  const labels = new THREE.Mesh(
    track(new THREE.PlaneGeometry(FRAME_SIZE, FRAME_SIZE).rotateX(-Math.PI / 2)),
    lacquered(buildLabelTexture(frameWood), 0.6),
  )
  labels.position.y = 0.002
  labels.receiveShadow = true
  scene.add(labels)

  const lightWood = track(woodTexture('#dcbd8e', '#b48d5e', '#f0dcb8', 21))
  const darkWood = track(woodTexture('#8a5a36', '#5a3519', '#a8784e', 29))
  for (const texture of [lightWood, darkWood]) texture.repeat.set(0.5, 0.5)
  const squareGeo = track(new THREE.BoxGeometry(1, BOARD_TOP, 1))
  const lightMat = lacquered(lightWood, 0.5)
  const darkMat = lacquered(darkWood, 0.5)
  for (let rank = 0; rank < 8; rank++) {
    for (let file = 0; file < 8; file++) {
      const square = `${FILES[file]}${rank + 1}`
      const mesh = new THREE.Mesh(squareGeo, (file + rank) % 2 === 1 ? lightMat : darkMat)
      mesh.position.copy(squarePosition(square, BOARD_TOP / 2))
      mesh.rotation.y = ((file * 3 + rank * 5) % 2) * Math.PI
      mesh.receiveShadow = true
      mesh.userData.square = square
      squareMeshes.push(mesh)
      scene.add(mesh)
    }
  }

  scene.add(piecesGroup, highlightGroup)
}

function buildLights() {
  scene.add(new THREE.HemisphereLight(0xfff6e8, 0x1a1410, 0.5))

  const key = new THREE.DirectionalLight(0xfff4e0, 2.2)
  key.position.set(4, 10, 6)
  key.castShadow = true
  key.shadow.mapSize.set(2048, 2048)
  key.shadow.camera.left = -6
  key.shadow.camera.right = 6
  key.shadow.camera.top = 6
  key.shadow.camera.bottom = -6
  key.shadow.bias = -0.0005
  scene.add(key)

  const rim = new THREE.DirectionalLight(0x8fb4ff, 0.45)
  rim.position.set(-6, 5, -6)
  scene.add(rim)
}

function rebuildPieces(animate: boolean) {
  piecesGroup.clear()
  pieceBySquare.clear()
  moveAnim = null

  for (let rank = 0; rank < 8; rank++) {
    for (let file = 0; file < 8; file++) {
      const piece = props.board[rank]?.[file]
      if (!piece) continue
      const isWhite = piece === piece.toUpperCase()
      const kind = piece.toLowerCase() as PieceKind
      const square = `${FILES[file]}${rank + 1}`
      const mesh = createPieceMesh(kind, pieceMaterials, isWhite)
      mesh.scale.setScalar(PIECE_SCALE)
      mesh.position.copy(squarePosition(square))
      if (kind === 'n') {
        const towardCenter = file < 4 ? -1 : 1
        const facing = isWhite ? Math.PI / 2 : -Math.PI / 2
        mesh.rotation.y = facing + towardCenter * (isWhite ? 1 : -1) * KNIGHT_TURN
      }
      mesh.userData.square = square
      pieceBySquare.set(square, mesh)
      piecesGroup.add(mesh)
    }
  }

  const last = props.lastMove
  const moved = last ? pieceBySquare.get(last.to) : undefined
  if (animate && last && moved) {
    moveAnim = {
      mesh: moved,
      from: squarePosition(last.from),
      to: squarePosition(last.to),
      start: performance.now(),
    }
    moved.position.copy(moveAnim.from)
  }
}

function addOverlay(square: string, geometry: THREE.BufferGeometry, material: THREE.Material, y: number) {
  const mesh = new THREE.Mesh(geometry, material)
  mesh.position.copy(squarePosition(square, BOARD_TOP + y))
  mesh.renderOrder = 1
  highlightGroup.add(mesh)
}

function rebuildHighlights() {
  highlightGroup.clear()
  if (props.lastMove) {
    addOverlay(props.lastMove.from, squareOverlayGeo, lastMoveMat, 0.002)
    addOverlay(props.lastMove.to, squareOverlayGeo, lastMoveMat, 0.002)
  }
  if (props.hint) {
    addOverlay(props.hint.from, squareOverlayGeo, hintMat, 0.0025)
    addOverlay(props.hint.to, squareOverlayGeo, hintMat, 0.0025)
  }
  if (props.checkSquare) addOverlay(props.checkSquare, squareOverlayGeo, checkMat, 0.003)
  if (props.selected) addOverlay(props.selected, squareOverlayGeo, selectedMat, 0.004)
  for (const target of props.targets) {
    const occupied = pieceBySquare.has(target)
    addOverlay(target, occupied ? captureRingGeo : targetDotGeo, targetMat, 0.005)
  }

  for (const [square, mesh] of pieceBySquare) {
    if (moveAnim?.mesh === mesh) continue
    mesh.position.y = BOARD_TOP + (square === props.selected ? SELECT_LIFT : 0)
  }
}

function fitDistance(): number {
  const aspect = camera?.aspect ?? 1
  return 14 / Math.min(aspect, 1)
}

function resetCamera() {
  if (!camera || !controls) return
  const direction = new THREE.Vector3(0, 1.2, props.flipped ? -1 : 1).normalize()
  camera.position.copy(direction.multiplyScalar(fitDistance()))
  controls.target.set(0, 0, 0)
  controls.update()
}

function resize() {
  if (!renderer || !camera || !controls || !container.value) return
  const { clientWidth: width, clientHeight: height } = container.value
  if (!width || !height) return
  renderer.setSize(width, height, false)
  camera.aspect = width / height
  camera.updateProjectionMatrix()
  controls.maxDistance = Math.max(30, fitDistance() * 1.5)
  const offset = camera.position.clone().sub(controls.target)
  offset.setLength(Math.min(Math.max(offset.length(), fitDistance()), controls.maxDistance))
  camera.position.copy(controls.target).add(offset)
}

function pickSquare(event: PointerEvent): string | null {
  if (!renderer || !camera) return null
  const rect = renderer.domElement.getBoundingClientRect()
  const pointer = new THREE.Vector2(
    ((event.clientX - rect.left) / rect.width) * 2 - 1,
    -((event.clientY - rect.top) / rect.height) * 2 + 1,
  )
  raycaster.setFromCamera(pointer, camera)
  const hits = raycaster.intersectObjects([...piecesGroup.children, ...squareMeshes], true)
  for (const hit of hits) {
    let node: THREE.Object3D | null = hit.object
    while (node && !node.userData.square) node = node.parent
    if (node) return String(node.userData.square)
  }
  return null
}

function onPointerDown(event: PointerEvent) {
  pointerDown = { x: event.clientX, y: event.clientY }
}

function onPointerUp(event: PointerEvent) {
  const start = pointerDown
  pointerDown = null
  if (!start) return
  if (Math.hypot(event.clientX - start.x, event.clientY - start.y) > CLICK_SLOP_PX) return
  const square = pickSquare(event)
  if (square) emit('squareClick', square[0], Number(square[1]) - 1)
}

function onPointerMove(event: PointerEvent) {
  if (!renderer || event.buttons) return
  const hoverable = props.interactive && pickSquare(event) !== null
  renderer.domElement.style.cursor = hoverable ? 'pointer' : 'grab'
}

function tick(now: number) {
  frameId = requestAnimationFrame(tick)
  if (!renderer || !camera || !controls) return

  if (moveAnim) {
    const t = Math.min(1, (now - moveAnim.start) / MOVE_MS)
    const eased = 1 - Math.pow(1 - t, 3)
    moveAnim.mesh.position.lerpVectors(moveAnim.from, moveAnim.to, eased)
    moveAnim.mesh.position.y = BOARD_TOP + Math.sin(Math.PI * t) * 0.3
    if (t >= 1) moveAnim = null
  }

  controls.update()
  renderer.render(scene, camera)
}

onMounted(() => {
  const host = container.value
  if (!host) return
  try {
    renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true })
  } catch {
    webglFailed.value = true
    return
  }
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2))
  renderer.shadowMap.enabled = true
  renderer.shadowMap.type = THREE.PCFSoftShadowMap
  renderer.toneMapping = THREE.NeutralToneMapping
  renderer.domElement.classList.add('chess-3d-canvas')
  host.appendChild(renderer.domElement)

  const pmrem = new THREE.PMREMGenerator(renderer)
  const roomEnvironment = new RoomEnvironment()
  scene.environment = track(pmrem.fromScene(roomEnvironment, 0.04).texture)
  scene.environmentIntensity = 0.55
  roomEnvironment.dispose()
  pmrem.dispose()

  camera = new THREE.PerspectiveCamera(40, 1, 0.1, 100)
  controls = new OrbitControls(camera, renderer.domElement)
  controls.enableDamping = true
  controls.dampingFactor = 0.08
  controls.enablePan = false
  controls.minDistance = 7
  controls.minPolarAngle = 0.15
  controls.maxPolarAngle = 1.25

  buildLights()
  buildBoard()
  rebuildPieces(false)
  rebuildHighlights()

  resize()
  resetCamera()

  renderer.domElement.addEventListener('pointerdown', onPointerDown)
  renderer.domElement.addEventListener('pointerup', onPointerUp)
  renderer.domElement.addEventListener('pointermove', onPointerMove)

  resizeObserver = new ResizeObserver(resize)
  resizeObserver.observe(host)
  frameId = requestAnimationFrame(tick)
})

onBeforeUnmount(() => {
  cancelAnimationFrame(frameId)
  resizeObserver?.disconnect()
  controls?.dispose()
  if (renderer) {
    renderer.domElement.removeEventListener('pointerdown', onPointerDown)
    renderer.domElement.removeEventListener('pointerup', onPointerUp)
    renderer.domElement.removeEventListener('pointermove', onPointerMove)
    renderer.dispose()
    renderer.domElement.remove()
  }
  for (const resource of disposables) resource.dispose()
  disposePieceGeometries()
})

watch(
  () => props.fen,
  () => {
    rebuildPieces(true)
    rebuildHighlights()
  },
)

watch(
  () => [props.selected, props.targets, props.lastMove, props.checkSquare, props.hint],
  rebuildHighlights,
)

watch(() => props.flipped, resetCamera)
</script>

<template>
  <div ref="container" class="chess-3d">
    <p v-if="webglFailed" class="fallback">3D view needs WebGL, which this browser can't provide.</p>
    <template v-else>
      <button type="button" class="reset-view" @click="resetCamera">Reset view</button>
      <p class="hint">Drag to rotate · scroll to zoom</p>
    </template>
  </div>
</template>

<style scoped>
.chess-3d {
  position: relative;
  width: 100%;
  height: 100%;
  min-height: 0;
  border-radius: 12px;
  overflow: hidden;
  background: radial-gradient(ellipse 80% 70% at 50% 40%, rgba(201, 154, 98, 0.12), transparent 70%);
}

.chess-3d :deep(.chess-3d-canvas) {
  display: block;
  width: 100%;
  height: 100%;
  touch-action: none;
  cursor: grab;
}

.reset-view {
  position: absolute;
  top: 0.5rem;
  right: 0.5rem;
  z-index: 2;
  font-size: 0.72rem;
  font-weight: 600;
  padding: 0.3rem 0.6rem;
  border-radius: 8px;
  border: 1px solid var(--border);
  background: rgba(21, 28, 44, 0.8);
  color: var(--text);
  cursor: pointer;
}

.reset-view:hover {
  background: rgba(31, 40, 60, 0.9);
}

.hint {
  position: absolute;
  bottom: 0.4rem;
  left: 50%;
  transform: translateX(-50%);
  margin: 0;
  font-size: 0.7rem;
  color: var(--text-muted);
  pointer-events: none;
  white-space: nowrap;
}

.fallback {
  display: grid;
  place-items: center;
  height: 100%;
  margin: 0;
  padding: 1rem;
  text-align: center;
  color: var(--text-muted);
}
</style>
