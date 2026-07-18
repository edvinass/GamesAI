import type { Room } from '@/types'

export interface LobbyValidation {
  valid: boolean
  message: string
  issues: string[]
}

export function validateLobby(room: Room): LobbyValidation {
  const issues: string[] = []

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
  if (count < 2) {
    issues.push('Need exactly 2 players')
  }
  if (count > 2) {
    issues.push('Battleship supports only 2 players')
  }

  return {
    valid: issues.length === 0,
    message: issues[0] ?? '2 captains ready — place your fleets!',
    issues,
  }
}
