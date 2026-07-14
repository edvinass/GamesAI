# Side Duel — Bug & Issue Review

**Date:** 2026-07-14  
**Scope:** Backend (`backend/app/games/duel/`, room service, websocket handlers, tests) and frontend (`frontend/src/games/duel/`, duel types, GameView/RoomView integration)

---

## Summary

| Severity | Count |
|----------|-------|
| Critical | 1 |
| High | 7 |
| Medium | 16 |
| Low | 14 |
| Info / design notes | 6 |

**Highest-impact issues:** power-up draft tick path skips round reset (breaks solo vs AI), stuck charge/powerup inputs after death, double movement prediction, keyboard input leaking under modals.

---

## Critical

### 1. Power-up draft tick path skips round reset

**Location:** `backend/app/games/duel/engine.py` — `apply_action` (lines 828–832) vs `tick` (lines 2156–2158)

When a round ends with power-up draft enabled, `_end_round` sets `pending_round_reset = True` and enters draft (lines 2129–2131). When the **human** completes the draft via `ban_powerup`, `apply_action` correctly calls `_reset_round`:

```python
if len(bans) >= len(state["players"]):
    if state.pop("pending_round_reset", False):
        self._reset_round(state)
    state["phase"] = "countdown"
    self._start_countdown(state)
```

When the **AI** completes the draft on a tick (typical in solo vs AI — human bans, AI auto-bans next tick), the tick handler does **not** call `_reset_round`:

```python
if len(bans) >= len(state["players"]):
    state["phase"] = "countdown"
    self._start_countdown(state)
```

**Impact:**
- Fighters are never respawned after a round (winner alive, loser dead).
- On `playing`, `len(alive) == 1` every tick triggers `_end_round` again (lines 2243–2245).
- Round score increments every ~75ms until the match ends.
- Broken gameplay in the common solo-practice / human+AI path.

**Test gap:** `test_round_end_enters_powerup_draft` only checks draft entry, not completion + reset.

---

## High

### 2. Stuck charge/powerup inputs after death or phase change

**Location:** `frontend/src/games/duel/DuelBoard.vue` — `onKeyUp` (706–730), `clearHeldInputs` (353–360), `canControl` (54–56)

`onKeyUp` returns early when `!canControl`. If the player dies, the round ends, or phase leaves `playing` while Space/E is held:
- `releaseCharge()` / `releasePowerupActivation()` never run
- Server may keep `charging: true` and charge state persists
- Local `setInterval` timers for charge/powerup keep running until unmount

`clearHeldInputs()` runs on blur/visibility change but **not** on phase or alive-state changes.

---

### 3. Double movement prediction (client prediction + renderer interpolation)

**Location:** `frontend/src/games/duel/DuelBoard.vue` (759–777); `frontend/src/games/duel/duelRenderer.ts` (473–483)

Two independent prediction layers stack:
1. `renderStateForFrame()` adds ±1 row via `predictedMoveDir`
2. `updateFighterPoses()` adds fractional movement from `move_direction` for the viewer

When server confirms movement, the ship can jump or overshoot briefly.

---

### 4. Keyboard input leaks during Rules modal (and other overlays)

**Location:** `frontend/src/games/duel/DuelBoard.vue` (794–795, 660–704); `frontend/src/views/GameView.vue` (199, 228–235)

`keydown`/`keyup` are bound to `window` unconditionally. Opening the Rules modal in `GameView.vue` does not disable duel input — W/S/Space/E still fire game actions underneath.

---

### 5. Charge ticks not synced from server (unlike powerup channel)

**Location:** `frontend/src/games/duel/DuelBoard.vue` (632–654 vs 464–473)

Charge uses a local `setInterval` and sends `charge_ticks` on release. There is no watch on `myFighter.charge_ticks` to reconcile with the server (powerup activation does this). Combined with `CLIENT_PROGRESS_LAG_TICKS = 2` on the backend, charge tier UI can show a different tier than what the server applies.

---

### 6. Burst power-up ignores `max_bullets_per_player`

**Location:** `backend/app/games/duel/engine.py` — `_try_shoot` (1156–1160) vs `_process_burst_shots` (1560–1584)

Normal shots enforce the cap in `_try_shoot`; burst uses `_spawn_bullet` directly with no cap check. A player can exceed the mutator limit (e.g. 6 in Chaos) during a 6-shot burst salvo.

---

### 7. Power-up activation lag compensation is client-trustable

**Location:** `backend/app/games/duel/engine.py` — `_powerup_activation_succeeds` (428–442), release handler (915–920)

`_powerup_activation_succeeds` allows activation when `client_ticks >= required` and `server_ticks >= min(5, required)`, even if server progress is well below required (e.g. shield needs 8 server ticks but can succeed at 5 with a forged client value). Charge shots are clamped more tightly (`CLIENT_PROGRESS_LAG_TICKS = 2`); power-ups are more exploitable.

---

### 8. AI completes channeled power-ups 1 tick early vs humans

**Location:** `backend/app/games/duel/ai.py` (709–713)

`_should_activate_powerup` uses `powerup_activation_ticks + 1 >= required` and `_apply_ai_inputs` activates immediately on `pu_release`, **before** `_increment_powerup_activation` runs. Humans need server ticks (or lag-compensated client ticks) via `_powerup_activation_succeeds`. AI can activate shield at 7 server ticks when 8 are required.

---

## Medium

### 9. Local charge/powerup intervals not cleared when phase changes

**Location:** `frontend/src/games/duel/DuelBoard.vue` (118–119, 608–623)

Phase watcher records milestones but never calls `clearHeldInputs()`. Intervals can run through `round_over`, `countdown`, `powerup_draft`, and `finished`.

---

### 10. Match finished overlay shows "Draw wins!" on null winner

**Location:** `frontend/src/games/duel/DuelBoard.vue` (77–82, 1017–1019)

`winnerName` returns `'Draw'` when `winner` is null, but the template always appends `" wins!"`. Users see **"Draw wins!"** instead of a proper draw/end message.

---

### 11. Hazard tick sound ignores shield

**Location:** `frontend/src/games/duel/DuelBoard.vue` (271–287)

Sound plays when the fighter is geometrically in a hazard zone. Backend skips hazard damage when shield is active (`engine.py` 1920–1921). Players hear hazard ticks while shield blocks damage.

---

### 12. Draft phase shows stale round state under overlay

**Location:** `frontend/src/games/duel/DuelBoard.vue` (972–994); `backend/app/games/duel/engine.py` (2127–2131)

After a round, backend enters `powerup_draft` **before** `_reset_round()` (via `pending_round_reset`). The canvas still shows dead fighters, bullets, etc. under the ban overlay until both players ban and the round resets. Compounded by issue #1 when AI completes the draft via tick.

---

### 13. Arena theme only partially applied

**Location:** `frontend/src/games/duel/DuelBoard.vue` (839); `frontend/src/games/duel/duelRenderer.ts` (580, 643–657, 672–677); `frontend/src/games/duel/themes.ts`

Lobby offers four themes, but the renderer only uses `theme.backdrop` for the starfield. Grid, hazards, midline, and arena fill use hardcoded colors. `themes.ts` defines `grid`, `midline`, `hazard`, `canvasCss` but most are unused in drawing code.

---

### 14. `isDuelState` type guard is fragile

**Location:** `frontend/src/types.ts` (546–548)

```typescript
export function isDuelState(state: GameState): state is DuelGameState {
  return 'fighters' in state
}
```

Any future game state with a `fighters` field would be misidentified as duel state in `GameView.vue`.

---

### 15. Decoy rendering hardcodes height 3

**Location:** `frontend/src/games/duel/duelRenderer.ts` (1320–1321)

Uses `cell * 3` instead of `state.fighter_height`. Wrong if `fighter_height` ever differs from 3 (backend allows 1–5).

---

### 16. Daily challenge date uses UTC

**Location:** `frontend/src/games/duel/dailyChallenge.ts` (11–12, 27–28)

`dateKey()` uses `toISOString().slice(0, 10)` (UTC). Players outside UTC get the wrong "daily" before/after local midnight.

---

### 17. `powerupsEnabled` fallback can disagree with backend

**Location:** `frontend/src/games/duel/DuelBoard.vue` (58)

```typescript
const powerupsEnabled = computed(() => props.gameState.powerups_enabled ?? props.gameState.match_format !== 'quick_duel')
```

Backend enables power-ups for quick duel when `quick_duel_loadout != 'none'` (`engine.py` 368–369). If `powerups_enabled` is missing from a stale payload, frontend hides power-up UI while backend allows them.

---

### 18. Hit sounds ignore `tick_hits` multi-hit events

**Location:** `frontend/src/games/duel/DuelBoard.vue` (237–247); `frontend/src/games/duel/duelRenderer.ts` (607–611)

Renderer processes `tick_hits` for VFX; `playGameSounds()` only reads `last_hit`. Bomb splashes / multi-target ticks produce one sound at most.

---

### 19. No UI for accessibility prefs (dead settings)

**Location:** `frontend/src/games/duel/visualPrefs.ts`; `frontend/src/games/duel/duelRenderer.ts` (3, 229, 1053)

Colorblind bullet palettes and shake intensity are read from `localStorage`, but nothing in duel UI calls `setColorblindMode`, `saveShakeIntensity`, or `setHitStopEnabled`. Users cannot configure these without devtools.

---

### 20. Countdown timer only updates on state tick, not wall clock

**Location:** `frontend/src/games/duel/DuelBoard.vue` (65–75, 996–998, 1014)

`countdownRemaining` is derived from `countdown_ends_at` vs `Date.now()` but nothing re-evaluates it between server ticks. Display can sit on the same second until the next state update.

---

### 21. Stale `ai_difficulties` when removing duel AI players

**Location:** `backend/app/services/room_service.py` — add (200–208) vs remove (261–266)

Adding a duel AI writes `ai_difficulties[player_id]`. `remove_player` only cleans that map for `tetris` and `poker`, not `duel`. Orphan entries can affect a replacement AI if IDs are reused or settings are merged oddly.

---

### 22. `tick_interval_ms()` ignores lobby `tick_ms` setting

**Location:** `backend/app/games/duel/engine.py` (384–385, 220)

`validate_settings` allows `tick_ms` 50–200 and exposes it in public state. `tick_interval_ms()` always returns `75`. The game loop uses `settings.tick_ms` for sleep, so simulation is per-tick not per-ms — but the engine API suggests a fixed 75ms rate.

---

### 23. Obstacle rotation breaks layout-seed determinism

**Location:** `backend/app/games/duel/engine.py` (1947–1961)

With `layout_seed` set, obstacles/power-ups/decoys are seeded; rotating obstacles pick `random.choice([-1, 1])` from the global RNG, so replays diverge when rotation is enabled.

---

### 24. Homing bullets ignore ghost when a decoy exists

**Location:** `backend/app/games/duel/engine.py` (1993–2009)

Homing steers toward the first enemy decoy and breaks before considering the real fighter. Ghost scrambling only applies to fighter targeting. May be intentional (decoy baits homing), but decoy always wins over ghost jitter.

---

## Low

### 25. Bombs do not interact with Mirror

**Location:** `backend/app/games/duel/engine.py` — bombs (1752–1770) vs mirror (1805–1817)

Normal bullets can be mirrored; bombs detonate on fighter contact without a mirror check. Inconsistent with "reflects incoming bullets" in rules.

---

### 26. AI draft bans are random and may duplicate opponent's ban

**Location:** `backend/app/games/duel/engine.py` (2149–2151)

AI picks `random.choice(POWERUP_TYPES)` without excluding types already banned. Wastes a ban slot; cosmetic/strategic only.

---

### 27. Solo-practice AI setup doesn't populate `ai_difficulties`

**Location:** `backend/app/services/room_service.py` (492–510 vs 200–208)

`_setup_duel_solo` adds one AI without an `ai_difficulties` entry (manual `add_ai_player` does). Falls back to global `ai_difficulty` — usually OK, but inconsistent with the manual AI path.

---

### 28. Disconnect does not pause or forfeit duel

**Location:** `backend/app/websocket/handlers.py` (133–148)

Disconnect only sets `is_connected=False` and broadcasts room update. Game loop and AI keep running; no forfeit/resign. May be intended, but there's no duel-specific handling.

---

### 29. No validation feedback for duplicate `ban_powerup`

**Location:** `backend/app/games/duel/engine.py` (817–819)

Duplicate ban attempts are silently ignored — OK, but no error feedback to client.

---

### 30. Canvas resized every animation frame

**Location:** `frontend/src/games/duel/DuelBoard.vue` (749–754)

Setting `canvas.width` / `canvas.height` every frame clears the bitmap and forces reallocation. Should only resize when container dimensions change (ResizeObserver already exists at 798–800).

---

### 31. `dangerRows` / incoming bullet heuristics are inaccurate

**Location:** `frontend/src/games/duel/DuelBoard.vue` (165–175, 335–351)

- Ignores vertical velocity (`vy`), homing, ricochets, and bombs
- Uses `bullet.y` only (not fighter height)
- `approxX = bullet.x + speed * 0.85` is a rough constant

Danger highlighting can false-positive or miss real threats.

---

### 32. Milestone stats are misleading

**Location:** `frontend/src/games/duel/stats.ts` (37–55); `frontend/src/games/duel/DuelBoard.vue` (1020–1022)

- `railgunKills` increments on activation, not kills
- `clutchHeals` triggers if heal was used anywhere in the match, not necessarily clutch

---

### 33. Phase Shift not shown in player bar badges

**Location:** `frontend/src/games/duel/DuelBoard.vue` (1130–1139); `frontend/src/types.ts` (105–127)

Backend exposes `phase_shift_active`; UI shows shield, ghost, mirror, etc., but not phase shift.

---

### 34. Freeze badge on scoreboard is ambiguous

**Location:** `frontend/src/games/duel/DuelBoard.vue` (1139)

`freeze_active` on a row could mean "you cast freeze" or "you are frozen" (backend sets `freeze_until` on the **target**). Same icon for both cases.

---

### 35. Power-up spawn toast can spam

**Location:** `frontend/src/games/duel/DuelBoard.vue` (494–504)

Notice key is `${orb.x}:${orb.y}:${orb.type}:${props.gameState.tick}`. Same orb re-broadcast across ticks can retrigger "spawned" toasts.

---

### 36. `keybinds` loaded but never persisted from UI

**Location:** `frontend/src/games/duel/keybinds.ts` (33–38); `DuelBoard.vue` (136)

`saveKeybinds` exists but is never called; custom binds cannot be changed in-app (defaults always used).

---

### 37. Duplicate `POWERUP_ACTIVATION_TICKS` constant

**Location:** `frontend/src/games/duel/powerupMeta.ts` (1); `frontend/src/games/duel/duelRenderer.ts` (119)

Same constant defined in two modules; one could drift from the other and from backend.

---

### 38. Game canvas lacks accessibility semantics

**Location:** `frontend/src/games/duel/DuelBoard.vue` (840)

`<canvas>` has no `role`, `aria-label`, or live region for critical game events (HP, round outcome). Event feed has `aria-live="polite"` but is easy to miss and incomplete.

---

### 39. Countdown / round-over overlays not announced to screen readers

**Location:** `frontend/src/games/duel/DuelBoard.vue` (996–1014)

Phase transitions ("Get ready!", "Round over", "Match over") are visual only; no `aria-live` region.

---

### 40. WebSocket action rejections often silent

**Location:** `frontend/src/views/GameView.vue` (149–153, 124–127)

Send failures show a toast. Backend rejects invalid actions during wrong phase by returning unchanged state with no error event — player gets no feedback for e.g. shooting during countdown.

---

### 41. Daily challenge can set obstacle count invisible in lobby

**Location:** `frontend/src/views/RoomView.vue` (173–181); `frontend/src/games/duel/DuelLobby.vue` (98–100)

If daily picks `bounce_house`, obstacle count is applied to settings but hidden in lobby UI (`showObstacleSetting` is false). Not wrong on backend (bounce house forces obstacles), but confusing in settings.

---

## Frontend / Backend Consistency

### Aligned (good)

- Charge tiers (`chargeTiers.ts` 6/11 thresholds ↔ `engine.py` 1139–1143)
- Power-up instant vs channeled lists and channel/effect durations (`powerupMeta.ts` ↔ `engine.py`)
- Match formats, draft, fog, shrinking arena (`rules.ts` ↔ `MATCH_FORMAT_PRESETS` / engine)
- Draw rounds: double KO → `round_winner=None`, round increments, no score change

### Minor inconsistencies

| Rule text (`rules.ts`) | Backend / UI reality |
|------------------------|----------------------|
| "Sniper is one-hit kills with a long reload" (line 36) | Sniper uses `instant_kill` on all hits, not just charged shots |
| Side swap in long matches (line 40) | Only `best_of_7` swaps every 2 rounds; not surfaced in UI |
| Sudden-death faster shrink | Backend halves shrink interval after round 3+; not mentioned in rules or UI |
| "Draw rounds replay with no score change" (line 40) | Correct behavior; wording slightly imprecise (round counter still increments) |
| `decoy` duration | Uses fallback 80 ticks because `decoy` isn't in `POWERUP_EFFECT_DURATIONS` on either side — consistent but implicit |
| `chargeEnabled` | Frontend derives from `match_format !== 'quick_duel'`; backend also respects `training_drill` / `charge_shot_enabled` |

---

## Test Gaps

| Missing coverage | Risk |
|------------------|------|
| Power-up draft completion via **tick** (AI second ban) + `pending_round_reset` | Would catch critical #1 |
| Double KO / draw round flow | Round/score/reset behavior |
| `mirror` bullet reflection | Combat correctness |
| `bounce_self_damage` ricochet self-hit | Mutator behavior |
| `side_swap_every_n_rounds` (best of 7) | Spawn/side correctness |
| Sniper / `instant_kill` mutator | One-shot rules |
| `phase_shift` movement through obstacles | Movement collision |
| Burst + bullet cap | Issue #6 |
| `remove_player` duel AI + `ai_difficulties` cleanup | Issue #21 |
| Simultaneous human `ban_powerup` race | Lock serializes, but no integration test |

Existing tests are solid for core combat, charge, shield, hazards, and AI movement/shooting heuristics (~60 engine tests, ~25 AI tests).

---

## Design Notes (not necessarily bugs)

| Topic | Location | Note |
|--------|-----------|------|
| Freeze blocks movement only | `engine.py` 1047–1048 | Frozen players can still shoot/charge; matches "stops movement" in rules |
| Pierce power-up vs spread pierce | `engine.py` 1193, 1586–1590 | Full-charge spread sets `pierce_obstacles`; pierce buff uses `_owner_has_pierce` — different mechanisms |
| Real-time both players act | `apply_action` | No turn order; both can send actions each tick — intentional for realtime |
| Rematch host-only controls | `GameView.vue`, `DuelBoard.vue` | Non-host sees "Waiting for host…" — by design |
| Duel uses tick loop, not turn AI | `handlers.py` | Duel excluded from `schedule_ai_turn`; AI runs in tick path |

---

## Recommended Fix Priority

1. **Fix draft tick path** — mirror `apply_action`: if `pending_round_reset`, call `_reset_round` before countdown (`engine.py` 2156–2158).
2. **Add regression test** — round ends → draft → AI completes ban → fighters respawn, scores unchanged until next elimination.
3. **Clear held inputs on phase/alive changes** — fix `onKeyUp` to always release charge/powerup when keys lift; call `clearHeldInputs()` in phase watcher.
4. **Disable window keyboard handlers when modals are open** — coordinate `GameView` rules modal with `DuelBoard` input.
5. **Remove double movement prediction** — pick one layer (renderer interpolation or `renderStateForFrame`, not both).
6. **Sync charge ticks from server** — add watch like powerup channel reconciliation.
7. **Apply bullet cap in `_process_burst_shots`** (or shared spawn helper).
8. **Extend `remove_player` cleanup** to include `duel` in the `ai_difficulties` branch.
9. **Tighten power-up activation** to use the same clamp logic as charge, or require `server_ticks >= required` for success.
