import { useRouter } from 'vue-router'
import { usePlayerStore } from '@/stores/player'

export function useLeaveRoom() {
  const router = useRouter()
  const playerStore = usePlayerStore()

  function leaveRoom(disconnect?: () => void) {
    disconnect?.()
    playerStore.clearSession()
    router.push('/')
  }

  return { leaveRoom }
}
