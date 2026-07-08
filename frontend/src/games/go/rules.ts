import type { GameRules } from '../codenames/rules'

export const goRules: GameRules = {
  title: 'Go',
  subtitle: '9×9 — surround territory and outscore your opponent',
  quickStart: [
    'Join with 2 players, or enable solo practice to play against AI.',
    'Black plays first. Click an empty intersection to place a stone.',
    'Surround enemy stones to capture them. Avoid self-capture.',
    'Pass twice in a row to end the game and count territory.',
  ],
  sections: [
    {
      heading: 'Placing stones',
      body: 'Stones go on intersections, not squares. Once placed, a stone does not move. A group with no liberties (empty adjacent points) is captured and removed.',
    },
    {
      heading: 'Ko rule',
      body: 'You cannot immediately recapture a single stone in a way that repeats the previous board position.',
    },
    {
      heading: 'Scoring',
      body: 'When both players pass, the game is scored using area rules: stones on the board plus surrounded empty territory. White receives 5.5 komi (compensation for moving second).',
    },
    {
      heading: 'AI opponent',
      body: 'Solo practice puts you as Black. Choose Easy (heuristic), Medium (light MCTS), or Hard (deeper MCTS) in the lobby.',
    },
  ],
  tips: [
    'Corners are easiest to defend; the center is most influential.',
    'Connect your stones into strong groups.',
    'Pass only when you believe there are no profitable moves left.',
  ],
}
