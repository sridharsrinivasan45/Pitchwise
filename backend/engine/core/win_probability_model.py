"""
win_probability_model.py
=========================
Trains a win-probability model on 2nd-innings (chasing) match states using
(runs needed, balls remaining, wickets in hand, par/target context).

Validates with a calibration check: do "70% predicted" situations actually
result in wins ~70% of the time historically?
"""

import pandas as pd
import numpy as np
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.model_selection import train_test_split
from sklearn.calibration import calibration_curve
from sklearn.metrics import roc_auc_score, brier_score_loss
import json


def build_wp_training_data(events_df):
    """
    Build one row per ball of the 2nd innings (chasing team's perspective)
    with the state needed to predict win probability.

    We deliberately exclude super overs (innings 3+) — different game,
    different dynamics, and far too little data (16 matches) to model
    separately or safely fold in.
    """
    df = events_df[events_df["innings"] == 2].copy()
    df = df[df["target"].notna()].copy()

    # Balls remaining in a 20-over innings = 120 legal balls total
    df["balls_remaining"] = (120 - df["legal_ball_num"]).clip(lower=0)
    df["wickets_in_hand"] = 10 - df["cum_wickets"]
    df["runs_needed"] = (df["target"] - df["cum_runs"]).clip(lower=0)

    # Current required run rate (per ball) — guard against div by zero
    # at the very last ball
    df["required_rpb"] = np.where(
        df["balls_remaining"] > 0,
        df["runs_needed"] / df["balls_remaining"],
        df["runs_needed"]  # last ball: just the raw runs needed
    )

    # Par score context: target itself, as a proxy for pitch/match difficulty
    df["target_size"] = df["target"]

    # Label: did the batting (chasing) team win?
    df["batting_team_won"] = (df["batting_team"] == df["winner"]).astype(int)

    # Drop the very last few "dead" balls where the match is already
    # mathematically decided (runs_needed <= 0, i.e. chase completed) —
    # these add no information and can leak into training as trivial 100%/0%
    df = df[df["runs_needed"] > 0].copy()

    # Also drop balls bowled after wickets_in_hand hits 0 (all out) —
    # these rows occur when the data still logs trailing deliveries
    df = df[df["wickets_in_hand"] > 0].copy()

    feature_cols = [
        "runs_needed",
        "balls_remaining",
        "wickets_in_hand",
        "required_rpb",
        "target_size",
    ]

    return df, feature_cols


def train_and_validate(events_path="events.parquet", out_model_path="wp_model.json"):
    events_df = pd.read_parquet(events_path)
    events_df = events_df.convert_dtypes(dtype_backend="numpy_nullable")
    wp_df, feature_cols = build_wp_training_data(events_df)

    print(f"Win-probability training rows: {len(wp_df)} "
          f"from {wp_df['match_id'].nunique()} matches")

    X = wp_df[feature_cols]
    y = wp_df["batting_team_won"]

    # Split by MATCH, not by row — otherwise balls from the same match
    # leak between train/test and inflate accuracy artificially
    match_ids = np.array(sorted(set(wp_df["match_id"].astype(str).tolist())))
    train_ids, test_ids = train_test_split(match_ids, test_size=0.2, random_state=42)

    train_mask = wp_df["match_id"].isin(train_ids)
    test_mask = wp_df["match_id"].isin(test_ids)

    X_train, y_train = X[train_mask], y[train_mask]
    X_test, y_test = X[test_mask], y[test_mask]

    model = GradientBoostingClassifier(
        n_estimators=150,
        max_depth=3,
        learning_rate=0.08,
        subsample=0.8,
        random_state=42,
    )
    model.fit(X_train, y_train)

    # ── Validation metrics ────────────────────────────────────
    probs_test = model.predict_proba(X_test)[:, 1]

    auc = roc_auc_score(y_test, probs_test)
    brier = brier_score_loss(y_test, probs_test)

    print(f"\nHeld-out AUC: {auc:.4f}")
    print(f"Held-out Brier score: {brier:.4f} (lower is better; 0.25 = coin flip)")

    # ── Calibration check ──────────────────────────────────────
    # This directly answers: "do 70% predictions actually win ~70% of the time?"
    print(f"\n{'='*55}")
    print("CALIBRATION CHECK")
    print(f"{'='*55}")

    prob_true, prob_pred = calibration_curve(y_test, probs_test, n_bins=10, strategy="quantile")

    print(f"{'Predicted P(win)':<20}{'Actual win rate':<20}{'Gap':<10}")
    print("-" * 50)
    calibration_rows = []
    for pt, pp in zip(prob_true, prob_pred):
        gap = pt - pp
        print(f"{pp*100:>6.1f}%{'':<13}{pt*100:>6.1f}%{'':<13}{gap*100:+.1f}pp")
        calibration_rows.append({"predicted": round(pp, 4), "actual": round(pt, 4)})

    # Specifically check the ~70% bucket the brief asked about
    bucket_70 = wp_df[test_mask].copy()
    bucket_70["pred"] = probs_test
    near_70 = bucket_70[(bucket_70["pred"] >= 0.65) & (bucket_70["pred"] < 0.75)]
    if len(near_70) > 0:
        actual_win_rate_70 = near_70["batting_team_won"].mean()
        print(f"\nSpecific check — balls predicted 65-75% win probability:")
        print(f"  Sample size: {len(near_70)} balls")
        print(f"  Actual win rate: {actual_win_rate_70*100:.1f}%")
        print(f"  (Target: should be close to 70%)")

    # ── Feature importance ──────────────────────────────────────
    print(f"\n{'='*55}")
    print("FEATURE IMPORTANCE")
    print(f"{'='*55}")
    for feat, imp in sorted(zip(feature_cols, model.feature_importances_), key=lambda x: -x[1]):
        print(f"  {feat:<20} {imp:.4f}")

    # ── Save model (as a simple lookup-friendly serialization) ──
    # We export sklearn's tree ensemble via predict on a grid, since plain
    # JSON export of GBM internals is messy — instead we pickle the model
    # for reuse by the rating engine.
    import pickle
    with open("wp_model.pkl", "wb") as f:
        pickle.dump({"model": model, "feature_cols": feature_cols}, f)

    metadata = {
        "auc": round(auc, 4),
        "brier_score": round(brier, 4),
        "n_train_matches": len(train_ids),
        "n_test_matches": len(test_ids),
        "n_train_balls": int(train_mask.sum()),
        "n_test_balls": int(test_mask.sum()),
        "calibration": calibration_rows,
        "feature_importance": {
            f: round(float(i), 4) for f, i in zip(feature_cols, model.feature_importances_)
        },
    }
    with open(out_model_path, "w") as f:
        json.dump(metadata, f, indent=2)

    print(f"\nModel saved to wp_model.pkl, metadata saved to {out_model_path}")

    return model, feature_cols, metadata


if __name__ == "__main__":
    train_and_validate()
