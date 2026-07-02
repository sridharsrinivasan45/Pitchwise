"""
IPL Player Rating System
========================
Rates every batter and bowler per match on a 0–10 scale,
then aggregates to season ratings with peak and consistency bonuses.

Data source: Cricsheet IPL JSON files
"""

import json
import glob
import os
from collections import defaultdict


# ─────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────

DATA_DIR   = "ipl_data"          # folder containing *.json match files
MIN_BALLS_FACED   = 6            # batter must face at least this many balls
MIN_BALLS_BOWLED  = 6            # bowler must bowl at least this many legal balls
MIN_MATCH_RATING  = 5            # minimum qualifying matches for season rating

# Season to analyse – set to None to run all seasons
TARGET_SEASON = "2007/08"        # e.g. "2024", "2007/08", or None


# ─────────────────────────────────────────
# PHASE HELPER
# ─────────────────────────────────────────

def get_phase(over_num):
    """Return 'powerplay', 'middle', or 'death' for a 0-indexed over number."""
    if over_num <= 5:
        return "powerplay"
    elif over_num <= 14:
        return "middle"
    else:
        return "death"


# ─────────────────────────────────────────
# MATCH-LEVEL BATTING RATING
# ─────────────────────────────────────────

def rate_batter(stats, team_score, team_wickets):
    """
    Score a batter 0–10 for one innings.

    stats keys: runs, balls, fours, sixes, dismissed,
                pp_runs, pp_balls, mid_runs, mid_balls,
                death_runs, death_balls
    """
    runs   = stats["runs"]
    balls  = stats["balls"]

    if balls < MIN_BALLS_FACED:
        return None          # too small a sample

    sr = (runs / balls) * 100

    # ── Base score: volume × rate ─────────────────────────
    # Milestone bonuses
    if runs >= 100:
        milestone = 3.0
    elif runs >= 75:
        milestone = 2.0
    elif runs >= 50:
        milestone = 1.5
    elif runs >= 30:
        milestone = 0.75
    elif runs >= 15:
        milestone = 0.25
    else:
        milestone = 0.0

    # Strike-rate component (T20 benchmark: 130 SR = neutral)
    sr_score = (sr - 130) / 30     # +1 per 30 SR above 130, −1 per 30 below
    sr_score  = max(-2.0, min(2.0, sr_score))

    # Boundary bonus
    boundary_bonus = (stats["fours"] * 0.05) + (stats["sixes"] * 0.12)
    boundary_bonus = min(boundary_bonus, 1.0)

    # Phase context multiplier – death runs hardest to score
    phase_bonus = 0.0
    if stats["death_balls"] >= 4:
        death_sr = (stats["death_runs"] / stats["death_balls"]) * 100
        if death_sr >= 200:
            phase_bonus += 0.5
        elif death_sr >= 150:
            phase_bonus += 0.25

    # Team innings context: did the player contribute when team struggled?
    if team_score > 0:
        contribution_pct = runs / team_score
        if contribution_pct >= 0.40:
            phase_bonus += 0.4
        elif contribution_pct >= 0.25:
            phase_bonus += 0.2

    # Not-out bonus (anchor innings)
    notout_bonus = 0.3 if not stats["dismissed"] and runs >= 20 else 0.0

    # ── Compose ───────────────────────────────────────────
    raw = (
        5.0              # neutral baseline
        + milestone
        + sr_score
        + boundary_bonus
        + phase_bonus
        + notout_bonus
    )

    return round(min(max(raw, 1.0), 10.0), 2)


# ─────────────────────────────────────────
# MATCH-LEVEL BOWLING RATING
# ─────────────────────────────────────────

def rate_bowler(stats, team_conceded, overs_bowled_team):
    """
    Score a bowler 0–10 for one innings.

    stats keys: wickets, runs_conceded, legal_balls,
                dots, fours_conceded, sixes_conceded
    """
    legal_balls = stats["legal_balls"]

    if legal_balls < MIN_BALLS_BOWLED:
        return None

    overs   = legal_balls / 6
    economy = stats["runs_conceded"] / overs if overs > 0 else 99

    # ── Wicket score ──────────────────────────────────────
    w = stats["wickets"]
    if w >= 5:
        wicket_score = 4.0
    elif w == 4:
        wicket_score = 3.0
    elif w == 3:
        wicket_score = 2.0
    elif w == 2:
        wicket_score = 1.0
    elif w == 1:
        wicket_score = 0.4
    else:
        wicket_score = 0.0

    # ── Economy score (T20 benchmark: 8.0 = neutral) ─────
    econ_score = (8.0 - economy) / 2.0    # +1 per 2 runs saved vs 8.0
    econ_score  = max(-2.5, min(2.5, econ_score))

    # ── Dot ball bonus ────────────────────────────────────
    dot_pct     = stats["dots"] / legal_balls if legal_balls > 0 else 0
    dot_bonus   = dot_pct * 1.0             # max +1.0 for 100% dots (unrealistic)
    dot_bonus   = min(dot_bonus, 0.8)

    # ── Boundary conceded penalty ─────────────────────────
    boundary_pen = (
        stats["fours_conceded"] * 0.03
        + stats["sixes_conceded"] * 0.07
    )
    boundary_pen = min(boundary_pen, 1.0)

    # ── Compose ───────────────────────────────────────────
    raw = (
        5.0
        + wicket_score
        + econ_score
        + dot_bonus
        - boundary_pen
    )

    return round(min(max(raw, 1.0), 10.0), 2)


# ─────────────────────────────────────────
# PARSE ONE MATCH FILE
# ─────────────────────────────────────────

def parse_match(filepath):
    """
    Returns a dict of player → {batting_rating, bowling_rating}
    for one match. Values are None if player didn't qualify.
    """
    with open(filepath) as f:
        match = json.load(f)

    info    = match["info"]
    season  = str(info.get("season", "unknown"))
    innings_data = match.get("innings", [])

    all_batting_ratings  = {}   # player → float|None
    all_bowling_ratings  = {}

    for innings in innings_data:
        batting_team = innings["team"]

        # ── Collect team total for context ────────────────
        team_runs     = 0
        team_wickets  = 0

        # First pass: aggregate team totals
        for over_obj in innings.get("overs", []):
            for ball in over_obj.get("deliveries", []):
                team_runs += ball["runs"]["batter"]
                if "wickets" in ball:
                    for wkt in ball["wickets"]:
                        if wkt["kind"] not in ("run out", "retired hurt", "obstructing the field"):
                            team_wickets += 1

        # ── Per-batter stats ──────────────────────────────
        batter_stats = defaultdict(lambda: {
            "runs": 0, "balls": 0, "fours": 0, "sixes": 0,
            "dismissed": False,
            "pp_runs": 0, "pp_balls": 0,
            "mid_runs": 0, "mid_balls": 0,
            "death_runs": 0, "death_balls": 0,
        })

        # ── Per-bowler stats ──────────────────────────────
        bowler_stats = defaultdict(lambda: {
            "wickets": 0, "runs_conceded": 0, "legal_balls": 0,
            "dots": 0, "fours_conceded": 0, "sixes_conceded": 0,
        })

        for over_obj in innings.get("overs", []):
            over_num = over_obj["over"]   # 0-indexed
            phase    = get_phase(over_num)

            for ball in over_obj.get("deliveries", []):
                batter  = ball["batter"]
                bowler  = ball["bowler"]
                runs_b  = ball["runs"]["batter"]
                extras  = ball.get("extras", {})
                is_wide = "wides" in extras
                is_nb   = "noballs" in extras

                # ── Batter ────────────────────────────────
                bs = batter_stats[batter]
                bs["runs"] += runs_b
                if not is_wide:
                    bs["balls"] += 1
                if runs_b == 4:
                    bs["fours"] += 1
                elif runs_b == 6:
                    bs["sixes"] += 1

                # Phase split
                if not is_wide:
                    if phase == "powerplay":
                        bs["pp_runs"]  += runs_b
                        bs["pp_balls"] += 1
                    elif phase == "middle":
                        bs["mid_runs"]   += runs_b
                        bs["mid_balls"]  += 1
                    else:
                        bs["death_runs"]  += runs_b
                        bs["death_balls"] += 1

                # Dismissal
                if "wickets" in ball:
                    for wkt in ball["wickets"]:
                        if wkt["player_out"] == batter:
                            bs["dismissed"] = True

                # ── Bowler ────────────────────────────────
                bwl = bowler_stats[bowler]
                bwl["runs_conceded"] += ball["runs"]["total"] - extras.get("legbyes", 0) - extras.get("byes", 0)

                if not is_wide and not is_nb:
                    bwl["legal_balls"] += 1
                    if runs_b == 0 and ball["runs"]["total"] == 0:
                        bwl["dots"] += 1

                if runs_b == 4:
                    bwl["fours_conceded"] += 1
                elif runs_b == 6:
                    bwl["sixes_conceded"] += 1

                if "wickets" in ball:
                    for wkt in ball["wickets"]:
                        if wkt["kind"] not in ("run out", "retired hurt", "obstructing the field"):
                            bwl["wickets"] += 1

        # ── Rate every batter ─────────────────────────────
        for player, stats in batter_stats.items():
            rating = rate_batter(stats, team_runs, team_wickets)
            # Keep best rating if player batted in both innings
            if player not in all_batting_ratings or (rating is not None and (all_batting_ratings[player] is None or rating > all_batting_ratings[player])):
                all_batting_ratings[player] = rating

        # ── Rate every bowler ─────────────────────────────
        for player, stats in bowler_stats.items():
            overs_team = sum(
                len(o["deliveries"]) for o in innings.get("overs", [])
            ) / 6
            rating = rate_bowler(stats, team_runs, overs_team)
            if player not in all_bowling_ratings or (rating is not None and (all_bowling_ratings[player] is None or rating > all_bowling_ratings[player])):
                all_bowling_ratings[player] = rating

    return season, all_batting_ratings, all_bowling_ratings


# ─────────────────────────────────────────
# SEASON AGGREGATION
# ─────────────────────────────────────────

def aggregate_season(batting_by_player, bowling_by_player):
    """
    Given lists of per-match ratings, compute a season rating.

    Formula:
        base      = trimmed mean (drop lowest if ≥8 matches)
        peak_bonus= (max_rating - base) * 0.20   ← rewards standout without double-counting
        cons_bonus= tiered on base
        final     = min(base + peak_bonus + cons_bonus, 10)
    """
    results = {}

    for player, ratings in batting_by_player.items():
        valid = [r for r in ratings if r is not None and r > 0]
        if len(valid) < MIN_MATCH_RATING:
            continue

        sorted_r = sorted(valid)
        # Drop single lowest if enough matches
        trimmed  = sorted_r[1:] if len(sorted_r) >= 8 else sorted_r
        base     = sum(trimmed) / len(trimmed)
        peak     = max(valid)
        peak_bonus = (peak - base) * 0.20

        if base >= 7.0:
            cons_bonus = 0.30
        elif base >= 6.0:
            cons_bonus = 0.15
        else:
            cons_bonus = 0.0

        final = min(base + peak_bonus + cons_bonus, 10.0)
        results[player] = {
            "season_rating": round(final, 2),
            "base_avg":      round(base, 2),
            "peak":          round(peak, 2),
            "matches":       len(valid),
            "consistency":   round(sum(1 for r in valid if r >= 7) / len(valid) * 100, 1),
        }

    return results


def classify_roles(players, bat_matches, bowl_matches):
    """
    Classify each player into specialist batter / bowler / all-rounder
    based on how many matches they registered a qualifying rating.
    """
    batters     = {}
    bowlers     = {}
    allrounders = {}
    unclassified = {}

    for player in players:
        bm = bat_matches.get(player, 0)
        wm = bowl_matches.get(player, 0)

        if bm >= 8 and wm <= 3:
            batters[player] = players[player]
        elif wm >= 8 and bm <= 3:
            bowlers[player] = players[player]
        elif bm >= 5 and wm >= 5:
            allrounders[player] = players[player]
        else:
            unclassified[player] = players[player]

    return batters, bowlers, allrounders, unclassified


# ─────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────

def run(target_season=None):
    files = sorted(glob.glob(os.path.join(DATA_DIR, "*.json")))

    # Storage: season → player → list of match ratings
    season_bat   = defaultdict(lambda: defaultdict(list))
    season_bowl  = defaultdict(lambda: defaultdict(list))

    print(f"Parsing {len(files)} match files...")

    for fp in files:
        try:
            season, bat_ratings, bowl_ratings = parse_match(fp)
        except Exception as e:
            print(f"  ⚠ Skipped {fp}: {e}")
            continue

        if target_season and season != target_season:
            continue

        for player, rating in bat_ratings.items():
            season_bat[season][player].append(rating)

        for player, rating in bowl_ratings.items():
            season_bowl[season][player].append(rating)

    seasons_to_run = [target_season] if target_season else sorted(season_bat.keys())

    for season in seasons_to_run:
        print(f"\n\n{'='*50}")
        print(f"  IPL {season} — PLAYER RATINGS")
        print(f"{'='*50}")

        bat_data  = season_bat[season]
        bowl_data = season_bowl[season]

        # Season aggregates
        bat_season  = aggregate_season(bat_data, {})
        bowl_season = aggregate_season(bowl_data, {})

        # Match count per player per discipline
        bat_match_counts  = {p: sum(1 for r in v if r is not None) for p, v in bat_data.items()}
        bowl_match_counts = {p: sum(1 for r in v if r is not None) for p, v in bowl_data.items()}

        # All players who have either a bat or bowl season rating
        all_players = {}
        for player in set(bat_season) | set(bowl_season):
            bat_info  = bat_season.get(player)
            bowl_info = bowl_season.get(player)

            # Combined season rating – weighted by matches
            bm = bat_info["matches"]  if bat_info  else 0
            wm = bowl_info["matches"] if bowl_info else 0
            total = bm + wm

            if total == 0:
                continue

            combined = (
                (bat_info["season_rating"]  * bm if bat_info  else 0) +
                (bowl_info["season_rating"] * wm if bowl_info else 0)
            ) / total

            all_players[player] = {
                "combined_rating": round(combined, 2),
                "bat":  bat_info,
                "bowl": bowl_info,
            }

        # Role classification
        batters, bowlers, allrounders, _ = classify_roles(
            all_players, bat_match_counts, bowl_match_counts
        )

        # ── Print leaderboards ────────────────────────────

        def print_leaderboard(title, group, rating_key, top_n=10):
            print(f"\n{'─'*40}")
            print(f"  {title}")
            print(f"{'─'*40}")
            ranked = sorted(
                group.items(),
                key=lambda x: x[1]["combined_rating"],
                reverse=True
            )[:top_n]

            for i, (player, info) in enumerate(ranked, 1):
                bat  = info["bat"]
                bowl = info["bowl"]

                bat_str  = f"Bat {bat['season_rating']}/10  (avg {bat['base_avg']} | peak {bat['peak']} | {bat['matches']}m | {bat['consistency']}% ≥7)" if bat else "—"
                bowl_str = f"Bowl {bowl['season_rating']}/10  (avg {bowl['base_avg']} | peak {bowl['peak']} | {bowl['matches']}m | {bowl['consistency']}% ≥7)" if bowl else "—"

                print(f"\n{i:>2}. {player}  [{info['combined_rating']}/10]")
                if bat:
                    print(f"     {bat_str}")
                if bowl:
                    print(f"     {bowl_str}")

        print_leaderboard(f"TOP BATTERS — IPL {season}",      batters,     "combined_rating")
        print_leaderboard(f"TOP BOWLERS — IPL {season}",      bowlers,     "combined_rating")
        print_leaderboard(f"TOP ALL-ROUNDERS — IPL {season}", allrounders, "combined_rating")

        # ── Consistency table ─────────────────────────────
        print(f"\n{'─'*40}")
        print(f"  MOST CONSISTENT — IPL {season}")
        print(f"{'─'*40}")

        cons_table = []
        for player, info in all_players.items():
            entries = []
            if info["bat"]:
                entries.append(info["bat"]["consistency"])
            if info["bowl"]:
                entries.append(info["bowl"]["consistency"])
            if entries:
                avg_cons = sum(entries) / len(entries)
                total_m  = (info["bat"]["matches"] if info["bat"] else 0) + \
                           (info["bowl"]["matches"] if info["bowl"] else 0)
                if total_m >= MIN_MATCH_RATING:
                    cons_table.append((player, round(avg_cons, 1), total_m))

        for i, (player, cons, m) in enumerate(
            sorted(cons_table, key=lambda x: x[1], reverse=True)[:10], 1
        ):
            print(f"  {i:>2}. {player:<25} {cons}%  ({m} matches)")


if __name__ == "__main__":
    run(target_season=TARGET_SEASON)
