import type { GameRules } from '../codenames/rules'

export const solitaireRules: GameRules = {
  title: 'Solitaire',
  subtitle: 'Classic Klondike — stack cards and clear the tableau',
  quickStart: [
    'Create a room and start alone — no other players needed.',
    'Build four foundation piles by suit from Ace to King.',
    'Move cards between tableau columns in alternating colors, descending order.',
    'Draw from the stock when stuck, and try to clear all cards to the foundations.',
  ],
  sections: [
    {
      heading: 'Foundations',
      body: 'Build up each foundation pile by suit from Ace to King. Click a card to auto-move it to its foundation if possible. Win by moving all 52 cards to the foundations.',
    },
    {
      heading: 'Tableau',
      body: 'Seven columns of cards. Stack cards in alternating colors (red on black, black on red) in descending order (King down to Ace). Drag face-up cards or piles onto a valid target (or click to select, then click a target). Empty columns can only be filled with a King.',
    },
    {
      heading: 'Stock & Waste',
      body: 'Click the stock pile to draw cards to the waste pile. The top card of the waste can be played to the tableau or foundations. When the stock is empty, click to recycle the waste back into the stock.',
    },
    {
      heading: 'Winning',
      body: 'Move all 52 cards to the four foundation piles to win. Every new deal is verified as winnable with careful play before you start. The game tracks your move count — try to win in as few moves as possible!',
    },
    {
      heading: 'Learn mode',
      body: 'Use Hint to highlight a good next move with a short reason. Use Watch to let the AI play step-by-step so you can learn by watching. You can stop Watch anytime and take over.',
    },
  ],
  tips: [
    'Always move Aces and Twos to foundations immediately.',
    'Try to expose face-down cards in the tableau as early as possible.',
    'Keep foundation piles roughly even to avoid blocking useful cards.',
    'Empty columns are valuable — save them for Kings that help expose hidden cards.',
    'Stuck? Press Hint for a suggestion, or Watch to see how the AI would play.',
  ],
}
