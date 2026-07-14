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

export type PowerupTier = 'common' | 'rare' | 'epic'

export const POWERUP_TIERS: Record<string, PowerupTier> = {
  rapid_fire: 'common',
  machine_gun: 'common',
  shield: 'common',
  wide_shot: 'common',
  homing: 'common',
  heal: 'common',
  pierce: 'rare',
  ghost: 'rare',
  freeze: 'rare',
  mirror: 'rare',
  overdrive: 'rare',
  bomb: 'rare',
  burst: 'rare',
  laser: 'epic',
  railgun: 'epic',
  cluster: 'epic',
}

export const POWERUP_TIER_LABELS: Record<PowerupTier, string> = {
  common: 'Common',
  rare: 'Rare',
  epic: 'Epic',
}

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

const BUFF_EFFECT_KEYS = [
  ['rapid_fire_until', 'rapid_fire_active', 'rapid_fire', 'Rapid Fire'],
  ['machine_gun_until', 'machine_gun_active', 'machine_gun', 'Machine Gun'],
  ['shield_until', 'shield_active', 'shield', 'Shield'],
  ['wide_shot_until', 'wide_shot_active', 'wide_shot', 'Wide Shot'],
  ['pierce_until', 'pierce_active', 'pierce', 'Pierce'],
  ['ghost_until', 'ghost_active', 'ghost', 'Ghost'],
  ['homing_until', 'homing_active', 'homing', 'Homing'],
  ['mirror_until', 'mirror_active', 'mirror', 'Mirror'],
  ['overdrive_until', 'overdrive_active', 'overdrive', 'Overdrive'],
  ['freeze_until', 'freeze_active', 'freeze', 'Freeze'],
] as const

export interface ActivePowerupEffect {
  id: string
  label: string
  remainingTicks: number
  totalTicks: number
  progress: number
}

export function isInstantPowerup(type: string | null | undefined): boolean {
  return Boolean(type && INSTANT_POWERUP_TYPES.has(type))
}

export function powerupTier(type: string | null | undefined): PowerupTier {
  if (!type) return 'common'
  return POWERUP_TIERS[type] ?? 'common'
}

export function powerupUseHint(type: string | null | undefined): string {
  if (!type) return ''
  if (isInstantPowerup(type)) return 'Press E or click Use to fire instantly'
  return 'Hold E until the bar fills, then release'
}

export function listActivePowerupEffects(
  effects: Record<string, unknown> | undefined,
  tick: number,
  effectDurationTicks = 80,
): ActivePowerupEffect[] {
  if (!effects) return []
  const active: ActivePowerupEffect[] = []
  for (const [untilKey, activeKey, id, label] of BUFF_EFFECT_KEYS) {
    const isActive = Boolean(effects[activeKey])
    const until = Number(effects[untilKey] ?? 0)
    if (!isActive && until <= tick) continue
    const remainingTicks = Math.max(0, until - tick)
    if (remainingTicks <= 0 && !isActive) continue
    const totalTicks = Math.max(effectDurationTicks, remainingTicks)
    active.push({
      id,
      label,
      remainingTicks,
      totalTicks,
      progress: Math.max(0, Math.min(1, remainingTicks / totalTicks)),
    })
  }
  return active
}
