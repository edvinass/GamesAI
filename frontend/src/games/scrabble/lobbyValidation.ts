import type { Room } from '@/types'

export interface LobbyValidation {
  valid: boolean
  message: string
  issues: string[]
}

export function validateLobby(room: Room): LobbyValidation {
  const issues: string[] = []

  if (room.settings?.solo_practice) {
    const humans = room.players.filter((player) => !player.is_ai)
    if (humans.length !== 1) {
      issues.push('Solo play needs exactly one human')
    }
    return {
      valid: issues.length === 0,
      message: issues[0] ?? 'Ready to play the AI',
      issues,
    }
  }

  const count = room.players.length
  if (count < 2) {
    issues.push('Need 2 to 4 players')
  }
  if (count > 4) {
    issues.push('Scrabble allows at most 4 players')
  }

  return {
    valid: issues.length === 0,
    message: issues[0] ?? `${count} players ready to draw tiles`,
    issues,
  }
}
