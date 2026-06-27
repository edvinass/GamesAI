export interface GameRulesSection {
  heading: string
  body: string
}

export interface GameRules {
  title: string
  sections: GameRulesSection[]
}

export const codenamesRules: GameRules = {
  title: 'Codenames',
  sections: [
    {
      heading: 'Overview',
      body: 'Two teams compete to find all of their secret words on a 5×5 board. One player per team is the Spymaster; everyone else is an Operative. Spymasters know which words belong to which team — operatives do not.',
    },
    {
      heading: 'Setup',
      body: 'Each team has 8 words to find (9 for the team that goes first). There are also neutral words and one black Assassin card. Teams alternate turns until one team finds all its words or someone hits the Assassin.',
    },
    {
      heading: 'Spymaster',
      body: 'On your team\'s turn, the Spymaster gives a one-word clue and a number (e.g. "OCEAN 3"). The number is how many board words relate to the clue. The clue must be a single word and cannot match any word on the board.',
    },
    {
      heading: 'Operatives',
      body: 'Operatives discuss and tap words they think match the clue. You may make one extra guess beyond the number given. After each guess, the card is revealed — if it is your team\'s color, you may keep guessing; if it is wrong, your turn ends immediately.',
    },
    {
      heading: 'Ending a turn',
      body: 'Operatives can stop guessing at any time by ending the turn, even if they have guesses remaining. When guesses run out or a wrong card is revealed, play passes to the other team.',
    },
    {
      heading: 'Winning',
      body: 'Find all of your team\'s words to win. If any team reveals the Assassin, they lose instantly and the other team wins.',
    },
  ],
}
