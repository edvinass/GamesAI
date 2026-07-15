import type { GameRules } from '../codenames/rules'

export const roborallyRules: GameRules = {
  title: 'RoboRally',
  subtitle: 'Program your robot through a deadly factory',
  quickStart: [
    'Each round, fill every unlocked register slot from your hand, then lock.',
    'Cards run in priority order (closest to the antenna first). Robots push.',
    'After each register: express belts → all belts → pushers → gears → crushers → lasers → flags/repairs.',
    'Visit checkpoints in order. First to finish wins. Fall in a pit or take 10 damage and you reboot.',
  ],
  sections: [
    {
      heading: 'Programming',
      body: 'Draw 9 cards minus your damage. Click hand cards into register slots, then lock. High damage locks the last registers so those cards stay from last round.',
      bullets: [
        'Click a hand card to fill the next empty slot; click a slot first to choose a specific register.',
        'Click a filled slot, then another slot, to reorder. Use × to return a card to your hand.',
        'Move 1/2/3 advances and can push other robots.',
        'Turn Left / Right rotate in place; Backup steps backward.',
        'Declare Power Down when locking to skip next round and clear all damage.',
      ],
    },
    {
      heading: 'Board elements',
      body: 'Factory tiles activate after each register card resolves.',
      bullets: [
        'Conveyors (yellow) and express (orange) move you; gears rotate you.',
        'Pushers shove on listed registers; crushers destroy on listed registers.',
        'Pits and leaving the board destroy you (lose a life, reboot at archive with 2 damage).',
        'Board lasers and robot lasers deal damage; robots block beams.',
        'Repair heals 1 and sets archive; Upgrade also draws an option card.',
      ],
    },
    {
      heading: 'Winning',
      body: 'Reach every checkpoint in order. Last robot standing also wins if everyone else is eliminated.',
    },
  ],
  tips: [
    'Announce Power Down before you explode — waking at 0 damage is often worth a skipped round.',
    'Watch register numbers on crusher/pusher tiles.',
    'Express belts move twice each register (express phase, then all belts).',
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
