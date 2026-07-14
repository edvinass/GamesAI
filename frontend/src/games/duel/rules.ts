import type { GameRules } from '../codenames/rules'

export const duelRules: GameRules = {
  title: 'Side Duel',
  subtitle: 'Dodge, charge, and outshoot your rival across multiple rounds',
  quickStart: [
    'Join a room with exactly 2 players (or practice solo vs AI).',
    'Pick a match format and mutator in the lobby.',
    'Move up and down to dodge incoming shots and use cover.',
    'Hold Space to charge a stronger shot; release to fire.',
    'Win rounds to take the match — first to majority wins.',
  ],
  sections: [
    {
      heading: 'Controls',
      body: 'Use W/S or arrow keys to move up and down. Hold a direction to keep moving. Tap Space for a quick shot in Quick Duel mode. In match modes, hold Space to charge and release to fire — longer charge means more damage or a wide spread.',
    },
    {
      heading: 'Health & crits',
      body: 'Fighters have 3 HP in match modes. Body hits deal 1 damage; center-row hits deal 2. Shields from power-ups block the next hit.',
    },
    {
      heading: 'Arena',
      body: 'Center obstacles block movement and bullets (ricochet in Bounce House). After a while the top and bottom rows shrink inward. Shoot through center power-ups to collect rapid fire, shield, wide shot, or ghost.',
    },
    {
      heading: 'Match formats',
      body: 'Quick duel is a single 1-HP showdown. Best of 3 and Best of 5 play multiple rounds with full mechanics.',
    },
    {
      heading: 'Mutators',
      body: 'Classic is the default. Chaos speeds up bullets and cooldowns. Sniper is one-hit kills with a long reload. Bounce House adds ricochets. Fog obscures the enemy vertical position.',
    },
    {
      heading: 'Winning',
      body: 'Win a round by reducing your opponent to 0 HP. Win the match by taking the majority of rounds. Draw rounds replay with no score change.',
    },
  ],
  tips: [
    'Strafe vertically while charging to bait predictable shots.',
    'Use obstacles to break line-of-sight and force repositioning.',
    'Tag center power-ups with a passing shot when safe.',
    'In Fog mode, watch bullet rows — they reveal true aim.',
    'Save shield for an all-in push when the arena shrinks.',
  ],
}
