import type { GameRules } from '../codenames/rules'

export const battleshipRules: GameRules = {
  title: 'Battleship',
  subtitle: 'Place your fleet and sink the enemy',
  quickStart: [
    'Join with exactly 2 players, or enable Vs AI for solo practice.',
    'Place all five ships on your 10×10 grid (or hit Auto-place), then Ready.',
    'Take turns firing at the opponent’s grid — hits and misses are marked.',
    'Sink every enemy ship to win.',
  ],
  sections: [
    {
      heading: 'The fleet',
      body: 'Each side has five ships: Carrier (5), Battleship (4), Cruiser (3), Submarine (3), and Destroyer (2). Ships cannot overlap or hang off the board.',
    },
    {
      heading: 'Placement',
      body: 'Select a ship, choose horizontal or vertical orientation, then click a cell for the bow. You can remove a ship and reposition it until you lock in with Ready. Auto-place fills a valid random layout.',
    },
    {
      heading: 'Battle',
      body: 'Once both players are ready, the first captain fires. Click an unmarked cell on the enemy grid. A hit or miss is revealed immediately, then the other player shoots. Turns always alternate.',
    },
    {
      heading: 'Winning',
      body: 'A ship sinks when every one of its cells has been hit. Sink the entire opposing fleet to win. You can resign at any time.',
    },
    {
      heading: 'AI opponent',
      body: 'Vs AI adds a bot captain. Easy fires mostly at random; Medium hunts around hits; Hard uses smarter targeting patterns.',
    },
  ],
  tips: [
    'Spread your ships — clustering makes one lucky salvo more devastating.',
    'After a hit, fire adjacent cells to finish the ship.',
    'Watch for ship lengths still afloat when guessing open water.',
    'Use Auto-place if you want a quick, fair layout.',
  ],
}
