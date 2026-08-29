export const COLOR_HEX: Record<string, string> = {
  brown: '#955436',
  light_blue: '#aae0fa',
  pink: '#d93a96',
  orange: '#f7941d',
  red: '#ed1b24',
  yellow: '#fef200',
  green: '#1fb25a',
  dark_blue: '#0072bb',
}

export const COLOR_LABEL: Record<string, string> = {
  brown: 'Brown',
  light_blue: 'Light Blue',
  pink: 'Pink',
  orange: 'Orange',
  red: 'Red',
  yellow: 'Yellow',
  green: 'Green',
  dark_blue: 'Dark Blue',
}

/** Short labels that still read like the classic board. */
export const SPACE_SHORT: Record<number, string> = {
  0: 'GO',
  1: 'Mediterranean Avenue',
  2: 'Community Chest',
  3: 'Baltic Avenue',
  4: 'Income Tax',
  5: 'Reading Railroad',
  6: 'Oriental Avenue',
  7: 'Chance',
  8: 'Vermont Avenue',
  9: 'Connecticut Avenue',
  10: 'Jail',
  11: 'St. Charles Place',
  12: 'Electric Company',
  13: 'States Avenue',
  14: 'Virginia Avenue',
  15: 'Pennsylvania Railroad',
  16: 'St. James Place',
  17: 'Community Chest',
  18: 'Tennessee Avenue',
  19: 'New York Avenue',
  20: 'Free Parking',
  21: 'Kentucky Avenue',
  22: 'Chance',
  23: 'Indiana Avenue',
  24: 'Illinois Avenue',
  25: 'B. & O. Railroad',
  26: 'Atlantic Avenue',
  27: 'Ventnor Avenue',
  28: 'Water Works',
  29: 'Marvin Gardens',
  30: 'Go To Jail',
  31: 'Pacific Avenue',
  32: 'North Carolina Avenue',
  33: 'Community Chest',
  34: 'Pennsylvania Avenue',
  35: 'Short Line',
  36: 'Chance',
  37: 'Park Place',
  38: 'Luxury Tax',
  39: 'Boardwalk',
}

/** Compact name for tight cells. */
export const SPACE_TINY: Record<number, string> = {
  0: 'GO',
  1: 'MEDITER-\nRANEAN\nAVENUE',
  2: 'COMMUNITY\nCHEST',
  3: 'BALTIC\nAVENUE',
  4: 'INCOME\nTAX',
  5: 'READING\nRAILROAD',
  6: 'ORIENTAL\nAVENUE',
  7: 'CHANCE',
  8: 'VERMONT\nAVENUE',
  9: 'CONNECTICUT\nAVENUE',
  10: 'IN\nJAIL',
  11: 'ST. CHARLES\nPLACE',
  12: 'ELECTRIC\nCOMPANY',
  13: 'STATES\nAVENUE',
  14: 'VIRGINIA\nAVENUE',
  15: 'PENNSYLVANIA\nRAILROAD',
  16: 'ST. JAMES\nPLACE',
  17: 'COMMUNITY\nCHEST',
  18: 'TENNESSEE\nAVENUE',
  19: 'NEW YORK\nAVENUE',
  20: 'FREE\nPARKING',
  21: 'KENTUCKY\nAVENUE',
  22: 'CHANCE',
  23: 'INDIANA\nAVENUE',
  24: 'ILLINOIS\nAVENUE',
  25: 'B. & O.\nRAILROAD',
  26: 'ATLANTIC\nAVENUE',
  27: 'VENTNOR\nAVENUE',
  28: 'WATER\nWORKS',
  29: 'MARVIN\nGARDENS',
  30: 'GO TO\nJAIL',
  31: 'PACIFIC\nAVENUE',
  32: 'N. CAROLINA\nAVENUE',
  33: 'COMMUNITY\nCHEST',
  34: 'PENNSYLVANIA\nAVENUE',
  35: 'SHORT\nLINE',
  36: 'CHANCE',
  37: 'PARK\nPLACE',
  38: 'LUXURY\nTAX',
  39: 'BOARDWALK',
}

export type BoardSide = 'bottom' | 'left' | 'top' | 'right' | 'corner'

export function spaceSide(id: number): BoardSide {
  if ([0, 10, 20, 30].includes(id)) return 'corner'
  if (id > 0 && id < 10) return 'bottom'
  if (id > 10 && id < 20) return 'left'
  if (id > 20 && id < 30) return 'top'
  return 'right'
}

/** CSS grid positions for spaces 0–39 on an 11×11 board. */
export function spaceGridPos(id: number): { row: number; col: number } {
  if (id >= 0 && id <= 10) return { row: 11, col: 11 - id }
  if (id >= 11 && id <= 20) return { row: 11 - (id - 10), col: 1 }
  if (id >= 21 && id <= 30) return { row: 1, col: id - 20 + 1 }
  return { row: id - 30 + 1, col: 11 }
}

export const TOKEN_GLYPHS = ['🎩', '🚗', '🐕', '⚔', '🚢', '🐈'] as const

export function tokenGlyph(index: number): string {
  return TOKEN_GLYPHS[index % TOKEN_GLYPHS.length]
}
