import { ref } from 'vue'
import type { Room } from '@/types'

const API = '/api'

export function useRoom() {
  const loading = ref(false)
  const error = ref<string | null>(null)

  async function createRoom(gameType: string, nickname: string) {
    loading.value = true
    error.value = null
    try {
      const res = await fetch(`${API}/rooms`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ game_type: gameType, nickname }),
      })
      if (!res.ok) {
        const data = await res.json().catch(() => ({}))
        throw new Error(data.detail ?? 'Failed to create room')
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
      const res = await fetch(`${API}/rooms/${roomId}/join`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ nickname }),
      })
      if (!res.ok) {
        const data = await res.json().catch(() => ({}))
        throw new Error(data.detail ?? 'Failed to join room')
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
    const res = await fetch(`${API}/rooms/${roomId}`)
    if (!res.ok) throw new Error('Room not found')
    return await res.json()
  }

  async function fetchGames() {
    const res = await fetch(`${API}/rooms/games`)
    return await res.json()
  }

  return { loading, error, createRoom, joinRoom, fetchRoom, fetchGames }
}
