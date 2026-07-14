import type { GameRules } from '../codenames/rules'

export const duelRules: GameRules = {
  title: 'Side Duel',
  subtitle: 'Dodge, charge, and outshoot your rival across multiple rounds',
  quickStart: [
    'Join a room with exactly 2 players (or practice solo vs AI).',
    'Pick a match format and mutator in the lobby.',
    'Move up and down to dodge incoming shots and use cover.',
    'Shoot through center power-ups to collect them, then hold Space to activate.',
    'Win rounds to take the match — first to majority wins.',
  ],
  sections: [
    {
      heading: 'Controls',
      body: 'Use W/S or arrow keys to move up and down. Tap Space for a quick shot in Quick Duel mode. In match modes, hold Space to charge and release to fire. When carrying a power-up, hold Space to activate it and use F to charge your weapon.',
    },
    {
      heading: 'Health & crits',
      body: 'Fighters have 3 HP in match modes. Body hits deal 1 damage; center-row hits deal 2. Shields block the next hit; Heal restores 1 HP.',
    },
    {
      heading: 'Arena',
      body: 'Center obstacles block movement and bullets (ricochet in Bounce House). After a while the top and bottom rows shrink inward — the red hazard zones. Power-ups spawn at random safe spots in the arena, linger for a short time, then vanish until the next cooldown.',
    },
    {
      heading: 'Power-ups',
      body: 'Rapid Fire speeds up shots. Shield blocks one hit. Wide Shot spreads your next volley. Ghost hides you from the enemy. Freeze locks the opponent in place. Laser fires a piercing beam. Homing curves bullets toward your rival. Mirror reflects incoming shots. Overdrive triples your next burst. Heal restores 1 HP.',
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
    'Tag power-ups with a passing shot before they despawn — they blink faster when about to vanish.',
    'Hold Space to activate a stored power-up; keep shooting with F while you carry one.',
    'In Fog mode, watch bullet rows — they reveal true aim.',
    'Save shield for an all-in push when the arena shrinks.',
  ],
}
