export const POWERUP_ACTIVATION_TICKS = 8

/** Fire immediately on E — no hold required */
export const INSTANT_POWERUP_TYPES = new Set([
  'heal',
  'laser',
  'railgun',
  'bomb',
  'cluster',
  'burst',
])

export const POWERUP_HINTS: Record<string, string> = {
  rapid_fire: 'Shorter reload between shots',
  machine_gun: 'Sprays fast regular bullets',
  shield: 'Blocks all damage for a few seconds',
  wide_shot: 'Three-row spread on every shot',
  pierce: 'Shots pass through cover and keep going',
  ghost: 'Harder for enemies to track your position',
  freeze: 'Freezes opponent movement',
  laser: 'Instant beam down your aim row',
  railgun: 'Piercing beam that ignores cover',
  homing: 'Bullets steer toward your opponent',
  heal: 'Restore 1 HP instantly',
  mirror: 'Reflects incoming bullets',
  overdrive: 'Wide, heavy shots for a few seconds',
  bomb: 'Launches an explosive projectile',
  cluster: 'Fires three bombs in a spread',
  burst: 'Unloads a six-shot rapid salvo',
}

export function isInstantPowerup(type: string | null | undefined): boolean {
  return Boolean(type && INSTANT_POWERUP_TYPES.has(type))
}

export function powerupUseHint(type: string | null | undefined): string {
  if (!type) return ''
  if (isInstantPowerup(type)) return 'Press E or click Use to fire instantly'
  return 'Hold E until the bar fills, then release'
}
