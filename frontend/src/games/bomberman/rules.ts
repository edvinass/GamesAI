import type { GameRules } from '../codenames/rules'

export const bombermanRules: GameRules = {
  title: 'Bomberman',
  subtitle: 'Last bomber standing',
  quickStart: [
    'Join a room with 2–8 players (or add AI bots).',
    'Use arrow keys or WASD to move. Release to stop.',
    'Press Space to plant a bomb under your feet.',
    'Blast soft walls for power-ups — bombs, range, and speed.',
    'Don’t get caught in the explosion. Last player alive wins.',
  ],
  sections: [
    {
      heading: 'Controls',
      body: 'Hold arrow keys or WASD to walk. Release the key to stop. Press Space to place a bomb (limited by your bomb count). You can walk off a bomb you just placed, but you cannot walk back onto it.',
    },
    {
      heading: 'Arena',
      body: 'The grid has indestructible hard walls and breakable soft walls. Explosions travel in four directions and stop at hard walls. Soft walls are destroyed and may drop power-ups.',
    },
    {
      heading: 'Power-ups',
      body: 'Bomb (+): carry more bombs at once. Range (+): longer explosions. Speed (+): move faster. Power-ups in a blast are destroyed.',
    },
    {
      heading: 'Winning',
      body: 'Eliminate every other bomber. The last player standing wins. If everyone dies in the same blast, the player with the most kills wins.',
    },
    {
      heading: 'AI & solo practice',
      body: 'The host can add AI players in the lobby, or enable solo practice for a 3-player game (you + 2 AI).',
    },
  ],
  tips: [
    'Always plan an escape route before you plant.',
    'Chain bombs to clear large areas of soft walls.',
    'Corner rivals with soft walls still up — traps cut off exits.',
    'Speed power-ups help you outrun your own fuses.',
  ],
}
