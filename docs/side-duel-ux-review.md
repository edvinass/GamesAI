# Side Duel — UX Review

**Date:** 2026-07-14  
**Scope:** Lobby (`DuelLobby.vue`, `RoomView.vue`), in-match UI (`DuelBoard.vue`, `duelRenderer.ts`), shell (`GameView.vue`), rules/copy (`rules.ts`, `powerupMeta.ts`)

This review focuses on **user experience** — clarity, discoverability, feedback, mobile usability, and flow — after the recent bug-fix pass.

---

## Summary

| Severity | Count |
|----------|-------|
| High | 8 |
| Medium | 18 |
| Low | 14 |

**Top themes:** mobile controls incomplete, spectator overlay blocks the action, lobby overwhelming for hosts, weak in-match teaching for power-ups/draft/shrink, and feedback that only appears during `playing` phase.

---

## High

### 1. Eliminated overlay blocks spectating
**Location:** `DuelBoard.vue` — eliminated overlay (lines 1166–1180)

When the player dies mid-round, a full opaque overlay (`background: rgba(0,0,0,0.72)`) covers the entire arena with “You were eliminated!” The round continues underneath, but the user cannot watch the fight they’re supposedly spectating. The sidebar only says “Spectating” while the main view is hidden.

**Impact:** Dead players lose the main reason to stay in the match — watching the round resolve.

**Suggestion:** Use a semi-transparent banner or side panel instead of a full-screen blocker; keep the canvas visible.

---

### 2. Touch controls have no power-up button
**Location:** `DuelBoard.vue` — touch controls (lines 1182–1228)

Mobile/tablet users get move (↑/▼) and fire (⚡) buttons, but no way to use stored power-ups without a physical keyboard. Power-up activation is bound to `E` only.

**Impact:** Mobile players cannot use a core mechanic in match modes.

**Suggestion:** Add a dedicated power-up touch button (tap vs hold, matching instant/channelled types).

---

### 3. Action feedback hidden outside `playing` phase
**Location:** `DuelBoard.vue` — `powerupNotice` (lines 977–984, 658–667)

Toasts for rejected actions (`action_rejected`), failed power-up holds, heal-at-full-HP, etc. only render when `gameState.phase === 'playing'`. During countdown, draft, or round-over, the user gets no visible feedback for invalid inputs.

**Impact:** Pressing fire during countdown feels broken — nothing happens and nothing explains why.

**Suggestion:** Show notices in all interactive phases, or add a global toast in `GameView.vue`.

---

### 4. Power-up draft lacks context and guidance
**Location:** `DuelBoard.vue` — draft overlay (lines 1101–1123)

The draft shows “Ban a power-up” and a flat grid of 18 equal buttons with names only. There is no explanation of *why* drafting happens, what banning does, tier/rarity, or which picks are strong in the current mutator.

**Impact:** New players face a wall of unexplained choices; experienced players get no strategic shortcuts.

**Suggestion:** Add a one-line explainer (“Remove one orb type from the pool for the rest of the match”), group by tier, show icons/colors, and optionally mark already-banned types.

---

### 5. Lobby settings are overwhelming
**Location:** `DuelLobby.vue` — host settings block (lines 118–227)

Hosts see 12+ controls in one card: format, mutator, secondary mutator, loadout, drill, theme, speed, AI difficulty, AI personality, obstacles, rotation, tutorial — plus the power-up encyclopedia below. No presets, no “recommended” path, no progressive disclosure.

**Impact:** High cognitive load before the first match; casual players may not understand interactions (e.g. drill + mutator + secondary).

**Suggestion:** Group into “Match”, “Arena”, “AI”, “Advanced”; add 2–3 curated presets (Casual, Ranked, Practice).

---

### 6. Non-host lobby is mostly empty
**Location:** `DuelLobby.vue` — `v-if="isHost"` on settings (line 118)

Guests only see the player list, validation banner, and “add AI” (host-only). They cannot preview match format, mutator, theme, or whether draft/shrink are enabled until the game starts.

**Impact:** Joiners don’t know what they’re signing up for; feels like waiting in a void.

**Suggestion:** Read-only summary card for non-hosts (“Host selected: Best of 5 · Chaos · Neon theme”).

---

### 7. Controls hint ignores touch layout
**Location:** `DuelBoard.vue` — `controls-hint` (lines 1283–1298)

The sidebar always references keyboard bindings (`W/S`, `Space`, `E`) even when touch controls are visible (`showTouchControls`).

**Impact:** Mobile users see irrelevant instructions; reinforces that the game is keyboard-first.

**Suggestion:** Branch hints: “Use on-screen arrows + ⚡” when touch mode is active.

---

### 8. Key rebinding is display-only
**Location:** `DuelBoard.vue` — visual prefs (lines 935–957); `keybinds.ts`

The settings panel shows current bindings and a “Reset keybinds” button, but there is no UI to *change* bindings — only reset to defaults. Label says “Controls:” but implies customization.

**Impact:** False affordance; accessibility users who need remapping are stuck.

**Suggestion:** Either add capture UI per action or remove rebind copy until supported.

---

## Medium

### 9. UI clutter stacks at top of arena
**Location:** `DuelBoard.vue` — powerup slot, notices, coach hint, match bar

During play, the top-left has the power-up slot card; top-center has spawn/collect toasts; bottom-left has event feed; match bar has format/mutator/shrink warning/settings. On smaller viewports these compete for attention.

**Impact:** Important warnings (shrink, incoming power-up) can be missed behind panels.

**Suggestion:** Consolidate HUD into zones with priority rules; collapse power-up slot to icon-only when inactive.

---

### 10. Effect badges are cryptic emoji-only
**Location:** `DuelBoard.vue` — player score row (lines 1259–1270)

Active buffs show as emoji (`🛡`, `❄→`, `◇`) with `title` tooltips only on hover. No text labels, durations, or grouping. Many simultaneous effects overflow the score row.

**Impact:** Players can’t parse fight state at a glance; mobile has no hover for tooltips.

**Suggestion:** Show timed buff chips (already exist on canvas for *your* buffs — extend pattern to scoreboard) or a compact “effects” popover.

---

### 11. Danger highlighting is unexplained
**Location:** `duelRenderer.ts` (lines 1212–1216); `DuelBoard.vue` — `dangerRows`

The player’s ship rows pulse red when bullets are incoming, but nothing tells the user what the red flash means. No legend, no first-time tooltip.

**Impact:** Subtle but useful feedback is invisible to players who don’t infer it.

**Suggestion:** One-time coach line: “Red rows = incoming fire” or a HUD legend toggle.

---

### 12. Shrink warning timing may be too late
**Location:** `DuelBoard.vue` — `shrinkWarningActive` (lines 224–227)

Warning appears only when shrink is ~2.4s away (`2400 / tickMs`). First-time shrink in a match may surprise players who haven’t internalized hazard zones.

**Impact:** Arena shrink feels sudden despite a late badge.

**Suggestion:** Earlier soft warning (“Arena will shrink soon”) and/or persistent hazard-zone legend after first shrink.

---

### 13. Tutorial hints are brief and round-1 only
**Location:** `DuelBoard.vue` — `updateCoachHint` (lines 243–271)

Tutorial mode shows hints only on round 1 countdown and first ~120 ticks of play. Power-up draft, charge tiers, fog, bounce house, and ban phase get no coaching.

**Impact:** Tutorial checkbox oversells how much guidance players receive.

**Suggestion:** Phase-specific hints (draft, first shrink, first power-up collected) or rename to “Opening tips”.

---

### 14. Secondary mutator invisible in match
**Location:** `DuelBoard.vue` — match bar (line 916)

Only primary mutator is shown (`MUTATOR_LABELS[gameState.mutator]`). Secondary overlay (Fog on Classic, Chaos boost) is not surfaced in the HUD.

**Impact:** Players forget stacked rules mid-match.

**Suggestion:** Show stacked mutators in match bar, e.g. `Classic + Fog`.

---

### 15. Quick duel loadout not shown in match
**Location:** Lobby `quickDuelLoadout`; `DuelBoard.vue`

If host picks a starting power-up loadout for quick duel, in-match UI doesn’t indicate it. `powerupsEnabled` is boolean with no loadout context.

**Impact:** Players don’t know a loadout rule is active.

**Suggestion:** Match-bar chip: “Loadout: Shield start”.

---

### 16. Fog mode has weak in-game signaling
**Location:** `duelRenderer.ts` — fog rendering; match bar

Fog mutator/overlay jitters enemy Y position, but HUD only shows a “Fog” tag. No explanation that aim rows are unreliable or that bullet trails reveal true position.

**Impact:** Fog feels random/unfair without teachable counterplay.

**Suggestion:** First-round fog tip; optional “imprecise enemy” icon near opponent score.

---

### 17. Auto-release power-up after 180ms may surprise users
**Location:** `DuelBoard.vue` — `watch(powerupReady)` (lines 671–684)

When channel completes, power-up auto-fires after 180ms without explicit “release now” requirement in UI (bar says “RELEASE!” but auto-release may feel unintended).

**Impact:** Players learning hold-to-activate may not realize they can release early/late intentionally.

**Suggestion:** Make auto-release optional in settings, or lengthen delay; clearer “Auto-releasing…” state.

---

### 18. “Same seed rematch” is jargon
**Location:** `DuelBoard.vue` — finished overlay (lines 1156–1158)

Button label assumes players understand layout seeds and deterministic obstacle placement.

**Impact:** Casual players won’t know what it does vs normal Rematch.

**Suggestion:** “Rematch (same arena layout)” with subtitle tooltip.

---

### 19. Match-end career stats are dense and unexplained
**Location:** `DuelBoard.vue` — milestones (line 1150)

One long line: “Career: X matches · Y perfect rounds · Z crits · railgun kills · clutch heals” with no definitions. Stats are local-only (localStorage) but presented like global progression.

**Impact:** Confusing metrics; “railgun kills” / “clutch heals” need context.

**Suggestion:** Break into labeled chips; note “Saved on this device only”.

---

### 20. Non-host match end has no agency
**Location:** `DuelBoard.vue` — finished overlay (line 1163)

Losers/non-hosts see “Waiting for host…” with no option to leave except header “Lobby”. No estimated wait, no “request rematch” ping.

**Impact:** Passive dead-end after a long match.

**Suggestion:** Prominent “Return to lobby” for non-hosts; optional rematch request button.

---

### 21. Opponent disconnect/forfeit not explained
**Location:** Backend forfeit on disconnect; `DuelBoard.vue` / `GameView.vue`

If a human disconnects, the backend forfeits the round, but the remaining player may not see a clear “Opponent disconnected — you win” message.

**Impact:** Abrupt round/match end feels like a bug.

**Suggestion:** Event-feed / overlay copy when win reason is disconnect.

---

### 22. Event feed competes with touch controls
**Location:** `DuelBoard.vue` — event feed (lines 1095–1099, 1402–1411)

Combat log sits bottom-left; touch move buttons sit bottom-left on mobile. Feed is `pointer-events: none` but visually overlaps.

**Impact:** Harder to read log on phone; cluttered corner.

**Suggestion:** Move feed above touch cluster or top-right on narrow screens.

---

### 23. Power-up encyclopedia buried in lobby scroll
**Location:** `DuelLobby.vue` / `PowerupEncyclopedia.vue`

Useful reference is a collapsed `<details>` below a long settings form. In-match, Rules modal is separate and may not include per-power-up detail.

**Impact:** Players don’t discover encyclopedia; learn by trial and error in combat.

**Suggestion:** Link “Browse power-ups” from match bar or first power-up collected; surface in Rules modal.

---

### 24. Daily challenge apply is opaque
**Location:** `DuelLobby.vue` — daily banner (lines 110–116)

“Use daily” applies format/mutator/obstacles/seed with no preview diff or confirmation. Host may not notice what changed.

**Impact:** Accidental misclick changes entire lobby setup silently.

**Suggestion:** Confirmation popover listing what will change vs current settings.

---

### 25. Arena theme picker has no live preview
**Location:** `DuelLobby.vue` — arena theme select (lines 174–181)

Four themes change backdrop/grid/hazard colors, but lobby only shows a dropdown label — no swatch or mini-preview.

**Impact:** Theme choice is guesswork until match starts.

**Suggestion:** Theme swatches or mini canvas preview in lobby.

---

### 26. Training drill effects not communicated in match
**Location:** Lobby `trainingDrill`; `DuelBoard.vue`

Drills like “Dodge only”, “Aim trainer”, “Power-up sandbox” alter rules substantially, but match HUD doesn’t show active drill name or constraints (e.g. movement locked).

**Impact:** Players forget why movement/shooting feels different.

**Suggestion:** Persistent drill badge in match bar + one-line constraint reminder.

---

## Low

### 27. Match bar doesn’t show “rounds to win”
**Location:** `DuelBoard.vue` — match bar (line 912)

Shows `Round 2 · Best of 5` but not “first to 3 wins”. Score row shows `2/3` per player — good — but match bar could reinforce win condition.

---

### 28. Round-over recap lacks winner emphasis
**Location:** `DuelBoard.vue` — round recap (lines 1134–1141)

Both players’ stats listed identically; winner’s row isn’t highlighted. Draw vs win text is clear, but stats block is neutral.

---

### 29. Countdown overlay is minimal
**Location:** `DuelBoard.vue` — countdown (lines 1125–1128)

Large number + “Get ready!” only. Doesn’t remind of round number, score, or banned power-ups going into next round.

---

### 30. Coach hint can overlap power-up notices
**Location:** `DuelBoard.vue` — coach hint (bottom center) vs powerup notice (top center)

Different Y positions — OK — but on short viewports power-up slot + charge bars + hints stack vertically and reduce playable canvas feel.

---

### 31. Visual prefs gear lacks visible label
**Location:** `DuelBoard.vue` — match bar (lines 925–932)

Icon-only ⚙ button; `aria-label` exists but sighted users may not discover accessibility settings.

---

### 32. Sound mute is emoji-only
**Location:** `DuelBoard.vue` — sound toggle (lines 917–924)

Same discoverability issue as gear; no “Sound” text on desktop.

---

### 33. Header clutter during fullscreen duel
**Location:** `GameView.vue` — header meta (lines 186–192)

“Voice chat optional — text Q&A built in” shows during fast-paced duel where horizontal space is precious.

---

### 34. Rules modal is disconnected from in-game coach
**Location:** `GameView.vue` — Rules button; `DuelBoard.vue` — tutorial hints

Two parallel teaching systems; Rules is comprehensive but modal blocks input; coach hints are minimal. No cross-link (“See Rules for full power-up list”).

---

### 35. HP pips scale poorly for quick duel (1 HP)
**Location:** `DuelBoard.vue` — hp-bar (lines 1251–1257)

Single pip works but looks sparse; no numeric `1/1` fallback for clarity.

---

### 36. Ban waiting state doesn’t show opponent progress
**Location:** `DuelBoard.vue` — draft waiting overlay (lines 1116–1123)

Shows ban list when populated, but no spinner/progress for “1/2 players banned” or AI ban delay feedback.

---

### 37. `powerup-callout` for arena orb easy to miss
**Location:** `DuelBoard.vue` — arena power-up callout (lines 1025+)

Small callout when orb is in arena and player has empty slot — competes with many HUD elements; spawn toast at top may duplicate.

---

### 38. Charge tier labels assume prior knowledge
**Location:** `DuelBoard.vue` — charge bar (line 1070)

Shows tier label + hint from `chargeTiers.ts` but no persistent explanation of crit row / spread tiers for new players.

---

### 39. AI personality has no in-game label
**Location:** Lobby `aiPersonality`; in-match UI

“Agressive / Turtle / Trickster” selected in lobby never appears in match — missed flavor and expectation-setting.

---

### 40. Player bar wraps awkwardly on narrow desktop
**Location:** `DuelBoard.vue` — `@media (max-width: 640px)` (lines 2164–2173)

Only stacks player bar; canvas HUD doesn’t adapt layout for 640–900px widths where sidebar + canvas squeeze.

---

## Accessibility (UX-related)

| Issue | Location | Note |
|-------|----------|------|
| Canvas game state opaque to screen readers | `DuelBoard.vue` | `aria-label` on canvas is static; HP, position, threats not announced |
| Phase announcements use `aria-live="assertive"` | `DuelBoard.vue` | Good for countdown; may interrupt during rapid round transitions |
| Effect badges rely on `title` tooltips | Player bar | Not keyboard/touch accessible |
| Color-only danger rows | `duelRenderer.ts` | Red pulse may be weak for color vision; colorblind mode affects bullets not danger |
| Low contrast on `overlay-hint` | Overlays | `var(--text-muted)` on dark overlay can be borderline |

---

## Positive UX (keep / build on)

- **Power-up slot card** — Strong visual for stored orb, tier color, hold vs instant copy.
- **Active buff rings** on canvas — Clear duration UI for local player.
- **Round recap overlay** — Useful stats between rounds.
- **Power-up encyclopedia** — Good reference content when found.
- **Shrink warning pill** — Right idea; needs earlier trigger.
- **Touch fire hold** — Charge-on-hold works on touch fire button.
- **Validation banner in lobby** — Clear ready/not-ready state.
- **Daily challenge banner** — Good engagement hook for hosts.
- **Event feed** — Nice combat narrative when readable.
- **Recent fixes** — Draw text, draft arena reset, modal input suspend, visual prefs panel are steps in the right direction.

---

## Recommended priorities

1. **Spectator-friendly death state** — don’t opaque-block the canvas.
2. **Mobile power-up control** — parity with keyboard.
3. **Global/toast feedback** — especially countdown and draft phases.
4. **Draft UX pass** — explain, group, show tiers/icons.
5. **Lobby simplification** — presets + guest-visible summary.
6. **HUD cleanup** — mutator stack, drill badge, touch-aware hints, less top clutter.

---

## Out of scope (design intent, not UX bugs)

- Host-only rematch controls (acceptable if communicated)
- Real-time dual input with no turn indicator (genre convention)
- Local-only career milestones (fine if labeled as such)
- Power-up complexity (game depth is high by design — UX should teach, not remove)
