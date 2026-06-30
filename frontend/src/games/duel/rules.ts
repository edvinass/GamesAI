import type { GameRules } from '../codenames/rules'

export const duelRules: GameRules = {
  title: 'Side Duel',
  subtitle: 'Shoot from opposite sides — dodge bullets and land the hit',
  quickStart: [
    'Join a room with exactly 2 players (or practice solo vs AI).',
    'You spawn on the left or right edge of the arena.',
    'Move up and down to dodge incoming shots.',
    'Press Space to fire horizontally toward your opponent.',
    'One direct hit wins the duel.',
  ],
  sections: [
    {
      heading: 'Controls',
      body: 'Use W/S or arrow keys to move up and down. Hold a direction to keep moving. Press Space to shoot. You cannot fire again until your weapon cools down.',
    },
    {
      heading: 'Arena',
      body: 'Each player stays on their side of the board. Bullets travel straight across the field at your current row.',
    },
    {
      heading: 'Winning',
      body: 'The first player to hit their opponent wins. If both are eliminated on the same tick, the duel is a draw.',
    },
    {
      heading: 'Solo practice',
      body: 'The host can enable solo practice to add one AI opponent for target practice.',
    },
  ],
  tips: [
    'Strafe vertically while shooting to make yourself harder to hit.',
    'Watch for bullets on your row and dodge early.',
    'Time your shots when your opponent is moving into your line of fire.',
  ],
}
