import type { GameRules } from '../codenames/rules'

export const pokerRules: GameRules = {
  title: 'Poker',
  subtitle: 'Bluff, bet, and beat your friends or AI',
  quickStart: [
    'Join a room with 2–6 players or enable solo practice against AI.',
    'Each hand starts with blinds posted and two hole cards dealt.',
    'Bet, check, call, raise, or fold through four betting rounds.',
    'Win the pot with the best hand at showdown or when everyone else folds.',
  ],
  sections: [
    {
      heading: 'Goal',
      body: 'Win chips by making the best five-card hand or forcing everyone else to fold.',
    },
    {
      heading: 'Setup',
      body: 'Each player starts with the same chip stack. Blinds rotate each hand — the small blind and big blind post forced bets before cards are dealt.',
    },
    {
      heading: 'Hand flow',
      body: 'You get two private hole cards. Five community cards are dealt in stages: flop (3), turn (1), river (1). Build your best hand from any combination of hole and community cards.',
    },
    {
      heading: 'Betting',
      body: 'On your turn you may fold, check (if no bet to call), call, raise in big-blind increments, or go all-in. Betting rounds happen after the deal, flop, turn, and river.',
    },
    {
      heading: 'Showdown',
      body: 'If two or more players remain after the river, hands are revealed and the best hand wins the pot. Ties split the pot evenly.',
    },
    {
      heading: 'AI opponents',
      body: 'Add AI players in the lobby or use solo practice to play against bots. AI acts automatically on its turn.',
    },
  ],
}
