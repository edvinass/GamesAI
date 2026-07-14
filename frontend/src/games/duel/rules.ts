import type { GameRules } from '../codenames/rules'

export const duelRules: GameRules = {
  title: 'Side Duel',
  subtitle: 'Dodge, charge, and outshoot your rival across multiple rounds',
  quickStart: [
    'Join a room with exactly 2 players (or practice solo vs AI).',
    'Pick a match format, mutator, and optional secondary overlay in the lobby.',
    'Move up and down to dodge incoming shots and use cover.',
    'Shoot or touch center power-ups to collect. Press E to activate stored power-ups.',
    'Win rounds to take the match — first to majority wins.',
  ],
  sections: [
    {
      heading: 'Controls',
      body: 'Use W/S or arrow keys to move. Tap Space for a quick shot in Quick Duel; hold Space to charge in match modes. Collect orbs by shooting or touching them. Press E to activate any stored power-up.',
    },
    {
      heading: 'Health & crits',
      body: 'Fighters have 3 HP in match modes. Body hits deal 1 damage; center-row hits deal 2. Active power-ups last several seconds — shields block every hit while active.',
    },
    {
      heading: 'Arena',
      body: 'Center obstacles block movement and bullets (ricochet in Bounce House). After a while the top and bottom rows shrink inward — red hazard zones deal damage on a timed interval. Power-ups spawn at random safe spots, linger briefly, then vanish until the next cooldown. Optional layout seeds keep obstacle placement consistent across rematches.',
    },
    {
      heading: 'Power-ups',
      body: 'Shoot orbs to collect, then press E to activate. Machine Gun and Rapid Fire spray fast bullets. Bomb and Cluster launch explosives. Burst fires a 6-round salvo. Laser and Railgun are instant beams — Railgun pierces cover. Pierce shots ignore obstacles. Phase Shift lets you pass through cover briefly. Decoy projects a fake ship to bait homing fire. Shield, Ghost, Mirror, Homing, Wide Shot, Overdrive, Freeze, and Heal round out the arsenal.',
    },
    {
      heading: 'Match formats',
      body: 'Quick duel is a single 1-HP showdown. Best of 3, 5, and 7 play multiple rounds with full mechanics. Multi-round matches can open with a power-up draft where each player bans one orb type.',
    },
    {
      heading: 'Mutators',
      body: 'Classic is the default. Chaos speeds up bullets and cooldowns. Sniper makes every hit lethal with a long reload between shots. Bounce House adds ricochets. Fog obscures the enemy vertical position. Secondary overlays (e.g. Fog on Classic) stack extra rules. Training drills like Aim Trainer lock movement for target practice.',
    },
    {
      heading: 'Winning',
      body: 'Win a round by reducing your opponent to 0 HP. Win the match by taking the majority of rounds. Draw rounds replay with no score change (the round counter still advances). Best of 7 swaps sides every two rounds. After round 3+, shrinking arenas accelerate into sudden death.',
    },
  ],
  tips: [
    'Strafe vertically while charging to bait predictable shots.',
    'Use obstacles to break line-of-sight and force repositioning.',
    'Move over a power-up to pick it up — you do not have to snipe it.',
    'Press E to activate stored power-ups.',
    'In Fog mode, watch bullet rows — they reveal true aim.',
    'Save shield for an all-in push when the arena shrinks.',
    'Ban an opponent’s comfort pick during the pre-match draft.',
  ],
}
