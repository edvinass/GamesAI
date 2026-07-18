import { computed, ref, type MaybeRefOrGetter, toValue } from 'vue'
import { roomInvitePath } from '@/utils/roomRef'

export function useShareRoom(options: {
  code: MaybeRefOrGetter<string | null | undefined>
  gameName?: MaybeRefOrGetter<string | undefined>
}) {
  const copied = ref<'link' | 'code' | null>(null)
  let copiedTimer: ReturnType<typeof setTimeout> | null = null

  const code = computed(() => {
    const value = toValue(options.code)
    return value ? value.toUpperCase() : ''
  })

  const shareUrl = computed(() => {
    if (!code.value || typeof window === 'undefined') return ''
    return `${window.location.origin}${roomInvitePath(code.value)}`
  })

  const canNativeShare = computed(
    () => typeof navigator !== 'undefined' && typeof navigator.share === 'function',
  )

  function flashCopied(kind: 'link' | 'code') {
    copied.value = kind
    if (copiedTimer) clearTimeout(copiedTimer)
    copiedTimer = setTimeout(() => {
      copied.value = null
    }, 2000)
  }

  async function copyText(text: string, kind: 'link' | 'code') {
    await navigator.clipboard.writeText(text)
    flashCopied(kind)
  }

  async function copyLink() {
    if (!shareUrl.value) return
    await copyText(shareUrl.value, 'link')
  }

  async function copyCode() {
    if (!code.value) return
    await copyText(code.value, 'code')
  }

  async function share() {
    if (!shareUrl.value) return

    const title = toValue(options.gameName)
      ? `Join my ${toValue(options.gameName)} game`
      : 'Join my game'
    const text = code.value
      ? `${title} — code ${code.value}`
      : title

    if (canNativeShare.value) {
      try {
        await navigator.share({ title, text, url: shareUrl.value })
        return
      } catch (e) {
        // User cancelled share sheet — don't fall through to clipboard
        if (e instanceof DOMException && e.name === 'AbortError') return
      }
    }

    await copyLink()
  }

  return {
    code,
    shareUrl,
    canNativeShare,
    copied,
    share,
    copyLink,
    copyCode,
  }
}
