/** Same-origin model path (proxied in dev, bundled for production builds). */
export const KATAGO_9X9_MODEL_URL = '/models/kata9x9.bin.gz'

export const KATAGO_9X9_MODEL_REMOTE =
  'https://github.com/lightvector/KataGo/releases/download/v1.13.2-kata9x9/kata9x9-b18c384nbt-20231025.bin.gz'

export const KATAGO_9X9_MODEL_NAME = 'kata9x9-b18c384nbt'

/** MCTS search budget for Hard solo play. */
export const KATAGO_HARD_MAX_TIME_MS = 16000
export const KATAGO_HARD_VISITS = 1200
