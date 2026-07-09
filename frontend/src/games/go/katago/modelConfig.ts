/** Same-origin model path (proxied in dev, bundled for production builds). */
export const KATAGO_9X9_MODEL_URL = '/models/kata9x9.bin.gz'

export const KATAGO_9X9_MODEL_REMOTE =
  'https://github.com/lightvector/KataGo/releases/download/v1.13.2-kata9x9/kata9x9-b18c384nbt-20231025.bin.gz'

export const KATAGO_9X9_MODEL_NAME = 'kata9x9-b18c384nbt'

/** Detect if running on a mobile device (phones/tablets with touch). */
function isMobileDevice(): boolean {
  if (typeof navigator === 'undefined') return false
  const ua = navigator.userAgent || ''
  return /Android|webOS|iPhone|iPad|iPod|BlackBerry|IEMobile|Opera Mini/i.test(ua) ||
    (navigator.maxTouchPoints > 0 && /Mobile|Tablet/i.test(ua))
}

/** Cache mobile detection result. */
const IS_MOBILE = isMobileDevice()

/** MCTS search budget for Hard solo play. Reduced on mobile to avoid browser warnings. */
export const KATAGO_HARD_MAX_TIME_MS = IS_MOBILE ? 6000 : 16000
export const KATAGO_HARD_VISITS = IS_MOBILE ? 600 : 2000
export const KATAGO_HARD_MAX_CHILDREN = IS_MOBILE ? 64 : 120
