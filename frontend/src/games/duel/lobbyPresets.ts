export interface DuelLobbyPreset {
  id: string
  label: string
  description: string
  settings: Record<string, unknown>
}

export const DUEL_LOBBY_PRESETS: DuelLobbyPreset[] = [
  {
    id: 'casual',
    label: 'Casual',
    description: 'Best of 3 · Classic rules',
    settings: {
      solo_practice: false,
      match_format: 'best_of_3',
      mutator: 'classic',
      mutator_secondary: 'none',
      training_drill: 'none',
      tutorial_mode: true,
      tick_ms: 75,
      obstacle_count: 2,
      obstacle_rotation: false,
      quick_duel_loadout: 'none',
      arena_theme: 'classic',
    },
  },
  {
    id: 'ranked',
    label: 'Ranked',
    description: 'Best of 5 · Power-up draft between rounds',
    settings: {
      solo_practice: false,
      match_format: 'best_of_5',
      mutator: 'classic',
      mutator_secondary: 'none',
      training_drill: 'none',
      tutorial_mode: false,
      tick_ms: 75,
      obstacle_count: 3,
      obstacle_rotation: true,
      quick_duel_loadout: 'none',
      arena_theme: 'neon',
    },
  },
  {
    id: 'practice',
    label: 'Solo practice',
    description: 'vs AI · Medium difficulty',
    settings: {
      solo_practice: true,
      match_format: 'best_of_3',
      mutator: 'classic',
      mutator_secondary: 'none',
      training_drill: 'none',
      tutorial_mode: true,
      tick_ms: 75,
      obstacle_count: 2,
      obstacle_rotation: false,
      quick_duel_loadout: 'none',
      arena_theme: 'classic',
      ai_difficulty: 'medium',
      ai_personality: 'balanced',
    },
  },
]
