import type { GameRules } from '../codenames/rules'

export const pinballRules: GameRules = {
  title: 'Pinball',
  subtitle: 'Classic arcade pinball — hit bumpers, score points, beat your high score',
  quickStart: [
    'Press SPACE or tap the screen to launch the ball.',
    'Use A/← for the left flipper and D/→ for the right flipper.',
    'Keep the ball in play by timing your flipper hits.',
    'Hit bumpers and targets to score points and build combos.',
  ],
  sections: [
    {
      heading: 'Flippers',
      body: 'The two flippers at the bottom of the table are your main control. Press A or Left Arrow (or tap the left button) to activate the left flipper, and D or Right Arrow (or tap the right button) for the right flipper. Time your hits to send the ball where you want it.',
    },
    {
      heading: 'Bumpers',
      body: 'Round bumpers bounce the ball away with force. Each hit scores 75-150 points depending on the bumper. Try to hit multiple bumpers in quick succession for combo multipliers.',
    },
    {
      heading: 'Targets',
      body: 'Rectangular targets award bonus points (250-1000) when hit. Each target can only be scored once per ball. Hit all targets for maximum points.',
    },
    {
      heading: 'Combos',
      body: 'Hit objects in quick succession to build a combo multiplier (up to 5x). The combo resets after 2 seconds without a hit. Chain together bumper and target hits for massive scores.',
    },
    {
      heading: 'Balls & Game Over',
      body: 'You start with 3 balls. If the ball drains past the flippers, you lose a ball. The game ends when all balls are lost. Your high score is saved locally.',
    },
  ],
  tips: [
    'Watch the ball trajectory and anticipate where it will go.',
    'Use gentle flipper taps to control the ball speed and direction.',
    'Try to hit the high-value center target for 1000 points.',
    'Keep combos going by aiming for clusters of bumpers.',
    'Let the ball rest on a raised flipper to plan your next shot.',
  ],
}
