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

export interface CodenamesGameState {
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

export interface SpyfallQuestionEntry {
  from_id: string
  to_id: string
  from_nickname: string
  to_nickname: string
  question: string
  answer: string
}

export interface SpyfallGameState {
  phase: 'questioning' | 'voting' | 'finished'
  round_id: string | null
  question_log: SpyfallQuestionEntry[]
  pending_question: { from_id: string; to_id: string; question: string } | null
  turn_order: string[]
  current_turn_index: number
  current_turn_player_id: string | null
  timer_ends_at: string | null
  votes: Record<string, string | null>
  votes_cast_count: number
  votes_total: number
  accused_player_id: string | null
  accusation_caller_id: string | null
  winner: 'spy' | 'residents' | null
  win_reason: string | null
  last_action: Record<string, unknown> | null
  players: Player[]
  is_spy: boolean | null
  viewer_location: string | null
  viewer_role: string | null
  location_names: string[] | null
  revealed_location: string | null
  revealed_spy_id: string | null
  revealed_assignments: Record<string, { role: string | null; is_spy: boolean }> | null
  viewer_id: string | null
}

export interface SnakeSegment {
  body: number[][]
  direction: string
  next_direction: string
  alive: boolean
  score: number
  color: string
}

export interface SnakeGameState {
  phase: 'countdown' | 'playing' | 'finished'
  countdown_ends_at: string | null
  tick: number
  grid_width: number
  grid_height: number
  food: [number, number] | null
  snakes: Record<string, SnakeSegment>
  players: Player[]
  winner: string | null
  win_reason: string | null
  last_action: Record<string, unknown> | null
  viewer_id: string | null
}

export interface DuelFighter {
  x: number
  y: number
  side: 'left' | 'right'
  alive: boolean
  move_direction: string
  pending_shoot: boolean
  cooldown_until_tick: number
  color: string
}

export interface DuelBullet {
  id: number
  x: number
  y: number
  vx: number
  owner_id: string
}

export interface DuelGameState {
  phase: 'countdown' | 'playing' | 'finished'
  countdown_ends_at: string | null
  tick: number
  grid_width: number
  grid_height: number
  fighter_height: number
  fighters: Record<string, DuelFighter>
  bullets: DuelBullet[]
  players: Player[]
  winner: string | null
  win_reason: string | null
  last_action: Record<string, unknown> | null
  viewer_id: string | null
}

export type GameState = CodenamesGameState | SpyfallGameState | SnakeGameState | DuelGameState

export function isCodenamesState(state: GameState): state is CodenamesGameState {
  return 'cards' in state
}

export function isSpyfallState(state: GameState): state is SpyfallGameState {
  return 'question_log' in state
}

export function isSnakeState(state: GameState): state is SnakeGameState {
  return 'snakes' in state
}

export function isDuelState(state: GameState): state is DuelGameState {
  return 'fighters' in state
}

export interface WsMessage {
  type: string
  room?: Room
  game_state?: GameState | null
  player_id?: string
  events?: Array<{ type: string; [key: string]: unknown }>
  message?: string
}
