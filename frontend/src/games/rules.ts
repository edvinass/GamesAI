import { codenamesRules, type GameRules } from './codenames/rules'
import { chessRules } from './chess/rules'
import { goRules } from './go/rules'
import { roborallyRules } from './roborally/rules'
import { duelRules } from './duel/rules'
import { gravityMasterRules } from './gravity_master/rules'
import { pokerRules } from './poker/rules'
import { snakeRules } from './snake/rules'
import { solitaireRules } from './solitaire/rules'
import { spyfallRules } from './spyfall/rules'
import { tetrisRules } from './tetris/rules'
import { connect4Rules } from './connect4/rules'

const rulesByGameType: Record<string, GameRules> = {
  codenames: codenamesRules,
  spyfall: spyfallRules,
  snake: snakeRules,
  duel: duelRules,
  tetris: tetrisRules,
  gravity_master: gravityMasterRules,
  poker: pokerRules,
  chess: chessRules,
  go: goRules,
  roborally: roborallyRules,
  connect4: connect4Rules,
  solitaire: solitaireRules,
}

export function getGameRules(gameType: string): GameRules | null {
  return rulesByGameType[gameType] ?? null
}

export type { GameRules, GameRulesSection } from './codenames/rules'
