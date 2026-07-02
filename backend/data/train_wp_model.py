"""
Train the Win Probability model using the uploaded PitchWise engine's methodology
UNCHANGED. This orchestrator:

  1. Loads all balls from Mongo (source of truth after Stage 2 ingest).
  2. Excludes matches where outcome.result in {'tie','no_result'} (Stage 1 decision).
  3. Writes an events.parquet in the exact shape engine.core.win_probability_model
     expects — no column renames, no methodology tweaks.
  4. Runs engine.core.win_probability_model.train_and_validate() verbatim.
  5. Saves every artifact for reproducibility:
       - wp_model.pkl               (the trained sklearn GBM + feature_cols)
       - wp_model.json              (engine's native metadata)
       - feature_importance.json
       - calibration.csv
       - calibration.png            (predicted vs actual win rate)
       - training_report.json       (this orchestrator's full report)

USAGE:
    python -m data.train_wp_model
    python -m data.train_wp_model --dry-run          (build parquet only, no training)
"""
from __future__ import annotations
import argparse
import asyncio
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND))

from dotenv import load_dotenv  # noqa: E402
load_dotenv(BACKEND / ".env")

import pandas as pd  # noqa: E402
from core.db import get_db  # noqa: E402

# These two ARTIFACT paths are where we persist everything for reproducibility.
ARTIFACTS = BACKEND / "engine" / "artifacts"
EVENTS_PARQUET = ARTIFACTS / "events.parquet"


# Engine's exact expected column order for train_and_validate
ENGINE_COLS = [
    "match_id", "innings", "over", "ball_in_over", "batter", "bowler",
    "runs_batter", "runs_total", "is_wicket", "is_legal",
    "cum_runs", "cum_wickets", "target", "legal_ball_num",
    "season", "batting_team", "winner",
]


async def _load_events_df(exclude_result_types: set[str]) -> tuple[pd.DataFrame, dict]:
    """
    Assemble the ball-level DataFrame from Mongo in engine's expected schema.
    Returns (df, stats).
    """
    db = get_db()

    # Which match_ids to exclude
    excluded_match_ids: list[str] = []
    excluded_reasons: dict[str, int] = {}
    async for m in db.matches.find(
        {"outcome.result": {"$in": list(exclude_result_types)}},
        {"_id": 0, "match_id": 1, "outcome.result": 1},
    ):
        excluded_match_ids.append(m["match_id"])
        r = m["outcome"]["result"]
        excluded_reasons[r] = excluded_reasons.get(r, 0) + 1

    query = {"match_id": {"$nin": excluded_match_ids}} if excluded_match_ids else {}
    proj = {col: 1 for col in ENGINE_COLS} | {"_id": 0}
    print(f"[train] loading balls (excluding {len(excluded_match_ids)} matches)...")
    rows: list[dict] = []
    cursor = db.balls.find(query, proj)
    async for b in cursor:
        rows.append(b)
    print(f"[train] loaded {len(rows)} balls")

    df = pd.DataFrame(rows, columns=ENGINE_COLS)

    stats = {
        "excluded_match_ids": excluded_match_ids,
        "excluded_reasons": excluded_reasons,
        "total_balls_loaded": len(rows),
        "match_count_included": int(df["match_id"].nunique()),
        "match_count_excluded": len(excluded_match_ids),
    }
    return df, stats


def _class_balance(df: pd.DataFrame) -> dict:
    """Fraction of chase-team-won across 2nd-innings training-eligible rows."""
    sec = df[df["innings"] == 2].copy()
    sec = sec[sec["target"].notna()]
    sec["batting_team_won"] = (sec["batting_team"] == sec["winner"]).astype(int)
    p_won = float(sec["batting_team_won"].mean())
    return {
        "second_innings_balls": int(len(sec)),
        "chase_won_fraction": round(p_won, 4),
        "chase_lost_fraction": round(1 - p_won, 4),
    }


def _data_quality_warnings(df: pd.DataFrame) -> list[str]:
    warnings: list[str] = []
    # Missing winner
    n_missing_winner = int(df["winner"].isna().sum())
    if n_missing_winner:
        warnings.append(f"{n_missing_winner} rows have winner=NA (should be 0 after tie/no_result filter)")
    # 1st-innings target should be NaN, 2nd-innings should be present
    inn1_targets = int(df[(df["innings"] == 1) & df["target"].notna()].shape[0])
    if inn1_targets:
        warnings.append(f"{inn1_targets} first-innings rows carry a target (expected 0)")
    inn2_notarget = int(df[(df["innings"] == 2) & df["target"].isna()].shape[0])
    if inn2_notarget:
        warnings.append(f"{inn2_notarget} second-innings rows missing target (will be dropped by engine filter)")
    # legal_ball_num monotonic
    grouped = df.groupby(["match_id", "innings"])["legal_ball_num"].apply(
        lambda s: s.is_monotonic_increasing
    )
    non_monotonic = int((~grouped).sum())
    if non_monotonic:
        warnings.append(f"{non_monotonic} innings have non-monotonic legal_ball_num (data inconsistency)")
    # cum_wickets never decreases and stays <=10 mostly
    over_wickets = int(df[df["cum_wickets"] > 10].shape[0])
    if over_wickets:
        warnings.append(f"{over_wickets} rows with cum_wickets > 10 (possible parsing bug)")
    return warnings


def _run_engine_training(events_path: Path, out_metadata_path: Path):
    """
    Invokes engine.core.win_probability_model.train_and_validate VERBATIM.
    Engine hardcodes pickle output to CWD/wp_model.pkl so we chdir into the
    artifacts directory before calling.
    """
    from engine.core.win_probability_model import train_and_validate  # local import
    cwd = os.getcwd()
    os.chdir(str(events_path.parent))
    try:
        model, feature_cols, metadata = train_and_validate(
            events_path=str(events_path),
            out_model_path=str(out_metadata_path.name),
        )
    finally:
        os.chdir(cwd)
    return model, feature_cols, metadata


def _plot_calibration(calibration_rows: list[dict], out_png: Path):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    pred = [r["predicted"] for r in calibration_rows]
    actual = [r["actual"] for r in calibration_rows]

    fig, ax = plt.subplots(figsize=(6, 6), dpi=140)
    ax.plot([0, 1], [0, 1], "--", color="#888", linewidth=1, label="Perfectly calibrated")
    ax.plot(pred, actual, "-o", color="#F5A623", linewidth=2, markersize=6, label="PitchWise WP model")
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.set_xlabel("Predicted P(win)")
    ax.set_ylabel("Actual win rate")
    ax.set_title("Win-probability calibration (held-out matches)")
    ax.grid(True, alpha=0.2)
    ax.legend(loc="lower right")
    fig.tight_layout()
    fig.savefig(out_png)
    plt.close(fig)


async def _run(exclude_tied: bool, dry_run: bool):
    t0 = time.time()
    ARTIFACTS.mkdir(parents=True, exist_ok=True)

    exclude_set = {"tie", "no_result"} if exclude_tied else set()
    df, load_stats = await _load_events_df(exclude_set)

    class_bal = _class_balance(df)
    warnings = _data_quality_warnings(df)

    # Write parquet (engine's expected input file)
    df.to_parquet(EVENTS_PARQUET, index=False)
    print(f"[train] wrote {len(df)} rows to {EVENTS_PARQUET}")

    if dry_run:
        print("[train] --dry-run: stopping before training call")
        return

    # Invoke engine — UNCHANGED
    print("[train] invoking engine.core.win_probability_model.train_and_validate ...")
    model, feature_cols, engine_meta = _run_engine_training(
        events_path=EVENTS_PARQUET,
        out_metadata_path=ARTIFACTS / "wp_model.json",
    )

    # Persist auxiliary artifacts
    (ARTIFACTS / "feature_importance.json").write_text(
        json.dumps(engine_meta["feature_importance"], indent=2)
    )
    calib_rows = engine_meta.get("calibration", [])
    with (ARTIFACTS / "calibration.csv").open("w") as f:
        f.write("predicted,actual\n")
        for r in calib_rows:
            f.write(f"{r['predicted']},{r['actual']}\n")
    if calib_rows:
        _plot_calibration(calib_rows, ARTIFACTS / "calibration.png")

    # Full report
    report = {
        "run_at": datetime.now(timezone.utc).isoformat(),
        "engine_source": "engine.core.win_probability_model.train_and_validate",
        "methodology_status": "UNCHANGED",
        "matches_included": load_stats["match_count_included"],
        "matches_excluded": load_stats["match_count_excluded"],
        "exclusion_reasons": load_stats["excluded_reasons"],
        "total_balls_loaded": load_stats["total_balls_loaded"],
        "class_balance": class_bal,
        "auc": engine_meta["auc"],
        "brier_score": engine_meta["brier_score"],
        "n_train_matches": engine_meta["n_train_matches"],
        "n_test_matches": engine_meta["n_test_matches"],
        "n_train_balls": engine_meta["n_train_balls"],
        "n_test_balls": engine_meta["n_test_balls"],
        "feature_importance": engine_meta["feature_importance"],
        "calibration": calib_rows,
        "data_quality_warnings": warnings,
        "artifacts": {
            "wp_model_pkl": str((ARTIFACTS / "wp_model.pkl").resolve()),
            "wp_model_metadata_json": str((ARTIFACTS / "wp_model.json").resolve()),
            "feature_importance_json": str((ARTIFACTS / "feature_importance.json").resolve()),
            "calibration_csv": str((ARTIFACTS / "calibration.csv").resolve()),
            "calibration_png": str((ARTIFACTS / "calibration.png").resolve()),
            "events_parquet": str(EVENTS_PARQUET.resolve()),
        },
        "seconds": round(time.time() - t0, 2),
    }
    (ARTIFACTS / "training_report.json").write_text(json.dumps(report, indent=2, default=str))

    # Pretty print
    print()
    print("=" * 60)
    print("PITCHWISE WP MODEL — TRAINING REPORT")
    print("=" * 60)
    print(f"Methodology: {report['methodology_status']}")
    print(f"Matches: {report['matches_included']} included · "
          f"{report['matches_excluded']} excluded ({report['exclusion_reasons']})")
    print(f"Balls loaded: {report['total_balls_loaded']:,}")
    print(f"Class balance (chase won): {class_bal['chase_won_fraction']*100:.1f}%  "
          f"({class_bal['second_innings_balls']:,} 2nd-innings balls)")
    print(f"Train / test balls: {report['n_train_balls']:,} / {report['n_test_balls']:,}")
    print(f"AUC: {report['auc']:.4f}   Brier: {report['brier_score']:.4f}")
    print()
    print("Feature importance:")
    for feat, imp in sorted(report["feature_importance"].items(), key=lambda x: -x[1]):
        print(f"  {feat:<20} {imp:.4f}")
    print()
    print("Calibration (predicted → actual):")
    for r in calib_rows:
        print(f"  {r['predicted']*100:>6.1f}% → {r['actual']*100:>6.1f}%")
    if warnings:
        print()
        print("Data quality warnings:")
        for w in warnings:
            print(f"  ! {w}")
    print()
    print(f"Artifacts saved under {ARTIFACTS}:")
    for k in ("wp_model_pkl", "wp_model_metadata_json", "feature_importance_json",
              "calibration_csv", "calibration_png", "events_parquet"):
        print(f"  {k}: {report['artifacts'][k]}")
    print(f"Elapsed: {report['seconds']}s")


def main():
    p = argparse.ArgumentParser(description="Train the PitchWise WP model.")
    p.add_argument("--include-tied", action="store_true",
                   help="Include tied/no_result matches (default: exclude per Stage 1 decision)")
    p.add_argument("--dry-run", action="store_true", help="Build events.parquet without training")
    args = p.parse_args()
    asyncio.run(_run(exclude_tied=not args.include_tied, dry_run=args.dry_run))

if __name__ == "__main__":
    main()
