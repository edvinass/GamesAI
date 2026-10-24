import { onBeforeUnmount, onMounted, toValue, watch, type MaybeRefOrGetter } from 'vue'

/**
 * Blocks pinch and double-tap zoom while the caller is mounted and enabled.
 * iOS ignores the viewport user-scalable flag, so the lock is done with
 * touch-action plus gesture listeners.
 */
export function useLockPageZoom(enabled: MaybeRefOrGetter<boolean> = true) {
  let listening = false

  function onGesture(event: Event) {
    event.preventDefault()
  }

  function onTouchMove(event: TouchEvent) {
    if (event.touches.length > 1) event.preventDefault()
  }

  function onTouchEnd(event: TouchEvent) {
    if (event.touches.length > 1) event.preventDefault()
  }

  function start() {
    if (listening) return
    listening = true
    document.documentElement.classList.add('lock-page-zoom')
    document.addEventListener('gesturestart', onGesture, { passive: false })
    document.addEventListener('gesturechange', onGesture, { passive: false })
    document.addEventListener('touchmove', onTouchMove, { passive: false })
    document.addEventListener('touchend', onTouchEnd, { passive: false })
  }

  function stop() {
    if (!listening) return
    listening = false
    document.documentElement.classList.remove('lock-page-zoom')
    document.removeEventListener('gesturestart', onGesture)
    document.removeEventListener('gesturechange', onGesture)
    document.removeEventListener('touchmove', onTouchMove)
    document.removeEventListener('touchend', onTouchEnd)
  }

  onMounted(() => {
    if (toValue(enabled)) start()
  })

  watch(
    () => toValue(enabled),
    (on) => {
      if (on) start()
      else stop()
    },
  )

  onBeforeUnmount(stop)
}
