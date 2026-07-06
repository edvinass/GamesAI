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
  snake: {
    name: 'Multiplayer Snake',
    description: 'Battle on a shared grid — last snake standing.',
    emoji: '🐍',
    lobbyHint: 'Need 2–8 players. Share the link or add AI to fill seats.',
  },
  duel: {
    name: 'Side Duel',
    description: 'Shoot from opposite sides — dodge bullets and land the hit.',
    emoji: '⚔️',
    lobbyHint: 'Need exactly 2 players. Share the link or add an AI opponent.',
  },
  tetris: {
    name: 'Multiplier Tetris',
    description: 'Each player stacks alone — speed rises, last board standing wins.',
    emoji: '🧱',
    lobbyHint: 'Need 2–4 players. Share the link or add AI to fill seats.',
  },
  gravity_master: {
    name: 'Gravity Master',
    description: 'Draw shapes that fall and become walls — guide the ball to the target.',
    emoji: '🪐',
    lobbyHint: 'Solo puzzle — just you. Start when ready.',
  },
  poker: {
    name: 'Poker',
    description: "Texas Hold'em — bluff, bet, and beat your friends (or AI).",
    emoji: '🃏',
    lobbyHint: 'Need 2–6 players. Share the link or add AI to fill seats.',
  },
}

export interface GameListItem {
  id: string
  name: string
  description: string
}

export function listKnownGames(): GameListItem[] {
  return Object.entries(metaByGameType).map(([id, meta]) => ({
    id,
    name: meta.name,
    description: meta.description,
  }))
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
