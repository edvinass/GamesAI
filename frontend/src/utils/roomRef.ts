/** Crockford-ish room codes from the backend (6 chars, no I/L/O/U). */
const ROOM_CODE_RE = /^[0-9A-HJ-NP-TV-Z]{6}$/i
const UUID_RE =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i

/**
 * Extract a room UUID or short invite code from pasted text / URLs.
 * Accepts: bare code, bare UUID, `/r/CODE`, `/room/UUID`, full URLs.
 */
export function parseRoomRef(input: string): string | null {
  const raw = input.trim()
  if (!raw) return null

  let candidate = raw

  try {
    const url = new URL(raw)
    candidate = url.pathname
  } catch {
    // not a full URL — treat as path or bare id
  }

  const pathMatch = candidate.match(/\/(?:r|room)\/([^/?#]+)/i)
  if (pathMatch?.[1]) {
    candidate = decodeURIComponent(pathMatch[1])
  } else {
    // Strip query/hash if someone pasted a path-like string
    candidate = candidate.split(/[?#]/)[0] ?? candidate
    candidate = candidate.replace(/^\/+/, '')
  }

  candidate = candidate.trim()

  if (UUID_RE.test(candidate)) return candidate.toLowerCase()

  const code = candidate.toUpperCase().replace(/[\s-]/g, '')
  if (ROOM_CODE_RE.test(code)) return code

  return null
}

export function isRoomCode(ref: string): boolean {
  return ROOM_CODE_RE.test(ref)
}

export function roomInvitePath(code: string): string {
  return `/r/${code.toUpperCase()}`
}
