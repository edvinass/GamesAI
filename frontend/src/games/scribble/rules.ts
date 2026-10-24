import type { GameRules } from '../codenames/rules'

export const scribbleRules: GameRules = {
  title: 'Scribble',
  subtitle: 'Draw the word. Everyone else tries to guess it.',
  quickStart: [
    'Get 2 to 8 players, or turn on solo practice to draw against three AI players.',
    'On your turn, pick one of three words. Harder words are worth more points.',
    'Draw on the canvas. Everyone else types guesses in the chat.',
    'Faster guesses score more. The drawer scores when other people get it.',
  ],
  sections: [
    {
      heading: 'Turns',
      body: 'Each round, every player draws once. The drawer picks a word in secret, then has the rest of the timer to sketch it. Guessers only see the letter count, plus a couple of letters as hints later in the turn.',
    },
    {
      heading: 'Guessing',
      body: 'Type your guess and press enter. A correct guess scores points and that player cannot guess again this turn. A guess one letter off is marked as close. When everyone has guessed, or the timer runs out, the word is revealed.',
    },
    {
      heading: 'Scoring',
      body: 'Easy words start at 100 points, medium at 200, and hard at 300. You keep more of that if you guess early, and a little less if someone else already got it. The drawer earns about half of what the guessers scored that turn.',
    },
    {
      heading: 'AI players',
      body: 'AI players can sit in open seats. They draw a simple picture when it is their turn, and they guess on a delay. Easy AI is slow and often wrong. Hard AI guesses sooner.',
    },
  ],
  tips: [
    'Draw the big shape first so people can guess before the hints land.',
    'Hard words pay more, but only if someone can tell what you drew.',
    'End the turn early once you are happy with the sketch.',
    'Watch for the close tag. You are one letter away.',
  ],
}
