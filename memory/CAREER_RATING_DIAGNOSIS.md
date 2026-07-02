# Career Rating Diagnosis — why Kohli reads 4.85 and Bumrah 5.68

**Scope:** Investigation only. No engine methodology has been changed.
**Data pulled live from the ingested archive** (2008–2026 IPL, on 2026-02-XX).

---

## 1. What the UI shows today

`GET /api/players` and `GET /api/players/{id}` both compute the career number as
the **arithmetic mean of every per-match `overall_rating`** the player has:

```python
# backend/routes/players.py
"avg_rating": {"$avg": "$overall_rating"}      # index
"avg_rating": ...avg of overall_rating docs... # profile
```

Empirically that gives:

| Player      | Matches | `mean(overall_rating)` (shown) | `median` | p25  | p75  | p95  | Matches in [4.5, 5.5] |
|-------------|---------|-------------------------------|----------|------|------|------|------------------------|
| V Kohli     | 276     | **4.85**                      | 4.52     | 2.13 | 7.61 | 9.93 | 32 / 276 (11.6%)       |
| JJ Bumrah   | 158     | **5.68**                      | 5.63     | 3.26 | 8.64 | 9.97 | 21 / 158 (13.3%)       |

These numbers *are* mathematically correct averages of the per-match ratings the
engine produces. The problem is that averaging per-match ratings the way we do
is the **wrong career aggregation** for how the engine defines a rating.

---

## 2. Why averaging match ratings compresses toward 5

The engine's per-match rating is:

```python
# engine/core/ratings_from_wpa.py
def wpa_to_rating(wpa_sum, scale=0.15):
    return round(5.0 + 5.0 * np.tanh(wpa_sum / scale), 2)
```

That is a bounded, S-shaped transform centred at 5 that **saturates near 0 and 10**.
Its input is a player's `total_wpa` in a single match — i.e. how many win-probability
points they added *in that particular game*. Two important properties of that input:

1. **WPA is roughly zero-sum within a match.** Across the entire ball-by-ball
   scoresheet the numbers sum to `winner_wpa − loser_wpa ≈ ±0.5`. Over a
   career, a top-10 batter facing 25% of their team's deliveries has an
   average per-match WPA that clusters around **~0.02**, not around a big
   positive number.

2. **The `tanh` is nonlinear and bounded.** A −0.15 WPA match maps to ~1.2/10,
   a +0.15 WPA match maps to ~8.8/10, but a +0.30 WPA match only nudges to
   ~9.7/10. So great matches saturate, whereas bad matches don't.

Combine those two: for career-length samples, the per-match ratings distribute
roughly symmetrically around the mid-5s **with heavy tails that are clipped by
the tanh saturation on the high side but not on the low side**. Taking the
straight arithmetic mean of that (i.e. `E[tanh(X/0.15)]`) is a textbook
**Jensen's-inequality collapse**: it pulls the number strongly toward
`tanh(E[X]/0.15) ≈ tanh(0) = 5.0`. This is exactly what you see — the medians
are 4.52 and 5.63, and 11–13% of every player's career sits in the flat
[4.5, 5.5] band.

Concretely, for Kohli:

```
mean(total_wpa)   = 0.0172
mean(rating)      = 4.85           ← what the UI shows
apply engine's own aggregate transform on mean(WPA):
   wpa_to_rating(0.0172, scale=0.15) = 5.56
```

The engine already includes the *correct* career-style aggregator — its
`build_season_ratings()` function — which averages WPA first, applies a
`matches / (matches + k)` reliability shrinkage, and *then* runs the tanh with
a tighter `scale=0.05` (because season-level averages of WPA are inherently
smaller than single-match totals). Applying that engine function to the full
career gives:

| Player   | `mean(rating)` (today) | Engine-style career (`avg WPA` → shrink → tanh, scale=0.05) | Engine-style career (scale=0.15) | Top-10 match avg |
|----------|-----------------------|---------------------------------------------------------------|----------------------------------|------------------|
| Kohli    | 4.85                  | **6.63**                                                      | 5.56                             | 9.99             |
| Bumrah   | 5.68                  | **8.54**                                                      | 6.43                             | 9.99             |

The `scale=0.05` numbers are the ones that pass the sanity check the user
described. **And crucially, they come from the engine's own function
(`wpa_to_rating`) applied at the correct aggregation stage** — not a new
formula.

---

## 3. Which of the four candidates the user listed is the culprit?

| Candidate            | Verdict                                                                                                                                            |
|----------------------|----------------------------------------------------------------------------------------------------------------------------------------------------|
| Season aggregation   | N/A here — the field is *career*, not season-scoped. But the engine's `build_season_ratings()` already models the same problem at season level.    |
| Rating normalization | Contributes. The per-match scale (`0.15`) is deliberately loose so an individual match rating "feels" fair. A career-level number needs a tighter scale (engine uses `0.05` for its season transform). |
| **Career aggregation** | **Primary root cause.** We compute `mean(rating)` instead of `wpa_to_rating(mean(WPA))`. The tanh's nonlinearity + WPA's near-zero-mean property collapses the mean toward 5. |
| Display scaling      | Not the cause. The 0–10 scale is fine; we're just plotting the wrong statistic on it.                                                              |

The engine methodology is not the problem. The engine even provides the right
function. Our product-layer aggregation is what's off.

---

## 4. Proposed fix (for approval, not yet applied)

**No engine change.** In the *product layer* (`backend/routes/players.py`):

1. Stop reporting `mean(overall_rating)` as "career rating".
2. Compute career rating exactly like the engine computes a season rating —
   just widened to the full career:
   ```python
   avg_wpa   = mean(total_wpa across matches)
   reliab    = n / (n + 5)                # engine's own shrinkage
   career    = wpa_to_rating(avg_wpa * reliab, scale=0.05)   # engine's own fn
   ```
   This calls the engine's own `wpa_to_rating` (no duplication, no
   remethodology), just at the correct aggregation stage.
3. Keep `best_rating` (peak match) and add a "top-10 match average" as a
   secondary highlight — a fan-legible peak metric that isn't compressed.
4. Optionally show a small tooltip on the badge:
   *"Career rating = engine's WPA-to-rating applied to shrunk career-avg WPA."*

Ballpark after the fix:

| Player   | Career rating (new) | Peak rating | Top-10 avg |
|----------|--------------------:|------------:|-----------:|
| Kohli    | ~6.6                | 10.00       | 9.99       |
| Bumrah   | ~8.5                | 10.00       | 9.99       |

These pass the intuitive sanity check the user described.

---

## 5. Non-goals

- We are **not** re-tuning any engine constant.
- We are **not** touching `engine/core/`.
- We are **not** redefining per-match rating semantics — those stay exactly as
  the engine specifies (they're the right scale for a single game).

Awaiting user approval before applying the aggregation change in
`routes/players.py`.
