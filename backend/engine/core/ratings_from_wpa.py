"""
ratings_from_wpa.py
====================
Aggregates per-ball WPA into match ratings and season ratings.

Conversion from raw WPA sum to a 0-10 scale uses a tanh transform, same
spirit as the original Run-Impact-based system, but now the underlying
currency is win-probability-shaped, not runs-shaped, so the same cumulative
total is properly comparable between someone who scored fast in a low-
context spell and someone whose runs were genuinely match-defining.
"""

import pandas as pd
import numpy as np


def wpa_to_rating(wpa_sum, scale=0.15):
    """
    Converts cumulative match WPA (typically -0.5 to +0.5 for a strong
    performance, since win prob is bounded 0-1 and a single player rarely
    swings the whole game alone) to a 0-10 rating.

    scale=0.15 means a WPA of +0.15 (a genuinely match-defining
    contribution) maps to roughly a 9/10 rating; tuned against the
    empirical WPA distribution below.
    """
    return round(5.0 + 5.0 * np.tanh(wpa_sum / scale), 2)


def build_match_ratings(wpa_df):
    batting = (
        wpa_df.groupby(["match_id", "batter"], as_index=False)
        .agg(
            runs=("runs_batter", "sum"),
            balls_faced=("is_legal", "sum"),
            batting_wpa=("batter_wpa_adjusted", "sum"),
        )
    )
    batting["batting_rating"] = batting["batting_wpa"].apply(wpa_to_rating)
    batting = batting.rename(columns={"batter": "player"})

    bowling = (
        wpa_df.groupby(["match_id", "bowler"], as_index=False)
        .agg(
            wickets=("is_wicket", "sum"),
            balls_bowled=("is_legal", "sum"),
            bowling_wpa=("bowler_wpa", "sum"),
        )
    )
    bowling["bowling_rating"] = bowling["bowling_wpa"].apply(wpa_to_rating)
    bowling = bowling.rename(columns={"bowler": "player"})

    match_ratings = batting.merge(bowling, on=["match_id", "player"], how="outer")
    match_ratings = match_ratings.fillna({
        "runs": 0, "balls_faced": 0, "batting_wpa": 0, "batting_rating": 0,
        "wickets": 0, "balls_bowled": 0, "bowling_wpa": 0, "bowling_rating": 0,
    })

    match_ratings["total_wpa"] = match_ratings["batting_wpa"] + match_ratings["bowling_wpa"]
    match_ratings["overall_rating"] = match_ratings["total_wpa"].apply(wpa_to_rating)

    return match_ratings


def build_season_ratings(match_ratings, wpa_df, min_matches=5):
    # season lookup per match
    season_lookup = wpa_df[["match_id", "season"]].drop_duplicates()
    mr = match_ratings.merge(season_lookup, on="match_id", how="left")

    season = (
        mr.groupby(["season", "player"], as_index=False)
        .agg(
            matches=("match_id", "nunique"),
            total_runs=("runs", "sum"),
            total_wickets=("wickets", "sum"),
            avg_wpa=("total_wpa", "mean"),
            peak_wpa=("total_wpa", "max"),
        )
    )

    season = season[season["matches"] >= min_matches].copy()

    # reliability shrinkage — same spirit as before but now documented:
    # k=5 chosen as a soft prior equal to the min_matches threshold itself,
    # so a player right at the qualification line gets ~50% shrinkage
    # toward the population mean WPA (which is ~0 by construction, since
    # WPA is zero-sum within each match). This is still a heuristic, not
    # derived from variance decomposition — flagged here rather than
    # presented as more rigorous than it is.
    k = 5
    season["reliability"] = season["matches"] / (season["matches"] + k)
    season["adjusted_wpa"] = season["avg_wpa"] * season["reliability"]
    season["season_rating"] = season["adjusted_wpa"].apply(lambda x: wpa_to_rating(x, scale=0.05))

    return season.sort_values("season_rating", ascending=False)


if __name__ == "__main__":
    wpa_df = pd.read_parquet("wpa_events.parquet")

    match_ratings = build_match_ratings(wpa_df)
    match_ratings.to_parquet("match_ratings.parquet", index=False)

    season_ratings = build_season_ratings(match_ratings, wpa_df)
    season_ratings.to_parquet("season_ratings.parquet", index=False)

    print("Top 20 season ratings (all seasons, min 5 matches):")
    print(season_ratings.head(20).to_string(index=False))

    print(f"\n\nSample match — top performers, match_id={match_ratings['match_id'].iloc[0]}:")
    sample_match = match_ratings[match_ratings["match_id"] == match_ratings["match_id"].iloc[0]]
    print(sample_match.sort_values("overall_rating", ascending=False).head(10).to_string(index=False))
