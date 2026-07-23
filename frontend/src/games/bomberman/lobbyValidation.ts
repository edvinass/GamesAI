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
          ? 'Ready for solo team practice (you Red vs 2 Blue AI)'
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
  if (mode === 'team') {
    if (count < 2) {
      issues.push('Team battle needs at least 2 players')
    }
    const red = room.players.filter((p) => p.team === 'red').length
    const blue = room.players.filter((p) => p.team === 'blue').length
    const unassigned = count - red - blue
    // Unassigned seats are auto-balanced at start, but both colors must be coverable.
    if (red === 0 && blue === 0 && unassigned < 2) {
      issues.push('Need at least one player on Red and one on Blue')
    } else if (red === 0 && unassigned === 0) {
      issues.push('Need at least one player on Red')
    } else if (blue === 0 && unassigned === 0) {
      issues.push('Need at least one player on Blue')
    }
  }

  const modeLabel =
    mode === 'team' ? 'Team battle' : mode === 'kill_race' ? 'Kill race' : 'Classic'
  const teamHint =
    mode === 'team'
      ? ` · Red ${room.players.filter((p) => p.team === 'red').length} / Blue ${room.players.filter((p) => p.team === 'blue').length}`
      : ''
  return {
    valid: issues.length === 0,
    message: issues[0] ?? `${count} players ready — ${modeLabel}${teamHint}`,
    issues,
  }
}
