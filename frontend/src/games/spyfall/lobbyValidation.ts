import type { Room } from '@/types'

export interface LobbyValidation {
  valid: boolean
  message: string
  issues: string[]
}

export function validateLobby(room: Room): LobbyValidation {
  const issues: string[] = []
  const minPlayers = Number(room.settings?.min_players ?? 3)
  const maxPlayers = Number(room.settings?.max_players ?? 8)
  const sameRoom = Boolean(room.settings?.same_room)

  if (room.settings?.solo_practice) {
    const humans = room.players.filter((p) => !p.is_ai)
    if (humans.length !== 1) {
      issues.push('Solo practice requires exactly one human player')
    }
    return {
      valid: issues.length === 0,
      message: issues[0] ?? 'Ready for solo practice against 2 AI',
      issues,
    }
  }

  const count = room.players.length
  if (sameRoom && room.players.some((p) => p.is_ai)) {
    issues.push('Same-room mode does not allow AI players — remove them first')
  }
  if (count < minPlayers) {
    issues.push(`Need at least ${minPlayers} players`)
  }
  if (count > maxPlayers) {
    issues.push(`Maximum ${maxPlayers} players allowed`)
  }

  const readyMessage = sameRoom
    ? `${count} players ready — same-room voice play`
    : `${count} players ready — start when everyone has joined`

  return {
    valid: issues.length === 0,
    message: issues[0] ?? readyMessage,
    issues,
  }
}
