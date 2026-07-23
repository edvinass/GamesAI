import type { GameRules } from '../codenames/rules'

export const bombermanRules: GameRules = {
  title: 'Bomberman',
  subtitle: 'Last bomber standing',
  quickStart: [
    'Join a room with 2–8 players (or add AI bots).',
    'Use arrow keys or WASD to move. Release to stop.',
    'Press Space to plant a bomb under your feet.',
    'Blast soft walls for power-ups — bombs, range, speed, throw, kick… and skulls.',
    'Don’t get caught in the explosion. Last player alive wins.',
  ],
  sections: [
    {
      heading: 'Controls',
      body: 'Hold arrow keys or WASD to walk. Release the key to stop. Press Space to place a bomb (limited by your bomb count). You can walk off a bomb you just placed, but you cannot walk back onto it. With Throw (Power Glove): stand on a bomb or face an adjacent one and press Space to pick it up, then press Space again to throw it. With Kick, walk into a bomb to send it sliding along the floor.',
    },
    {
      heading: 'Arena',
      body: 'Each lobby picks an arena layout (Classic, Fortress, Islands, The Narrows, and more). Hard walls are permanent; soft walls break and may drop power-ups. Explosions travel in four directions and stop at hard walls.',
    },
    {
      heading: 'Power-ups',
      body: 'Bomb (💣): carry more bombs at once. Range (🔥): longer explosions. Speed (⚡): move faster. Throw (🧤): Space on/facing a bomb to pick it up, then Space to throw — it flies 3 tiles and lands there, or on the next empty tile past an obstacle/bomb. Kick (🦵): walk into a bomb to kick it along the ground until it hits a wall, soft block, or another bomb. Power-ups in a blast are destroyed.',
    },
    {
      heading: 'Skull diseases',
      body: 'Skull (💀) curses you with a random temporary disease. You blink while cursed, but the exact disease is not named — discover it from how you move and bomb. Touch another player to pass the curse (and cure yourself). Diseases: crawl slowly, cannot plant bombs, auto-plant bombs every step, reversed controls, bombs with a short fuse, or perpetual motion (cannot stop).',
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
    'If you pick up a skull, tag someone else to pass the curse.',
  ],
}
