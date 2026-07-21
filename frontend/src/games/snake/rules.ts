import type { GameRules } from '../codenames/rules'

export const snakeRules: GameRules = {
  title: 'Multiplayer Snake',
  subtitle: 'Battle on a shared grid — last snake standing',
  quickStart: [
    'Join a room with 2–8 players (or add AI bots).',
    'Use arrow keys or WASD to steer your snake.',
    'Eat apples, gold, poison, ghost, or ammo pellets.',
    'Press Space to shoot when you have ammo — hits drain rival score.',
    'Pass through walls — you wrap to the opposite side.',
    'Last snake alive wins; ties go to highest score.',
  ],
  sections: [
    {
      heading: 'Controls',
      body: 'Your snake moves continuously once the countdown ends. Press arrow keys or WASD to change direction. You cannot reverse 180° in one tick, but you can queue turns while moving in a straight line. Press Space to fire a shot when you have ammo.',
    },
    {
      heading: 'Battle arena',
      body: 'All snakes share one grid. Leaving one edge wraps you to the opposite side. Hitting yourself or another snake\'s body eliminates you.',
    },
    {
      heading: 'Food types',
      body: 'Three pellets are on the board at once. Red apple: +1 score and grow by 1. Golden: +3 score and grow by 2. Poison (lime): shrinks you by 2 (never below length 3) and gives no score. Ghost (cyan): +1 score, grow by 1, and briefly phase through your own body. Ammo (orange): +1 score and +2 shots.',
    },
    {
      heading: 'Shooting',
      body: 'Shots travel in the direction you are facing. Hitting another snake removes 1 score. If their score goes negative, they die. Landing a kill awards bonus score.',
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
    'Use wrap-around walls to escape tight spots.',
    'Queue your next turn early — e.g. right then up then left for a quick corner.',
    'Golden pellets are worth the detour; poison is bait near rivals.',
    'Save ammo for high-score rivals — a few hits can push them negative and finish them.',
    'Ghost timing lets you cut through your own coil to escape or ambush.',
  ],
}
