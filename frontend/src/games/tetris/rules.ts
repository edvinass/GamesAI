import type { GameRules } from '../codenames/rules'

export const tetrisRules: GameRules = {
  title: 'Multiplier Tetris',
  subtitle: 'Each player stacks on their own board — last one standing wins',
  quickStart: [
    'Join a room with 2–4 players (or add AI bots), or play alone for a high score.',
    'Enable Single player in the lobby to play solo — no opponents needed.',
    'Each player has their own 10×20 board.',
    'Use arrow keys to move and rotate pieces.',
    'Press Space to hard-drop a piece instantly.',
    'Clear lines to score; every 10 lines raises your level and speed.',
    'If new pieces cannot spawn, you are eliminated.',
    'Last player alive wins.',
  ],
  sections: [
    {
      heading: 'Controls',
      body: 'Arrow Left/Right move the piece. Arrow Up or X rotates clockwise; Z rotates counter-clockwise. Arrow Down soft-drops. Space hard-drops instantly.',
    },
    {
      heading: 'Your own board',
      body: 'Unlike classic battle Tetris, boards are independent — you only control your stack. Watch opponents in the mini-boards around yours.',
    },
    {
      heading: 'Speed',
      body: 'Gravity accelerates as you clear lines (every 10 lines = +1 level). Higher levels mean faster drops, just like standard Tetris.',
    },
    {
      heading: 'Elimination',
      body: 'When blocks reach the top and a new piece cannot spawn, that player is out. The last surviving board wins.',
    },
    {
      heading: 'AI difficulty',
      body: 'The host can set Easy, Normal, or Hard for each AI in the lobby. Easy AI pauses longer between moves; Hard AI is snappier. The next piece appears as soon as the AI locks its drop.',
    },
    {
      heading: 'Single player',
      body: 'Enable Single player (high score) in the lobby to play alone. Clear as many lines as you can before topping out. Your line count is your final score.',
    },
    {
      heading: 'AI & solo practice',
      body: 'The host can add AI players in the lobby, or enable solo practice for a 4-player game (you + 3 AI). Single player and solo practice are separate modes.',
    },
  ],
  tips: [
    'Keep your stack flat — holes are hard to recover from at high speed.',
    'Hard-drop to lock pieces quickly when you know the placement.',
    'Watch opponent levels — a player near topping out may win by default soon.',
  ],
}
