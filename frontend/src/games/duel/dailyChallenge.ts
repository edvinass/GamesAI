export interface DailyChallenge {
  dateKey: string
  label: string
  mutator: string
  mutatorSecondary: string
  obstacleCount: number
  matchFormat: string
  layoutSeed: number
}

function dateKey(d = new Date()): string {
  return d.toISOString().slice(0, 10)
}

function hashString(input: string): number {
  let h = 0
  for (let i = 0; i < input.length; i++) {
    h = (h * 31 + input.charCodeAt(i)) >>> 0
  }
  return h
}

const MUTATORS = ['classic', 'chaos', 'sniper', 'bounce_house', 'fog'] as const
const SECONDARIES = ['none', 'fog', 'chaos'] as const
const FORMATS = ['quick_duel', 'best_of_3', 'best_of_5', 'best_of_7'] as const

export function getDailyChallenge(d = new Date()): DailyChallenge {
  const key = dateKey(d)
  const seed = hashString(key)
  const mutator = MUTATORS[seed % MUTATORS.length]
  const mutatorSecondary = SECONDARIES[(seed >> 3) % SECONDARIES.length]
  const obstacleCount = 1 + ((seed >> 5) % 5)
  const matchFormat = FORMATS[(seed >> 7) % FORMATS.length]
  return {
    dateKey: key,
    label: `Daily — ${mutator.replace('_', ' ')}${mutatorSecondary !== 'none' ? ` + ${mutatorSecondary}` : ''}`,
    mutator,
    mutatorSecondary,
    obstacleCount,
    matchFormat,
    layoutSeed: seed,
  }
}
