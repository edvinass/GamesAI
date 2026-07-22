export interface Player {
  id: string
  nickname: string
  team: 'red' | 'blue' | null
  role: 'spymaster' | 'operative' | null
  is_ai: boolean
  is_connected: boolean
  ai_difficulty?: 'easy' | 'normal' | 'medium' | 'hard' | 'pro'
}

export interface Room {
  id: string
  code: string
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
  spoken?: boolean
}

export interface SpyfallGameState {
  phase: 'questioning' | 'voting' | 'finished'
  round_id: string | null
  question_log: SpyfallQuestionEntry[]
  pending_question: { from_id: string; to_id: string; question: string; spoken?: boolean } | null
  turn_order: string[]
  current_turn_index: number
  current_turn_player_id: string | null
  timer_ends_at: string | null
  votes: Record<string, string | null>
  votes_cast_count: number
  votes_total: number
  accused_player_id: string | null
  accusation_caller_id: string | null
  viewer_has_voted: boolean
  winner: 'spy' | 'residents' | null
  win_reason: string | null
  last_action: Record<string, unknown> | null
  players: Player[]
  is_spy: boolean | null
  viewer_location: string | null
  viewer_role: string | null
  location_names: string[] | null
  same_room: boolean
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
  pending_grow?: number
  ghost_until_tick?: number
  ammo?: number
  speed_mode?: 'normal' | 'fast' | 'slow'
  speed_until_tick?: number
  move_credit?: number
}

export type SnakeFoodType = 'apple' | 'golden' | 'poison' | 'ghost' | 'ammo' | 'turbo' | 'slow'

export interface SnakeFood {
  x: number
  y: number
  type: SnakeFoodType
}

export interface SnakeProjectile {
  id: string
  x: number
  y: number
  direction: string
  owner_id: string
  ttl: number
  color?: string
}

export interface SnakeGameState {
  phase: 'countdown' | 'playing' | 'finished'
  countdown_ends_at: string | null
  tick: number
  tick_ms?: number
  grid_width: number
  grid_height: number
  foods: SnakeFood[]
  projectiles?: SnakeProjectile[]
  snakes: Record<string, SnakeSegment>
  players: Player[]
  winner: string | null
  win_reason: string | null
  score_to_win?: number
  last_action: Record<string, unknown> | null
  viewer_id: string | null
}

export type BombermanPowerupType = 'bomb' | 'range' | 'speed' | 'throw' | 'kick'

export interface BombermanBomber {
  x: number
  y: number
  direction: string
  next_direction: string
  facing?: string
  alive: boolean
  color: string
  max_bombs: number
  bomb_range: number
  speed_level: number
  can_throw?: boolean
  can_kick?: boolean
  carrying_bomb_id?: string | null
  move_credit?: number
  kills: number
  passable_bomb_ids?: string[]
}

export interface BombermanBomb {
  id: string
  x: number
  y: number
  owner_id: string
  range: number
  fuse: number
  flight?: 'throw' | 'kick' | 'carried' | null
  sliding?: boolean
  slide_dir?: string | null
  land_x?: number | null
  land_y?: number | null
}

export interface BombermanExplosion {
  x: number
  y: number
  ttl: number
}

export interface BombermanPowerup {
  x: number
  y: number
  type: BombermanPowerupType
}

export interface BombermanGameState {
  phase: 'countdown' | 'playing' | 'finished'
  countdown_ends_at: string | null
  tick: number
  tick_ms?: number
  grid_width: number
  grid_height: number
  /** 0 empty, 1 hard wall, 2 soft wall */
  grid: number[][]
  map_id?: string
  map_name?: string
  bombers: Record<string, BombermanBomber>
  bombs: BombermanBomb[]
  explosions: BombermanExplosion[]
  powerups: BombermanPowerup[]
  players: Player[]
  winner: string | null
  win_reason: string | null
  last_action: Record<string, unknown> | null
  viewer_id: string | null
}

export interface DuelFighterEffects {
  machine_gun_until?: number
  shield_until?: number
  wide_shot_until?: number
  pierce_until?: number
  ghost_until?: number
  homing_until?: number
  jam_until?: number
  ricochet_until?: number
  afterburner_until?: number
  exposed_until?: number
  jam_cast_until?: number
  expose_cast_until?: number
  ghost_active?: boolean
  jam_active?: boolean
  exposed_active?: boolean
  homing_active?: boolean
  machine_gun_active?: boolean
  shield_active?: boolean
  wide_shot_active?: boolean
  pierce_active?: boolean
  ricochet_active?: boolean
  afterburner_active?: boolean
  jam_cast_active?: boolean
  expose_cast_active?: boolean
}

export interface DuelFighter {
  x: number
  y: number
  display_y?: number
  side: 'left' | 'right'
  alive: boolean
  hp: number
  max_hp: number
  move_direction: string
  pending_shoot: boolean
  charging?: boolean
  charge_ticks?: number
  cooldown_until_tick: number
  color: string
  stored_powerup?: string | null
  powerup_charges?: number
  activating_powerup?: boolean
  powerup_activation_ticks?: number
  effects?: DuelFighterEffects
}

export interface DuelBullet {
  id: number
  x: number
  y: number
  vx: number
  vy?: number
  owner_id: string
  damage?: number
  bounces_remaining?: number
  homing?: boolean
  kind?: 'normal' | 'bomb'
}

export interface DuelObstacle {
  x: number
  y: number
  w: number
  h: number
  vy?: number
}

export interface DuelPowerup {
  x: number
  y: number
  type:
    | 'machine_gun'
    | 'shield'
    | 'wide_shot'
    | 'pierce'
    | 'ghost'
    | 'jam'
    | 'snipe'
    | 'railgun'
    | 'homing'
    | 'heal'
    | 'ricochet'
    | 'bomb'
    | 'cluster'
    | 'burst'
    | 'afterburner'
    | 'expose'
    | 'shockwave'
  despawn_at_tick?: number
}

export interface DuelEventLogEntry {
  tick: number
  message: string
  kind: 'info' | 'success' | 'warn'
}

export interface DuelStatBlock {
  damage_dealt: number
  damage_taken: number
  crits: number
  powerups_used: number
  hazard_ticks: number
  perfect_rounds?: number
  clutch_heals?: number
  railgun_kills?: number
}

export interface DuelLastHit {
  player_id: string
  shooter_id?: string
  damage: number
  crit: boolean
  blocked?: boolean
  y?: number
}

export interface DuelGameState {
  phase: 'powerup_draft' | 'countdown' | 'playing' | 'round_over' | 'finished'
  countdown_ends_at: string | null
  tick: number
  round: number
  round_scores: Record<string, number>
  round_winner: string | null
  best_of: number
  match_format: string
  mutator: string
  mutator_secondary?: string
  arena_theme?: string
  training_drill?: string
  tutorial_mode?: boolean
  powerups_enabled: boolean
  charge_shot_enabled?: boolean
  effect_duration_ticks?: number
  powerup_lifetime_ticks?: number
  bullet_speed: number
  tick_ms: number
  charge_max_ticks: number
  grid_width: number
  grid_height: number
  playable_y_min: number
  playable_y_max: number
  shrinking_arena?: boolean
  shrink_start_tick?: number
  shrink_interval_ticks?: number
  hazard_damage?: number
  hazard_damage_interval_ticks?: number
  layout_seed?: number | null
  fog?: boolean
  fighter_height: number
  obstacles: DuelObstacle[]
  fighters: Record<string, DuelFighter>
  bullets: DuelBullet[]
  powerup: DuelPowerup | null
  event_log?: DuelEventLogEntry[]
  round_stats?: Record<string, DuelStatBlock>
  match_stats?: Record<string, DuelStatBlock>
  powerup_bans?: Record<string, string>
  rematch_requests?: string[]
  players: Player[]
  winner: string | null
  win_reason: string | null
  last_action: Record<string, unknown> | null
  last_hit: DuelLastHit | null
  tick_hits?: DuelLastHit[]
  viewer_id: string | null
}

export interface TetrisActivePiece {
  type: string
  rotation: number
  x: number
  y: number
}

export interface TetrisBoardState {
  grid: (string | null)[][]
  active: TetrisActivePiece | null
  active_color: string | null
  next_queue: string[]
  next_colors: string[]
  alive: boolean
  lines_cleared: number
  level: number
  color: string
  drop_interval_ticks?: number
}

export interface TetrisGameState {
  phase: 'countdown' | 'playing' | 'finished'
  countdown_ends_at: string | null
  tick: number
  board_width: number
  board_height: number
  boards: Record<string, TetrisBoardState>
  players: Player[]
  settings: Record<string, unknown>
  winner: string | null
  win_reason: string | null
  final_score: number | null
  last_action: Record<string, unknown> | null
  viewer_id: string | null
}

export interface GravityMasterLevel {
  id: number
  name: string
  hint: string
  world_width: number
  world_height: number
  max_ink: number
  ball: { x: number; y: number; radius: number }
  target: { x: number; y: number; radius: number }
  static_bodies: Array<{
    type: 'rect' | 'circle'
    x: number
    y: number
    width?: number
    height?: number
    radius?: number
    angle?: number
  }>
  gears?: Array<{
    x: number
    y: number
    radius: number
    angular_velocity: number
    teeth?: number
  }>
  moving_platforms?: Array<{
    x: number
    y: number
    width: number
    height: number
    travel: number
    axis: 'x' | 'y'
    speed: number
    phase?: number
  }>
  bouncers?: Array<{
    x: number
    y: number
    width: number
    height: number
    angle?: number
    restitution?: number
  }>
  seesaws?: Array<{
    x: number
    y: number
    width: number
    height?: number
    angle?: number
  }>
  magnets?: Array<{
    x: number
    y: number
    radius: number
    strength: number
  }>
  layout_scale?: number
}

export interface GravityMasterGameState {
  phase: 'drawing' | 'simulating' | 'finished'
  level_index: number
  levels_total: number
  level: GravityMasterLevel
  ink_used: number
  players: Player[]
  settings: Record<string, unknown>
  winner: string | null
  win_reason: string | null
  last_action: Record<string, unknown> | null
  viewer_id: string | null
}

export interface PlayingCard {
  rank: string
  suit: string
}

export interface PokerPlayerState {
  id: string
  nickname: string
  is_ai: boolean
  chips: number
  bet_this_round: number
  total_bet_hand: number
  status: 'active' | 'folded' | 'all_in' | 'eliminated'
  hole_cards: PlayingCard[]
  hand_description?: string
}

export interface PokerPot {
  amount: number
  eligible_player_ids: string[]
}

export interface PokerWinner {
  player_id: string
  amount: number
  hand: string | null
}

export interface PokerGameState {
  phase: 'preflop' | 'flop' | 'turn' | 'river' | 'showdown' | 'hand_complete' | 'game_over'
  hand_number: number
  dealer_index: number
  dealer_player_id: string | null
  seat_order: string[]
  community_cards: PlayingCard[]
  players: PokerPlayerState[]
  pot_total: number
  pots: PokerPot[]
  current_actor_id: string | null
  current_bet: number
  min_raise: number
  last_action: Record<string, unknown> | null
  winners: PokerWinner[]
  winner: string | null
  win_reason: string | null
  settings: Record<string, unknown>
  host_id: string | null
  viewer_id: string | null
  bet_to_call: number
  can_check: boolean
  min_raise_to: number
  max_raise_to: number
  raise_options: number[]
  raise_increment: number
  win_by_fold: boolean
}

export interface ChessPlayerState {
  id: string
  nickname: string
  is_ai: boolean
  color: 'w' | 'b'
}

export interface ChessMove {
  from: string
  to: string
  promotion?: string | null
  capture?: boolean
  player_id?: string
  uci?: string
}

export interface ChessGameState {
  phase: 'playing' | 'game_over'
  fen: string
  board: Array<Array<string | null>>
  players: ChessPlayerState[]
  white_player_id: string
  black_player_id: string
  current_color: 'w' | 'b'
  current_actor_id: string | null
  in_check: boolean
  legal_moves: Array<{ from: string; to: string; promotion?: string | null }>
  move_history: ChessMove[]
  last_move: ChessMove | null
  winner: string | null
  winner_color: 'w' | 'b' | null
  win_reason: string | null
  draw_offer_from?: string | null
  settings: Record<string, unknown>
  host_id: string | null
  viewer_id: string | null
  viewer_color: 'w' | 'b' | null
}

export interface GoPlayerState {
  id: string
  nickname: string
  is_ai: boolean
  color: 'B' | 'W'
}

export interface GoMove {
  type: 'play' | 'pass'
  coord?: string
  row?: number
  col?: number
  player_id?: string
  color?: 'B' | 'W'
  captured?: { B: number; W: number }
}

export interface GoScore {
  black_stones: number
  white_stones: number
  black_territory: number
  white_territory: number
  black_score: number
  white_score: number
  komi: number
  winner_color: 'B' | 'W' | null
}

export interface GoGameState {
  phase: 'playing' | 'game_over'
  board: Array<Array<string | null>>
  board_size: number
  players: GoPlayerState[]
  black_player_id: string
  white_player_id: string
  current_color: 'B' | 'W'
  current_actor_id: string | null
  legal_plays: Array<{ row: number; col: number; coord: string }>
  move_history: GoMove[]
  last_move: GoMove | null
  consecutive_passes: number
  captured: { B: number; W: number }
  ko_point?: [number, number] | null
  winner: string | null
  winner_color: 'B' | 'W' | null
  win_reason: string | null
  score: GoScore | null
  settings: Record<string, unknown>
  host_id: string | null
  viewer_id: string | null
  viewer_color: 'B' | 'W' | null
}

export interface RoboRallyCard {
  id: string
  type?: string
  priority?: number
  hidden?: boolean
}

export interface RoboRallyOption {
  id: string
  type: string
  name: string
  description?: string
}

export interface RoboRallyRobot {
  x: number
  y: number
  facing: 'N' | 'E' | 'S' | 'W'
  checkpoints_reached: number
  damage?: number
  lives?: number
  archive?: { x: number; y: number }
  options?: RoboRallyOption[]
  powered_down?: boolean
  pending_power_down?: boolean
  pending_reboot?: boolean
  eliminated?: boolean
}

export interface RoboRallyEdgeWall {
  x: number
  y: number
  dir: 'N' | 'E' | 'S' | 'W'
}

export interface RoboRallyConveyor {
  x: number
  y: number
  dir: 'N' | 'E' | 'S' | 'W'
  express?: boolean
  rotate?: 'none' | 'left' | 'right'
}

export interface RoboRallyBoardState {
  id: string
  name: string
  width: number
  height: number
  walls: Array<RoboRallyEdgeWall | number[]>
  conveyors?: RoboRallyConveyor[]
  gears?: Array<{ x: number; y: number; dir: 'left' | 'right' }>
  pushers?: Array<{ x: number; y: number; dir: string; registers: number[] }>
  crushers?: Array<{ x: number; y: number; registers: number[] }>
  pits?: number[][]
  lasers?: Array<{ x: number; y: number; dir: string; strength?: number }>
  repairs?: number[][]
  upgrades?: number[][]
  checkpoints: number[][]
  antenna: number[]
}

export interface RoboRallyPlayerState {
  id: string
  nickname: string
  is_ai: boolean
  color: string
  seat: number
}

export interface RoboRallyGameState {
  phase: 'programming' | 'executing' | 'finished'
  round: number
  board: RoboRallyBoardState
  robots: Record<string, RoboRallyRobot>
  players: RoboRallyPlayerState[]
  player_order: string[]
  register_order: string[]
  hands: Record<string, RoboRallyCard[]>
  programs: Record<string, Array<RoboRallyCard | null>>
  lock_status: Record<string, boolean>
  register_locks?: Record<string, boolean[]>
  register_size: number
  execution_log: Array<Record<string, unknown>>
  winner: string | null
  win_reason: string | null
  settings: Record<string, unknown>
  available_maps: Array<{ id: string; name: string }>
  viewer_id: string | null
  total_checkpoints: number
}

export interface BattleshipShipDef {
  id: string
  name: string
  length: number
}

export interface BattleshipShip {
  id: string
  name: string
  length: number
  cells: Array<[number, number]> | null
  hits: number
  sunk: boolean
  placed: boolean
}

export interface BattleshipPlayerState {
  id: string
  nickname: string
  is_ai: boolean
  ready: boolean
}

export interface BattleshipShot {
  row: number
  col: number
  result: 'hit' | 'miss' | 'sunk'
  player_id: string
  target_player_id: string
  ship_id: string | null
  sunk_ship: { id: string; name: string; cells: Array<[number, number]> } | null
}

export interface BattleshipCell {
  row: number
  col: number
  state: 'empty' | 'ship' | 'hit' | 'miss'
  ship_id?: string
}

export interface BattleshipFleetPublic {
  ready: boolean
  ships: BattleshipShip[]
  shots: Record<string, 'hit' | 'miss'>
  ships_remaining: number
}

export interface BattleshipGameState {
  phase: 'placing' | 'playing' | 'game_over'
  size: number
  ship_defs: BattleshipShipDef[]
  players: BattleshipPlayerState[]
  player_order: string[]
  fleets: Record<string, BattleshipFleetPublic>
  boards: Record<string, { grid: BattleshipCell[][] }>
  current_actor_id: string | null
  shot_history: BattleshipShot[]
  last_shot: BattleshipShot | null
  winner: string | null
  win_reason: string | null
  legal_shots: Array<{ row: number; col: number }>
  settings: Record<string, unknown>
  host_id?: string
  viewer_id: string | null
  opponent_id: string | null
}

export interface Connect4PlayerState {
  id: string
  nickname: string
  is_ai: boolean
  color: 'red' | 'yellow'
}

export interface Connect4Move {
  col: number
  row: number
  color: 'red' | 'yellow'
  player_id: string
}

export interface Connect4GameState {
  phase: 'playing' | 'game_over'
  board: Array<Array<string | null>>
  rows: number
  cols: number
  players: Connect4PlayerState[]
  red_player_id: string
  yellow_player_id: string
  current_color: 'red' | 'yellow'
  current_actor_id: string | null
  move_history: Connect4Move[]
  last_move: Connect4Move | null
  winner: string | null
  winner_color: 'red' | 'yellow' | null
  win_reason: string | null
  winning_cells: Array<[number, number]> | null
  legal_moves: Array<{ col: number }>
  settings: Record<string, unknown>
  viewer_id: string | null
  viewer_color: 'red' | 'yellow' | null
}

export interface SolitaireCard {
  rank: string | null
  suit: string | null
  face_up: boolean
}

export interface SolitaireFoundation {
  top: { rank: string; suit: string } | null
  count: number
}

export interface SolitaireHint {
  type: string
  source?: string
  source_index?: number | null
  card_index?: number
  target_col?: number
  reason?: string
}

export interface SolitaireGameState {
  phase: 'playing' | 'finished'
  tableau: SolitaireCard[][]
  foundations: Record<string, SolitaireFoundation>
  stock_count: number
  waste_top: SolitaireCard | null
  waste_fan?: SolitaireCard[]
  waste_count: number
  moves: number
  players: Player[]
  settings: Record<string, unknown>
  winner: string | null
  win_reason: string | null
  last_action: Record<string, unknown> | null
  viewer_id: string | null
  can_auto_complete: boolean
  autoplay?: boolean
  hint?: SolitaireHint | null
}

export type GameState = CodenamesGameState | SpyfallGameState | SnakeGameState | BombermanGameState | DuelGameState | TetrisGameState | GravityMasterGameState | PokerGameState | ChessGameState | GoGameState | RoboRallyGameState | Connect4GameState | BattleshipGameState | SolitaireGameState

export function isCodenamesState(state: GameState): state is CodenamesGameState {
  return 'cards' in state
}

export function isSpyfallState(state: GameState): state is SpyfallGameState {
  return 'question_log' in state
}

export function isSnakeState(state: GameState): state is SnakeGameState {
  return 'snakes' in state
}

export function isBombermanState(state: GameState): state is BombermanGameState {
  return 'bombers' in state && 'bombs' in state && 'grid' in state && Array.isArray((state as BombermanGameState).grid)
}

export function isDuelState(state: GameState): state is DuelGameState {
  return 'fighters' in state && 'bullets' in state && 'grid_width' in state
}

export function isTetrisState(state: GameState): state is TetrisGameState {
  return 'boards' in state && 'board_width' in state
}

export function isGravityMasterState(state: GameState): state is GravityMasterGameState {
  return 'level_index' in state && 'levels_total' in state && 'level' in state
}

export function isPokerState(state: GameState): state is PokerGameState {
  return 'seat_order' in state && 'community_cards' in state && 'pot_total' in state
}

export function isChessState(state: GameState): state is ChessGameState {
  return 'fen' in state && 'legal_moves' in state && 'white_player_id' in state
}

export function isGoState(state: GameState): state is GoGameState {
  return 'legal_plays' in state && 'black_player_id' in state && !('fen' in state)
}

export function isRoboRallyState(state: GameState): state is RoboRallyGameState {
  return 'register_order' in state && 'robots' in state && 'register_size' in state
}

export function isConnect4State(state: GameState): state is Connect4GameState {
  return 'red_player_id' in state && 'yellow_player_id' in state && 'cols' in state
}

export function isBattleshipState(state: GameState): state is BattleshipGameState {
  return 'fleets' in state && 'boards' in state && 'ship_defs' in state && 'legal_shots' in state
}

export function isSolitaireState(state: GameState): state is SolitaireGameState {
  return 'tableau' in state && 'foundations' in state && 'stock_count' in state
}

export interface WsMessage {
  type: string
  room?: Room
  game_state?: GameState | null
  player_id?: string
  nickname?: string
  emoji?: string
  events?: Array<{ type: string; [key: string]: unknown }>
  message?: string
}
