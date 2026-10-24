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
      issues.push('Solo practice needs exactly one human player')
    }
    return {
      valid: issues.length === 0,
      message: issues[0] ?? 'Ready to draw against 3 AI players',
      issues,
    }
  }

  const count = room.players.length
  if (count < 2) issues.push('Need at least 2 players')
  if (count > 8) issues.push('Scribble allows up to 8 players')

  return {
    valid: issues.length === 0,
    message: issues[0] ?? `${count} players ready to scribble`,
    issues,
  }
}
