import { ref } from 'vue'
import type { Room } from '@/types'

const API = '/api'
const REQUEST_TIMEOUT_MS = 20_000

async function fetchWithTimeout(
  input: RequestInfo | URL,
  init?: RequestInit,
): Promise<Response> {
  const controller = new AbortController()
  const timer = setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS)
  try {
    return await fetch(input, { ...init, signal: controller.signal })
  } catch (e) {
    if (e instanceof DOMException && e.name === 'AbortError') {
      throw new Error('Request timed out — is the server running?')
    }
    throw e
  } finally {
    clearTimeout(timer)
  }
}

export function useRoom() {
  const loading = ref(false)
  const error = ref<string | null>(null)

  async function createRoom(gameType: string, nickname: string) {
    loading.value = true
    error.value = null
    try {
      const res = await fetchWithTimeout(`${API}/rooms`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ game_type: gameType, nickname }),
      })
      if (!res.ok) {
        const data = await res.json().catch(() => ({}))
        const detail = data.detail
        const message = typeof detail === 'string'
          ? detail
          : Array.isArray(detail)
            ? detail.map((d: { msg?: string }) => d.msg).filter(Boolean).join(', ')
            : 'Failed to create room'
        throw new Error(message || 'Failed to create room')
      }
      return await res.json()
    } catch (e) {
      error.value = e instanceof Error ? e.message : 'Unknown error'
      throw e
    } finally {
      loading.value = false
    }
  }

  async function joinRoom(roomId: string, nickname: string) {
    loading.value = true
    error.value = null
    try {
      const res = await fetchWithTimeout(`${API}/rooms/${roomId}/join`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ nickname }),
      })
      if (!res.ok) {
        const data = await res.json().catch(() => ({}))
        const detail = data.detail
        const message = typeof detail === 'string'
          ? detail
          : Array.isArray(detail)
            ? detail.map((d: { msg?: string }) => d.msg).filter(Boolean).join(', ')
            : 'Failed to join room'
        throw new Error(message || 'Failed to join room')
      }
      return await res.json()
    } catch (e) {
      error.value = e instanceof Error ? e.message : 'Unknown error'
      throw e
    } finally {
      loading.value = false
    }
  }

  async function fetchRoom(roomId: string): Promise<Room> {
    const res = await fetchWithTimeout(`${API}/rooms/${roomId}`)
    if (!res.ok) throw new Error('Room not found')
    return await res.json()
  }

  async function fetchGames() {
    const res = await fetchWithTimeout(`${API}/rooms/games`)
    if (!res.ok) {
      throw new Error(`Failed to load games (${res.status})`)
    }
    const data = await res.json()
    if (!Array.isArray(data)) {
      throw new Error('Invalid games response')
    }
    return data
  }

  return { loading, error, createRoom, joinRoom, fetchRoom, fetchGames }
}
