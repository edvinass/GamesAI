import type { GameRules } from '../codenames/rules'

export const roborallyRules: GameRules = {
  title: 'RoboRally',
  subtitle: 'Race your robot through factory checkpoints',
  quickStart: [
    'Each round, pick program cards from your hand and fill every register slot.',
    'Lock your program when ready — execution starts once everyone locks.',
    'Robots run cards in priority order (closest to the antenna first).',
    'Visit checkpoints 1 → 2 → 3 in order. First robot to finish all checkpoints wins!',
  ],
  sections: [
    {
      heading: 'Programming phase',
      body: 'Drag or click cards from your hand into the register slots at the bottom. You must fill all slots before locking.',
      bullets: [
        'Move cards advance your robot forward (blocked by walls and other robots).',
        'Turn Left / Turn Right rotate your robot in place.',
        'Backup moves one square backward.',
        'Your hand is hidden from other players until the round executes.',
      ],
    },
    {
      heading: 'Execution',
      body: 'When all players lock, robots execute one register slot at a time. Within each slot, robots act in priority order.',
      bullets: [
        'Priority is based on distance to the antenna (📡 on the board).',
        'Hitting a checkpoint in the correct order advances your progress.',
        'You must visit checkpoints sequentially — no skipping!',
      ],
    },
    {
      heading: 'Winning',
      body: 'The first robot to reach the final checkpoint wins the race.',
    },
    {
      heading: 'Solo & AI',
      body: 'Enable solo practice in the lobby to race against an AI opponent, or add AI players to fill empty seats.',
    },
  ],
  tips: [
    'Plan a full register — think about where you will be after each card.',
    'Turn cards are cheap ways to line up for the next checkpoint.',
    'Watch the priority order — robots ahead of you may block your path.',
  ],
}

export const CARD_LABELS: Record<string, string> = {
  move_1: 'Move 1',
  move_2: 'Move 2',
  move_3: 'Move 3',
  turn_left: '↺ Left',
  turn_right: '↻ Right',
  backup: '⬅ Backup',
}

export const CARD_SHORT: Record<string, string> = {
  move_1: '1',
  move_2: '2',
  move_3: '3',
  turn_left: '↺',
  turn_right: '↻',
  backup: '◀',
}

export const FACING_ARROW: Record<string, string> = {
  N: '↑',
  E: '→',
  S: '↓',
  W: '←',
}
