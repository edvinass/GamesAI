export interface PokerHandRanking {
  name: string
  description: string
  example: string
}

/** Best to worst — matches backend hand categories in `hand_eval.py`. */
export const pokerHandRankings: PokerHandRanking[] = [
  {
    name: 'Straight Flush',
    description: 'Five cards in a row, all the same suit. A royal flush (A-K-Q-J-10 of one suit) is the best possible hand.',
    example: '9♠ 8♠ 7♠ 6♠ 5♠',
  },
  {
    name: 'Four of a Kind',
    description: 'Four cards of the same rank.',
    example: 'K♥ K♦ K♣ K♠ 3♥',
  },
  {
    name: 'Full House',
    description: 'Three of a kind plus a pair.',
    example: 'Q♣ Q♦ Q♥ 4♠ 4♣',
  },
  {
    name: 'Flush',
    description: 'Five cards of the same suit, not in sequence.',
    example: 'A♦ J♦ 8♦ 5♦ 2♦',
  },
  {
    name: 'Straight',
    description: 'Five cards in a row, mixed suits. Ace can play high (A-K-Q-J-10) or low (5-4-3-2-A).',
    example: '10♣ 9♦ 8♥ 7♠ 6♣',
  },
  {
    name: 'Three of a Kind',
    description: 'Three cards of the same rank.',
    example: '7♠ 7♥ 7♦ K♣ 2♠',
  },
  {
    name: 'Two Pair',
    description: 'Two different pairs.',
    example: 'J♣ J♠ 5♥ 5♦ A♣',
  },
  {
    name: 'Pair',
    description: 'Two cards of the same rank.',
    example: 'A♠ A♥ K♦ 9♣ 4♠',
  },
  {
    name: 'High Card',
    description: 'No other combination — highest card wins.',
    example: 'A♣ Q♦ 9♥ 6♠ 2♣',
  },
]
