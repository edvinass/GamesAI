import type { GameRules } from '../codenames/rules'

export const pacmanRules: GameRules = {
  title: 'Pac-Man',
  subtitle: 'Race for pellets in a shared maze',
  quickStart: [
    'Join with 2–4 players (or enable solo practice vs AI).',
    'Use arrow keys or WASD to steer your Pac-Man.',
    'Eat pellets for points. Power pellets let you eat ghosts — and rivals.',
    'Last Pac-Man with lives wins. Clear the maze and highest score wins.',
  ],
  sections: [
    {
      heading: 'Controls',
      body: 'Hold arrow keys or WASD to set your next turn. Turns buffer at corridors — you keep sliding until the turn opens.',
    },
    {
      heading: 'Maze',
      body: 'Pellets are shared: first player to a cell claims it. Side tunnels wrap you to the opposite side. Four AI ghosts patrol with scatter and chase modes.',
    },
    {
      heading: 'Power pellets',
      body: 'Eating a power pellet frightens the ghosts. Chomp them for bonus points (combo multiplies). While powered, you can also eat a non-powered rival Pac-Man to steal a life.',
    },
    {
      heading: 'Winning',
      body: 'Eliminate every other Pac-Man (last standing). If the maze is cleared while multiple players still have lives, the highest score among the living wins.',
    },
    {
      heading: 'AI & solo practice',
      body: 'The host can add AI Pac-Men in the lobby, or enable solo practice for a 3-player game (you + 2 AI).',
    },
  ],
  tips: [
    'Grab power pellets when ghosts close in — then turn the hunt around.',
    'Tunnel wraps are great escape routes.',
    'Don’t leave corner pellets for later if a rival is nearby.',
    'When powered, hunting another Pac-Man can swing the match.',
  ],
}
