export const pokerReactionEmojis = ['👍', '🔥', '😂', '😮', '👏', '🃏', '💰', '😎', '🫡', '💀'] as const

export type PokerReactionEmoji = (typeof pokerReactionEmojis)[number]

export interface PokerReaction {
  id: string
  playerId: string
  nickname: string
  emoji: string
}

export const pokerReactionSet = new Set<string>(pokerReactionEmojis)
