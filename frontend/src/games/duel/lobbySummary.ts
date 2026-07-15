import type { Room } from '@/types'

const FORMAT_LABELS: Record<string, string> = {
  best_of_3: 'Best of 3',
  best_of_5: 'Best of 5',
  best_of_7: 'Best of 7',
  quick_duel: 'Quick duel',
}

export function formatDuelLobbySummary(room: Room): string[] {
  const s = room.settings ?? {}
  const lines: string[] = []

  if (s.solo_practice) {
    lines.push('Solo practice vs AI')
    const diff = String(s.ai_difficulty ?? 'medium')
    lines.push(`AI: ${diff.charAt(0).toUpperCase()}${diff.slice(1)}`)
  }

  const format = FORMAT_LABELS[String(s.match_format ?? 'best_of_5')] ?? String(s.match_format)
  lines.push(`Match: ${format}`)

  return lines
}
