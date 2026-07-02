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

- P0 M4 WhySheet + PitchAnimation (crown jewel — clickable rating breakdown with per-ball evidence)
- P0 M4 WhySheet + PitchAnimation (crown jewel)
- P0 M7 Ask PitchWise + M5 Narrator (needs Emergent LLM key wired)
- P1 M6 Historical Parallels (needs 5 more curated matches ingested)
- P1 M10 Innings DNA Card renderer
- P2 M9 Player Profile depth (spider chart, career line)

## Deferred / Removed from MVP

Auth, notifications, social layer, multi-league (BBL/PSL/WPL), video highlights, fantasy team
builder, blog, settings, onboarding tour, dark-mode toggle.

## Next Immediate Tasks (M4 kick-off, awaiting user green light)

1. `GET /api/ratings/{match_id}/{player_id}?at_ball_id=xxx` — return the full RatingBreakdown from the adapter
2. `WhySheet` component — slide-up sheet with base rating → component list → final rating → similar-innings placeholder
3. `PitchAnimation` component — SVG pitch diagram, ball trajectory line, shot arc animated
4. Wire RatingBadge onExplain to open WhySheet with the correct player + current at_ball_id
5. Wire momentum chart moment dots to open the WhySheet for that ball's key player

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
