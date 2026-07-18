import type { GameRules } from '../codenames/rules'

export const connect4Rules: GameRules = {
  title: 'Connect Four',
  subtitle: 'Drop discs to connect four in a row',
  quickStart: [
    'Join with exactly 2 players, or enable solo practice to play against AI.',
    'Red plays first. Click a column to drop your disc.',
    'Connect four of your discs in a row — horizontally, vertically, or diagonally — to win.',
    'If the board fills up with no winner, the game is a draw.',
  ],
  sections: [
    {
      heading: 'How to play',
      body: 'On your turn, click any column with available space to drop your disc. The disc falls to the lowest empty cell in that column. Players alternate turns until someone wins or the board fills up.',
    },
    {
      heading: 'Winning',
      body: 'Connect four of your colored discs in a row to win. Lines can be horizontal (across), vertical (up/down), or diagonal. The winning line is highlighted when the game ends.',
    },
    {
      heading: 'Strategy tips',
      body: 'Control the center columns — they give you more opportunities to connect four. Watch for threats and block your opponent when they have three in a row. Setting up multiple winning opportunities ("forks") can guarantee a win.',
    },
    {
      heading: 'AI opponent',
      body: 'Enable solo practice to play against an AI. Choose Easy, Medium, or Hard difficulty in the lobby. The AI uses minimax with alpha-beta pruning for optimal play on higher difficulties.',
    },
  ],
  tips: [
    'The center column is the most powerful — it connects to the most potential lines.',
    'Try to create a "seven" trap: two threats that share a single piece.',
    'Block your opponent when they have three in a row with an open end.',
    'Plan ahead — sometimes the best move is not the most obvious one.',
  ],
}
