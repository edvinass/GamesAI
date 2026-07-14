export const POWERUP_ACTIVATION_TICKS = 8

export const INSTANT_POWERUP_TYPES = new Set([
  'heal',
  'snipe',
  'railgun',
  'bomb',
  'cluster',
  'burst',
  'shockwave',
])

/** Hold duration before channeled power-ups activate — keep in sync with backend POWERUP_CHANNEL_TICKS */
export const POWERUP_CHANNEL_TICKS: Record<string, number> = {
  machine_gun: 6,
  shield: 8,
  wide_shot: 6,
  homing: 7,
  pierce: 7,
  ghost: 7,
  jam: 8,
  ricochet: 7,
  afterburner: 6,
  expose: 7,
}

export type PowerupTier = 'common' | 'rare' | 'epic'

export const POWERUP_TIERS: Record<string, PowerupTier> = {
  machine_gun: 'common',
  shield: 'common',
  wide_shot: 'common',
  homing: 'common',
  heal: 'common',
  shockwave: 'common',
  pierce: 'rare',
  ghost: 'rare',
  jam: 'rare',
  ricochet: 'rare',
  afterburner: 'rare',
  expose: 'rare',
  bomb: 'rare',
  burst: 'rare',
  snipe: 'epic',
  railgun: 'epic',
  cluster: 'epic',
}

export const POWERUP_TIER_LABELS: Record<PowerupTier, string> = {
  common: 'Common',
  rare: 'Rare',
  epic: 'Epic',
}

/** Active buff/debuff length in ticks — keep in sync with backend POWERUP_EFFECT_DURATIONS */
export const POWERUP_EFFECT_DURATIONS: Record<string, number> = {
  machine_gun: 180,
  shield: 200,
  wide_shot: 150,
  pierce: 140,
  ghost: 170,
  jam: 100,
  homing: 160,
  ricochet: 140,
  afterburner: 110,
  expose: 130,
}

export const BOMB_CHARGES = 3

export const POWERUP_HINTS: Record<string, string> = {
  machine_gun: 'Fast single-row spray — ~14s',
  shield: 'Blocks all damage — ~16s',
  wide_shot: 'Three-row spread on every shot — ~12s',
  pierce: 'Shots pass through cover and fighters — ~10s',
  ghost: 'Enemies see a faint silhouette — homing shots drift off target',
  jam: 'Silences enemy guns and movement — ~7.5s',
  snipe: 'One fast shot that pierces cover for heavy damage',
  railgun: 'Piercing beam through cover — heavy damage',
  homing: 'Bullets steer toward your opponent with lock-on guidance — ~12s',
  heal: 'Restore 1 HP instantly',
  ricochet: 'Your shots bounce off walls and cover — ~10s',
  afterburner: 'Move two rows per tick while strafing — ~8s',
  expose: 'Reveals enemy position in fog and counters Ghost — ~10s',
  bomb: `Fire up to ${BOMB_CHARGES} bombs — wide blast on wall impact`,
  cluster: 'Fires three bombs in a vertical spread',
  burst: 'Unloads a six-shot rapid salvo',
  shockwave: 'Pushes enemies away from your aim row',
}

const BUFF_EFFECT_KEYS = [
  ['machine_gun_until', 'machine_gun_active', 'machine_gun', 'Machine Gun'],
  ['shield_until', 'shield_active', 'shield', 'Shield'],
  ['wide_shot_until', 'wide_shot_active', 'wide_shot', 'Wide Shot'],
  ['pierce_until', 'pierce_active', 'pierce', 'Pierce'],
  ['ghost_until', 'ghost_active', 'ghost', 'Ghost'],
  ['homing_until', 'homing_active', 'homing', 'Homing'],
  ['ricochet_until', 'ricochet_active', 'ricochet', 'Ricochet'],
  ['afterburner_until', 'afterburner_active', 'afterburner', 'Afterburner'],
  ['jam_until', 'jam_active', 'jam', 'Jammed'],
  ['jam_cast_until', 'jam_cast_active', 'jam', 'Jam cast'],
  ['exposed_until', 'exposed_active', 'expose', 'Exposed'],
  ['expose_cast_until', 'expose_cast_active', 'expose', 'Expose cast'],
] as const

export interface ActivePowerupEffect {
  id: string
  label: string
  remainingTicks: number
  totalTicks: number
  progress: number
  remainingSec: number
}

export function powerupTier(type: string | null | undefined): PowerupTier {
  if (!type) return 'common'
  return POWERUP_TIERS[type] ?? 'common'
}

export function isInstantPowerup(type: string | null | undefined): boolean {
  return Boolean(type && INSTANT_POWERUP_TYPES.has(type))
}

export function powerupChannelTicks(type: string | null | undefined): number {
  if (!type) return POWERUP_ACTIVATION_TICKS
  return POWERUP_CHANNEL_TICKS[type] ?? POWERUP_ACTIVATION_TICKS
}

export function powerupEffectDuration(type: string | null | undefined, fallback = 80): number {
  if (!type) return fallback
  return POWERUP_EFFECT_DURATIONS[type] ?? fallback
}

export function formatPowerupSeconds(ticks: number, tickMs: number): string {
  const sec = Math.max(0, (ticks * tickMs) / 1000)
  if (sec >= 10) return `${Math.round(sec)}s`
  return `${Math.round(sec * 10) / 10}s`
}

export function powerupUseHint(
  type: string | null | undefined,
  _tickMs = 75,
  charges?: number | null,
): string {
  if (type === 'bomb' && charges != null && charges > 0) {
    return `Press to fire (${charges} left)`
  }
  return 'Press to activate'
}

export function listActivePowerupEffects(
  effects: Record<string, unknown> | undefined,
  tick: number,
  tickMs = 75,
  fallbackDuration = 80,
): ActivePowerupEffect[] {
  if (!effects) return []
  const active: ActivePowerupEffect[] = []
  for (const [untilKey, activeKey, id, label] of BUFF_EFFECT_KEYS) {
    const isActive = Boolean(effects[activeKey])
    const until = Number(effects[untilKey] ?? 0)
    if (!isActive && until <= tick) continue
    const remainingTicks = Math.max(0, until - tick)
    if (remainingTicks <= 0 && !isActive) continue
    const totalTicks = powerupEffectDuration(id, fallbackDuration)
    active.push({
      id,
      label,
      remainingTicks,
      totalTicks,
      progress: Math.max(0, Math.min(1, remainingTicks / totalTicks)),
      remainingSec: (remainingTicks * tickMs) / 1000,
    })
  }
  return active
}

export function canUseStoredPowerup(
  type: string | null | undefined,
  hp: number,
  maxHp: number,
): boolean {
  if (!type) return false
  if (type === 'heal') return hp < maxHp
  return true
}
