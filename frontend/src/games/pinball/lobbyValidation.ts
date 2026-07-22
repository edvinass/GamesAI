import type { Room } from '@/types'

export interface LobbyValidation {
  valid: boolean
  message: string
  issues: string[]
}

export function validateLobby(room: Room): LobbyValidation {
  const issues: string[] = []
  const humans = room.players.filter((p) => !p.is_ai)

  if (humans.length !== 1) {
    issues.push('Pinball requires exactly one player')
  }
  if (room.players.some((p) => p.is_ai)) {
    issues.push('Remove AI players — this is a solo arcade game')
  }

  return {
    valid: issues.length === 0,
    message: issues[0] ?? 'Ready to play Pinball!',
    issues,
  }
}
