export interface ChargeTier {
  minTicks: number
  label: string
  damage: number
  width: number
  hint: string
}

export const CHARGE_TIERS: ChargeTier[] = [
  { minTicks: 11, label: 'Full spread', damage: 2, width: 3, hint: '3-row pierce burst' },
  { minTicks: 6, label: 'Heavy shot', damage: 2, width: 1, hint: 'Center-row crit potential' },
  { minTicks: 1, label: 'Quick tap', damage: 1, width: 1, hint: 'Fast single shot' },
  { minTicks: 0, label: 'Tap', damage: 1, width: 1, hint: 'No charge' },
]

export function chargeTierForTicks(ticks: number, instantKill = false): ChargeTier {
  if (instantKill) {
    return { minTicks: 0, label: 'Sniper', damage: 99, width: 1, hint: 'One-hit kill' }
  }
  for (const tier of CHARGE_TIERS) {
    if (ticks >= tier.minTicks) return tier
  }
  return CHARGE_TIERS[CHARGE_TIERS.length - 1]
}
