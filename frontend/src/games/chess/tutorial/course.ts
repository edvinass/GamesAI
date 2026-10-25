export type LessonKind = 'theory' | 'puzzle' | 'mini' | 'review' | 'match'

export interface LessonStep {
  prompt: string
  /** First move is the hint. Every entry must be legal in the position. */
  accept: string[]
  reply?: string
  success?: string
  wrong?: string
  /** Any checkmating move counts. `accept[0]` is still the hint. */
  anyMate?: boolean
}

export interface Drill {
  fen: string
  steps: LessonStep[]
  explain?: string
  inCheck?: boolean
}

export interface Lesson {
  id: string
  sectionId: 'pieces' | 'tactics'
  title: string
  kind: LessonKind
  summary: string
  drills: Drill[]
  mini?: { seconds: number; fen: string }
  match?: { oscar: 'gentle' | 'sharp' }
}

export interface CourseSection {
  id: Lesson['sectionId']
  index: number
  title: string
  summary: string
}

export const HEARTS = 5

export const sections: CourseSection[] = [
  {
    id: 'pieces',
    index: 1,
    title: 'The pieces',
    summary: 'How the pieces move, how a king is trapped, and a first game.',
  },
  {
    id: 'tactics',
    index: 2,
    title: 'First tactics',
    summary: 'Take the better piece, then fork, pin, and mate.',
  },
]

const startFen = 'rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1'

export const lessons: Lesson[] = [
  {
    id: 'rook',
    sectionId: 'pieces',
    title: 'The rook',
    kind: 'theory',
    summary: 'Rooks run along ranks and files.',
    drills: [
      {
        fen: '7k/8/8/8/8/8/8/R3K3 w - - 0 1',
        steps: [
          {
            prompt: 'Rooks slide along a rank or a file. Move this rook to a8.',
            accept: ['a1a8'],
            wrong: 'The rook can move there, but this lesson wants it on a8.',
          },
        ],
      },
      {
        fen: '7k/8/8/8/R7/8/8/4K3 w - - 0 1',
        explain: 'A rook can cross the whole board when nothing stands in the way.',
        steps: [
          {
            prompt: 'Same piece, other direction. Slide the rook to h4.',
            accept: ['a4h4'],
            wrong: 'From a4 the rook can travel the fourth rank. h4 is on that rank.',
          },
        ],
      },
    ],
  },
  {
    id: 'bishop',
    sectionId: 'pieces',
    title: 'The bishop',
    kind: 'theory',
    summary: 'Bishops stay on one color.',
    drills: [
      {
        fen: '7k/8/8/8/8/8/8/2B1K3 w - - 0 1',
        steps: [
          {
            prompt: 'Bishops move diagonally. Take this one to h6.',
            accept: ['c1h6'],
            wrong: 'Bishops never move straight along a rank or a file.',
          },
        ],
      },
      {
        fen: '7k/8/8/8/3B4/8/8/4K3 w - - 0 1',
        explain: 'Each bishop keeps the color it started on for the whole game.',
        steps: [
          {
            prompt: 'This bishop is already in the middle. Move it to a7.',
            accept: ['d4a7'],
            wrong: 'Follow the diagonal from d4 up toward a7.',
          },
        ],
      },
    ],
  },
  {
    id: 'queen',
    sectionId: 'pieces',
    title: 'The queen',
    kind: 'theory',
    summary: 'The queen combines rook and bishop.',
    drills: [
      {
        fen: '7k/8/8/8/8/8/8/3QK3 w - - 0 1',
        steps: [
          {
            prompt: 'The queen moves like a rook or a bishop. Slide her to d8.',
            accept: ['d1d8'],
            wrong: 'd8 is straight up the d-file from d1.',
          },
        ],
      },
      {
        fen: '7k/8/8/8/3Q4/8/8/4K3 w - - 0 1',
        explain: 'The queen is the strongest piece because she can use either path.',
        steps: [
          {
            prompt: 'Now a diagonal. Move the queen to a7.',
            accept: ['d4a7'],
            wrong: 'From d4, a7 is a diagonal. The queen can take it.',
          },
        ],
      },
    ],
  },
  {
    id: 'knight',
    sectionId: 'pieces',
    title: 'The knight',
    kind: 'theory',
    summary: 'Knights jump in an L.',
    drills: [
      {
        fen: '7k/8/8/8/8/8/8/1N2K3 w - - 0 1',
        steps: [
          {
            prompt: 'Knights jump in an L, two squares one way and one to the side. Jump to c3.',
            accept: ['b1c3'],
            wrong: 'From b1 the L lands on c3 or a3. c3 is the one toward the center.',
          },
        ],
      },
      {
        fen: '7k/8/8/8/3N4/8/8/4K3 w - - 0 1',
        explain: 'A knight is the only piece that can jump over other pieces.',
        steps: [
          {
            prompt: 'From the middle, a knight has more jumps. Move it to f5.',
            accept: ['d4f5'],
            wrong: 'Two squares toward f, then one up, lands on f5.',
          },
        ],
      },
    ],
  },
  {
    id: 'king',
    sectionId: 'pieces',
    title: 'The king',
    kind: 'theory',
    summary: 'The king steps one square.',
    drills: [
      {
        fen: '7k/8/8/8/8/8/8/4K3 w - - 0 1',
        steps: [
          {
            prompt: 'The king moves one square in any direction. Step to e2.',
            accept: ['e1e2'],
            wrong: 'The king cannot travel like a queen. One square is the limit.',
          },
        ],
      },
      {
        fen: '8/8/8/8/4K3/8/8/7k w - - 0 1',
        explain: 'You cannot leave your king on a square the opponent attacks. That rule is called check.',
        steps: [
          {
            prompt: 'Step the king to f5.',
            accept: ['e4f5'],
            wrong: 'f5 is one diagonal step from e4.',
          },
        ],
      },
    ],
  },
  {
    id: 'pawn',
    sectionId: 'pieces',
    title: 'The pawn',
    kind: 'theory',
    summary: 'Pawns step forward.',
    drills: [
      {
        fen: '4k3/8/8/8/8/8/4P3/4K3 w - - 0 1',
        steps: [
          {
            prompt: 'A pawn on its first move can step one or two squares forward. Push this pawn to e4.',
            accept: ['e2e4'],
            wrong: 'Pawns do not move backward or sideways. e4 is two squares forward.',
          },
        ],
      },
      {
        fen: '4k3/8/8/8/4P3/8/8/4K3 w - - 0 1',
        explain: 'After the first move, a pawn steps only one square forward.',
        steps: [
          {
            prompt: 'This pawn has already moved. Step it to e5.',
            accept: ['e4e5'],
            wrong: 'From e4 the pawn only has one forward square, e5.',
          },
        ],
      },
    ],
  },
  {
    id: 'captures',
    sectionId: 'pieces',
    title: 'Capturing',
    kind: 'theory',
    summary: 'Land on an enemy piece to take it.',
    drills: [
      {
        fen: '7k/8/p7/8/8/8/8/R3K3 w - - 0 1',
        steps: [
          {
            prompt: 'To capture, move onto the enemy piece. Take the pawn with the rook.',
            accept: ['a1a6'],
            wrong: 'The pawn is on a6, straight up the file from the rook.',
          },
        ],
      },
      {
        fen: '7k/8/8/8/5p2/8/8/2B1K3 w - - 0 1',
        steps: [
          {
            prompt: 'Bishops capture on the same diagonal they move. Take the pawn.',
            accept: ['c1f4'],
            wrong: 'The pawn on f4 is on the bishop’s diagonal.',
          },
        ],
      },
      {
        fen: '7k/8/8/8/8/8/4p3/4K1N1 w - - 0 1',
        steps: [
          {
            prompt: 'Knights capture on the square they jump to. Take the pawn.',
            accept: ['g1e2'],
            wrong: 'The pawn on e2 is one knight jump from g1.',
          },
        ],
      },
      {
        fen: '4k3/8/8/3p4/4P3/8/8/4K3 w - - 0 1',
        explain: 'Pawns are the exception. They move straight, but they capture one square diagonally.',
        steps: [
          {
            prompt: 'Take the black pawn with your pawn.',
            accept: ['e4d5'],
            wrong: 'The pawn on e4 captures diagonally, onto d5. It cannot take a piece straight ahead.',
          },
        ],
      },
    ],
  },
  {
    id: 'defend',
    sectionId: 'pieces',
    title: 'Defending',
    kind: 'theory',
    summary: 'Move a piece that is under attack.',
    drills: [
      {
        fen: '7k/8/8/3p4/4N3/8/8/4K3 w - - 0 1',
        steps: [
          {
            prompt: 'The pawn on d5 attacks your knight. Move the knight to c3.',
            accept: ['e4c3'],
            wrong: 'c3 is a knight jump, and the pawn on d5 does not attack it.',
          },
        ],
      },
      {
        fen: '7k/8/8/3n4/4P3/8/8/4K3 w - - 0 1',
        explain: 'If an enemy piece lands where your pawn can take it, capturing back is a recapture.',
        steps: [
          {
            prompt: 'The knight on d5 is loose. Recapture it with the pawn.',
            accept: ['e4d5'],
            wrong: 'Your pawn on e4 captures diagonally onto d5.',
          },
        ],
      },
    ],
  },
  {
    id: 'check',
    sectionId: 'pieces',
    title: 'Check',
    kind: 'theory',
    summary: 'Get the king out of attack.',
    drills: [
      {
        fen: '4k3/4r3/8/8/8/8/8/4K3 w - - 0 1',
        inCheck: true,
        steps: [
          {
            prompt: 'That rook attacks your king. This is check. Step the king aside.',
            accept: ['e1d1', 'e1f1', 'e1d2', 'e1f2'],
            wrong: 'In check, the only legal moves are ones that get the king safe. Step off the e-file.',
          },
        ],
      },
      {
        fen: '4k3/4r3/8/8/8/8/R7/4K3 w - - 0 1',
        inCheck: true,
        steps: [
          {
            prompt: 'You can also block a sliding check. Put your rook on e2.',
            accept: ['a2e2'],
            wrong: 'Moving the rook to e2 stands between the checking rook and your king.',
          },
        ],
      },
      {
        fen: '4k3/8/8/8/8/5n2/8/4KQ2 w - - 0 1',
        inCheck: true,
        explain: 'Three ways out of check: move the king, block the attack, or capture the checker.',
        steps: [
          {
            prompt: 'The knight on f3 is checking. Capture it with the queen.',
            accept: ['f1f3'],
            wrong: 'The queen on f1 can take the knight on f3 along the file.',
          },
        ],
      },
    ],
  },
  {
    id: 'checkmate',
    sectionId: 'pieces',
    title: 'Checkmate',
    kind: 'theory',
    summary: 'Check with no escape ends the game.',
    drills: [
      {
        fen: '6k1/5ppp/8/8/8/8/8/R5K1 w - - 0 1',
        steps: [
          {
            prompt: 'The black king is stuck behind its own pawns. Slide the rook to a8 for checkmate.',
            accept: ['a1a8'],
            anyMate: true,
            wrong: 'Checkmate means the king is in check and has no safe square. a8 checks along the back rank.',
          },
        ],
      },
      {
        fen: '7k/8/6K1/7Q/8/8/8/8 w - - 0 1',
        explain: 'If the king can capture the checker, block, or step away, it is only check. Mate means none of those work.',
        steps: [
          {
            prompt: 'Find checkmate in one move.',
            accept: ['h5h7'],
            anyMate: true,
            wrong: 'Look for a queen move that checks, and that your king on g6 still defends.',
          },
        ],
      },
    ],
  },
  {
    id: 'specials',
    sectionId: 'pieces',
    title: 'Special moves',
    kind: 'theory',
    summary: 'Promotion and en passant.',
    drills: [
      {
        fen: '4k3/P7/8/8/8/8/8/4K3 w - - 0 1',
        steps: [
          {
            prompt: 'A pawn that reaches the last rank promotes. Move to a8 and become a queen.',
            accept: ['a7a8q'],
            wrong: 'Push the pawn to a8, then choose the queen.',
          },
        ],
      },
      {
        fen: '4k3/8/8/3pP3/8/8/8/4K3 w - d6 0 1',
        explain: 'En passant is a one-move chance. If an enemy pawn jumps two squares beside yours, you may capture it as if it had moved one.',
        steps: [
          {
            prompt: 'The black pawn just jumped from d7 to d5. Capture it en passant.',
            accept: ['e5d6'],
            wrong: 'Your pawn on e5 captures onto d6, and the pawn on d5 leaves the board.',
          },
        ],
      },
    ],
  },
  {
    id: 'opening',
    sectionId: 'pieces',
    title: 'Starting a game',
    kind: 'theory',
    summary: 'Develop a knight, then castle.',
    drills: [
      {
        fen: startFen,
        steps: [
          {
            prompt: 'Bring a knight toward the center. Jump the knight from g1 to f3.',
            accept: ['g1f3'],
            reply: 'e7e5',
            success: 'Black answered in the center. Your turn again.',
            wrong: 'g1 to f3 is the knight jump toward the middle.',
          },
          {
            prompt: 'Claim a central square with the e-pawn. Push it to e4.',
            accept: ['e2e4'],
            wrong: 'The pawn on e2 can move two squares to e4.',
          },
        ],
      },
      {
        fen: '4k3/8/8/8/8/8/8/R3K2R w KQ - 0 1',
        explain: 'Castling tucks the king away and brings a rook toward the center. You can castle once per game, and not out of check.',
        steps: [
          {
            prompt: 'Castle kingside. Move the king from e1 to g1.',
            accept: ['e1g1'],
            wrong: 'Kingside castling slides the king two squares toward the rook, to g1. The rook hops to f1.',
          },
        ],
      },
    ],
  },
  {
    id: 'mini-knights',
    sectionId: 'pieces',
    title: 'Knight hunt',
    kind: 'mini',
    summary: 'Grab material before the clock runs out.',
    drills: [],
    mini: {
      seconds: 90,
      fen: 'k7/2b5/rn2p3/3p3q/8/2N2N2/8/6K1 w - - 0 1',
    },
  },
  {
    id: 'review-pieces',
    sectionId: 'pieces',
    title: 'Piece review',
    kind: 'review',
    summary: 'A short mix from this section.',
    drills: [
      {
        fen: '4k3/8/8/3p4/4P3/8/8/4K3 w - - 0 1',
        steps: [
          {
            prompt: 'Capture with the pawn.',
            accept: ['e4d5'],
            wrong: 'Pawns capture diagonally. d5 is the capture square.',
          },
        ],
      },
      {
        fen: '4k3/4r3/8/8/8/8/8/4K3 w - - 0 1',
        inCheck: true,
        steps: [
          {
            prompt: 'You are in check. Step the king to a safe square.',
            accept: ['e1d1', 'e1f1', 'e1d2', 'e1f2'],
            wrong: 'Leave the e-file. The rook attacks every square on it.',
          },
        ],
      },
      {
        fen: '6k1/5ppp/8/8/8/8/8/R5K1 w - - 0 1',
        explain: 'You can play a full game from here. Checkmate is still the goal.',
        steps: [
          {
            prompt: 'Finish with checkmate.',
            accept: ['a1a8'],
            anyMate: true,
            wrong: 'The rook belongs on the back rank, on a8.',
          },
        ],
      },
    ],
  },
  {
    id: 'match-gentle',
    sectionId: 'pieces',
    title: 'Play Oscar',
    kind: 'match',
    summary: 'A full game against a gentle coach.',
    drills: [],
    match: { oscar: 'gentle' },
  },
  {
    id: 'values',
    sectionId: 'tactics',
    title: 'Piece value',
    kind: 'puzzle',
    summary: 'A queen is worth more than a pawn.',
    drills: [
      {
        fen: '6k1/8/8/3q4/p7/2N5/8/6K1 w - - 0 1',
        explain: 'Pawns are 1, knights and bishops 3, rooks 5, and the queen 9. Take the bigger piece when both hang.',
        steps: [
          {
            prompt: 'Your knight can take a pawn or a queen. Take the queen.',
            accept: ['c3d5'],
            wrong: 'The queen on d5 is worth far more than the pawn on a4.',
          },
        ],
      },
    ],
  },
  {
    id: 'fork',
    sectionId: 'tactics',
    title: 'The fork',
    kind: 'puzzle',
    summary: 'One piece attacks two at once.',
    drills: [
      {
        fen: 'k7/2q1r3/8/8/8/2N5/8/K7 w - - 0 1',
        explain: 'A fork is one move that attacks two pieces. The opponent can save only one, so you win the other.',
        steps: [
          {
            prompt: 'Jump the knight to a square that attacks both the queen and the rook.',
            accept: ['c3d5'],
            wrong: 'd5 attacks c7 and e7. That is the fork.',
          },
        ],
      },
    ],
  },
  {
    id: 'pin',
    sectionId: 'tactics',
    title: 'The pin',
    kind: 'puzzle',
    summary: 'A piece that cannot move off the line.',
    drills: [
      {
        fen: '4k3/8/2n5/8/B7/8/8/4K3 w - - 0 1',
        explain: 'The knight is pinned. Moving it would put its own king in check, so it cannot capture your bishop.',
        steps: [
          {
            prompt: 'The bishop pins the knight to the king. Capture the knight.',
            accept: ['a4c6'],
            wrong: 'a4 to c6 takes the knight. It cannot step off the diagonal.',
          },
        ],
      },
    ],
  },
  {
    id: 'mate-two',
    sectionId: 'tactics',
    title: 'Mate in two',
    kind: 'puzzle',
    summary: 'Two checks, and the king is done.',
    drills: [
      {
        fen: '6k1/8/8/8/8/8/R7/5RK1 w - - 0 1',
        explain: 'The first rook forces the king to the edge. The second rook delivers mate on the back rank.',
        steps: [
          {
            prompt: 'Check with the rook on the a-file. Move it to a7.',
            accept: ['a2a7'],
            reply: 'g8h8',
            success: 'The king has only one legal square.',
            wrong: 'a7 checks along the seventh rank and takes away the escape squares.',
          },
          {
            prompt: 'Now mate with the other rook.',
            accept: ['f1f8'],
            anyMate: true,
            wrong: 'f8 checks the king on the back rank, and the rook on a7 covers g7.',
          },
        ],
      },
    ],
  },
  {
    id: 'mini-bishop',
    sectionId: 'tactics',
    title: 'Bishop hunt',
    kind: 'mini',
    summary: 'A bishop and a knight, ninety seconds.',
    drills: [],
    mini: {
      seconds: 90,
      fen: 'k7/8/2p2p2/3q4/4B3/5N2/8/6K1 w - - 0 1',
    },
  },
  {
    id: 'review-tactics',
    sectionId: 'tactics',
    title: 'Tactics review',
    kind: 'review',
    summary: 'Value, then mate.',
    drills: [
      {
        fen: '6k1/8/8/4q1p1/8/5N2/8/6K1 w - - 0 1',
        steps: [
          {
            prompt: 'Take the piece that is worth more.',
            accept: ['f3e5'],
            wrong: 'The queen on e5 is the bigger capture. The pawn on g5 can wait.',
          },
        ],
      },
      {
        fen: '7k/8/6K1/7Q/8/8/8/8 w - - 0 1',
        explain: 'Same pattern as before. A queen protected by her king is a classic mate.',
        steps: [
          {
            prompt: 'Find checkmate.',
            accept: ['h5h7'],
            anyMate: true,
            wrong: 'The queen needs a checking square that your king still defends.',
          },
        ],
      },
    ],
  },
  {
    id: 'match-sharp',
    sectionId: 'tactics',
    title: 'Oscar again',
    kind: 'match',
    summary: 'The same game, a sharper Oscar.',
    drills: [],
    match: { oscar: 'sharp' },
  },
]

export function lessonMark(kind: LessonKind): string {
  switch (kind) {
    case 'theory':
      return '★'
    case 'puzzle':
      return '◆'
    case 'mini':
      return '♘'
    case 'review':
      return '🏆'
    case 'match':
      return '♜'
  }
}

export function lessonById(id: string): Lesson | undefined {
  return lessons.find((lesson) => lesson.id === id)
}
