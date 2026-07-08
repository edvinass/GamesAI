import type { GameRules } from '../codenames/rules'

export const chessRules: GameRules = {
  title: 'Chess',
  subtitle: 'Classic strategy — outmaneuver your opponent or the AI',
  quickStart: [
    'Join with exactly 2 players, or enable solo practice to play against AI.',
    'White moves first. Click a piece, then click a highlighted square.',
    'Capture the enemy king by checkmate — or resign if you’re lost.',
    'You can offer a draw; your opponent must accept.',
  ],
  sections: [
    {
      heading: 'How to move',
      body: 'Select one of your pieces, then choose a legal destination. Legal squares are highlighted. For pawn promotions, pick Queen, Rook, Bishop, or Knight when prompted.',
    },
    {
      heading: 'Special moves',
      body: 'Castling, en passant, and pawn promotion are fully supported. You cannot castle out of check or through attacked squares.',
    },
    {
      heading: 'Winning',
      body: 'Checkmate wins the game. Stalemate and the fifty-move rule end in a draw. Resigning awards the win to your opponent.',
    },
    {
      heading: 'AI opponent',
      body: 'Enable solo practice to play as White against an AI. Choose Easy, Medium, or Hard difficulty in the lobby. In a two-player room you can also add one AI seat.',
    },
  ],
  tips: [
    'Control the center early with pawns and knights.',
    'Develop pieces before launching attacks.',
    'When in check, only moves that resolve the check are legal.',
  ],
}
