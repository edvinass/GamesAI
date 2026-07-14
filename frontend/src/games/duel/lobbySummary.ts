import type { Room } from '@/types'
import { ARENA_THEMES } from './themes'

const FORMAT_LABELS: Record<string, string> = {
  quick_duel: 'Quick duel',
  best_of_3: 'Best of 3',
  best_of_5: 'Best of 5',
  best_of_7: 'Best of 7',
}

const MUTATOR_LABELS: Record<string, string> = {
  classic: 'Classic',
  chaos: 'Chaos',
  sniper: 'Sniper',
  bounce_house: 'Bounce House',
  fog: 'Fog',
}

const DRILL_LABELS: Record<string, string> = {
  none: 'None',
  dodge_only: 'Dodge only',
  aim_trainer: 'Aim trainer',
  powerup_sandbox: 'Power-up sandbox',
}

export function formatDuelLobbySummary(room: Room): string[] {
  const s = room.settings ?? {}
  const lines: string[] = []

  if (s.solo_practice) {
    lines.push('Solo practice vs AI')
  }

  const format = FORMAT_LABELS[String(s.match_format ?? 'best_of_5')] ?? String(s.match_format)
  lines.push(`Format: ${format}`)

  let mutator = MUTATOR_LABELS[String(s.mutator ?? 'classic')] ?? String(s.mutator)
  const secondary = String(s.mutator_secondary ?? 'none')
  if (secondary !== 'none') {
    const secLabel = MUTATOR_LABELS[secondary] ?? secondary
    mutator = `${mutator} + ${secLabel}`
  }
  lines.push(`Rules: ${mutator}`)

  const themeId = String(s.arena_theme ?? 'classic')
  const theme = ARENA_THEMES[themeId as keyof typeof ARENA_THEMES]
  lines.push(`Theme: ${theme?.label ?? themeId}`)

  const drill = String(s.training_drill ?? 'none')
  if (drill !== 'none') {
    lines.push(`Drill: ${DRILL_LABELS[drill] ?? drill}`)
  }

  if (s.match_format === 'quick_duel' && s.quick_duel_loadout && s.quick_duel_loadout !== 'none') {
    lines.push(`Loadout: ${String(s.quick_duel_loadout).replace(/_/g, ' ')}`)
  }

  if (s.tutorial_mode) {
    lines.push('Opening tips enabled')
  }

  const speed = Number(s.tick_ms ?? 75)
  lines.push(`Speed: ${speed}ms tick`)

  return lines
}
