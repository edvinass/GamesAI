/** Minimal KataGo engine types (adapted from Web KaTrain, MIT). */

export type Player = 'black' | 'white'
export type Intersection = Player | null
export type BoardState = Intersection[][]
export type GameRules = 'japanese' | 'chinese' | 'korean'
export type KataGoBackendPreference = 'wasm' | 'webgpu' | 'cpu'
export type FloatArray = Float32Array | number[]

export interface Move {
  x: number
  y: number
  player: Player
}

export interface CandidateMove {
  x: number
  y: number
  winRate: number
  scoreLead: number
  visits: number
  order: number
}

export interface AnalysisResult {
  rootWinRate: number
  rootScoreLead: number
  moves: CandidateMove[]
  territory: number[][]
}

export type RegionOfInterest = { xMin: number; xMax: number; yMin: number; yMax: number }
