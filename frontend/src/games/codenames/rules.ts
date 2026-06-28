export interface GameRulesSection {
  heading: string
  body: string
  bullets?: string[]
}

export interface GameRules {
  title: string
  subtitle?: string
  quickStart?: string[]
  sections: GameRulesSection[]
  tips?: string[]
}

export const codenamesRules: GameRules = {
  title: 'Codenames',
  subtitle: 'Team word-guessing on a shared board',
  quickStart: [
    'Split into red and blue: one Spymaster and at least one Operative per team.',
    'Spymasters see all word colors; Operatives only see words until they are revealed.',
    'On your team\'s turn, the Spymaster gives a one-word clue and a number.',
    'Operatives guess words; wrong guesses end your turn immediately.',
  ],
  sections: [
    {
      heading: 'Board setup',
      body: 'The board has 25 words. Each team has words to find — 9 for the team that starts, 8 for the other. There are also neutral words and one black Assassin card.',
    },
    {
      heading: 'Spymaster clues',
      body: 'Give a single-word clue and a number (how many unrevealed words relate to it). Examples: OCEAN 3, FRUIT 2.',
      bullets: [
        'Clue must be one word only — no proper names or made-up words.',
        'Clue cannot match or closely resemble any word still on the board (including plurals and suffixes like BUG → BUGS).',
        'The app validates clues and rejects invalid ones.',
      ],
    },
    {
      heading: 'Operative guesses',
      body: 'Tap words you think match the clue. Your team may guess one extra word beyond the number given.',
      bullets: [
        'Correct team color: you may keep guessing.',
        'Wrong color or neutral: your turn ends.',
        'Assassin: your team loses instantly.',
        'You can end the turn early at any time.',
      ],
    },
    {
      heading: 'Winning',
      body: 'Reveal all of your team\'s words to win. Hit the Assassin and you lose on the spot.',
    },
    {
      heading: 'AI & solo practice',
      body: 'The host can add AI players to empty slots, or enable solo practice to play as the red Operative against AI teammates.',
    },
  ],
  tips: [
    'Use voice chat to discuss guesses — the app handles clues and reveals.',
    'Spymasters: track which clues already led to wrong guesses before giving a new one.',
    'Operatives: say your reasoning out loud so teammates can agree before you tap.',
  ],
}
