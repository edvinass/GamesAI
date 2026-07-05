export interface CollisionEvent {
  x: number
  y: number
  /** Normalized impact strength 0–1. */
  intensity: number
  /** ball = ball hit something; shape = drawn piece hit static/other piece. */
  kind: 'ball' | 'shape'
}

interface Particle {
  x: number
  y: number
  vx: number
  vy: number
  life: number
  maxLife: number
  size: number
  color: string
}

interface Ripple {
  x: number
  y: number
  radius: number
  maxRadius: number
  life: number
  maxLife: number
  color: string
  lineWidth: number
}

interface Flash {
  x: number
  y: number
  radius: number
  life: number
  maxLife: number
  color: string
}

const MAX_PARTICLES = 48

export class VisualEffects {
  private particles: Particle[] = []
  private ripples: Ripple[] = []
  private flashes: Flash[] = []
  private shake = 0

  clear(): void {
    this.particles = []
    this.ripples = []
    this.flashes = []
    this.shake = 0
  }

  spawnCollision(event: CollisionEvent, scale: number): void {
    const t = Math.min(1, event.intensity)
    if (t < 0.12) return

    const isBall = event.kind === 'ball'
    const sparkCount = isBall ? (t > 0.5 ? 3 : 2) : 1
    const palette = isBall
      ? ['rgba(252, 165, 165, 0.45)', 'rgba(251, 191, 36, 0.4)', 'rgba(254, 243, 199, 0.35)']
      : ['rgba(251, 191, 36, 0.35)', 'rgba(148, 163, 184, 0.3)']

    for (let i = 0; i < sparkCount && this.particles.length < MAX_PARTICLES; i++) {
      const angle = Math.random() * Math.PI * 2
      const speed = (0.6 + Math.random() * 1.2) * scale * (0.4 + t * 0.3)
      this.particles.push({
        x: event.x + (Math.random() - 0.5) * 1.5 * scale,
        y: event.y + (Math.random() - 0.5) * 1.5 * scale,
        vx: Math.cos(angle) * speed,
        vy: Math.sin(angle) * speed - scale * 0.25,
        life: 1,
        maxLife: 0.15 + Math.random() * 0.12,
        size: (0.5 + Math.random() * 0.6) * scale,
        color: palette[Math.floor(Math.random() * palette.length)],
      })
    }

    if (isBall && t > 0.35) {
      this.ripples.push({
        x: event.x,
        y: event.y,
        radius: 1 * scale,
        maxRadius: (3 + t * 4) * scale,
        life: 1,
        maxLife: 0.22,
        color: 'rgba(252, 165, 165, 0.28)',
        lineWidth: 0.6 * scale,
      })
    }
  }

  spawnWin(x: number, y: number, scale: number): void {
    const colors = ['#4ade80', '#86efac', '#bbf7d0', '#fef08a', '#ffffff']
    for (let i = 0; i < 48 && this.particles.length < MAX_PARTICLES; i++) {
      const angle = (i / 48) * Math.PI * 2 + Math.random() * 0.4
      const speed = (3 + Math.random() * 6) * scale
      this.particles.push({
        x,
        y,
        vx: Math.cos(angle) * speed,
        vy: Math.sin(angle) * speed - 2 * scale,
        life: 1,
        maxLife: 0.6 + Math.random() * 0.5,
        size: (2 + Math.random() * 3) * scale,
        color: colors[i % colors.length],
      })
    }
    for (let r = 0; r < 3; r++) {
      this.ripples.push({
        x,
        y,
        radius: 4 * scale,
        maxRadius: (36 + r * 18) * scale,
        life: 1,
        maxLife: 0.7 + r * 0.15,
        color: 'rgba(74, 222, 128, 0.9)',
        lineWidth: (2.5 - r * 0.5) * scale,
      })
    }
    this.shake = Math.max(this.shake, 4 * scale)
  }

  update(): { shakeX: number; shakeY: number } {
    const dt = 1 / 60

    for (let i = this.particles.length - 1; i >= 0; i--) {
      const p = this.particles[i]
      p.x += p.vx
      p.y += p.vy
      p.vy += 0.35 * dt * 60
      p.vx *= 0.98
      p.life -= dt / p.maxLife
      if (p.life <= 0) this.particles.splice(i, 1)
    }

    for (let i = this.ripples.length - 1; i >= 0; i--) {
      const r = this.ripples[i]
      r.life -= dt / r.maxLife
      r.radius = r.maxRadius * (1 - r.life * r.life)
      if (r.life <= 0) this.ripples.splice(i, 1)
    }

    for (let i = this.flashes.length - 1; i >= 0; i--) {
      const f = this.flashes[i]
      f.life -= dt / f.maxLife
      if (f.life <= 0) this.flashes.splice(i, 1)
    }

    let shakeX = 0
    let shakeY = 0
    if (this.shake > 0.15) {
      shakeX = (Math.random() - 0.5) * this.shake
      shakeY = (Math.random() - 0.5) * this.shake
      this.shake *= 0.82
    } else {
      this.shake = 0
    }

    return { shakeX, shakeY }
  }

  draw(ctx: CanvasRenderingContext2D): void {
    for (const f of this.flashes) {
      const alpha = f.life * f.life
      const grad = ctx.createRadialGradient(f.x, f.y, 0, f.x, f.y, f.radius)
      grad.addColorStop(0, f.color)
      grad.addColorStop(1, 'rgba(255,255,255,0)')
      ctx.save()
      ctx.globalAlpha = alpha
      ctx.fillStyle = grad
      ctx.beginPath()
      ctx.arc(f.x, f.y, f.radius, 0, Math.PI * 2)
      ctx.fill()
      ctx.restore()
    }

    for (const r of this.ripples) {
      ctx.save()
      ctx.globalAlpha = r.life * 0.5
      ctx.strokeStyle = r.color
      ctx.lineWidth = r.lineWidth * r.life
      ctx.beginPath()
      ctx.arc(r.x, r.y, Math.max(0.5, r.radius), 0, Math.PI * 2)
      ctx.stroke()
      ctx.restore()
    }

    for (const p of this.particles) {
      ctx.save()
      ctx.globalAlpha = Math.min(0.55, p.life * 0.7)
      ctx.fillStyle = p.color
      ctx.beginPath()
      ctx.arc(p.x, p.y, Math.max(0.4, p.size * p.life), 0, Math.PI * 2)
      ctx.fill()
      ctx.restore()
    }
  }
}

/** Seeded star positions for a stable background. */
const STARS = Array.from({ length: 48 }, (_, i) => ({
  x: ((i * 137.508) % 100) / 100,
  y: ((i * 73.291 + 17) % 100) / 100,
  r: 0.4 + (i % 5) * 0.25,
  twinkle: i * 0.7,
}))

export function drawBackground(
  ctx: CanvasRenderingContext2D,
  w: number,
  h: number,
  time: number,
): void {
  const gradient = ctx.createLinearGradient(0, 0, 0, h)
  gradient.addColorStop(0, '#0a0f1e')
  gradient.addColorStop(0.55, '#111827')
  gradient.addColorStop(1, '#1a2332')
  ctx.fillStyle = gradient
  ctx.fillRect(0, 0, w, h)

  const vignette = ctx.createRadialGradient(w / 2, h / 2, h * 0.2, w / 2, h / 2, h * 0.85)
  vignette.addColorStop(0, 'rgba(59, 130, 246, 0.04)')
  vignette.addColorStop(1, 'rgba(0, 0, 0, 0.35)')
  ctx.fillStyle = vignette
  ctx.fillRect(0, 0, w, h)

  ctx.save()
  ctx.strokeStyle = 'rgba(148, 163, 184, 0.06)'
  ctx.lineWidth = 1
  const grid = 40
  for (let x = 0; x <= w; x += grid) {
    ctx.beginPath()
    ctx.moveTo(x, 0)
    ctx.lineTo(x, h)
    ctx.stroke()
  }
  for (let y = 0; y <= h; y += grid) {
    ctx.beginPath()
    ctx.moveTo(0, y)
    ctx.lineTo(w, y)
    ctx.stroke()
  }
  ctx.restore()

  for (const star of STARS) {
    const alpha = 0.15 + 0.12 * Math.sin(time * 0.002 + star.twinkle)
    ctx.fillStyle = `rgba(226, 232, 240, ${alpha})`
    ctx.beginPath()
    ctx.arc(star.x * w, star.y * h, star.r, 0, Math.PI * 2)
    ctx.fill()
  }
}

export function drawStaticBody(
  ctx: CanvasRenderingContext2D,
  body: { type: 'rect' | 'circle'; x: number; y: number; width?: number; height?: number; radius?: number; angle?: number },
  scale: number,
): void {
  ctx.save()
  ctx.translate(body.x, body.y)
  if (body.angle) ctx.rotate(body.angle)

  ctx.shadowColor = 'rgba(0, 0, 0, 0.45)'
  ctx.shadowBlur = 8 * scale
  ctx.shadowOffsetY = 3 * scale

  if (body.type === 'circle') {
    const r = body.radius ?? 20 * scale
    const grad = ctx.createRadialGradient(-r * 0.3, -r * 0.3, r * 0.1, 0, 0, r)
    grad.addColorStop(0, '#94a3b8')
    grad.addColorStop(0.6, '#64748b')
    grad.addColorStop(1, '#475569')
    ctx.fillStyle = grad
    ctx.beginPath()
    ctx.arc(0, 0, r, 0, Math.PI * 2)
    ctx.fill()
    ctx.strokeStyle = 'rgba(203, 213, 225, 0.35)'
    ctx.lineWidth = 1.5 * scale
    ctx.stroke()
  } else {
    const bw = body.width ?? 40 * scale
    const bh = body.height ?? 16 * scale
    const grad = ctx.createLinearGradient(0, -bh / 2, 0, bh / 2)
    grad.addColorStop(0, '#94a3b8')
    grad.addColorStop(0.45, '#64748b')
    grad.addColorStop(1, '#475569')
    ctx.fillStyle = grad
    ctx.fillRect(-bw / 2, -bh / 2, bw, bh)
    ctx.strokeStyle = 'rgba(203, 213, 225, 0.3)'
    ctx.lineWidth = 1 * scale
    ctx.strokeRect(-bw / 2, -bh / 2, bw, bh)
    ctx.fillStyle = 'rgba(255, 255, 255, 0.08)'
    ctx.fillRect(-bw / 2 + 2, -bh / 2 + 1, bw - 4, Math.max(2, bh * 0.25))
  }

  ctx.restore()
}

export function drawTarget(
  ctx: CanvasRenderingContext2D,
  x: number,
  y: number,
  radius: number,
  scale: number,
  time: number,
): void {
  const pulse = 0.5 + 0.5 * Math.sin(time * 0.004)
  const ringCount = 3
  for (let i = ringCount; i >= 1; i--) {
    const expand = 1 + (i / ringCount) * 0.12 * pulse
    ctx.beginPath()
    ctx.arc(x, y, radius * expand, 0, Math.PI * 2)
    ctx.strokeStyle = `rgba(34, 197, 94, ${0.12 * pulse / i})`
    ctx.lineWidth = 2 * scale
    ctx.stroke()
  }

  ctx.save()
  ctx.shadowColor = '#22c55e'
  ctx.shadowBlur = 14 * scale * (0.6 + pulse * 0.4)
  const fillGrad = ctx.createRadialGradient(x, y, radius * 0.1, x, y, radius)
  fillGrad.addColorStop(0, `rgba(74, 222, 128, ${0.45 + pulse * 0.15})`)
  fillGrad.addColorStop(1, 'rgba(34, 197, 94, 0.15)')
  ctx.fillStyle = fillGrad
  ctx.beginPath()
  ctx.arc(x, y, radius, 0, Math.PI * 2)
  ctx.fill()
  ctx.restore()

  ctx.beginPath()
  ctx.arc(x, y, radius, 0, Math.PI * 2)
  ctx.strokeStyle = '#22c55e'
  ctx.lineWidth = 3 * scale
  ctx.stroke()

  ctx.beginPath()
  ctx.arc(x, y, radius * 0.55, 0, Math.PI * 2)
  ctx.strokeStyle = 'rgba(134, 239, 172, 0.6)'
  ctx.lineWidth = 1.5 * scale
  ctx.stroke()

  ctx.fillStyle = '#86efac'
  ctx.font = `bold ${Math.max(11, 13 * scale)}px system-ui, sans-serif`
  ctx.textAlign = 'center'
  ctx.textBaseline = 'middle'
  ctx.fillText('TARGET', x, y)
}

export function drawDrawnShape(
  ctx: CanvasRenderingContext2D,
  localPolygon: { x: number; y: number }[],
  x: number,
  y: number,
  angle: number,
  scale: number,
): void {
  if (localPolygon.length < 3) return
  ctx.save()
  ctx.translate(x, y)
  ctx.rotate(angle)

  ctx.shadowColor = 'rgba(245, 158, 11, 0.35)'
  ctx.shadowBlur = 6 * scale
  ctx.shadowOffsetY = 2 * scale

  ctx.beginPath()
  ctx.moveTo(localPolygon[0].x, localPolygon[0].y)
  for (let i = 1; i < localPolygon.length; i++) {
    ctx.lineTo(localPolygon[i].x, localPolygon[i].y)
  }
  ctx.closePath()

  const grad = ctx.createLinearGradient(0, -20 * scale, 0, 20 * scale)
  grad.addColorStop(0, '#fcd34d')
  grad.addColorStop(0.5, '#f59e0b')
  grad.addColorStop(1, '#d97706')
  ctx.fillStyle = grad
  ctx.fill()

  ctx.strokeStyle = '#b45309'
  ctx.lineWidth = 1.8 * scale
  ctx.stroke()

  ctx.clip()
  ctx.fillStyle = 'rgba(255, 255, 255, 0.12)'
  ctx.fillRect(-200 * scale, -200 * scale, 400 * scale, 80 * scale)
  ctx.restore()
}

export function drawBall(
  ctx: CanvasRenderingContext2D,
  x: number,
  y: number,
  radius: number,
  angle: number,
  scale: number,
  released: boolean,
  velocity: { x: number; y: number },
  trail: { x: number; y: number }[],
): void {
  const speed = Math.hypot(velocity.x, velocity.y)

  for (let i = 0; i < trail.length; i++) {
    const t = (i + 1) / (trail.length + 1)
    const pt = trail[i]
    ctx.beginPath()
    ctx.arc(pt.x, pt.y, radius * t * 0.85, 0, Math.PI * 2)
    ctx.fillStyle = `rgba(239, 68, 68, ${t * 0.22})`
    ctx.fill()
  }

  ctx.save()
  ctx.translate(x, y)
  ctx.rotate(angle)

  if (released && speed > 1) {
    ctx.shadowColor = '#ef4444'
    ctx.shadowBlur = (6 + Math.min(speed, 12) * 0.8) * scale
  }

  const grad = ctx.createRadialGradient(-radius * 0.35, -radius * 0.35, radius * 0.05, 0, 0, radius)
  if (released) {
    grad.addColorStop(0, '#fecaca')
    grad.addColorStop(0.45, '#ef4444')
    grad.addColorStop(1, '#991b1b')
  } else {
    grad.addColorStop(0, 'rgba(254, 202, 202, 0.7)')
    grad.addColorStop(0.5, 'rgba(239, 68, 68, 0.55)')
    grad.addColorStop(1, 'rgba(153, 27, 27, 0.45)')
  }
  ctx.fillStyle = grad
  ctx.beginPath()
  ctx.arc(0, 0, radius, 0, Math.PI * 2)
  ctx.fill()

  ctx.strokeStyle = released ? '#fca5a5' : 'rgba(252, 165, 165, 0.7)'
  ctx.lineWidth = 2 * scale
  if (!released) {
    ctx.setLineDash([4 * scale, 4 * scale])
  }
  ctx.stroke()
  ctx.setLineDash([])

  ctx.strokeStyle = 'rgba(255, 255, 255, 0.45)'
  ctx.lineWidth = 1.5 * scale
  ctx.beginPath()
  ctx.arc(0, 0, radius * 0.72, -0.6, 0.9)
  ctx.stroke()

  ctx.strokeStyle = 'rgba(255, 255, 255, 0.25)'
  ctx.lineWidth = 1 * scale
  ctx.beginPath()
  ctx.moveTo(0, 0)
  ctx.lineTo(radius * 0.65, 0)
  ctx.stroke()

  ctx.restore()
}
