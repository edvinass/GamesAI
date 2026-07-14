export type ArenaThemeId = 'classic' | 'neon' | 'asteroid' | 'crt'

export interface ArenaTheme {
  id: ArenaThemeId
  label: string
  backdrop: [string, string]
  grid: string
  midline: string
  hazard: string
  canvasCss: string
}

export const ARENA_THEMES: Record<ArenaThemeId, ArenaTheme> = {
  classic: {
    id: 'classic',
    label: 'Classic',
    backdrop: ['#121a2b', '#070b12'],
    grid: 'rgba(100, 116, 139, 0.12)',
    midline: 'rgba(148, 163, 184, 0.35)',
    hazard: 'rgba(239, 68, 68, 0.35)',
    canvasCss: '#070b12',
  },
  neon: {
    id: 'neon',
    label: 'Neon Grid',
    backdrop: ['#0f172a', '#020617'],
    grid: 'rgba(34, 211, 238, 0.16)',
    midline: 'rgba(168, 85, 247, 0.45)',
    hazard: 'rgba(244, 63, 94, 0.4)',
    canvasCss: '#020617',
  },
  asteroid: {
    id: 'asteroid',
    label: 'Asteroid Field',
    backdrop: ['#1c1917', '#0c0a09'],
    grid: 'rgba(120, 113, 108, 0.14)',
    midline: 'rgba(251, 191, 36, 0.3)',
    hazard: 'rgba(249, 115, 22, 0.38)',
    canvasCss: '#0c0a09',
  },
  crt: {
    id: 'crt',
    label: 'Retro CRT',
    backdrop: ['#14532d', '#052e16'],
    grid: 'rgba(74, 222, 128, 0.12)',
    midline: 'rgba(34, 197, 94, 0.35)',
    hazard: 'rgba(250, 204, 21, 0.35)',
    canvasCss: '#052e16',
  },
}

export function resolveTheme(id: string | null | undefined): ArenaTheme {
  const key = (id ?? 'classic') as ArenaThemeId
  return ARENA_THEMES[key] ?? ARENA_THEMES.classic
}
