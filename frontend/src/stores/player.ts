import { defineStore } from 'pinia'
import { ref } from 'vue'

const STORAGE_KEY = 'gamesai_player'

interface PlayerSession {
  nickname: string
  sessionToken: string
  playerId: string
  roomId: string
}

function loadSession(): PlayerSession | null {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    return raw ? JSON.parse(raw) : null
  } catch {
    return null
  }
}

export const usePlayerStore = defineStore('player', () => {
  const nickname = ref(loadSession()?.nickname ?? '')
  const sessionToken = ref(loadSession()?.sessionToken ?? '')
  const playerId = ref(loadSession()?.playerId ?? '')
  const roomId = ref(loadSession()?.roomId ?? '')

  function saveSession(data: PlayerSession) {
    nickname.value = data.nickname
    sessionToken.value = data.sessionToken
    playerId.value = data.playerId
    roomId.value = data.roomId
    localStorage.setItem(STORAGE_KEY, JSON.stringify(data))
  }

  function setNickname(name: string) {
    nickname.value = name
  }

  function clearSession() {
    nickname.value = ''
    sessionToken.value = ''
    playerId.value = ''
    roomId.value = ''
    localStorage.removeItem(STORAGE_KEY)
  }

  return { nickname, sessionToken, playerId, roomId, saveSession, setNickname, clearSession }
})
