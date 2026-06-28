export interface GameMeta {
  name: string
  description: string
  emoji: string
  lobbyHint: string
}

const metaByGameType: Record<string, GameMeta> = {
  codenames: {
    name: 'Codenames',
    description: 'Two teams race to find their words on a 5×5 board.',
    emoji: '🎯',
    lobbyHint: 'Assign one Spymaster and at least one Operative per team, then start.',
  },
  spyfall: {
    name: 'Spyfall',
    description: 'One spy hides among residents at a secret location.',
    emoji: '🕵️',
    lobbyHint: 'Need 3–8 players. Share the link or add AI to fill seats.',
  },
}

export function getGameMeta(gameType: string): GameMeta {
  return (
    metaByGameType[gameType] ?? {
      name: gameType,
      description: '',
      emoji: '🎮',
      lobbyHint: 'Invite friends and start when everyone is ready.',
    }
  )
}
