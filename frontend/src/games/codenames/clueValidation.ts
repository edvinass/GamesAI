const MIN_SUBSTRING_CLUE_LEN = 3

export function normalizeClueWord(clue: string): string {
  return clue.trim().toUpperCase()
}

export function getBoardWords(cards: { word: string }[] | string[]): Set<string> {
  const words =
    cards.length === 0 || typeof cards[0] === 'string'
      ? (cards as string[])
      : (cards as { word: string }[]).map((c) => c.word)
  return new Set(words.map((word) => word.toUpperCase()))
}

export function conflictingBoardWord(clue: string, boardWords: Set<string>): string | null {
  const normalized = normalizeClueWord(clue)
  if (boardWords.has(normalized)) {
    return normalized
  }
  if (normalized.length >= MIN_SUBSTRING_CLUE_LEN) {
    for (const word of boardWords) {
      if (normalized.includes(word) || word.includes(normalized)) {
        return word
      }
    }
  }
  return null
}

export function validateClueWord(clue: string, boardWords: Set<string>): string | null {
  const normalized = normalizeClueWord(clue)
  if (!normalized) {
    return 'Clue must be a single word'
  }
  if (normalized.split(/\s+/).length > 1) {
    return 'Clue must be a single word'
  }

  const conflict = conflictingBoardWord(normalized, boardWords)
  if (conflict) {
    if (normalized === conflict) {
      return 'Clue cannot match a word on the board'
    }
    return `Clue is too similar to board word '${conflict.charAt(0)}${conflict.slice(1).toLowerCase()}'`
  }
  return null
}
