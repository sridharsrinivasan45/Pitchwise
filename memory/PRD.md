# PitchWise — PRD & Build Log

## Problem Statement (verbatim intent)

Build **PitchWise**, an AI-native cricket intelligence platform for IPL fans, that:
- Delivers a proprietary player impact engine wrapped in an explainable AI experience
- Positions as *"The FotMob for cricket — cricket, explained."*
- Wins the Emergent x Raj Shamani Build Challenge
- Becomes the daily companion for cricket fans during every IPL season

## Product Principles (locked)

1. Every rating must be explainable — traceable to specific balls
2. Every screen teaches something Cricbuzz cannot
3. Debate is good; artificial controversy is not
4. Every AI opinion is backed by evidence from the engine
5. Engine is the tech moat; product is the experience around it

## Core Users

IPL fans (primary), fantasy players (revenue path), analysts/journalists (post-MVP)

## Success Metric

A fan opens PitchWise before Cricbuzz after a match, spends 5–10 minutes exploring,
shares at least one insight, and returns for the next game.

## MVP Scope (locked — 4 features)

1. **Live Match Pulse** — momentum chart, ambient AI narration, top impact ratings updating ball-by-ball
2. **The "Why?" Sheet** — explainable rating breakdown with clickable ball-level evidence
3. **Time Machine** — 6 curated iconic IPL matches replayable ball-by-ball with live-evolving ratings
4. **Ask PitchWise** — grounded Cmd+K AI analyst with citations

Supporting: Innings DNA share card (distribution loop), Historical Parallels (moat feature), minimal Player Profile.

## Navigation

- `/` — Live (default)
- `/time-machine`
- `/players` + `/players/:id`
- `/about`
- Cmd+K persistent Ask PitchWise (post-M7)

## Architecture

- **Backend:** FastAPI + Motor (async MongoDB). Modular: `core/`, `engine/adapter.py`, `engine/contracts.py`, `routes/`, `data/`.
- **Frontend:** React 19 + CRA + Tailwind + shadcn primitives + Framer Motion + Recharts. Dark theme with amber accent (`#F5A623`), Fraunces + JetBrains Mono + Inter Tight.
- **Engine integration:** Adapter pattern. `engine/adapter.py` is the ONLY caller of engine internals. Contracts in `engine/contracts.py`.
- **AI:** Claude Sonnet 4.5 via Emergent Universal LLM key (integration deferred to M5+).

## Database (MongoDB) — 5 collections

`matches`, `balls`, `ratings_snapshots`, `players`, `moments`.
Indexed for match-scoped ball, player, sequence, impact-score queries.

## Build Order (12 milestones)

M0 Skeleton · M1 Data Foundation · M2 Live Screen (Static) · M3 Replay Ticker (SSE)
M4 WhySheet (crown jewel) · M5 AI Narrator · M6 Historical Parallels · M7 Ask PitchWise
M8 Time Machine Grid · M9 Player Profile · M10 Innings DNA Card · M11 About + Polish · M12 Testing

---

## Completed

### M0 — Skeleton (✔ verified 2026-07-02)
- FastAPI modular app with `/api/health` returning 200
- MongoDB connection via Motor, single client, PyObjectId + BaseDocument helpers
- React router with 5 routes (`/`, `/time-machine`, `/players`, `/players/:id`, `/about`)
- Dark aesthetic: amber accent, Fraunces editorial + JetBrains Mono + Inter Tight
- TopNav (glassmorphic, sticky) with Ask PitchWise button placeholder
- All routes render, no console errors (verified via screenshot on external URL)

### M1 — Data Foundation (✔ verified 2026-07-02)
- Seed script `data/seed_curated.py` — Rinku's 5-sixes match (KKR vs GT, 2023-04-09)
  - 119 balls (2nd innings, 20 overs)
  - 20th over hand-encoded: 6, 6, 6, 6, 6 by Rinku off Yash Dayal
  - Pressure index, difficulty, WP-before/after computed per ball
  - Ratings snapshots (238) + Moments (10) auto-derived
- Adapter (`engine/adapter.py`) exposes stable contract to product code:
  - `list_matches`, `get_match`, `stream_balls`, `get_ball_by_id`
  - `get_match_state`, `get_moments`, `get_rating_breakdown`, `get_impact_board`
- Contracts (`engine/contracts.py`): `BallEvent`, `RatingBreakdown`, `RatingComponent`, `ImpactRow`, `MomentumPoint`, `Moment`, `MatchState`, `MatchSummary`
- API endpoints verified via curl on external URL:
  - `GET /api/matches?featured=true` → 1 match
  - `GET /api/matches/{id}` → full summary
  - `GET /api/matches/{id}/state` → 119 momentum points, 6 top impact rows
  - `GET /api/matches/{id}/moments` → 10 flagged moments, Rinku sixes ranked top
  - `GET /api/matches/{id}/impact-board` → Rinku 9.9, Gurbaz 9.9, Nitish 8.6, Russell 8.6, ...
- Live page consumes real API and renders the Rinku 5 Sixes card

## Backlog (P0/P1)

- **NEXT: Stage 5 validation** — screenshot-and-verify all four surfaces (Live, Replay, Momentum, Impact Board, WhySheet) against the real engine end-to-end
- P0 M4 WhySheet + PitchAnimation (crown jewel)
- P0 M7 Ask PitchWise + M5 Narrator (needs Emergent LLM key wired)
- P1 M6 Historical Parallels (needs 5 more curated matches ingested)
- P1 M10 Innings DNA Card renderer
- P2 M9 Player Profile depth (spider chart, career line)

## Deferred / Removed from MVP

Auth, notifications, social layer, multi-league (BBL/PSL/WPL), video highlights, fantasy team
builder, blog, settings, onboarding tour, dark-mode toggle.

## Next Immediate Tasks (Engine integration, awaiting user handoff)

1. User drops real Python engine into `backend/engine/core/`
2. Rewire `engine/adapter.py` internals to call the real engine (same contract, same 8 methods)
3. Sanity-check all 4 milestones (M1 endpoints, M2 static UI, M3 SSE replay, M4 WhySheet) with the new engine outputs
4. Update seed → ingest more matches (target: 6 curated matches for Time Machine)

## Milestones Completed

### M4 — WhySheet + PitchAnimation (✔ verified 2026-07-02)

**Backend (adapter interface UNCHANGED, only additions):**
- `Moment` contract extended with optional `batter_id` + `bowler_id` (populated in seed) — enables correct player attribution when a moment card is tapped
- New route `routes/ratings.py` mounted at `GET /api/ratings/{match_id}/{player_id}?at_ball_id=xxx`
- Delegates entirely to `adapter.get_rating_breakdown` — no engine logic here

**Frontend:**
- `components/rating/WhySheet.jsx` — the crown jewel
  - Slides in from the right (spring 260/30), Esc to close, backdrop click to close
  - **Header:** team badge · role, player name (editorial 2xl), rating (huge amber 4xl), delta (green/red), base rating (dim)
  - **Headline:** ONE commentator-quality sentence generated deterministically from the components. Examples:
    - *"Rinku Singh is rated 9.9 because 5 sixes in the death overs happened when the match hung on every ball."*
    - Templates for "wickets in death," "boundary-heavy hand," and generic top-contribution fallback
  - **Rating evolution** — mini sparkline shows the player's rating trajectory across their innings, base → final
  - **"The moment that mattered most"** — highlighted card with `PitchAnimation` on left + humanized description + raw impact weight
  - **Counterfactual** — *"Without this one delivery, Rinku Singh would be rated around 9.1 instead of 9.9."*
  - **"What lifted the rating"** — top 5 positive components, each row: label + over.ball + phase + weight + one-sentence reason
  - **"What hurt the rating"** — top 4 negatives (only shown when present)
  - **Footer:** *"Every explanation traces to a ball. No paraphrasing."*
- `components/rating/PitchAnimation.jsx` — minimal SVG cricket-field diagram (aerial view)
  - Deterministic geometry from ball outcome: 6 → arc to boundary, 4 → shorter arc, wicket → stumps hit + red X, dot → no shot
  - Framer motion pathLength animations for delivery + shot
  - No fabricated data, no ball-tracking pretense
- `humanizeComponent(reason_code)` maps engine codes to plain-English micro-explanations (PRESSURE_BOUNDARY, DOT_UNDER_PRESSURE, WICKET_KEY_MOMENT, BOUNDARY, ROTATE_STRIKE, CONCEDED_BOUNDARY, CONCEDED_MINOR)
- `MomentCard` now clickable → opens WhySheet for the moment's attributed player (batter for boundaries/turning points, bowler for wickets)
- `RatingBadge` `onExplain` wired throughout — impact-board taps + moment-card taps both open the sheet
- Fixes applied: hooks declared before early returns (React rule of hooks); breakdown state cleared on player change; ESLint hoisted Recharts render-prop components to module scope

**Verified via screenshots:**
- Impact-board Rinku tap → sheet shows correct headline, 5 sixes in death overs, counterfactual 9.1 vs 9.9, pitch animation of a six trajectory
- Moment-card tap → correctly opens the batter's sheet (not the top-rated keeper), attribution via `moment.batter_id`
- Zero console errors after fixes; ESLint clean (only ignored shadcn `ui/` warnings remain)

**Product principles verified for M4:**
- One question answered ("Why is this player rated this way?") ✓
- Cricket-fan-comprehensible, no data-scientist jargon ✓
- Commentator tone (headline, humanized micro-explanations) ✓
- Every claim traceable to a ball_id in the components list ✓
- No invented explanations; deterministic templates only ✓
- Clarity over complexity — one big pitch animation, one headline, one evolution chart, three lists ✓

## Milestones Completed

### M3 — Replay Ticker (SSE) (✔ verified 2026-07-02)

**Backend (adapter interface UNCHANGED):**
- New route `routes/stream.py` mounted at `GET /api/matches/{match_id}/stream?from_ball=0&speed=1&mode=replay`
- Server-Sent Events: emits `meta` event with total_balls at connection, then one `tick` event per ball at cadence `0.9s / speed`, then an `end` event
- Each tick payload: `{seq, total, ball, state:{current_over,current_ball,latest_ball_id,top_impact,momentum,latest_moment}, narration}`
- Static narration rules (`_narration_for`) — event-based lines placeholder until M5 AI narrator takes over
- Client disconnect honored via `Request.is_disconnected()`
- SSE headers: `Cache-Control: no-cache`, `X-Accel-Buffering: no`, `Connection: keep-alive`

**Frontend:**
- `hooks/useMatchStream.js` — EventSource wrapper with clean lifecycle:
  - Auto-plays on mount, streams incrementally, closes on unmount
  - `play` / `pause` / `setSpeed` / `restart` / `seekToBall` API
  - Speed change reopens the stream from the current cursor (seamless)
- `components/live/ReplayControls.jsx` — big amber play/pause button, replaying/paused/complete status, ball N/M counter, over.ball display, animated progress ribbon, speed chips (0.5×/1×/2×/4×), "Skip to the finish" button (jumps to ball 108 = start of over 19)
- `MomentumChart` — added `live` prop; when live, a pulsing amber "live head" reference dot marks the current ball tip
- `ImpactBoard` — added `layout` + `AnimatePresence` for spring reorder when ratings swap; "ON STRIKE" chip + amber outline on the batter facing the current ball

**Verified via screenshots:**
- Mid-innings replay: Over 6.3, Venkatesh on strike with amber outline, curve extending, live-head pulse at tip, controls showing "REPLAYING · Ball 33/119"
- Death-over replay at 2×: Over 20.4, narration "SIX at O20.4. Rinku is rewriting this over — pressure 9.9", 4 amber dots on chart, Rinku at 9.2 +0.77 with ON STRIKE badge
- Completed state: Ball 119/119, control switches to restart icon, Rinku *reordered* from #3 → #1 (Framer layout animation), all 5 death-over amber dots visible
- Zero console errors; ESLint clean across `hooks/`, `components/live/`, `pages/`

## Milestones Completed

### M2 — Live Screen (Static) (✔ verified 2026-07-02)

**Backend tuning (placeholder engine only):**
- Dampened rolling rating delta by 0.35 so ratings differentiate rather than saturate at 9.9
- Boosted over-20 Rinku impact deltas and increased wicket penalties so the placeholder tells the right story
- Rating breakdown component `weight` still records the raw contribution (unchanged) — only the trajectory scaling changed

**Frontend components (all reusable):**
- `lib/format.js` — over notation, delta formatting, rating tone, moment type labels
- `components/rating/RatingBadge.jsx` — tappable rating tile with hot/warm/neutral tones, Framer animation on rating change, size variants sm/md/lg. This is the interaction backbone.
- `components/rating/Sparkline.jsx` — pure-SVG inline sparkline with amber fill for rising trends
- `components/live/MatchHeader.jsx` — teams, score, current over, Time Machine badge, venue
- `components/live/NarrationLine.jsx` — animated one-line narration surface (static text in M2, AI in M5)
- `components/live/MomentumChart.jsx` — full-width Recharts area chart of win probability with amber gradient, moment reference dots (amber for turning points, pink for boundary streaks), hover tooltip
- `components/live/ImpactBoard.jsx` — 6-card grid with team+role chip, name, sparkline, RatingBadge; entrance stagger animation
- `components/live/MomentCard.jsx` — moment type, over.ball, impact score, narrative, hot border for turning points

**Live page:**
- Loads featured match, full state, top 6 moments in parallel
- Renders header → narration → momentum chart → impact board → moment strip (top moment + 3 also-decisive)
- Loading, error, and empty states handled
- Footer credits the "PitchWise impact engine · adapter v0.1 (placeholder)" — the abstraction is visible in the UI

**Verified:**
- Screenshot on external URL shows the WP curve rising from ~40% through 19 overs and *spiking vertically* in the 20th (5 amber dots for Rinku sixes)
- Impact board: Rinku 9.9 with +0.74 delta (rising, amber-highlighted), Gurbaz 9.9 flat, Venkatesh 9.4, then decliners
- Moment cards render with impact scores 8.7–8.8, all correctly attributed to the 20th over
- Zero console errors on load
- ESLint clean across all M2 files

**Known M2 limitations (deferred, not blocking):**
- Moment narratives are placeholder — 4 of the "also decisive" moments say near-identical text because the placeholder engine only differentiates on WP swing. Real engine + AI narrator (M5) will fix this.
- Rating badge tap has `onExplain` prop wired but no handler yet — WhySheet ships in M4.
- Momentum dots are not click-to-jump — that interaction ships with M3+M4.


---

### Session 2026-02 — Product-experience polish (before Milestone 5)

### Fix 1: Historical matches now open in Live (P0)
- Root cause: `Live.jsx` ignored the `?match_id=` query param — always fetched the featured match. Fallback was also broken: `if (!featured.length)` was checking `.length` on an object `{matches, total}`, so it always short-circuited.
- Also: `skipTarget` variable was referenced but never defined; the Skip-to-finish button used a hardcoded ball index (244) specific to the Rinku match.
- Fix: `Live.jsx` now reads `useSearchParams()`, loads the requested match, falls back to featured only when no query param is present, and computes `skipTarget` dynamically via `GET /api/matches/{id}/skip-to-death`. `ReplayControls` conditionally renders the Skip button.
- Verified by testing_agent iteration_6 across 4 distinct matches (featured + 3 historical) + Time Machine navigation.

### Fix 2: WhySheet 404 on rating clicks (P0, surfaced during Fix 1 verification)
- Root cause: `balls.ball_uid` was ingested as `<m>-i<inn>-<legal_num>` (e.g. `1535465-i2-109`), but `ratings_snapshots.after_ball_id` and `moments.ball_id` were written by the engine pipeline in `<m>-i<inn>-o<over>.<ball>` format. The adapter surfaced the balls-collection format as `latest_ball_id`, so WhySheet's snapshot lookup never matched.
- Fix (adapter-only, no engine change): added `_ball_uid(b)` that synthesizes the canonical over.ball format. `_ball_doc_to_event`, `momentum` points, and `latest_ball_id` all use it. Also added a graceful fallback in `get_rating_breakdown`: unknown `at_ball_id` now falls back to the latest snapshot for that player instead of 404.
- Follow-up cosmetic: `ballOverParts` in `WhySheet.jsx` now strips the `"o"` prefix so "Over 3.4" renders (previously "Over NaN.4").
- Verified by testing_agent iteration_7 (backend + frontend) and self-screenshot: "Boundary at Over 1.3", rating badge 1.4, positives/negatives populated.

### Report 2: Career rating calibration diagnosis (no code change)
- Kohli's career rating showed 4.85 and Bumrah's 5.68 — the user flagged this as failing a sanity check.
- Root cause diagnosed: **product-layer aggregation**, not engine methodology. We compute `mean(overall_rating)` across matches, but `overall_rating = 5 + 5*tanh(match_total_wpa / 0.15)` is nonlinear + bounded. Averaging bounded/saturating quantities is classic Jensen collapse toward 5. Compounded by WPA being roughly zero-sum within a match.
- The engine already provides the correct aggregation shape: `build_season_ratings()` — average WPA first, shrink by `n/(n+k)`, then apply `wpa_to_rating(..., scale=0.05)`.
- Applying that same aggregator to full career (not just a season) yields **Kohli 6.6, Bumrah 8.5** — passes intuitive sanity check.
- **No code changed yet** — full diagnosis in `/app/memory/CAREER_RATING_DIAGNOSIS.md`. Awaiting user approval before applying the fix in `routes/players.py`.

### Fix 3: Career rating aggregation (P1) — APPROVED & IMPLEMENTED
- `routes/players.py` now imports `engine.core.ratings_from_wpa.wpa_to_rating` (unchanged engine function) and applies it at the correct aggregation stage.
- New `_career_rating(avg_wpa, n_matches)` helper mirrors `build_season_ratings`: `reliability = n/(n+5)`, `career_rating = wpa_to_rating(avg_wpa * reliability, scale=0.05)`.
- List endpoint groups on `avg_wpa` (engine currency) instead of `avg overall_rating`. Sort keys unchanged (rating/matches/name).
- Profile endpoint returns `career.avg_rating`, `career.avg_batting`, `career.avg_bowling` all computed via the same aggregator on their respective WPA columns. Also exposes `career.avg_wpa` for auditability. `career.best_rating` (peak single-match) unchanged.
- Sanity check on well-known players: Kohli 6.63, Bumrah 8.54, Dhoni 5.06 (defensible — his median per-match WPA is negative), AB de Villiers 9.57, Sunil Narine 9.12, Andre Russell 8.78, Rashid Khan 9.31. All within expected ranges.
- Engine `core/` untouched. Verified by testing_agent iteration_8.

### Fix 4: Momentum chart innings-break divider (P1) — DONE
- `MomentumChart.jsx` now parses innings from ball_id (`-i(\d+)-`), detects innings transitions, and renders a dashed vertical `ReferenceLine` with "Innings break" / "Super over" labels for each transition.
- Verified visually and by testing_agent iteration_8 across historical + featured matches.

### Still up next
- ✅ Historical matches load in Live (verified)
- ✅ WhySheet works on any match (verified)
- ✅ Career rating aggregation uses engine methodology (verified)
- ✅ Momentum chart innings-break divider (verified)
- ✅ Live empty state + last-match persistence, no hardcoded ids (verified iter 9)
- ✅ **Milestone 5 — AI Narrator (evidence-grounded explanation layer)** (verified iter 10, 22/22 backend, 100% frontend)
  - Deterministic template-first pipeline: `build_evidence → render_verdict/turning/players → _polish_one (Claude Sonnet 4.5) → _verify_polished`
  - LLM polish silently falls back to template on any grounding-verifier failure
  - Verifier enforces: (a) every number in polished output exists in evidence dict, (b) hard-blocked wordlist (`\b(brilliant|shocking|thrilling|...)\b`)
  - New endpoint: `GET /api/matches/{id}/narration?polish=<0|1>&refresh=<0|1>`, cached in `db.narrations`
  - Time Machine cards left-join cached verdict; Live page renders `MatchExplanation` between MatchHeader and MomentumChart (Score → Verdict → Momentum → Impact Board)
  - Verified across 5 IPL archetypes: miracle_chase (1359487), runs_thriller (1359542), one_sided/batting-dominated (1082591, 1082596), bowling_defence (1535465), super_over (1178426)
- 🛑 STOP for user review before any additional features
- ✅ **UX polish pass (10 highest-impact improvements)** (verified iter 11, all 10 items PASS after RatingBadge fix)
  - #1 Mobile bottom nav (P0) · #2 Match Verdict skeleton loading (P0) · #3 Live empty-state balance (P0)
  - #4 Match Header mobile stacking · #5 Time Machine 2-row filter layout · #6 Archetype chip on cards
  - #7 Global focus-visible outlines · #8 RatingBadge equal-width (64/88/128 min-w) · #9 Player Profile skeleton + tenure chronology
  - #10 Ask PitchWise "Coming soon" affordance · bonus: MomentumChart mobile height + TimeMachine grid skeleton
- 🛑 STOP for user review after polish pass
- 🟠 Ask PitchWise (Cmd+K Analyst) — next
- 🔵 Historical Parallels, Innings DNA share card
