export const POWERUP_ACTIVATION_TICKS = 8

export const INSTANT_POWERUP_TYPES = new Set([
  'heal',
  'laser',
  'railgun',
  'bomb',
  'cluster',
  'burst',
  'decoy',
])

/** Hold duration before channeled power-ups activate — keep in sync with backend POWERUP_CHANNEL_TICKS */
export const POWERUP_CHANNEL_TICKS: Record<string, number> = {
  rapid_fire: 6,
  machine_gun: 6,
  shield: 8,
  wide_shot: 6,
  homing: 7,
  pierce: 7,
  ghost: 7,
  freeze: 8,
  mirror: 8,
  overdrive: 7,
  phase_shift: 7,
}

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
  phase_shift: 'epic',
  decoy: 'rare',
}

export const POWERUP_TIER_LABELS: Record<PowerupTier, string> = {
  common: 'Common',
  rare: 'Rare',
  epic: 'Epic',
}

/** Active buff/debuff length in ticks — keep in sync with backend POWERUP_EFFECT_DURATIONS */
export const POWERUP_EFFECT_DURATIONS: Record<string, number> = {
  rapid_fire: 140,
  machine_gun: 180,
  shield: 200,
  wide_shot: 150,
  pierce: 140,
  ghost: 170,
  freeze: 110,
  homing: 160,
  mirror: 150,
  overdrive: 130,
  phase_shift: 120,
  decoy: 140,
}

export const BOMB_CHARGES = 3

export const POWERUP_HINTS: Record<string, string> = {
  rapid_fire: 'Halves reload — ~10s of faster shots',
  machine_gun: 'Fast single-row spray — ~14s',
  shield: 'Blocks all damage — ~16s',
  wide_shot: 'Three-row spread on every shot — ~12s',
  pierce: 'Shots pass through cover and fighters — ~10s',
  ghost: 'Enemies see a faint silhouette — homing shots drift off target',
  freeze: 'Stops opponent movement — ~8s',
  laser: 'Instant beam down your aim row (stops at cover)',
  railgun: 'Piercing beam through cover — heavy damage',
  homing: 'Bullets steer toward your opponent with lock-on guidance — ~12s',
  heal: 'Restore 1 HP instantly',
  mirror: 'Reflects the next incoming bullets — ~12s',
  overdrive: 'Wide heavy shots (2 dmg) — ~10s',
  bomb: `Fire up to ${BOMB_CHARGES} bombs — wide blast on wall impact`,
  cluster: 'Fires three bombs in a vertical spread',
  burst: 'Unloads a six-shot rapid salvo',
  phase_shift: 'Pass through cover (not bullets) — ~10s',
  decoy: 'Spawns a fake silhouette to bait shots — ~10s',
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
  ['phase_shift_until', 'phase_shift_active', 'phase_shift', 'Phase Shift'],
  ['freeze_until', 'freeze_active', 'freeze', 'Frozen'],
  ['freeze_cast_until', 'freeze_cast_active', 'freeze', 'Freeze cast'],
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
