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
  matchStats: Record<
    string,
    {
      perfect_rounds?: number
      crits?: number
      clutch_heals?: number
      railgun_kills?: number
    }
  > | undefined,
): DuelMilestones {
  const current = loadMilestones()
  const mine = matchStats?.[playerId]
  if (!mine) return current
  current.matchesPlayed += 1
  current.perfectRounds += mine.perfect_rounds ?? 0
  current.critsLanded += mine.crits ?? 0
  current.clutchHeals += mine.clutch_heals ?? 0
  current.railgunKills += mine.railgun_kills ?? 0
  saveMilestones(current)
  return current
}
