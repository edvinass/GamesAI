import type { GameRules } from '../codenames/rules'

export const pinballRules: GameRules = {
  title: 'Pinball',
  subtitle: 'Classic arcade pinball — plunge, flip, and chase the high score',
  quickStart: [
    'Hold SPACE (or the Plunger button) to pull the plunger, release to launch. Tapping the table launches at a fixed strength.',
    'Left flipper: Z, A, ← or Left Shift. Right flipper: /, D, → or Right Shift. On touch, tap the left or right half of the table.',
    'Keep the ball alive. Hold a flipper up to cradle the ball and line up your shot.',
    'Light all three top lanes to raise the end-of-ball bonus multiplier.',
  ],
  sections: [
    {
      heading: 'Plunger & skill shot',
      body: 'While the ball waits in the shooter lane, one top lane lamp blinks. Use the flippers to move it, then plunge. If the ball\'s first switch is that lane, you get a 5,000-point skill shot. A soft plunge drops back into the lane so you can try again.',
    },
    {
      heading: 'Top lanes & bonus multiplier',
      body: 'Rolling through an unlit top lane lights it (500). Light all three to advance the bonus multiplier to 2X, 3X and 5X. After that, each completed set scores 25,000. Flipper buttons shift the lit lanes (lane change) so you can steer toward the unlit one.',
    },
    {
      heading: 'Targets',
      body: 'Knock down all four yellow drop targets on the left for 5,000. Hit all three blue standup targets on the right to light and collect an Extra Ball (once per game, then 10,000). The centre saucer captures the ball for 2,500 × your bonus multiplier and kicks it back out.',
    },
    {
      heading: 'Bumpers, slings & lanes',
      body: 'Pop bumpers (100) and slingshots (10) kick the ball hard. Inlanes feed the flippers (500). Outlanes pay 2,000 but usually drain the ball.',
    },
    {
      heading: 'Bonus & balls',
      body: 'Most switches add 1,000 to the bonus. When a ball drains, the bonus is paid out times the multiplier and then resets. A short ball save protects each new ball right after launch. You get 3 balls, and your best score is saved.',
    },
  ],
  tips: [
    'Cradle the ball on a raised flipper, then let it roll down to aim before flipping.',
    'Shots from the flipper tip travel wider; shots near the base go up the middle.',
    'Use lane change to line up the last unlit top lane before the ball gets there.',
    'Don\'t flail. Flipping both flippers at once often sends the ball straight down the middle.',
  ],
}
