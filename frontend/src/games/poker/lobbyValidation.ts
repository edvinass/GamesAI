import type { Room } from '@/types'

export function validateLobby(room: Room): { valid: boolean; message: string; issues: string[] } {
  const settings = room.settings ?? {}
  const count = room.players.length
  const solo = Boolean(settings.solo_practice)

  if (solo) {
    const humans = room.players.filter((p) => !p.is_ai)
    if (humans.length !== 1) {
      return {
        valid: false,
        message: 'Solo practice needs exactly one human player',
        issues: ['Remove extra human players or disable solo practice'],
      }
    }
    return { valid: true, message: 'Ready for solo practice', issues: [] }
  }

  const min = Number(settings.min_players ?? 2)
  const max = Number(settings.max_players ?? 6)
  const issues: string[] = []

  if (count < min) issues.push(`Need at least ${min} players (currently ${count})`)
  if (count > max) issues.push(`Maximum ${max} players (currently ${count})`)

  if (issues.length) {
    return { valid: false, message: issues[0], issues }
  }
  return { valid: true, message: `Ready — ${count} players at the table`, issues: [] }
}
