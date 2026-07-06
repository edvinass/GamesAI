import type { GameRules } from '../codenames/rules'

export const gravityMasterRules: GameRules = {
  title: 'Gravity Master',
  subtitle: 'Draw shapes that fall and become physical walls — guide the ball to the target',
  quickStart: [
    'Create a room and start alone — no other players needed.',
    'Draw lines on the canvas — each shape drops under gravity as soon as you release.',
    'Draw as many shapes as you need to build ramps and walls.',
    'Press Drop ball when ready to release the ball.',
    'Guide the ball into the target to clear the level.',
  ],
  sections: [
    {
      heading: 'Drawing',
      body: 'Click and drag to draw. There is no ink limit — draw as many shapes as you want. Each stroke becomes a physical object that falls immediately. Undo removes your last shape. Clear removes all drawn shapes.',
    },
    {
      heading: 'Drop ball',
      body: 'The ball stays in place until you press Drop ball. Once released, it rolls and bounces on your drawn shapes and the grey level platforms. You can keep drawing while the ball is moving.',
    },
    {
      heading: 'Winning',
      body: 'Touch the target with the ball to advance. If the ball falls off or gets stuck, use Retry to start the level over.',
    },
    {
      heading: 'Levels',
      body: 'Fifty puzzles with increasing difficulty — gaps to bridge, obstacles to navigate, and trickier layouts on later stages.',
    },
  ],
  tips: [
    'Let shapes settle before dropping the ball so your ramp is stable.',
    'Draw wide platforms so the ball does not roll off the edge.',
    'You can add new shapes mid-roll to redirect the ball.',
  ],
}
