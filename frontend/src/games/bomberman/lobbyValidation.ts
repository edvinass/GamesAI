import type { Room } from '@/types'

export interface LobbyValidation {
  valid: boolean
  message: string
  issues: string[]
}

export function validateLobby(room: Room): LobbyValidation {
  const issues: string[] = []
  const minPlayers = Number(room.settings?.min_players ?? 2)
  const maxPlayers = Number(room.settings?.max_players ?? 8)
  const mode = String(room.settings?.game_mode ?? 'classic')

  if (room.settings?.solo_practice) {
    const humans = room.players.filter((p) => !p.is_ai)
    if (humans.length !== 1) {
      issues.push('Solo practice requires exactly one human player')
    }
    const modeHint =
      mode === 'kill_race'
        ? 'Ready for solo kill race against 2 AI'
        : mode === 'team'
          ? 'Ready for solo team practice (you + 2 AI)'
          : 'Ready for solo practice against 2 AI'
    return {
      valid: issues.length === 0,
      message: issues[0] ?? modeHint,
      issues,
    }
  }

  const count = room.players.length
  if (count < minPlayers) {
    issues.push(`Need at least ${minPlayers} players`)
  }
  if (count > maxPlayers) {
    issues.push(`Maximum ${maxPlayers} players allowed`)
  }
  if (mode === 'team' && count < 2) {
    issues.push('Team battle needs at least 2 players')
  }

  const modeLabel =
    mode === 'team' ? 'Team battle' : mode === 'kill_race' ? 'Kill race' : 'Classic'
  return {
    valid: issues.length === 0,
    message: issues[0] ?? `${count} players ready — ${modeLabel}`,
    issues,
  }
}
