import type { Player, Room } from '@/types'

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
      message: issues[0] ?? 'Ready for solo practice',
      issues,
    }
  }

  for (const [team, label] of [
    ['red', 'Red'],
    ['blue', 'Blue'],
  ] as const) {
    const teamPlayers = room.players.filter((p) => p.team === team)
    const spymasters = teamPlayers.filter((p) => p.role === 'spymaster')
    const operatives = teamPlayers.filter((p) => p.role === 'operative')

    if (spymasters.length !== 1) {
      issues.push(`${label} team needs exactly one spymaster`)
    }
    if (operatives.length < 1) {
      issues.push(`${label} team needs at least one operative`)
    }
  }

  return {
    valid: issues.length === 0,
    message: issues[0] ?? 'Teams are ready — start when everyone is set',
    issues,
  }
}

export function teamSpymaster(players: Player[], team: 'red' | 'blue') {
  return players.find((p) => p.team === team && p.role === 'spymaster')
}

export function teamOperatives(players: Player[], team: 'red' | 'blue') {
  return players.filter((p) => p.team === team && p.role === 'operative')
}
