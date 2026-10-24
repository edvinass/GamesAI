import type { GameRules } from '../codenames/rules'

export const scrabbleRules: GameRules = {
  title: 'Scrabble',
  subtitle: 'Build words. Score the premium squares.',
  quickStart: [
    'Play with 2 to 4 people, or switch on solo play to face the AI.',
    'On your turn, drag tiles onto the board in one row or one column, then press Play.',
    'The first word has to cover the center star. Later words have to touch a tile already on the board.',
    'Use every letter in a real word. Cross words count too. A blank can be any letter and scores 0.',
  ],
  sections: [
    {
      heading: 'Turns',
      body: 'You have three choices. Play one or more tiles that form valid words, exchange tiles when the bag still has at least 7, or pass.',
    },
    {
      heading: 'Scoring',
      body: 'Each letter has a point value. Premium squares multiply a new letter or the whole word, and they count only on the turn the tile is placed. Using all 7 tiles adds 50 points.',
      bullets: [
        'DL and TL double or triple one new letter.',
        'DW and TW double or triple the whole word.',
        'A tile on a premium square counts in every word it makes that turn.',
      ],
    },
    {
      heading: 'Ending',
      body: 'The game ends when someone plays their last tile and the bag is empty, or after six scoreless turns in a row. Leftover tiles are subtracted from your score. If you played out, you also add everyone else\'s leftover points.',
    },
    {
      heading: 'AI opponent',
      body: 'Solo play adds one AI opponent when the game starts. Easy plays modest words. Hard looks for the highest score it can find.',
    },
  ],
  tips: [
    'Save a blank for a spot that opens a high-scoring word.',
    'Parallel plays, where each new tile also makes a short cross word, add up fast.',
    'An S or a blank can hook onto a word that is already on the board.',
    'If your rack is stuck, exchange the awkward letters while the bag is still full.',
  ],
}
