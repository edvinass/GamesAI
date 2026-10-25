import { Chess } from 'chess.js'
import { lessons } from './course.ts'
import { bestSafeMove, pickGreedyCapture, pickOscarMove } from './oscarAi.ts'

function fail(message: string): never {
  throw new Error(message)
}

function playUci(chess: Chess, uci: string) {
  const move = chess.moves({ verbose: true }).find((candidate) => candidate.lan === uci)
  if (!move) fail(`${uci} is illegal in ${chess.fen()}`)
  chess.move({ from: move.from, to: move.to, promotion: move.promotion })
  return move
}

for (const lesson of lessons) {
  if (lesson.kind === 'mini') {
    if (!lesson.mini) fail(`${lesson.id} missing mini settings`)
    const chess = new Chess(lesson.mini.fen)
    if (chess.isGameOver()) fail(`${lesson.id} mini starts finished`)
    if (!chess.moves({ verbose: true }).some((move) => move.isCapture())) {
      fail(`${lesson.id} mini has no capture`)
    }
    continue
  }
  if (lesson.kind === 'match') {
    if (!lesson.match) fail(`${lesson.id} missing match settings`)
    const chess = new Chess()
    const move = pickOscarMove(chess, lesson.match.oscar)
    if (!move) fail(`${lesson.id} oscar has no move`)
    playUci(chess, move)
    if (!bestSafeMove(new Chess())) fail('safe move missing')
    continue
  }
  if (lesson.drills.length === 0) fail(`${lesson.id} has no drills`)
  for (const drill of lesson.drills) {
    const chess = new Chess(drill.fen)
    if (drill.inCheck && !chess.isCheck()) fail(`${lesson.id} expected check`)
    for (const step of drill.steps) {
      const legal = new Set(chess.moves({ verbose: true }).map((move) => move.lan))
      for (const uci of step.accept) {
        if (!legal.has(uci)) fail(`${lesson.id} accept ${uci} illegal in ${chess.fen()}`)
      }
      if (step.anyMate) {
        const mates = chess.moves({ verbose: true }).filter((move) => {
          const next = new Chess(chess.fen())
          next.move({ from: move.from, to: move.to, promotion: move.promotion })
          return next.isCheckmate()
        })
        if (!mates.some((move) => move.lan === step.accept[0])) {
          fail(`${lesson.id} hint ${step.accept[0]} is not mate`)
        }
      }
      playUci(chess, step.accept[0])
      if (step.reply) playUci(chess, step.reply)
    }
  }
}

const greedy = new Chess('k7/8/2p2p2/3q4/4B3/5N2/8/6K1 w - - 0 1')
greedy.move({ from: 'e4', to: 'd5' })
const reply = pickGreedyCapture(greedy)
if (!reply) fail('greedy produced nothing')

console.log(`ok ${lessons.length} lessons`)
