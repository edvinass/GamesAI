import type { GameRules } from '../codenames/rules'

export const duelRules: GameRules = {
  title: 'Side Duel',
  subtitle: 'Dodge, charge, and outshoot your rival across multiple rounds',
  quickStart: [
    'Join a room with exactly 2 players (or practice solo vs AI).',
    'Pick a match format and mutator in the lobby.',
    'Move up and down to dodge incoming shots and use cover.',
    'Shoot or touch center power-ups to collect. Tap E for bombs and lasers; hold E for shields and buffs.',
    'Win rounds to take the match — first to majority wins.',
  ],
  sections: [
    {
      heading: 'Controls',
      body: 'Use W/S or arrow keys to move. Tap Space for a quick shot in Quick Duel; hold Space to charge in match modes. Collect orbs by shooting or touching them. Tap E for instant power-ups (bombs, lasers, heal); hold E briefly for buffs like Shield or Machine Gun.',
    },
    {
      heading: 'Health & crits',
      body: 'Fighters have 3 HP in match modes. Body hits deal 1 damage; center-row hits deal 2. Active power-ups last several seconds — shields block every hit while active.',
    },
    {
      heading: 'Arena',
      body: 'Center obstacles block movement and bullets (ricochet in Bounce House). After a while the top and bottom rows shrink inward — the red hazard zones. Power-ups spawn at random safe spots in the arena, linger for a short time, then vanish until the next cooldown.',
    },
    {
      heading: 'Power-ups',
      body: 'Shoot orbs to collect, then hold E to activate. Machine Gun and Rapid Fire spray fast bullets. Bomb and Cluster launch explosives. Burst fires a 6-round salvo. Laser and Railgun are instant beams — Railgun pierces cover. Pierce shots ignore obstacles. Shield, Ghost, Mirror, Homing, Wide Shot, Overdrive, Freeze, and Heal round out the arsenal.',
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
    'Move over a power-up to pick it up — you do not have to snipe it.',
    'Tap E for bombs and lasers; hold E for shields and timed buffs.',
    'In Fog mode, watch bullet rows — they reveal true aim.',
    'Save shield for an all-in push when the arena shrinks.',
  ],
}
