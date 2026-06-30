import type { GameRules } from '../codenames/rules'

export const snakeRules: GameRules = {
  title: 'Multiplayer Snake',
  subtitle: 'Battle on a shared grid — last snake standing',
  quickStart: [
    'Join a room with 2–8 players (or add AI bots).',
    'Use arrow keys or WASD to steer your snake.',
    'Eat food to grow and score points.',
    'Avoid walls, your own body, and other snakes.',
    'Last snake alive wins; ties go to highest score.',
  ],
  sections: [
    {
      heading: 'Controls',
      body: 'Your snake moves continuously once the countdown ends. Press arrow keys or WASD to change direction. You cannot reverse 180° instantly.',
    },
    {
      heading: 'Battle arena',
      body: 'All snakes share one grid. Colliding with a wall, yourself, or another snake\'s body eliminates you.',
    },
    {
      heading: 'Food',
      body: 'One food pellet appears at a time on a random empty cell. Eating it grows your snake by one segment and adds to your score.',
    },
    {
      heading: 'Winning',
      body: 'The last snake alive wins. If multiple snakes die on the same tick, the highest score wins.',
    },
    {
      heading: 'AI & solo practice',
      body: 'The host can add AI players in the lobby, or enable solo practice for a 3-player game (you + 2 AI).',
    },
  ],
  tips: [
    'Plan ahead — your snake keeps moving every tick.',
    'Cut off opponents by blocking their path.',
    'Growing longer makes tight turns riskier.',
  ],
}
