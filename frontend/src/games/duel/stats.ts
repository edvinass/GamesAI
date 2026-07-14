const STORAGE_KEY = 'duel-milestones'

export interface DuelMilestones {
  matchesPlayed: number
  perfectRounds: number
  critsLanded: number
  clutchHeals: number
  railgunKills: number
}

const EMPTY: DuelMilestones = {
  matchesPlayed: 0,
  perfectRounds: 0,
  critsLanded: 0,
  clutchHeals: 0,
  railgunKills: 0,
}

export function loadMilestones(): DuelMilestones {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (!raw) return { ...EMPTY }
    return { ...EMPTY, ...JSON.parse(raw) }
  } catch {
    return { ...EMPTY }
  }
}

export function saveMilestones(stats: DuelMilestones): void {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(stats))
  } catch {
    /* ignore */
  }
}

export function recordMatchMilestones(
  playerId: string,
  matchStats: Record<string, { perfect_rounds?: number; crits?: number; powerups_used?: number }> | undefined,
  lastActions: string[],
): DuelMilestones {
  const current = loadMilestones()
  const mine = matchStats?.[playerId]
  if (!mine) return current
  current.matchesPlayed += 1
  current.perfectRounds += mine.perfect_rounds ?? 0
  current.critsLanded += mine.crits ?? 0
  if (lastActions.includes('heal') && (mine.powerups_used ?? 0) > 0) {
    current.clutchHeals += 1
  }
  if (lastActions.includes('railgun')) {
    current.railgunKills += 1
  }
  saveMilestones(current)
  return current
}
