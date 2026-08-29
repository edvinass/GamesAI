export type GameCategory = 'party' | 'classic' | 'arcade' | 'solo'

export interface GameMeta {
  name: string
  description: string
  emoji: string
  lobbyHint: string
  category: GameCategory
  players: string
  accent: string
}

export const GAME_CATEGORIES: { id: GameCategory | 'all'; label: string }[] = [
  { id: 'all', label: 'All' },
  { id: 'party', label: 'Party' },
  { id: 'classic', label: 'Classic' },
  { id: 'arcade', label: 'Arcade' },
  { id: 'solo', label: 'Solo' },
]

const metaByGameType: Record<string, GameMeta> = {
  codenames: {
    name: 'Codenames',
    description: 'Two teams race to find their words on a 5×5 board.',
    emoji: '🎯',
    lobbyHint: 'Assign one Spymaster and at least one Operative per team, then start.',
    category: 'party',
    players: '4–8',
    accent: '#5b9cff',
  },
  spyfall: {
    name: 'Spyfall',
    description: 'One spy hides among residents at a secret location.',
    emoji: '🕵️',
    lobbyHint: 'Need 3–8 players. Share the link or add AI to fill seats.',
    category: 'party',
    players: '3–8',
    accent: '#a78bfa',
  },
  snake: {
    name: 'Multiplayer Snake',
    description: 'Race to 50 on a shared grid — food types, ammo, and shooting.',
    emoji: '🐍',
    lobbyHint: 'Need 2–8 players. Share the link or add AI to fill seats.',
    category: 'arcade',
    players: '2–8',
    accent: '#3dd68c',
  },
  duel: {
    name: 'Side Duel',
    description: 'Best-of rounds with HP, cover, power-ups, charge shots, and mutators.',
    emoji: '⚔️',
    lobbyHint: 'Need exactly 2 players. Pick a format and mutator, then start.',
    category: 'arcade',
    players: '2',
    accent: '#ff6b9d',
  },
  tetris: {
    name: 'Multiplier Tetris',
    description: 'Each player stacks alone — speed rises, last board standing wins.',
    emoji: '🧱',
    lobbyHint: 'Need 2–4 players. Share the link or add AI to fill seats.',
    category: 'arcade',
    players: '2–4',
    accent: '#f0a060',
  },
  bomberman: {
    name: 'Bomberman',
    description: 'Plant bombs, break soft walls, grab power-ups — last bomber standing wins.',
    emoji: '💣',
    lobbyHint: 'Classic, teams, kill race, or stock lives — pick a preset in the lobby.',
    category: 'arcade',
    players: '2–8',
    accent: '#f97316',
  },
  pacman: {
    name: 'Pac-Man',
    description: 'Race for pellets in a shared maze — dodge ghosts or eat your rivals.',
    emoji: '🟡',
    lobbyHint: 'Multiplayer, solo practice vs AI, or single player against the ghosts.',
    category: 'arcade',
    players: '1–4',
    accent: '#facc15',
  },
  gravity_master: {
    name: 'Gravity Master',
    description: 'Draw shapes that fall and become walls — guide the ball to the target.',
    emoji: '🪐',
    lobbyHint: 'Solo puzzle — just you. Start when ready.',
    category: 'solo',
    players: 'Solo',
    accent: '#7c6cf0',
  },
  poker: {
    name: 'Poker',
    description: "Texas Hold'em — bluff, bet, and beat your friends (or AI).",
    emoji: '🃏',
    lobbyHint: 'Need 2–6 players. Share the link or add AI to fill seats.',
    category: 'classic',
    players: '2–6',
    accent: '#d4b06a',
  },
  monopoly: {
    name: 'Monopoly',
    description: 'Buy properties, charge rent, auction and trade — last tycoon standing.',
    emoji: '🏠',
    lobbyHint: 'Need 2–6 players. Share the link or add AI to fill seats.',
    category: 'classic',
    players: '2–6',
    accent: '#1a3d2e',
  },
  chess: {
    name: 'Chess',
    description: 'Classic chess — play a friend or challenge the AI.',
    emoji: '♟️',
    lobbyHint: 'Need exactly 2 players. Share the link or add an AI opponent.',
    category: 'classic',
    players: '2',
    accent: '#eef2f9',
  },
  go: {
    name: 'Go',
    description: '9×9 Go — surround territory and beat the AI.',
    emoji: '⚫',
    lobbyHint: 'Need exactly 2 players. Share the link or add an AI opponent.',
    category: 'classic',
    players: '2',
    accent: '#8b9cb3',
  },
  roborally: {
    name: 'RoboRally',
    description: 'Program your robot through checkpoints on a factory floor.',
    emoji: '🤖',
    lobbyHint: 'Need 2–4 players. Pick a map, add AI to fill seats, then start.',
    category: 'party',
    players: '2–4',
    accent: '#5b9cff',
  },
  connect4: {
    name: 'Connect Four',
    description: 'Drop discs to connect four in a row — play a friend or AI.',
    emoji: '🔴',
    lobbyHint: 'Need exactly 2 players. Share the link or add an AI opponent.',
    category: 'classic',
    players: '2',
    accent: '#ff5c6c',
  },
  battleship: {
    name: 'Battleship',
    description: 'Place your fleet and sink the enemy — play a friend or AI.',
    emoji: '🚢',
    lobbyHint: 'Need exactly 2 players. Share the link or add an AI opponent.',
    category: 'classic',
    players: '2',
    accent: '#40c4e0',
  },
  solitaire: {
    name: 'Solitaire',
    description: 'Classic Klondike — stack cards and clear the tableau.',
    emoji: '🂡',
    lobbyHint: 'Solo card game — just you. Start when ready.',
    category: 'solo',
    players: 'Solo',
    accent: '#3dd68c',
  },
  pinball: {
    name: 'Pinball',
    description: 'Classic arcade pinball — hit bumpers, score points, beat your high score.',
    emoji: '🎱',
    lobbyHint: 'Solo arcade game — just you. Start when ready.',
    category: 'arcade',
    players: 'Solo',
    accent: '#5352ed',
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
      category: 'party',
      players: '—',
      accent: '#5b9cff',
    }
  )
}
