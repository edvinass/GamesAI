export interface DuelKeybinds {
  moveUp: string[]
  moveDown: string[]
  fire: string[]
  powerup: string[]
}

export type DuelKeybindAction = keyof DuelKeybinds

export const KEYBIND_ACTION_LABELS: Record<DuelKeybindAction, string> = {
  moveUp: 'Move up',
  moveDown: 'Move down',
  fire: 'Fire / charge',
  powerup: 'Power-up',
}

const STORAGE_KEY = 'duel-keybinds'

export const DEFAULT_KEYBINDS: DuelKeybinds = {
  moveUp: ['KeyW', 'ArrowUp'],
  moveDown: ['KeyS', 'ArrowDown'],
  fire: ['Space'],
  powerup: ['KeyE'],
}

export function loadKeybinds(): DuelKeybinds {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (!raw) return { ...DEFAULT_KEYBINDS }
    const parsed = JSON.parse(raw) as Partial<DuelKeybinds>
    return {
      moveUp: parsed.moveUp?.length ? parsed.moveUp : DEFAULT_KEYBINDS.moveUp,
      moveDown: parsed.moveDown?.length ? parsed.moveDown : DEFAULT_KEYBINDS.moveDown,
      fire: parsed.fire?.length ? parsed.fire : DEFAULT_KEYBINDS.fire,
      powerup: parsed.powerup?.length ? parsed.powerup : DEFAULT_KEYBINDS.powerup,
    }
  } catch {
    return { ...DEFAULT_KEYBINDS }
  }
}

export function saveKeybinds(bindings: DuelKeybinds): void {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(bindings))
  } catch {
    /* ignore */
  }
}

export function matchesBinding(code: string, keys: string[]): boolean {
  return keys.includes(code)
}

export function formatBindingLabel(keys: string[]): string {
  return keys
    .map((code) => {
      if (code === 'Space') return 'Space'
      if (code.startsWith('Key')) return code.slice(3)
      if (code.startsWith('Arrow')) return code.replace('Arrow', '')
      return code
    })
    .join(' / ')
}
