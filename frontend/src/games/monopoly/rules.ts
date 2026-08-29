import type { GameRules } from '../codenames/rules'

export const monopolyRules: GameRules = {
  title: 'Monopoly',
  subtitle: 'Buy, auction, trade — last tycoon standing',
  quickStart: [
    'Join with 2–6 players or play solo against 2 AI opponents.',
    'On your turn roll the dice, move, and buy or auction unowned properties.',
    'Collect rent, build houses on complete color sets, and trade with rivals.',
    'Bankrupt everyone else to win.',
  ],
  sections: [
    {
      heading: 'Goal',
      body: 'Be the last player who is not bankrupt. Own sets, charge rent, and force rivals out.',
    },
    {
      heading: 'Turn flow',
      body: 'Roll two dice and move. Land on an unowned property to buy it or start an auction. Pay rent on owned properties. Doubles grant another roll; three doubles in a row send you to Jail.',
    },
    {
      heading: 'Auctions & trading',
      body: 'Declining a purchase starts an auction for all solvent players. Between turns you can propose trades of cash and properties (sell buildings on a color first).',
    },
    {
      heading: 'Building & mortgaging',
      body: 'With a complete unmortgaged color set, build houses evenly, then hotels. Mortgage properties for cash; unmortgage for mortgage value plus 10%.',
    },
    {
      heading: 'Jail',
      body: 'Pay $50, use a Get Out of Jail Free card, or try to roll doubles. After three failed rolls you must pay and leave.',
    },
    {
      heading: 'AI opponents',
      body: 'Add AI in the lobby or use solo practice. Bots buy, bid, build, trade, and manage debt automatically.',
    },
  ],
}
