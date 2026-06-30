import { codenamesRules, type GameRules } from './codenames/rules'
import { duelRules } from './duel/rules'
import { snakeRules } from './snake/rules'
import { spyfallRules } from './spyfall/rules'

const rulesByGameType: Record<string, GameRules> = {
  codenames: codenamesRules,
  spyfall: spyfallRules,
  snake: snakeRules,
  duel: duelRules,
}

export function getGameRules(gameType: string): GameRules | null {
  return rulesByGameType[gameType] ?? null
}

export type { GameRules, GameRulesSection } from './codenames/rules'
