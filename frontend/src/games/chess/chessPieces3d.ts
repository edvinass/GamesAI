import * as THREE from 'three'

export type PieceKind = 'p' | 'n' | 'b' | 'r' | 'q' | 'k'

interface Part {
  geometry: THREE.BufferGeometry
  position?: [number, number, number]
  scale?: [number, number, number]
  rotationY?: number
}

const LATHE_SEGMENTS = 40

const BASE: Array<[number, number]> = [
  [0, 0],
  [0.36, 0],
  [0.37, 0.04],
  [0.35, 0.08],
  [0.3, 0.1],
  [0.3, 0.13],
  [0.26, 0.15],
]

function lathe(points: Array<[number, number]>): THREE.BufferGeometry {
  return new THREE.LatheGeometry(
    points.map(([r, y]) => new THREE.Vector2(r, y)),
    LATHE_SEGMENTS,
  )
}

function sphere(radius: number): THREE.BufferGeometry {
  return new THREE.SphereGeometry(radius, 24, 16)
}

/** Horse head silhouette with the snout pointing +x, extruded along z. */
function knightHead(): THREE.BufferGeometry {
  const outline: Array<[number, number]> = [
    [-0.2, 0.18],
    [0.2, 0.18],
    [0.17, 0.36],
    [0.08, 0.46],
    [0.28, 0.52],
    [0.34, 0.6],
    [0.3, 0.68],
    [0.12, 0.8],
    [0.06, 0.94],
    [-0.01, 0.98],
    [-0.06, 0.86],
    [-0.16, 0.78],
    [-0.24, 0.56],
    [-0.24, 0.34],
  ]
  const shape = new THREE.Shape()
  shape.moveTo(outline[0][0], outline[0][1])
  for (const [x, y] of outline.slice(1)) shape.lineTo(x, y)
  shape.closePath()
  const geometry = new THREE.ExtrudeGeometry(shape, {
    depth: 0.18,
    bevelEnabled: true,
    bevelThickness: 0.04,
    bevelSize: 0.03,
    bevelSegments: 3,
  })
  geometry.translate(0, 0, -0.09)
  return geometry
}

function buildParts(kind: PieceKind): Part[] {
  switch (kind) {
    case 'p':
      return [
        {
          geometry: lathe([
            ...BASE,
            [0.2, 0.18],
            [0.14, 0.3],
            [0.11, 0.4],
            [0.17, 0.42],
            [0.17, 0.45],
            [0.09, 0.47],
            [0, 0.47],
          ]),
        },
        { geometry: sphere(0.14), position: [0, 0.58, 0] },
      ]
    case 'r': {
      const parts: Part[] = [
        {
          geometry: lathe([
            ...BASE,
            [0.24, 0.2],
            [0.2, 0.3],
            [0.19, 0.5],
            [0.25, 0.54],
            [0.25, 0.66],
            [0, 0.66],
          ]),
        },
      ]
      const merlon = new THREE.BoxGeometry(0.12, 0.1, 0.1)
      for (let i = 0; i < 4; i++) {
        const angle = (i * Math.PI) / 2 + Math.PI / 4
        parts.push({
          geometry: merlon,
          position: [Math.cos(angle) * 0.18, 0.71, Math.sin(angle) * 0.18],
          rotationY: -angle,
        })
      }
      return parts
    }
    case 'n':
      return [
        { geometry: lathe([...BASE, [0.24, 0.2], [0.22, 0.24], [0, 0.24]]) },
        { geometry: knightHead() },
      ]
    case 'b':
      return [
        {
          geometry: lathe([
            ...BASE,
            [0.2, 0.2],
            [0.13, 0.36],
            [0.11, 0.48],
            [0.18, 0.5],
            [0.18, 0.53],
            [0.1, 0.55],
            [0, 0.55],
          ]),
        },
        { geometry: sphere(1), position: [0, 0.72, 0], scale: [0.15, 0.22, 0.15] },
        { geometry: sphere(0.045), position: [0, 0.97, 0] },
      ]
    case 'q': {
      const parts: Part[] = [
        {
          geometry: lathe([
            ...BASE,
            [0.22, 0.2],
            [0.14, 0.4],
            [0.11, 0.6],
            [0.19, 0.63],
            [0.19, 0.66],
            [0.13, 0.68],
            [0.2, 0.84],
            [0.16, 0.85],
            [0, 0.8],
          ]),
        },
        { geometry: sphere(0.075), position: [0, 0.88, 0] },
      ]
      const bead = sphere(0.04)
      for (let i = 0; i < 8; i++) {
        const angle = (i * Math.PI) / 4
        parts.push({
          geometry: bead,
          position: [Math.cos(angle) * 0.19, 0.87, Math.sin(angle) * 0.19],
        })
      }
      return parts
    }
    case 'k':
      return [
        {
          geometry: lathe([
            ...BASE,
            [0.23, 0.2],
            [0.15, 0.42],
            [0.12, 0.64],
            [0.2, 0.67],
            [0.2, 0.7],
            [0.13, 0.72],
            [0.19, 0.88],
            [0.19, 0.9],
            [0, 0.94],
          ]),
        },
        { geometry: new THREE.BoxGeometry(0.06, 0.24, 0.06), position: [0, 1.06, 0] },
        { geometry: new THREE.BoxGeometry(0.2, 0.06, 0.06), position: [0, 1.08, 0] },
      ]
  }
}

const partCache = new Map<PieceKind, Part[]>()

function getParts(kind: PieceKind): Part[] {
  let parts = partCache.get(kind)
  if (!parts) {
    parts = buildParts(kind)
    partCache.set(kind, parts)
  }
  return parts
}

export function createPieceMesh(kind: PieceKind, material: THREE.Material): THREE.Group {
  const group = new THREE.Group()
  for (const part of getParts(kind)) {
    const mesh = new THREE.Mesh(part.geometry, material)
    if (part.position) mesh.position.set(...part.position)
    if (part.scale) mesh.scale.set(...part.scale)
    if (part.rotationY) mesh.rotation.y = part.rotationY
    mesh.castShadow = true
    mesh.receiveShadow = true
    group.add(mesh)
  }
  return group
}

export function disposePieceGeometries(): void {
  const seen = new Set<THREE.BufferGeometry>()
  for (const parts of partCache.values()) {
    for (const part of parts) {
      if (seen.has(part.geometry)) continue
      seen.add(part.geometry)
      part.geometry.dispose()
    }
  }
  partCache.clear()
}
