import { codenamesRules, type GameRules } from './codenames/rules'

const rulesByGameType: Record<string, GameRules> = {
  codenames: codenamesRules,
}

export function getGameRules(gameType: string): GameRules | null {
  return rulesByGameType[gameType] ?? null
}

export type { GameRules, GameRulesSection } from './codenames/rules'
