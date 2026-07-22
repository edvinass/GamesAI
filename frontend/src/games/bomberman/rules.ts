import type { GameRules } from '../codenames/rules'

export const bombermanRules: GameRules = {
  title: 'Bomberman',
  subtitle: 'Last bomber standing',
  quickStart: [
    'Join a room with 2–8 players (or add AI bots).',
    'Use arrow keys or WASD to move. Release to stop.',
    'Press Space to plant a bomb under your feet.',
    'Blast soft walls for power-ups — bombs, range, speed, throw, and kick.',
    'Don’t get caught in the explosion. Last player alive wins.',
  ],
  sections: [
    {
      heading: 'Controls',
      body: 'Hold arrow keys or WASD to walk. Release the key to stop. Press Space to place a bomb (limited by your bomb count). You can walk off a bomb you just placed, but you cannot walk back onto it. With Throw, walk onto any bomb and press Space to throw it. With Kick, walk into a bomb to send it sliding along the floor.',
    },
    {
      heading: 'Arena',
      body: 'Each lobby picks an arena layout (Classic, Fortress, Islands, The Narrows, and more). Hard walls are permanent; soft walls break and may drop power-ups. Explosions travel in four directions and stop at hard walls.',
    },
    {
      heading: 'Power-ups',
      body: 'Bomb (💣): carry more bombs at once. Range (🔥): longer explosions. Speed (⚡): move faster. Throw (🧤): walk onto a bomb and press Space — it flies over walls and soft blocks. Kick (🦵): walk into a bomb to kick it along the ground until it hits a wall, soft block, or another bomb. Power-ups in a blast are destroyed.',
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
    'Throw a bomb over walls into a corridor to surprise rivals.',
    'Kick bombs down long lanes to catch players at a distance.',
  ],
}
