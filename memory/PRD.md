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

- P0 M2 Live Screen (Static): momentum chart, RatingBadge, ImpactBoard, MomentCard
- P0 M3 Replay Ticker (SSE endpoint + frontend hook)
- P0 M4 WhySheet + PitchAnimation (crown jewel)
- P0 M7 Ask PitchWise + M5 Narrator (needs Emergent LLM key wired)
- P1 M6 Historical Parallels (needs 5 more curated matches ingested)
- P1 M10 Innings DNA Card renderer
- P2 M9 Player Profile depth (spider chart, career line)

## Deferred / Removed from MVP

Auth, notifications, social layer, multi-league (BBL/PSL/WPL), video highlights, fantasy team
builder, blog, settings, onboarding tour, dark-mode toggle.

## Next Immediate Tasks (M2 kick-off, awaiting user green light)

1. Build MomentumChart (Recharts area chart) + `RatingBadge` reusable
2. ImpactBoard grid + MomentCard on Live page
3. All static-only (no SSE yet) — reads current state from `/api/matches/{id}/state`
