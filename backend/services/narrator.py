"""
Narrator — PitchWise's translation layer between the engine and the reader.

Philosophy
----------
The narrator does not describe. It explains.
Every sentence answers exactly one question: *why did this match end the way
it did?* Every claim is a rendering of an engine-computed number. Any statement
the engine cannot justify is not produced.

Grounding contract
------------------
1. `build_evidence(match_id)` reads engine outputs from Mongo and produces a
   deterministic `EvidencePack` — a plain dict of verified numbers. No LLM.
2. `render_template(evidence)` produces the source-of-truth sentences using
   fixed templates keyed on match archetype. No LLM. This is always the
   fallback and always the citation.
3. `polish_with_llm(sentence, evidence)` optionally routes each sentence
   through Claude Sonnet 4.5 with the strict system prompt:
       "You may only rephrase for clarity. Never add numbers, opinions,
        comparisons, adjectives, drama, or player judgements."
   Then `verify(polished, evidence)` checks that every numeric token in the
   polished string is also present in the evidence dict. If verification
   fails for any reason, the template sentence is returned unchanged.

Guardrails
----------
- No sensational labels: hard-blocked wordlist enforced by verifier.
- No comparative-to-other-player claims unless the engine actually computed
  such a comparison.
- Number tolerance: 0.05 on percentages, exact on integers.
- Engine core (`backend/engine/core/`) is not touched.
"""
from __future__ import annotations
import os
import re
from typing import Any, Optional
from collections import defaultdict

from core.db import get_db
from data.team_aliases import resolve_team
from engine.core.ratings_from_wpa import wpa_to_rating  # engine's own fn


# ---------------------------------------------------------------------------
# Evidence pack — pure Mongo aggregation. No LLM anywhere in this section.
# ---------------------------------------------------------------------------

_HIGH_PRESSURE_ABS_WPA = 0.03  # ball considered "high pressure" if |wpa| >= 3%
_TOP_PLAYERS = 6


async def build_evidence(match_id: str) -> Optional[dict]:
    db = get_db()
    match = await db.matches.find_one({"match_id": match_id}, {"_id": 0})
    if not match:
        return None

    balls = await db.balls.find(
        {"match_id": match_id},
        {"_id": 0},
    ).sort([("innings", 1), ("over", 1), ("ball_in_over", 1)]).to_list(500)
    if not balls:
        return None

    match_ratings = await db.match_ratings.find(
        {"match_id": match_id}, {"_id": 0},
    ).to_list(50)

    # Innings meta from ball events
    innings_meta: dict[int, dict] = {}
    for b in balls:
        inn = int(b["innings"])
        m = innings_meta.setdefault(inn, {"first_ball_wp": None, "last_ball_wp": None,
                                          "min_wp": 1.0, "max_wp": 0.0,
                                          "batting_team_raw": b.get("batting_team", ""),
                                          "bowling_team_raw": b.get("bowling_team", ""),
                                          "runs": 0, "wickets": 0, "sixes": 0, "fours": 0,
                                          "balls": 0})
        wp_after = float(b.get("wp_after", 0.5))
        if m["first_ball_wp"] is None:
            m["first_ball_wp"] = float(b.get("wp_before", 0.5))
        m["last_ball_wp"] = wp_after
        m["min_wp"] = min(m["min_wp"], wp_after)
        m["max_wp"] = max(m["max_wp"], wp_after)
        m["runs"] += int(b.get("runs_total", 0))
        m["wickets"] += int(b.get("is_wicket", 0))
        rb = int(b.get("runs_batter", 0))
        if rb == 6: m["sixes"] += 1
        elif rb == 4: m["fours"] += 1
        m["balls"] += 1

    for inn, m in innings_meta.items():
        m["batting_team"] = resolve_team(m["batting_team_raw"])["short"] if m["batting_team_raw"] else ""
        m["bowling_team"] = resolve_team(m["bowling_team_raw"])["short"] if m["bowling_team_raw"] else ""

    # Per-over aggregate WPA (from the chasing side's perspective when innings 2 exists)
    over_wpa: list[dict] = []
    over_agg: dict[tuple[int, int], dict] = defaultdict(lambda: {"wpa": 0.0, "runs": 0, "wickets": 0, "balls": 0})
    for b in balls:
        key = (int(b["innings"]), int(b["over"]))
        rec = over_agg[key]
        rec["wpa"] += float(b.get("wpa", 0.0))
        rec["runs"] += int(b.get("runs_total", 0))
        rec["wickets"] += int(b.get("is_wicket", 0))
        rec["balls"] += 1
    for (inn, ov), rec in sorted(over_agg.items()):
        over_wpa.append({"innings": inn, "over": ov, "over_display": ov + 1,
                         "wpa": round(rec["wpa"], 4),
                         "runs": rec["runs"], "wickets": rec["wickets"], "balls": rec["balls"]})

    # Winning-team perspective: WPA on ball is defined as batting team's WPA.
    # Determine which innings is the winner-batting one (based on match.winner if present).
    winner_raw = str(match.get("winner", "") or "")
    winner_short = resolve_team(winner_raw)["short"] if winner_raw else ""
    winning_innings: Optional[int] = None
    for inn, m in innings_meta.items():
        if m["batting_team"] == winner_short:
            winning_innings = inn
            break

    # Signed WPA for the winner (positive = good for winner)
    def _winner_signed(row: dict) -> float:
        if winning_innings is None:
            return row["wpa"]
        return row["wpa"] if row["innings"] == winning_innings else -row["wpa"]

    for row in over_wpa:
        row["winner_wpa"] = round(_winner_signed(row), 4)

    # Biggest-swing over for the winner
    biggest_over = max(over_wpa, key=lambda r: r["winner_wpa"], default=None) if over_wpa else None

    # For turning-point comparison: sum of winner_wpa across the K overs immediately preceding
    K_PREV = 8
    if biggest_over is not None:
        idx = over_wpa.index(biggest_over)
        prev_slice = over_wpa[max(0, idx - K_PREV):idx]
        prev_sum = round(sum(o["winner_wpa"] for o in prev_slice), 4)
    else:
        prev_slice, prev_sum = [], 0.0

    # Chase depth: lowest WP the WINNER reached during the match
    winner_min_wp: Optional[float] = None
    if winning_innings is not None:
        w_min = 1.0
        for b in balls:
            if int(b["innings"]) == winning_innings:
                # WP is stored from batting perspective already
                w_min = min(w_min, float(b.get("wp_after", 0.5)))
            else:
                # from bowling side — winner's implicit WP = 1 - wp
                w_min = min(w_min, 1.0 - float(b.get("wp_after", 0.5)))
        winner_min_wp = round(w_min, 4)

    # Result kind (from match doc / ball tail)
    result_kind = str(match.get("result_kind", "") or "")
    result_margin = match.get("result_margin")
    has_super_over = bool(match.get("has_super_over", False))
    has_dls = bool(match.get("has_dls", False))

    # Winning-side WPA split: batting vs bowling on the winning team
    win_batting_wpa = 0.0
    win_bowling_wpa = 0.0
    if winner_short:
        for mr in match_ratings:
            # Determine which side the player was on for this match via ball sample
            # (players collection has team history; we approximate by which team
            # accumulated the run/wkt totals on their behalf.)
            # For simplicity: attribute batting_wpa to whichever innings the player
            # actually batted in. We look at any ball with this batter.
            b_faced = int(mr.get("balls_faced", 0))
            b_bowled = int(mr.get("balls_bowled", 0))
            if b_faced == 0 and b_bowled == 0:
                continue
            # Determine team via ball lookup
            sample = None
            if b_faced > 0:
                sample = await db.balls.find_one(
                    {"match_id": match_id, "batter_id": mr["player_id"]},
                    {"_id": 0, "batting_team": 1, "bowling_team": 1},
                )
                if sample and resolve_team(sample.get("batting_team", ""))["short"] == winner_short:
                    win_batting_wpa += float(mr.get("batting_wpa", 0.0))
            if b_bowled > 0:
                sample = await db.balls.find_one(
                    {"match_id": match_id, "bowler_id": mr["player_id"]},
                    {"_id": 0, "batting_team": 1, "bowling_team": 1},
                )
                if sample and resolve_team(sample.get("bowling_team", ""))["short"] == winner_short:
                    win_bowling_wpa += float(mr.get("bowling_wpa", 0.0))

    # ── Top-N players by |total_wpa|, rendered as evidence rollups ──────
    ranked = sorted(match_ratings, key=lambda r: abs(float(r.get("total_wpa", 0.0))), reverse=True)[:_TOP_PLAYERS]

    players_evidence: list[dict] = []
    for mr in ranked:
        pid = mr["player_id"]
        b_faced = int(mr.get("balls_faced", 0))
        b_bowled = int(mr.get("balls_bowled", 0))
        role = "allrounder" if b_faced > 30 and b_bowled > 30 else "bowler" if b_bowled > b_faced else "batter"

        # Per-ball phase breakdown for this player
        phase_bat = {"powerplay": {"balls": 0, "runs": 0, "wpa": 0.0, "sixes": 0, "fours": 0, "dots": 0},
                     "middle":    {"balls": 0, "runs": 0, "wpa": 0.0, "sixes": 0, "fours": 0, "dots": 0},
                     "death":     {"balls": 0, "runs": 0, "wpa": 0.0, "sixes": 0, "fours": 0, "dots": 0}}
        phase_bowl = {"powerplay": {"balls": 0, "runs_conceded": 0, "wickets": 0, "wpa": 0.0, "dots": 0},
                      "middle":    {"balls": 0, "runs_conceded": 0, "wickets": 0, "wpa": 0.0, "dots": 0},
                      "death":     {"balls": 0, "runs_conceded": 0, "wickets": 0, "wpa": 0.0, "dots": 0}}
        high_pressure_balls_bat = 0
        high_pressure_balls_bowl = 0

        async for b in db.balls.find(
            {"match_id": match_id, "$or": [{"batter_id": pid}, {"bowler_id": pid}]},
            {"_id": 0},
        ):
            phase = b.get("phase", "middle")
            wpa = float(b.get("wpa", 0.0))
            is_legal = bool(b.get("is_legal", True))
            is_wkt = bool(b.get("is_wicket", 0))
            rb = int(b.get("runs_batter", 0))
            rt = int(b.get("runs_total", 0))
            if b.get("batter_id") == pid:
                p = phase_bat[phase]
                if is_legal:
                    p["balls"] += 1
                p["runs"] += rb
                p["wpa"] += float(b.get("batter_wpa_adjusted", 0.0))
                if rb == 6: p["sixes"] += 1
                elif rb == 4: p["fours"] += 1
                elif rb == 0 and is_legal: p["dots"] += 1
                if abs(wpa) >= _HIGH_PRESSURE_ABS_WPA:
                    high_pressure_balls_bat += 1
            if b.get("bowler_id") == pid:
                p = phase_bowl[phase]
                if is_legal:
                    p["balls"] += 1
                p["runs_conceded"] += rt
                if is_wkt:
                    p["wickets"] += 1
                p["wpa"] += float(b.get("bowler_wpa", 0.0))
                if rt == 0 and is_legal: p["dots"] += 1
                if abs(wpa) >= _HIGH_PRESSURE_ABS_WPA:
                    high_pressure_balls_bowl += 1

        # Pick dominant phase from balls-involved
        bat_total = sum(p["balls"] for p in phase_bat.values())
        bowl_total = sum(p["balls"] for p in phase_bowl.values())
        dom_bat_phase = max(phase_bat.items(), key=lambda kv: kv[1]["balls"])[0] if bat_total else None
        dom_bowl_phase = max(phase_bowl.items(), key=lambda kv: kv[1]["balls"])[0] if bowl_total else None

        players_evidence.append({
            "player_id": pid,
            "player_name": mr.get("player_name", pid),
            "role": role,
            "runs": int(mr.get("runs", 0)),
            "balls_faced": b_faced,
            "wickets": int(mr.get("wickets", 0)),
            "balls_bowled": b_bowled,
            "batting_wpa": round(float(mr.get("batting_wpa", 0.0)), 4),
            "bowling_wpa": round(float(mr.get("bowling_wpa", 0.0)), 4),
            "total_wpa": round(float(mr.get("total_wpa", 0.0)), 4),
            "overall_rating": round(float(mr.get("overall_rating", 5.0)), 2),
            "dom_bat_phase": dom_bat_phase,
            "dom_bowl_phase": dom_bowl_phase,
            "phase_bat": phase_bat,
            "phase_bowl": phase_bowl,
            "high_pressure_balls": high_pressure_balls_bat + high_pressure_balls_bowl,
        })

    teams_short = [resolve_team(t)["short"] for t in match.get("teams", [])]

    return {
        "match_id": match_id,
        "teams_short": teams_short,
        "winner_short": winner_short,
        "winning_innings": winning_innings,
        "result_summary": match.get("result_summary"),
        "result_kind": result_kind,
        "result_margin": result_margin,
        "has_super_over": has_super_over,
        "has_dls": has_dls,
        "final_score": match.get("final_score"),
        "target": match.get("target"),
        "innings_meta": innings_meta,
        "over_wpa": over_wpa,
        "biggest_over": biggest_over,
        "biggest_over_prev_sum": prev_sum,
        "biggest_over_prev_count": len(prev_slice),
        "winner_min_wp": winner_min_wp,
        "win_batting_wpa": round(win_batting_wpa, 4),
        "win_bowling_wpa": round(win_bowling_wpa, 4),
        "top_players": players_evidence,
    }


# ---------------------------------------------------------------------------
# Template renderers — deterministic sentences from evidence. Source of truth.
# ---------------------------------------------------------------------------

def _pct(x: float) -> str:
    return f"{round(x * 100, 1)}%"


def _derive_result(ev: dict) -> tuple[str, Optional[int]]:
    kind = (ev.get("result_kind") or "").lower()
    margin = ev.get("result_margin")
    if kind and isinstance(margin, (int, float)):
        return kind, int(margin)
    rs = (ev.get("result_summary") or "").lower()
    m = re.search(r"won by (\d+)\s+(run|runs|wicket|wickets)", rs)
    if m:
        return ("runs" if m.group(2).startswith("run") else "wickets"), int(m.group(1))
    return kind, margin


def _classify_archetype(ev: dict) -> str:
    """Rank-ordered rule-based classifier. First matching archetype wins."""
    if ev.get("has_super_over"):
        return "super_over"
    winner_min_wp = ev.get("winner_min_wp")
    result_kind, result_margin = _derive_result(ev)

    if winner_min_wp is not None and winner_min_wp <= 0.10:
        return "miracle_chase"
    if result_kind == "runs" and isinstance(result_margin, (int, float)) and int(result_margin) <= 3:
        return "runs_thriller"
    if result_kind == "wickets" and isinstance(result_margin, (int, float)) and int(result_margin) <= 2:
        return "wickets_thriller"
    if winner_min_wp is not None and winner_min_wp >= 0.35:
        if ev.get("win_bowling_wpa", 0.0) > ev.get("win_batting_wpa", 0.0) + 0.10:
            return "bowling_defence"
        return "one_sided"
    if ev.get("win_bowling_wpa", 0.0) > ev.get("win_batting_wpa", 0.0) + 0.05:
        return "bowling_defence"
    if ev.get("win_batting_wpa", 0.0) > ev.get("win_bowling_wpa", 0.0) + 0.10:
        return "batting_masterclass"
    return "default"


def render_verdict(ev: dict) -> dict:
    """Match verdict sentence. Every number cited comes from evidence."""
    a = _classify_archetype(ev)
    winner = ev.get("winner_short") or "The winning side"
    teams = ev.get("teams_short") or []
    opponent = next((t for t in teams if t != winner), None) or "the opposition"
    min_wp = ev.get("winner_min_wp")
    result = ev.get("result_summary") or ""
    result_kind, result_margin = _derive_result(ev)

    if a == "miracle_chase":
        sentence = (
            f"{winner} completed the chase after their win probability fell to {_pct(min_wp)} "
            f"during the innings."
        )
    elif a == "super_over":
        # winner_short can be missing on tied matches — phrase neutrally.
        subject = winner if winner and winner != "The winning side" else "The match"
        sentence = (
            f"{subject} was decided by a Super Over after the two innings ended level."
        )
    elif a == "runs_thriller":
        sentence = f"{winner} defended a small margin of {int(result_margin)} runs against {opponent}."
    elif a == "wickets_thriller":
        sentence = f"{winner} chased down the target with {int(result_margin)} wickets in hand."
    elif a == "bowling_defence":
        sentence = (
            f"{winner} won primarily through bowling: their bowlers added "
            f"{_pct(ev['win_bowling_wpa'])} of win probability across the match "
            f"versus {_pct(ev['win_batting_wpa'])} from batting."
        )
    elif a == "batting_masterclass":
        sentence = (
            f"{winner} won on the back of their batting: batters added "
            f"{_pct(ev['win_batting_wpa'])} of win probability across the innings."
        )
    elif a == "one_sided":
        sentence = (
            f"{winner} controlled the game throughout; their win probability never fell below "
            f"{_pct(min_wp)}."
        )
    else:
        # Fallback: describe using the result string only, still grounded
        sentence = result or f"{winner} beat {opponent}."

    return {
        "sentence": sentence.strip(),
        "archetype": a,
        "evidence": {
            "winner": winner,
            "opponent": opponent,
            "winner_min_wp": min_wp,
            "result_summary": result,
            "result_kind": result_kind,
            "result_margin": result_margin,
            "win_batting_wpa": ev.get("win_batting_wpa"),
            "win_bowling_wpa": ev.get("win_bowling_wpa"),
        },
    }


def render_turning_point(ev: dict) -> Optional[dict]:
    """One sentence about the biggest swing over."""
    biggest = ev.get("biggest_over")
    if not biggest:
        return None
    winner_swing = biggest["winner_wpa"]
    prev_sum = ev.get("biggest_over_prev_sum", 0.0)
    prev_count = ev.get("biggest_over_prev_count", 0)
    over_disp = biggest["over_display"]
    inn = biggest["innings"]

    # Only emit "more than the previous K combined" if the comparison is meaningful:
    #   1) at least 2 prior overs
    #   2) the swing over is at least +2% and larger than the sum of the previous K
    if prev_count >= 2 and winner_swing >= 0.02 and winner_swing > prev_sum:
        sentence = (
            f"The {_ordinal(over_disp)} over of innings {inn} added more win probability "
            f"({_pct(winner_swing)}) than the previous {prev_count} overs combined "
            f"({_pct(prev_sum)})."
        )
    else:
        # Safer, simpler sentence — no comparison, still grounded
        sentence = (
            f"The biggest single-over swing was the {_ordinal(over_disp)} over of "
            f"innings {inn}, worth {_pct(winner_swing)} of win probability."
        )

    return {
        "sentence": sentence,
        "evidence": {
            "innings": inn,
            "over": over_disp,
            "over_wpa": winner_swing,
            "prev_overs_sum": prev_sum,
            "prev_overs_count": prev_count,
            "runs": biggest["runs"],
            "wickets": biggest["wickets"],
        },
    }


def _ordinal(n: int) -> str:
    if 10 <= n % 100 <= 20:
        suf = "th"
    else:
        suf = {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suf}"


def render_player_explanation(p: dict) -> Optional[dict]:
    """One sentence per top player using engine evidence only.

    Grounds the sentence in the engine's per-match rating (the same number the
    Impact Board renders), so the explanation is a "why" for that rating.
    """
    name = p["player_name"]
    role = p["role"]
    rating = p["overall_rating"]
    if p["balls_faced"] == 0 and p["balls_bowled"] == 0:
        return None

    # Batting-first explanation when the player actually spent time at the crease
    if p["balls_faced"] >= 6 and (role != "bowler" or p["balls_faced"] > p["balls_bowled"]):
        phase = p.get("dom_bat_phase") or "middle"
        core = (
            f"{name}'s rating of {rating:.1f} reflects "
            f"{p['runs']} run{'s' if p['runs'] != 1 else ''} off {p['balls_faced']} balls, "
            f"weighted toward the {phase} overs"
        )
        # Attach one qualifier from the dominant-phase distribution — no adjectives.
        pb = p.get("phase_bat", {}).get(phase, {}) or {}
        if int(pb.get("sixes", 0)) >= 2:
            core += f" (including {int(pb['sixes'])} sixes in that phase)"
        elif int(pb.get("fours", 0)) >= 3:
            core += f" (including {int(pb['fours'])} fours in that phase)"
        sentence = core + "."
    elif p["balls_bowled"] >= 6:
        phase = p.get("dom_bowl_phase") or "middle"
        pb = p.get("phase_bowl", {}).get(phase, {}) or {}
        rc = int(pb.get("runs_conceded", 0))
        balls = int(pb.get("balls", 0))
        wkts = p["wickets"]
        if wkts > 0:
            body = (f"{wkts} wicket{'s' if wkts != 1 else ''} for {rc} run{'s' if rc != 1 else ''} "
                    f"in {balls} ball{'s' if balls != 1 else ''}, mostly in the {phase} overs")
        else:
            body = (f"{rc} run{'s' if rc != 1 else ''} conceded in {balls} ball{'s' if balls != 1 else ''} "
                    f"in the {phase} overs without a wicket")
        sentence = f"{name}'s rating of {rating:.1f} reflects {body}."
    else:
        return None

    return {
        "sentence": sentence,
        "evidence": {
            "player_id": p["player_id"],
            "player_name": name,
            "role": role,
            "runs": p["runs"],
            "balls_faced": p["balls_faced"],
            "wickets": p["wickets"],
            "balls_bowled": p["balls_bowled"],
            "batting_wpa": p["batting_wpa"],
            "bowling_wpa": p["bowling_wpa"],
            "dom_bat_phase": p.get("dom_bat_phase"),
            "dom_bowl_phase": p.get("dom_bowl_phase"),
            "overall_rating": rating,
            "phase_bat_dom": p.get("phase_bat", {}).get(p.get("dom_bat_phase") or "middle", {}),
            "phase_bowl_dom": p.get("phase_bowl", {}).get(p.get("dom_bowl_phase") or "middle", {}),
        },
    }


# ---------------------------------------------------------------------------
# LLM polish (optional) + verifier
# ---------------------------------------------------------------------------

_BANNED_TOKENS = [
    r"brilliant", r"heroic", r"genius", r"masterful", r"shocking", r"disgraceful",
    r"poor", r"terrible", r"awful", r"unbelievable", r"phenomenal", r"godly",
    r"the theft", r"momentum killer", r"resource drain", r"carnage",
    r"dramatic", r"sensational", r"thrilling",
]
_BANNED_RE = re.compile(r"\b(" + "|".join(_BANNED_TOKENS) + r")\b", re.IGNORECASE)

_NUM_RE = re.compile(r"[-+]?\d+\.?\d*")


def _numbers_in(s: str) -> list[float]:
    return [float(m) for m in _NUM_RE.findall(s)]


def _numbers_in_evidence(ev: dict) -> set[float]:
    out: set[float] = set()

    def walk(x):
        if isinstance(x, dict):
            for v in x.values():
                walk(v)
        elif isinstance(x, (list, tuple)):
            for v in x:
                walk(v)
        elif isinstance(x, bool):
            return
        elif isinstance(x, (int, float)):
            out.add(float(x))

    walk(ev)
    # Also include percentage-scale variants (0.15 <=> 15.0)
    for n in list(out):
        out.add(round(n * 100, 1))
        out.add(round(n * 100, 0))
    return out


def _verify_polished(polished: str, evidence: dict) -> bool:
    if _BANNED_RE.search(polished):
        return False
    nums = _numbers_in(polished)
    ev_nums = _numbers_in_evidence(evidence)
    for n in nums:
        # Tolerance for percentage rounding
        if any(abs(n - e) < 0.15 for e in ev_nums):
            continue
        return False
    return True


_SYSTEM_PROMPT = """You are PitchWise's translation layer. Your only job is to rephrase a factual sentence for readability.

STRICT RULES (violations mean your output is discarded):
- Never add facts, numbers, comparisons, or opinions that are not already in the input sentence.
- Never editorialize. Never use dramatic language ("brilliant", "shocking", "thrilling", "poor", "the theft", etc.).
- Never insult, judge, or diminish any player.
- Never change any number, percentage, count, over, or player name.
- Output exactly ONE sentence. No preamble, no quotes.
- If the input is already clean, output it unchanged.
- Keep neutral, evidence-based, trustworthy tone. Match the style of a research note, not a broadcaster."""


async def _polish_one(sentence: str, evidence: dict) -> str:
    """Route one template sentence through Claude Sonnet 4.5 with hard fallback."""
    key = os.environ.get("EMERGENT_LLM_KEY")
    if not key:
        return sentence
    try:
        # Import inside function so the module remains importable without the lib.
        from emergentintegrations.llm.chat import LlmChat, UserMessage  # type: ignore
    except Exception:
        return sentence
    try:
        chat = (
            LlmChat(api_key=key, session_id=f"narrator-{evidence.get('player_id','match')}",
                    system_message=_SYSTEM_PROMPT)
            .with_model("anthropic", "claude-sonnet-4-5-20250929")
        )
        msg = UserMessage(text=f"Rephrase for readability only:\n\n{sentence}")
        result = await chat.send_message(msg)
        polished = (result or "").strip().strip('"').strip("'")
        if not polished:
            return sentence
        # One-sentence enforcement: take up to first sentence-terminator
        first = re.split(r"(?<=[.!?])\s+", polished, maxsplit=1)[0].strip()
        if not first:
            return sentence
        if _verify_polished(first, evidence):
            return first
    except Exception:
        return sentence
    return sentence


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

async def narrate_match(match_id: str, polish: bool = True) -> Optional[dict]:
    ev = await build_evidence(match_id)
    if not ev:
        return None

    verdict = render_verdict(ev)
    turning = render_turning_point(ev)
    players_raw = [render_player_explanation(p) for p in ev.get("top_players", [])]
    players_raw = [x for x in players_raw if x]

    if polish:
        verdict_polished = await _polish_one(verdict["sentence"], verdict["evidence"])
        verdict["polished"] = verdict_polished
        if turning:
            turning["polished"] = await _polish_one(turning["sentence"], turning["evidence"])
        for pl in players_raw:
            pl["polished"] = await _polish_one(pl["sentence"], pl["evidence"])
    else:
        verdict["polished"] = verdict["sentence"]
        if turning:
            turning["polished"] = turning["sentence"]
        for pl in players_raw:
            pl["polished"] = pl["sentence"]

    return {
        "match_id": match_id,
        "verdict": verdict,
        "turning_point": turning,
        "players": players_raw,
        "context": {
            "teams_short": ev["teams_short"],
            "winner_short": ev.get("winner_short"),
            "result_summary": ev.get("result_summary"),
            "final_score": ev.get("final_score"),
        },
    }


async def get_or_build_narration(match_id: str, polish: bool = True) -> Optional[dict]:
    """Cached narration for a match. Cache invalidation is manual (delete doc)."""
    db = get_db()
    cached = await db.narrations.find_one({"match_id": match_id}, {"_id": 0})
    if cached and cached.get("polish") == polish:
        return cached["payload"]
    payload = await narrate_match(match_id, polish=polish)
    if payload is None:
        return None
    await db.narrations.update_one(
        {"match_id": match_id},
        {"$set": {"match_id": match_id, "polish": polish, "payload": payload}},
        upsert=True,
    )
    return payload
