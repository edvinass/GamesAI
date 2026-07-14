import { POWERUP_COLORS, POWERUP_ICONS, POWERUP_LABELS } from './duelRenderer'
import {
  POWERUP_HINTS,
  POWERUP_TIER_LABELS,
  powerupTier,
  type PowerupTier,
} from './powerupMeta'

export const MUTATOR_LABELS: Record<string, string> = {
  classic: 'Classic',
  chaos: 'Chaos',
  sniper: 'Sniper',
  bounce_house: 'Bounce House',
  fog: 'Fog',
}

export const DRILL_LABELS: Record<string, string> = {
  none: '',
  dodge_only: 'Dodge drill',
  aim_trainer: 'Aim trainer',
  powerup_sandbox: 'Power-up sandbox',
}

export const DRILL_HINTS: Record<string, string> = {
  dodge_only: 'Movement only — practice dodging',
  aim_trainer: 'Movement locked — focus on aim',
  powerup_sandbox: 'Power-ups spawn faster for practice',
}

export const PERSONALITY_LABELS: Record<string, string> = {
  balanced: 'Balanced AI',
  aggressive: 'Aggressive AI',
  turtle: 'Turtle AI',
  trickster: 'Trickster AI',
}

export function mutatorStackLabel(primary: string, secondary?: string | null): string {
  const base = MUTATOR_LABELS[primary] ?? primary
  if (!secondary || secondary === 'none' || secondary === primary) return base
  const extra = MUTATOR_LABELS[secondary] ?? secondary
  return `${base} + ${extra}`
}

export const DRAFT_TIER_ACCENTS: Record<PowerupTier, string> = {
  common: 'rgba(148, 163, 184, 0.35)',
  rare: 'rgba(192, 132, 252, 0.45)',
  epic: 'rgba(252, 211, 77, 0.55)',
}

export interface DraftPowerupOption {
  id: string
  label: string
  icon: string
  color: string
  hint: string
  tier: PowerupTier
  banned: boolean
}

export interface DraftTierGroup {
  tier: PowerupTier
  label: string
  options: DraftPowerupOption[]
}

export function buildDraftTierGroups(bannedTypes: Iterable<string>): DraftTierGroup[] {
  const banned = new Set(bannedTypes)
  const tiers: PowerupTier[] = ['common', 'rare', 'epic']
  return tiers
    .map((tier) => ({
      tier,
      label: POWERUP_TIER_LABELS[tier],
      options: Object.keys(POWERUP_LABELS)
        .filter((id) => powerupTier(id) === tier)
        .map((id) => ({
          id,
          label: POWERUP_LABELS[id],
          icon: POWERUP_ICONS[id],
          color: POWERUP_COLORS[id],
          hint: POWERUP_HINTS[id] ?? '',
          tier,
          banned: banned.has(id),
        })),
    }))
    .filter((group) => group.options.length > 0)
}
