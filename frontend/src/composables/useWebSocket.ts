import { ref, watch, onUnmounted, type Ref } from 'vue'
import type { WsMessage } from '@/types'

export function useWebSocket(roomId: Ref<string> | string, token: Ref<string> | string) {
  const connected = ref(false)
  const lastMessage = ref<WsMessage | null>(null)
  const error = ref<string | null>(null)

  let ws: WebSocket | null = null
  let reconnectTimer: ReturnType<typeof setTimeout> | null = null
  let intentionalClose = false

  const getRoomId = () => (typeof roomId === 'string' ? roomId : roomId.value)
  const getToken = () => (typeof token === 'string' ? token : token.value)

  function connect() {
    const rid = getRoomId()
    const tok = getToken()
    if (!rid || !tok) return

    if (ws) {
      intentionalClose = true
      ws.close()
      ws = null
    }
    intentionalClose = false

    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    const host = window.location.host
    const url = `${protocol}//${host}/ws/rooms/${rid}?token=${encodeURIComponent(tok)}`
    ws = new WebSocket(url)

    ws.onopen = () => {
      connected.value = true
      error.value = null
    }

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data) as WsMessage
        if (data.type === 'error') {
          error.value = data.message ?? 'Unknown error'
        }
        lastMessage.value = data
      } catch {
        error.value = 'Failed to parse message'
      }
    }

    ws.onclose = () => {
      connected.value = false
      if (!intentionalClose && getToken()) {
        reconnectTimer = setTimeout(connect, 2000)
      }
    }

    ws.onerror = () => {
      error.value = 'Connection error'
    }
  }

  function send(data: Record<string, unknown>) {
    if (ws?.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify(data))
      return true
    }
    error.value = 'Not connected — try again in a moment'
    return false
  }

  function disconnect() {
    intentionalClose = true
    if (reconnectTimer) clearTimeout(reconnectTimer)
    ws?.close()
    ws = null
  }

  if (typeof token !== 'string') {
    watch([() => getRoomId(), () => getToken()], ([rid, tok]) => {
      if (rid && tok) connect()
      else disconnect()
    }, { immediate: true })
  } else if (typeof roomId === 'string' && token) {
    connect()
  }

  onUnmounted(disconnect)

  return { connected, lastMessage, error, send, disconnect, reconnect: connect }
}
