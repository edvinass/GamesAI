import { lessons, type Lesson } from './course'

const KEY = 'chess-learn-progress'

export interface LearnProgress {
  stars: Record<string, number>
  skipped: string[]
  xp: number
}

export function emptyProgress(): LearnProgress {
  return { stars: {}, skipped: [], xp: 0 }
}

export function loadProgress(): LearnProgress {
  try {
    const raw = localStorage.getItem(KEY)
    if (!raw) return emptyProgress()
    const parsed = JSON.parse(raw) as Partial<LearnProgress>
    return {
      stars: parsed.stars && typeof parsed.stars === 'object' ? parsed.stars : {},
      skipped: Array.isArray(parsed.skipped) ? parsed.skipped.filter((id) => typeof id === 'string') : [],
      xp: typeof parsed.xp === 'number' && parsed.xp > 0 ? parsed.xp : 0,
    }
  } catch {
    return emptyProgress()
  }
}

export function saveProgress(progress: LearnProgress) {
  localStorage.setItem(KEY, JSON.stringify(progress))
}

export function starsForHearts(heartsLeft: number, heartsMax: number): number {
  if (heartsLeft <= 0) return 0
  if (heartsLeft >= heartsMax) return 3
  if (heartsLeft >= heartsMax - 2) return 2
  return 1
}

/** Duolingo mini-match bands: 5, 20, and 40 capture points. */
export function miniStars(points: number): number {
  if (points >= 40) return 3
  if (points >= 20) return 2
  if (points >= 5) return 1
  return 0
}

export function isCleared(progress: LearnProgress, lesson: Lesson): boolean {
  if ((progress.stars[lesson.id] ?? 0) > 0) return true
  return lesson.kind === 'match' && progress.skipped.includes(lesson.id)
}

export function isUnlocked(progress: LearnProgress, index: number): boolean {
  if (index <= 0) return true
  return isCleared(progress, lessons[index - 1])
}

export function applyStars(
  progress: LearnProgress,
  id: string,
  stars: number,
): { progress: LearnProgress; gained: number } {
  const prev = progress.stars[id] ?? 0
  const next = Math.max(prev, stars)
  const gained = next - prev
  return {
    gained,
    progress: {
      ...progress,
      stars: { ...progress.stars, [id]: next },
      xp: progress.xp + gained * 10,
    },
  }
}

export function skipMatch(progress: LearnProgress, id: string): LearnProgress {
  if (progress.skipped.includes(id)) return progress
  return { ...progress, skipped: [...progress.skipped, id] }
}

export function weakestLesson(progress: LearnProgress): Lesson | null {
  let found: Lesson | null = null
  let lowest = 4
  for (const lesson of lessons) {
    if (lesson.kind === 'match' || lesson.kind === 'mini') continue
    const stars = progress.stars[lesson.id] ?? 0
    if (stars <= 0 || stars >= 3) continue
    if (stars < lowest) {
      lowest = stars
      found = lesson
    }
  }
  return found
}
