import * as THREE from 'three'
import { RoomEnvironment } from 'three/examples/jsm/environments/RoomEnvironment.js'
import {
  createPieceMesh,
  type PieceKind,
  type PieceMaterials,
} from './chessPieces3d'

const KINDS: PieceKind[] = ['p', 'n', 'b', 'r', 'q', 'k']
const SIZE = 384

/** Between a side view and true isometric. */
const ELEVATION = (22 * Math.PI) / 180
const AZIMUTH = (18 * Math.PI) / 180

let cache: Record<string, string> | null = null

export function getIsoPieceSprites(): Record<string, string> | null {
  if (cache) return cache
  try {
    cache = renderSprites()
    return cache
  } catch {
    return null
  }
}

function renderSprites(): Record<string, string> {
  const renderer = new THREE.WebGLRenderer({
    antialias: true,
    alpha: true,
    preserveDrawingBuffer: true,
  })
  renderer.setSize(SIZE, SIZE)
  renderer.setPixelRatio(1)
  renderer.setClearColor(0x000000, 0)
  renderer.shadowMap.enabled = true
  renderer.shadowMap.type = THREE.PCFSoftShadowMap
  renderer.toneMapping = THREE.NeutralToneMapping
  renderer.toneMappingExposure = 1.05

  const pmrem = new THREE.PMREMGenerator(renderer)
  const room = new RoomEnvironment()
  const environment = pmrem.fromScene(room, 0.04).texture
  room.dispose()
  pmrem.dispose()

  const materials = duoMaterials()
  const scene = new THREE.Scene()
  scene.environment = environment
  scene.environmentIntensity = 0.35

  scene.add(new THREE.HemisphereLight(0xf7fafc, 0x243240, 0.72))
  const key = new THREE.DirectionalLight(0xf3f6f8, 1.7)
  key.position.set(3, 7, 4)
  key.castShadow = true
  key.shadow.mapSize.set(1024, 1024)
  key.shadow.camera.left = -2
  key.shadow.camera.right = 2
  key.shadow.camera.top = 2
  key.shadow.camera.bottom = -2
  key.shadow.bias = -0.001
  scene.add(key)
  const rim = new THREE.DirectionalLight(0x8fb4ff, 0.4)
  rim.position.set(-4, 4, -3)
  scene.add(rim)

  const ground = new THREE.Mesh(
    new THREE.PlaneGeometry(6, 6),
    new THREE.ShadowMaterial({ opacity: 0.38 }),
  )
  ground.rotation.x = -Math.PI / 2
  ground.position.y = 0.001
  ground.receiveShadow = true
  scene.add(ground)

  const camera = new THREE.OrthographicCamera(-1, 1, 1, -1, 0.01, 30)
  const pieces: { key: string; mesh: THREE.Group }[] = []
  const bounds = new THREE.Box3()

  for (const kind of KINDS) {
    for (const isWhite of [true, false]) {
      const mesh = createPieceMesh(kind, materials, isWhite)
      if (kind === 'n') {
        // Snout points +x. Face the camera, white and black turned opposite ways.
        mesh.rotation.y = isWhite ? AZIMUTH - 0.35 : AZIMUTH + Math.PI + 0.35
      }
      mesh.updateMatrixWorld(true)
      bounds.expandByObject(mesh)
      pieces.push({ key: `${isWhite ? 'w' : 'b'}${kind.toUpperCase()}`, mesh })
    }
  }

  bounds.expandByScalar(0.015)
  bounds.min.y = Math.min(bounds.min.y, -0.01)
  frameCamera(camera, bounds)

  const urls: Record<string, string> = {}
  for (const { key, mesh } of pieces) {
    scene.add(mesh)
    renderer.toneMappingExposure = key.startsWith('w') ? 0.82 : 1.05
    renderer.render(scene, camera)
    urls[key] = renderer.domElement.toDataURL('image/png')
    scene.remove(mesh)
  }

  ground.geometry.dispose()
  ;(ground.material as THREE.Material).dispose()
  materials.dispose()
  environment.dispose()
  renderer.dispose()
  return urls
}

/** Matte plastic, close to Duolingo: pale cool gray and blue slate. */
function duoMaterials(): PieceMaterials {
  const white = new THREE.MeshPhysicalMaterial({
    color: 0xb7c6d4,
    roughness: 0.48,
    metalness: 0,
    clearcoat: 0.18,
    clearcoatRoughness: 0.6,
  })
  const black = new THREE.MeshPhysicalMaterial({
    color: 0x3a4c5e,
    roughness: 0.42,
    metalness: 0,
    clearcoat: 0.22,
    clearcoatRoughness: 0.5,
  })
  const accent = new THREE.MeshStandardMaterial({ color: 0x24303c, roughness: 0.55 })
  return {
    white,
    black,
    accent,
    dispose() {
      white.dispose()
      black.dispose()
      accent.dispose()
    },
  }
}

function frameCamera(camera: THREE.OrthographicCamera, box: THREE.Box3): void {
  const center = box.getCenter(new THREE.Vector3())
  const dir = new THREE.Vector3(
    Math.cos(ELEVATION) * Math.sin(AZIMUTH),
    Math.sin(ELEVATION),
    Math.cos(ELEVATION) * Math.cos(AZIMUTH),
  )
  camera.position.copy(center).addScaledVector(dir, 12)
  camera.lookAt(center)
  camera.updateMatrixWorld()

  const inv = camera.matrixWorldInverse
  const xs = [box.min.x, box.max.x]
  const ys = [box.min.y, box.max.y]
  const zs = [box.min.z, box.max.z]
  let max = 0
  const point = new THREE.Vector3()
  for (const x of xs) {
    for (const y of ys) {
      for (const z of zs) {
        point.set(x, y, z).applyMatrix4(inv)
        max = Math.max(max, Math.abs(point.x), Math.abs(point.y))
      }
    }
  }
  const half = max * 1.02
  camera.left = -half
  camera.right = half
  camera.top = half
  camera.bottom = -half
  camera.updateProjectionMatrix()
}
