export interface Player {
  id: string
  nickname: string
  team: 'red' | 'blue' | null
  role: 'spymaster' | 'operative' | null
  is_ai: boolean
  is_connected: boolean
}

export interface Room {
  id: string
  game_type: string
  status: 'lobby' | 'playing' | 'finished'
  settings: Record<string, unknown>
  host_player_id: string | null
  players: Player[]
}

export interface Card {
  index: number
  word: string
  revealed: boolean
  color?: string
}

export interface GameState {
  cards: Card[]
  starting_team: string
  current_team: string
  phase: 'clue' | 'guess'
  current_clue: { word: string; number: number } | null
  guesses_remaining: number
  winner: string | null
  win_reason: string | null
  red_remaining: number
  blue_remaining: number
  last_action: Record<string, unknown> | null
  players: Player[]
  viewer_role: string | null
  viewer_team: string | null
}

export interface WsMessage {
  type: string
  room?: Room
  game_state?: GameState | null
  player_id?: string
  events?: Array<{ type: string; [key: string]: unknown }>
  message?: string
}
