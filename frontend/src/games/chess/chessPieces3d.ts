import * as THREE from 'three'

export type PieceKind = 'p' | 'n' | 'b' | 'r' | 'q' | 'k'

export interface PieceMaterials {
  white: THREE.Material
  black: THREE.Material
  accent: THREE.Material
  dispose(): void
}

interface Part {
  geometry: THREE.BufferGeometry
  position?: [number, number, number]
  rotation?: [number, number, number]
  scale?: [number, number, number]
  accent?: boolean
}

const LATHE_SEGMENTS = 72

/** Builds a lathe silhouette bottom-up as (radius, height) points. */
class Profile {
  private points: THREE.Vector2[] = [new THREE.Vector2(0, 0)]

  private get last(): THREE.Vector2 {
    return this.points[this.points.length - 1]
  }

  to(r: number, y: number): this {
    this.points.push(new THREE.Vector2(r, y))
    return this
  }

  quad(cr: number, cy: number, r: number, y: number, steps = 8): this {
    const curve = new THREE.QuadraticBezierCurve(
      this.last.clone(),
      new THREE.Vector2(cr, cy),
      new THREE.Vector2(r, y),
    )
    this.points.push(...curve.getPoints(steps).slice(1))
    return this
  }

  curve(c1r: number, c1y: number, c2r: number, c2y: number, r: number, y: number, steps = 16): this {
    const curve = new THREE.CubicBezierCurve(
      this.last.clone(),
      new THREE.Vector2(c1r, c1y),
      new THREE.Vector2(c2r, c2y),
      new THREE.Vector2(r, y),
    )
    this.points.push(...curve.getPoints(steps).slice(1))
    return this
  }

  /** Half-round moulding that bulges outward and ends directly above the current point. */
  bead(height: number, bulge: number, steps = 10): this {
    const { x: r, y } = this.last
    for (let i = 1; i <= steps; i++) {
      const a = -Math.PI / 2 + (Math.PI * i) / steps
      this.to(r + bulge * Math.cos(a), y + (height / 2) * (1 + Math.sin(a)))
    }
    return this
  }

  /** Closes the top with a ball of the given center height and radius. */
  sphereTo(cy: number, radius: number, steps = 18): this {
    const start = Math.asin(THREE.MathUtils.clamp((this.last.y - cy) / radius, -1, 1))
    for (let i = 1; i <= steps; i++) {
      const a = start + ((Math.PI / 2 - start) * i) / steps
      this.to(i === steps ? 0 : radius * Math.cos(a), cy + radius * Math.sin(a))
    }
    return this
  }

  lathe(): THREE.BufferGeometry {
    return new THREE.LatheGeometry(this.points, LATHE_SEGMENTS)
  }
}

/** Shared Staunton foot: rounded plinth, torus roll, cove and bead. Ends at (topR, 0.19). */
function stauntonBase(topR: number): Profile {
  return new Profile()
    .to(0.35, 0)
    .quad(0.372, 0, 0.372, 0.022)
    .to(0.372, 0.034)
    .quad(0.372, 0.05, 0.355, 0.052)
    .bead(0.05, 0.02)
    .quad(0.335, 0.106, 0.31, 0.11)
    .curve(0.28, 0.113, 0.265, 0.13, 0.268, 0.15)
    .to(0.27, 0.152)
    .bead(0.024, 0.012)
    .quad(0.25, 0.18, topR, 0.19)
}

function sphere(radius: number): THREE.BufferGeometry {
  return new THREE.SphereGeometry(radius, 32, 20)
}

function scaleUvs(geometry: THREE.BufferGeometry, factor: number): void {
  const uv = geometry.getAttribute('uv')
  for (let i = 0; i < uv.count; i++) uv.setXY(i, uv.getX(i) * factor, uv.getY(i) * factor)
  uv.needsUpdate = true
}

/** Horse head silhouette with the snout pointing +x, extruded along z with a soft bevel. */
function knightHead(): THREE.BufferGeometry {
  const s = new THREE.Shape()
  s.moveTo(-0.17, 0.2)
  s.lineTo(0.19, 0.2)
  s.bezierCurveTo(0.2, 0.3, 0.14, 0.36, 0.1, 0.42)
  s.bezierCurveTo(0.16, 0.45, 0.26, 0.5, 0.33, 0.55)
  s.quadraticCurveTo(0.37, 0.58, 0.35, 0.63)
  s.quadraticCurveTo(0.33, 0.68, 0.27, 0.7)
  s.bezierCurveTo(0.2, 0.73, 0.13, 0.78, 0.09, 0.84)
  s.lineTo(0.07, 0.95)
  s.lineTo(0.02, 0.9)
  s.quadraticCurveTo(-0.04, 0.9, -0.08, 0.84)
  s.bezierCurveTo(-0.18, 0.76, -0.24, 0.6, -0.23, 0.45)
  s.quadraticCurveTo(-0.22, 0.3, -0.17, 0.2)

  const geometry = new THREE.ExtrudeGeometry(s, {
    depth: 0.1,
    curveSegments: 16,
    bevelEnabled: true,
    bevelThickness: 0.045,
    bevelSize: 0.035,
    bevelSegments: 6,
  })
  geometry.translate(0, 0, -0.05)
  scaleUvs(geometry, 2.5)
  return geometry
}

/** One battlement block of the rook crown, centered on +x. */
function merlon(inner: number, outer: number, height: number, arc: number): THREE.BufferGeometry {
  const bevel = 0.008
  const shape = new THREE.Shape()
  shape.absarc(0, 0, outer, -arc / 2, arc / 2, false)
  shape.absarc(0, 0, inner, arc / 2, -arc / 2, true)
  shape.closePath()
  const geometry = new THREE.ExtrudeGeometry(shape, {
    depth: height - 2 * bevel,
    curveSegments: 12,
    bevelEnabled: true,
    bevelThickness: bevel,
    bevelSize: bevel,
    bevelSegments: 3,
  })
  geometry.rotateX(-Math.PI / 2)
  geometry.translate(0, bevel, 0)
  scaleUvs(geometry, 3)
  return geometry
}

/** Cross pattée for the king's finial, centered at the origin facing z. */
function kingCross(): THREE.BufferGeometry {
  const w = 0.028
  const f = 0.055
  const arm = 0.095
  const foot = 0.1
  const dip = 0.018
  const s = new THREE.Shape()
  s.moveTo(-w, w)
  s.lineTo(-f, arm)
  s.quadraticCurveTo(0, arm - dip, f, arm)
  s.lineTo(w, w)
  s.lineTo(arm, f)
  s.quadraticCurveTo(arm - dip, 0, arm, -f)
  s.lineTo(w, -w)
  s.lineTo(f, -foot)
  s.quadraticCurveTo(0, -foot + dip, -f, -foot)
  s.lineTo(-w, -w)
  s.lineTo(-arm, -f)
  s.quadraticCurveTo(-arm + dip, 0, -arm, f)
  s.closePath()
  const geometry = new THREE.ExtrudeGeometry(s, {
    depth: 0.035,
    curveSegments: 10,
    bevelEnabled: true,
    bevelThickness: 0.012,
    bevelSize: 0.01,
    bevelSegments: 4,
  })
  geometry.translate(0, 0, -0.0175)
  scaleUvs(geometry, 3)
  return geometry
}

function ring(
  geometry: THREE.BufferGeometry,
  count: number,
  radius: number,
  y: number,
): Part[] {
  return Array.from({ length: count }, (_, i) => {
    const angle = (i * Math.PI * 2) / count
    return {
      geometry,
      position: [Math.cos(angle) * radius, y, Math.sin(angle) * radius] as [number, number, number],
    }
  })
}

function buildPawn(): Part[] {
  const body = stauntonBase(0.22)
    .curve(0.17, 0.24, 0.12, 0.3, 0.11, 0.38)
    .to(0.105, 0.4)
    .quad(0.2, 0.4, 0.2, 0.42)
    .quad(0.2, 0.44, 0.16, 0.445)
    .quad(0.1, 0.45, 0.085, 0.47)
    .sphereTo(0.56, 0.12)
  return [{ geometry: body.lathe() }]
}

function buildRook(): Part[] {
  const body = stauntonBase(0.25)
    .curve(0.23, 0.25, 0.2, 0.32, 0.2, 0.42)
    .curve(0.2, 0.48, 0.22, 0.5, 0.23, 0.52)
    .bead(0.022, 0.01)
    .to(0.235, 0.545)
    .to(0.255, 0.56)
    .to(0.26, 0.598)
    .quad(0.26, 0.605, 0.252, 0.605)
    .to(0, 0.605)
  const count = 6
  const block = merlon(0.175, 0.25, 0.11, ((Math.PI * 2) / count) * 0.62)
  const merlons: Part[] = Array.from({ length: count }, (_, i) => ({
    geometry: block,
    position: [0, 0.6, 0],
    rotation: [0, (i * Math.PI * 2) / count, 0],
  }))
  return [{ geometry: body.lathe() }, ...merlons]
}

function buildKnight(): Part[] {
  const base = stauntonBase(0.24)
    .quad(0.26, 0.2, 0.25, 0.215)
    .bead(0.02, 0.01)
    .quad(0.22, 0.24, 0, 0.24)

  const mane = new THREE.CubicBezierCurve(
    new THREE.Vector2(-0.08, 0.84),
    new THREE.Vector2(-0.18, 0.76),
    new THREE.Vector2(-0.24, 0.6),
    new THREE.Vector2(-0.23, 0.45),
  )
  const tuft = sphere(1)
  const tufts: Part[] = []
  const steps = 9
  for (let i = 1; i < steps; i++) {
    const t = i / steps
    const point = mane.getPoint(t)
    const tangent = mane.getTangent(t)
    const outward = new THREE.Vector2(tangent.y, -tangent.x).multiplyScalar(0.025)
    tufts.push({
      geometry: tuft,
      position: [point.x + outward.x, point.y + outward.y, 0],
      rotation: [0, 0, Math.atan2(tangent.y, tangent.x)],
      scale: [0.04, 0.03, 0.07],
    })
  }

  const eye = sphere(0.02)
  const nostril = sphere(0.016)
  return [
    { geometry: base.lathe() },
    { geometry: knightHead() },
    ...tufts,
    { geometry: eye, position: [0.13, 0.765, 0.09], accent: true },
    { geometry: eye, position: [0.13, 0.765, -0.09], accent: true },
    { geometry: nostril, position: [0.3, 0.64, 0.06], accent: true },
    { geometry: nostril, position: [0.3, 0.64, -0.06], accent: true },
  ]
}

function buildBishop(): Part[] {
  const body = stauntonBase(0.21)
    .curve(0.15, 0.26, 0.1, 0.36, 0.095, 0.5)
    .to(0.095, 0.52)
    .quad(0.19, 0.52, 0.19, 0.54)
    .quad(0.19, 0.555, 0.14, 0.56)
    .bead(0.03, 0.02)
    .quad(0.1, 0.595, 0.085, 0.61)
    .curve(0.16, 0.63, 0.17, 0.72, 0.13, 0.8)
    .curve(0.1, 0.85, 0.05, 0.88, 0.03, 0.9)
    .to(0.03, 0.91)
    .sphereTo(0.95, 0.045)

  const slit = new THREE.TorusGeometry(0.148, 0.008, 8, 40, Math.PI)
  slit.rotateZ(-Math.PI / 2)
  slit.rotateX(Math.PI / 2)
  return [
    { geometry: body.lathe() },
    { geometry: slit, position: [0, 0.72, 0], rotation: [0, 0, 0.45], accent: true },
  ]
}

function buildQueen(): Part[] {
  const body = stauntonBase(0.23)
    .curve(0.17, 0.27, 0.11, 0.4, 0.1, 0.58)
    .quad(0.2, 0.58, 0.2, 0.6)
    .quad(0.2, 0.615, 0.15, 0.62)
    .bead(0.028, 0.015)
    .quad(0.11, 0.655, 0.1, 0.67)
    .curve(0.12, 0.74, 0.2, 0.81, 0.215, 0.86)
    .quad(0.218, 0.875, 0.2, 0.878)
    .quad(0.15, 0.87, 0.13, 0.875)
    .curve(0.12, 0.9, 0.09, 0.93, 0.05, 0.945)
    .to(0.035, 0.955)
    .sphereTo(0.995, 0.05)
  return [{ geometry: body.lathe() }, ...ring(sphere(0.03), 10, 0.207, 0.885)]
}

function buildKing(): Part[] {
  const body = stauntonBase(0.24)
    .curve(0.18, 0.28, 0.12, 0.43, 0.11, 0.62)
    .quad(0.21, 0.62, 0.21, 0.64)
    .quad(0.21, 0.655, 0.16, 0.66)
    .bead(0.03, 0.016)
    .quad(0.12, 0.695, 0.11, 0.71)
    .curve(0.13, 0.78, 0.2, 0.85, 0.205, 0.9)
    .quad(0.207, 0.915, 0.19, 0.92)
    .curve(0.16, 0.93, 0.13, 0.97, 0.09, 0.99)
    .quad(0.06, 1.0, 0.05, 1.005)
    .bead(0.02, 0.015)
    .quad(0.03, 1.03, 0, 1.03)
  return [
    { geometry: body.lathe() },
    ...ring(sphere(0.018), 14, 0.2, 0.905),
    { geometry: kingCross(), position: [0, 1.125, 0] },
  ]
}

function buildParts(kind: PieceKind): Part[] {
  switch (kind) {
    case 'p':
      return buildPawn()
    case 'r':
      return buildRook()
    case 'n':
      return buildKnight()
    case 'b':
      return buildBishop()
    case 'q':
      return buildQueen()
    case 'k':
      return buildKing()
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

export function createPieceMesh(
  kind: PieceKind,
  materials: PieceMaterials,
  isWhite: boolean,
): THREE.Group {
  const group = new THREE.Group()
  const body = isWhite ? materials.white : materials.black
  for (const part of getParts(kind)) {
    const mesh = new THREE.Mesh(part.geometry, part.accent ? materials.accent : body)
    if (part.position) mesh.position.set(...part.position)
    if (part.rotation) mesh.rotation.set(...part.rotation)
    if (part.scale) mesh.scale.set(...part.scale)
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

function seededRandom(seed: number): () => number {
  let state = seed >>> 0
  return () => {
    state = (state + 0x6d2b79f5) >>> 0
    let t = state
    t = Math.imul(t ^ (t >>> 15), t | 1)
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61)
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296
  }
}

/** Procedural wood grain that tiles horizontally so lathe seams stay invisible. */
export function woodTexture(
  base: string,
  grain: string,
  highlight: string,
  seed: number,
): THREE.CanvasTexture {
  const size = 512
  const canvas = document.createElement('canvas')
  canvas.width = size
  canvas.height = size
  const ctx = canvas.getContext('2d')!
  const rand = seededRandom(seed)

  ctx.fillStyle = base
  ctx.fillRect(0, 0, size, size)

  ctx.fillStyle = highlight
  for (let i = 0; i < 16; i++) {
    ctx.globalAlpha = 0.04 + rand() * 0.07
    const x = rand() * size
    const width = 10 + rand() * 45
    ctx.fillRect(x, 0, width, size)
    ctx.fillRect(x - size, 0, width, size)
  }

  ctx.strokeStyle = grain
  for (let i = 0; i < 140; i++) {
    ctx.globalAlpha = 0.05 + rand() * 0.2
    ctx.lineWidth = 0.6 + rand() * 2.2
    const x0 = rand() * size
    const amp = 2 + rand() * 8
    const freq = 0.004 + rand() * 0.012
    const phase = rand() * Math.PI * 2
    for (const shift of [0, -size]) {
      ctx.beginPath()
      for (let y = 0; y <= size; y += 8) {
        const x = x0 + shift + Math.sin(y * freq + phase) * amp
        if (y === 0) ctx.moveTo(x, y)
        else ctx.lineTo(x, y)
      }
      ctx.stroke()
    }
  }
  ctx.globalAlpha = 1

  const texture = new THREE.CanvasTexture(canvas)
  texture.wrapS = THREE.RepeatWrapping
  texture.wrapT = THREE.RepeatWrapping
  texture.repeat.set(2, 1)
  texture.colorSpace = THREE.SRGBColorSpace
  texture.anisotropy = 8
  return texture
}

export function createPieceMaterials(): PieceMaterials {
  const boxwood = woodTexture('#f2e5cb', '#b08a58', '#fffaf0', 7)
  const ebony = woodTexture('#2e1e15', '#0f0906', '#5a3c29', 13)
  const white = new THREE.MeshPhysicalMaterial({
    map: boxwood,
    roughness: 0.32,
    clearcoat: 0.85,
    clearcoatRoughness: 0.14,
  })
  const black = new THREE.MeshPhysicalMaterial({
    map: ebony,
    roughness: 0.28,
    clearcoat: 1,
    clearcoatRoughness: 0.08,
  })
  const accent = new THREE.MeshStandardMaterial({ color: 0x0b0705, roughness: 0.5 })
  return {
    white,
    black,
    accent,
    dispose() {
      for (const resource of [boxwood, ebony, white, black, accent]) resource.dispose()
    },
  }
}
