"""
wpa_engine.py
=============
Phase 2: Replace Run Impact with Win Probability Added (WPA) per ball.

For 2nd innings (chasing): WPA is computed directly using the trained
win-probability model — win prob before the ball vs after the ball.

For 1st innings (setting a total): there is no "win probability" in the
same sense mid-innings, because the chase hasn't started. Instead we use
the standard sabermetric-style trick: project what the team's win
probability WOULD be if this same state (overs gone, wickets lost, current
run rate) were a chase against a league-average target. This is an
approximation, clearly flagged as such — it is NOT the same rigor as the
2nd-innings calculation, and that distinction is preserved in the output
columns so the limitation stays visible rather than hidden.

This file also folds in Phase 3 (opposition adjustment): each ball's
WPA contribution to the bowler is scaled by that bowler's season economy
rate relative to the league average for the season, so a dot ball against
a part-timer doesn't count the same as a dot ball against an elite bowler.
"""

import pandas as pd
import numpy as np
import pickle


LEAGUE_AVG_FIRST_INNINGS_TOTAL = 169  # from historical data, used as the
                                       # implied "target" for 1st-innings
                                       # win-probability projection


def load_wp_model(path="wp_model.pkl"):
    with open(path, "rb") as f:
        d = pickle.load(f)
    return d["model"], d["feature_cols"]


def compute_win_prob(model, feature_cols, runs_needed, balls_remaining, wickets_in_hand, target_size):
    """Vectorised win-probability lookup for the chasing team."""
    X = pd.DataFrame({
        "runs_needed": runs_needed,
        "balls_remaining": balls_remaining,
        "wickets_in_hand": wickets_in_hand,
        "required_rpb": np.where(balls_remaining > 0, runs_needed / np.maximum(balls_remaining, 1), runs_needed),
        "target_size": target_size,
    })
    return model.predict_proba(X)[:, 1]


def add_wpa_second_innings(df, model, feature_cols):
    """
    df: ball-by-ball rows for innings == 2 only, sorted by match_id, legal_ball_num.
    Adds win_prob_before, win_prob_after, wpa (for the BATTING team).
    """
    df = df.sort_values(["match_id", "legal_ball_num"]).copy()
    for col in ["legal_ball_num", "cum_runs", "cum_wickets", "runs_total", "is_wicket", "is_legal", "target"]:
        df[col] = df[col].astype("float64")

    df["balls_remaining"] = (120 - df["legal_ball_num"]).clip(lower=0)
    df["wickets_in_hand"] = 10 - df["cum_wickets"]
    df["runs_needed"] = (df["target"] - df["cum_runs"]).clip(lower=0)

    # State BEFORE this ball: undo this ball's runs/wicket
    df["runs_needed_before"] = df["runs_needed"] + df["runs_total"]
    df["wickets_before"] = df["wickets_in_hand"] + df["is_wicket"]
    df["balls_remaining_before"] = df["balls_remaining"] + df["is_legal"]

    df["win_prob_before"] = compute_win_prob(
        model, feature_cols,
        df["runs_needed_before"].clip(lower=0.01),
        df["balls_remaining_before"].clip(lower=1),
        df["wickets_before"].clip(lower=1),
        df["target"],
    )

    df["win_prob_after"] = compute_win_prob(
        model, feature_cols,
        df["runs_needed"].clip(lower=0.01),
        df["balls_remaining"].clip(lower=1),
        df["wickets_in_hand"].clip(lower=1),
        df["target"],
    )

    # If the chase is already over (runs_needed <= 0) win_prob_after pins to 1.0
    df.loc[df["runs_needed"] <= 0, "win_prob_after"] = 1.0
    # If all out, win_prob_after pins to 0.0
    df.loc[df["wickets_in_hand"] <= 0, "win_prob_after"] = 0.0

    df["wpa"] = df["win_prob_after"] - df["win_prob_before"]
    df["innings_type"] = "chase"

    return df


def add_wpa_first_innings(df, model, feature_cols):
    """
    Approximation for 1st innings: treat the current state as if it were a
    chase of the league-average target. This lets every ball still get a
    win-probability-shaped value, while keeping it clearly flagged as an
    approximation (innings_type == 'set') rather than a true WPA computation
    --- the true asymmetry of "setting" vs "chasing" is a known limitation
    this does not fully solve, see project notes / methodology critique.
    """
    df = df.sort_values(["match_id", "legal_ball_num"]).copy()
    for col in ["legal_ball_num", "cum_runs", "cum_wickets", "runs_total", "is_wicket", "is_legal"]:
        df[col] = df[col].astype("float64")

    df["balls_remaining"] = (120 - df["legal_ball_num"]).clip(lower=0)
    df["wickets_in_hand"] = 10 - df["cum_wickets"]

    implied_target = LEAGUE_AVG_FIRST_INNINGS_TOTAL
    df["runs_needed"] = (implied_target - df["cum_runs"]).clip(lower=0.01)

    df["runs_needed_before"] = (implied_target - (df["cum_runs"] - df["runs_total"])).clip(lower=0.01)
    df["wickets_before"] = (df["wickets_in_hand"] + df["is_wicket"]).clip(lower=1)
    df["balls_remaining_before"] = (df["balls_remaining"] + df["is_legal"]).clip(lower=1)

    df["win_prob_before"] = compute_win_prob(
        model, feature_cols,
        df["runs_needed_before"],
        df["balls_remaining_before"],
        df["wickets_before"],
        pd.Series([implied_target] * len(df), index=df.index),
    )
    df["win_prob_after"] = compute_win_prob(
        model, feature_cols,
        df["runs_needed"],
        df["balls_remaining"].clip(lower=1),
        df["wickets_in_hand"].clip(lower=1),
        pd.Series([implied_target] * len(df), index=df.index),
    )

    df["wpa"] = df["win_prob_after"] - df["win_prob_before"]
    df["innings_type"] = "set"

    return df


def compute_opposition_adjustment(events_df):
    """
    Phase 3: opposition adjustment.

    For each bowler-season, compute economy rate relative to the league
    average economy rate that season. A bowler with a much better-than-
    average economy rate is "tougher" to score off — so a batter's WPA
    earned against them is scaled UP slightly, and conversely a bowler's
    own WPA conceded is scaled to reflect they were facing a tougher
    matchup if the SCORING side was elite.

    This is intentionally simple (a multiplier on season economy rate vs
    league average), not a full adjusted-plus-minus model — that would
    need iterative opponent-adjustment (similar to RAPM in basketball)
    and a lot more data than 1,230 matches comfortably support.
    """
    legal = events_df[events_df["is_legal"] == 1].copy()

    bowler_season = (
        legal.groupby(["season", "bowler"])
        .agg(balls=("is_legal", "sum"), runs=("runs_total", "sum"))
        .reset_index()
    )
    bowler_season["economy"] = bowler_season["runs"] / (bowler_season["balls"] / 6)

    league_season_economy = (
        legal.groupby("season")
        .apply(lambda g: g["runs_total"].sum() / (g["is_legal"].sum() / 6), include_groups=False)
        .rename("league_economy")
        .reset_index()
    )

    bowler_season = bowler_season.merge(league_season_economy, on="season")

    # Minimum-balls filter — small samples produce wild economy rates
    bowler_season = bowler_season[bowler_season["balls"] >= 60].copy()

    # Strength multiplier: league_economy / bowler_economy
    # >1 means bowler is BETTER than average (concedes less) -> tougher matchup
    # <1 means bowler is WORSE than average (concedes more) -> easier matchup
    bowler_season["strength_multiplier"] = (
        bowler_season["league_economy"] / bowler_season["economy"]
    ).clip(0.7, 1.4)  # capped to avoid small-sample blowups distorting ratings

    return bowler_season[["season", "bowler", "economy", "league_economy", "strength_multiplier"]]


def build_wpa_dataset(events_path="events.parquet", model_path="wp_model.pkl"):
    model, feature_cols = load_wp_model(model_path)
    events_df = pd.read_parquet(events_path)
    events_df = events_df.convert_dtypes(dtype_backend="numpy_nullable")

    # Super overs (innings 3+) excluded — different dynamics, model not fit for them
    events_df = events_df[events_df["innings"].isin([1, 2])].copy()

    second_innings = events_df[
        (events_df["innings"] == 2) & events_df["target"].notna()
    ].copy()
    first_innings = events_df[events_df["innings"] == 1].copy()

    wpa_2nd = add_wpa_second_innings(second_innings, model, feature_cols)
    wpa_1st = add_wpa_first_innings(first_innings, model, feature_cols)

    full = pd.concat([wpa_1st, wpa_2nd], ignore_index=True)

    # ── Opposition adjustment (Phase 3) ──────────────────────────
    opp_adj = compute_opposition_adjustment(events_df)
    full = full.merge(opp_adj[["season", "bowler", "strength_multiplier"]],
                       on=["season", "bowler"], how="left")
    full["strength_multiplier"] = full["strength_multiplier"].fillna(1.0)

    # Batter WPA: credited as-is (the runs they scored against whatever
    # bowler they faced). Adjusted batter WPA scales UP if the bowler
    # was tougher than average (strength_multiplier > 1), reflecting
    # that the same runs against a better bowler are worth more.
    full["batter_wpa"] = full["wpa"]
    full["batter_wpa_adjusted"] = full["wpa"] * full["strength_multiplier"]

    # Bowler WPA: negative of batting team's WPA (a wicket/dot that lowers
    # batting team's win prob RAISES the bowling team's win prob by the
    # same amount, zero-sum within the ball). No opposition adjustment is
    # applied on the bowling side here, since strength_multiplier already
    # describes THIS bowler — adjusting their own value by their own
    # strength would be circular. Opposition adjustment for bowlers (i.e.
    # facing strong batting lineups) is a natural next step but is not
    # implemented in this version — flagged as a limitation.
    full["bowler_wpa"] = -full["wpa"]

    return full


if __name__ == "__main__":
    wpa_df = build_wpa_dataset()
    wpa_df.to_parquet("wpa_events.parquet", index=False)

    print(f"WPA dataset built: {len(wpa_df)} balls across "
          f"{wpa_df['match_id'].nunique()} matches")
    print(f"\nInnings type breakdown:")
    print(wpa_df["innings_type"].value_counts())

    print(f"\nWPA distribution (batting team perspective):")
    print(wpa_df["wpa"].describe())

    print(f"\nSample rows (2nd innings / chase):")
    sample = wpa_df[wpa_df["innings_type"] == "chase"].head(10)
    print(sample[["match_id", "over", "ball_in_over", "batter", "bowler",
                   "runs_total", "win_prob_before", "win_prob_after", "wpa",
                   "strength_multiplier", "batter_wpa_adjusted"]].to_string())
