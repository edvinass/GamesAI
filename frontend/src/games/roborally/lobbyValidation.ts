import type { Room } from '@/types'

export interface LobbyValidation {
  valid: boolean
  message: string
  issues: string[]
}

export function validateLobby(room: Room): LobbyValidation {
  const issues: string[] = []
  const minPlayers = Number(room.settings?.min_players ?? 2)
  const maxPlayers = Number(room.settings?.max_players ?? 4)

  if (room.settings?.solo_practice) {
    const humans = room.players.filter((p) => !p.is_ai)
    if (humans.length !== 1) {
      issues.push('Solo practice requires exactly one human player')
    }
    return {
      valid: issues.length === 0,
      message: issues[0] ?? 'Ready for solo practice against AI',
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

  return {
    valid: issues.length === 0,
    message: issues[0] ?? `${count} racers ready — program your robots!`,
    issues,
  }
}
