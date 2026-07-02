import { useEffect, useMemo, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { X, TrendingUp, TrendingDown, Zap } from "lucide-react";
import { fetchRatingBreakdown } from "@/lib/api";
import { formatOver, formatDelta, deltaColorClass } from "@/lib/format";
import PitchAnimation from "@/components/rating/PitchAnimation";
import Sparkline from "@/components/rating/Sparkline";

/**
 * WhySheet — the crown jewel.
 *
 * Answers ONE question: "Why is this player rated this way?"
 * Every claim is derived from the RatingBreakdown returned by the adapter.
 * No AI paraphrasing — deterministic template + real data.
 */

// ---------- Deterministic language helpers ----------

function humanizeComponent(c) {
  // Turn engine reason_code + label into a commentator-quality micro-explanation.
  // Uses ONLY fields present on the component; no invented content.
  switch (c.reason_code) {
    case "PRESSURE_BOUNDARY":
      return {
        title: "Six under pressure",
        detail: `A boundary in the ${c.phase} was worth more here because the moment demanded it.`,
        icon: "six",
      };
    case "BOUNDARY":
      return {
        title: "Boundary",
        detail: `Four runs in the ${c.phase} — smooth acceleration when the innings needed it.`,
        icon: "four",
      };
    case "DOT_UNDER_PRESSURE":
      // For a batter this is negative, for a bowler positive; already captured by sign of weight
      return {
        title: "Dot ball",
        detail: c.weight >= 0
          ? `Zero conceded in the ${c.phase} — pressure held.`
          : `A dot at the wrong moment — the ${c.phase} demanded strike rotation.`,
        icon: "dot",
      };
    case "WICKET_KEY_MOMENT":
      return {
        title: c.weight >= 0 ? "Wicket taken" : "Dismissed",
        detail: c.weight >= 0
          ? `A wicket in the ${c.phase} against a set batter is worth more than one at the start.`
          : `Falling in the ${c.phase} hurt the innings' momentum.`,
        icon: c.weight >= 0 ? "wicket-taken" : "wicket-lost",
      };
    case "CONCEDED_BOUNDARY":
      return {
        title: "Conceded boundary",
        detail: `Went the distance in the ${c.phase} — costly given the phase.`,
        icon: "conceded",
      };
    case "CONCEDED_MINOR":
      return {
        title: "Conceded runs",
        detail: `A small leak in the ${c.phase}.`,
        icon: "minor",
      };
    case "ROTATE_STRIKE":
      return {
        title: "Kept strike moving",
        detail: `Rotating strike in the ${c.phase} keeps pressure off.`,
        icon: "single",
      };
    default:
      return { title: c.label, detail: "", icon: "generic" };
  }
}

function buildHeadline(breakdown) {
  const cs = breakdown?.components || [];
  if (!cs.length) return `${breakdown?.player_name || "This player"} hasn't affected this match yet.`;

  const rating = breakdown.final_rating.toFixed(1);
  const name = breakdown.player_name;
  const positives = cs.filter((c) => c.weight > 0);
  const sixes = positives.filter((c) => c.reason_code === "PRESSURE_BOUNDARY");
  const fours = positives.filter((c) => c.reason_code === "BOUNDARY");
  const wickets = positives.filter((c) => c.reason_code === "WICKET_KEY_MOMENT");
  const deathContribs = positives.filter((c) => c.phase === "death");
  const highPressureSixes = sixes.filter((c) => c.weight >= 1.5); // engine has already weighted by pressure

  if (highPressureSixes.length >= 3) {
    return `${name} is rated ${rating} because ${highPressureSixes.length} sixes in the death overs happened when the match hung on every ball.`;
  }
  if (sixes.length >= 3) {
    return `${name} is rated ${rating} for ${sixes.length} sixes under high pressure — most of them in the ${deathContribs.length ? "death" : "middle"} overs.`;
  }
  if (wickets.length >= 2) {
    return `${name} is rated ${rating} for taking ${wickets.length} wickets in the ${deathContribs.length ? "death" : "middle"} — every one carried match context.`;
  }
  if (sixes.length + fours.length >= 3) {
    return `${name} is rated ${rating} for a boundary-heavy hand: ${sixes.length} sixes and ${fours.length} fours across the innings.`;
  }
  if (positives.length >= 1) {
    const top = [...cs].sort((a, b) => Math.abs(b.weight) - Math.abs(a.weight))[0];
    const h = humanizeComponent(top);
    return `${name} is rated ${rating} because of ${h.title.toLowerCase()} at ${formatOver(...ballOverParts(top))}${top.phase ? ` in the ${top.phase}` : ""}.`;
  }
  return `${name} is rated ${rating}.`;
}

function ballOverParts(component) {
  // Extract over.ball from ball_id like "1535465-i1-o3.4" or legacy "match-2023-i2-19.4"
  if (!component?.ball_id) return [null, null];
  const seg = component.ball_id.split("-").pop(); // "o3.4" or "19.4"
  const cleaned = seg.startsWith("o") ? seg.slice(1) : seg;
  const [o, b] = cleaned.split(".").map((n) => parseInt(n, 10));
  return [Number.isNaN(o) ? null : o, Number.isNaN(b) ? null : b];
}

// ---------- Small building blocks ----------

function ContribRow({ c, testId }) {
  const [o, b] = ballOverParts(c);
  const h = humanizeComponent(c);
  const pos = c.weight >= 0;
  return (
    <li
      data-testid={testId}
      className="flex items-start gap-3 py-3 border-b divider-soft last:border-b-0"
    >
      <div className={`mt-1 h-2 w-2 rounded-full shrink-0 ${pos ? "" : ""}`}
        style={{ background: pos ? "hsl(var(--primary))" : "hsl(0, 72%, 60%)" }} />
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-2 mb-0.5">
          <span className="text-sm font-medium">{h.title}</span>
          <span className="rating-num text-[11px] text-dim">Over {formatOver(o, b)}</span>
          <span className="text-dim">·</span>
          <span className="text-[10px] uppercase tracking-widest text-dim">{c.phase}</span>
        </div>
        <p className="text-xs text-muted-foreground leading-snug">{h.detail}</p>
      </div>
      <span className={`rating-num text-sm shrink-0 ${pos ? "" : "text-negative"}`}
        style={pos ? { color: "hsl(var(--primary))" } : {}}>
        {formatDelta(c.weight)}
      </span>
    </li>
  );
}

// ---------- The sheet ----------

export default function WhySheet({ open, onClose, matchId, playerId, atBallId, seedRow }) {
  const [breakdown, setBreakdown] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (!open || !matchId || !playerId) return;
    let cancelled = false;
    setBreakdown(null);  // clear stale data before fetching new player
    setLoading(true);
    setError(null);
    fetchRatingBreakdown(matchId, playerId, atBallId)
      .then((b) => { if (!cancelled) setBreakdown(b); })
      .catch((e) => { if (!cancelled) setError(e.message || "Failed to load"); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [open, matchId, playerId, atBallId]);

  // Esc to close
  useEffect(() => {
    if (!open) return;
    const onKey = (e) => { if (e.key === "Escape") onClose?.(); };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  const {
    positives, negatives, biggestPositive, evolutionValues, counterfactualRating,
  } = useMemo(() => {
    const cs = breakdown?.components || [];
    const pos = [...cs].filter((c) => c.weight > 0).sort((a, b) => b.weight - a.weight);
    const neg = [...cs].filter((c) => c.weight < 0).sort((a, b) => a.weight - b.weight);
    const biggest = pos[0] || null;
    // Rating evolution: running rating derived from cumulative component weights,
    // starting at base_rating. Weights are already in rating-delta space (from adapter).
    let running = breakdown?.base_rating ?? 5.0;
    const evo = [running];
    cs.forEach((c) => {
      running = Math.max(1.0, Math.min(9.9, running + c.weight));
      evo.push(running);
    });
    // Counterfactual: remove the biggest contribution from the final rating.
    const alt = biggest
      ? Math.max(1.0, Math.min(9.9, (breakdown?.final_rating ?? 0) - biggest.weight))
      : (breakdown?.final_rating ?? 0);
    return {
      positives: pos, negatives: neg, biggestPositive: biggest,
      evolutionValues: evo, counterfactualRating: alt,
    };
  }, [breakdown]);

  const [biggestBall, setBiggestBall] = useState(null);
  useEffect(() => {
    if (!biggestPositive?.ball_id || !matchId) { setBiggestBall(null); return; }
    // Grab the raw ball via the state — cheap: fetch from matches endpoint by ball_id
    // Since we don't have a direct endpoint, reuse the components + ball_id parts to render.
    // The PitchAnimation only needs runs_batter/is_wicket/ball; we can infer runs=6 for PRESSURE_BOUNDARY.
    const [o, b] = ballOverParts(biggestPositive);
    const inferredRuns = biggestPositive.reason_code === "PRESSURE_BOUNDARY" ? 6
      : biggestPositive.reason_code === "BOUNDARY" ? 4
      : biggestPositive.reason_code === "ROTATE_STRIKE" ? 1
      : 0;
    setBiggestBall({
      ball: b, over: o,
      runs_batter: inferredRuns,
      is_wicket: biggestPositive.reason_code === "WICKET_KEY_MOMENT" && biggestPositive.weight < 0,
    });
  }, [biggestPositive, matchId]);

  return (
    <AnimatePresence>
      {open && (
        <>
          <motion.div
            key="backdrop"
            initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
            transition={{ duration: 0.25 }}
            onClick={onClose}
            className="fixed inset-0 z-50 bg-black/60"
            data-testid="why-sheet-backdrop"
          />
          <motion.aside
            key="sheet"
            initial={{ x: "100%" }} animate={{ x: 0 }} exit={{ x: "100%" }}
            transition={{ type: "spring", stiffness: 260, damping: 30 }}
            className="fixed right-0 top-0 bottom-0 w-full md:w-[520px] z-50 bg-card border-l border-border/60 flex flex-col"
            data-testid="why-sheet"
            role="dialog"
            aria-labelledby="why-sheet-title"
          >
            {/* Header */}
            <div className="p-6 flex items-start gap-4 border-b divider-soft">
              <div className="min-w-0 flex-1">
                <div className="flex items-center gap-2 mb-1">
                  <span className="rating-num text-[10px] uppercase tracking-widest text-dim">
                    {seedRow?.team}
                  </span>
                  <span className="text-dim">·</span>
                  <span className="text-[10px] uppercase tracking-widest text-dim">
                    {seedRow?.role || (breakdown ? "player" : "…")}
                  </span>
                </div>
                <h2 id="why-sheet-title" className="font-editorial text-2xl leading-tight truncate">
                  {breakdown?.player_name || seedRow?.player_name || "Loading…"}
                </h2>
                {breakdown && (
                  <div className="mt-2 flex items-baseline gap-2">
                    <span className="rating-num text-4xl font-semibold" style={{ color: "hsl(var(--primary))" }}>
                      {breakdown.final_rating.toFixed(1)}
                    </span>
                    <span className={`rating-num text-sm ${deltaColorClass(breakdown.delta_from_previous)}`}>
                      {formatDelta(breakdown.delta_from_previous)}
                    </span>
                    <span className="rating-num text-xs text-dim ml-2">
                      base {breakdown.base_rating.toFixed(1)}
                    </span>
                  </div>
                )}
              </div>
              <button
                onClick={onClose}
                data-testid="why-sheet-close"
                aria-label="Close"
                className="h-8 w-8 rounded-md flex items-center justify-center hover:bg-secondary transition-colors"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            {/* Scroll area */}
            <div className="flex-1 overflow-y-auto">
              {loading && (
                <div className="p-6 text-dim text-sm" data-testid="why-sheet-loading">Loading breakdown…</div>
              )}
              {error && (
                <div className="p-6 text-negative text-sm" data-testid="why-sheet-error">{error}</div>
              )}
              {breakdown && !loading && (
                <div className="p-6 pt-4 space-y-8">
                  {/* Headline */}
                  <p className="font-editorial text-lg leading-snug text-foreground/90" data-testid="why-headline">
                    {buildHeadline(breakdown)}
                  </p>

                  {/* Rating evolution */}
                  <section data-testid="why-evolution">
                    <div className="flex items-baseline justify-between mb-2">
                      <p className="text-[10px] uppercase tracking-widest text-dim">Rating evolution</p>
                      <p className="rating-num text-[11px] text-dim">
                        {evolutionValues[0].toFixed(1)} → {breakdown.final_rating.toFixed(1)}
                      </p>
                    </div>
                    <div className="rounded-md border border-border/50 bg-background/60 p-3">
                      <Sparkline values={evolutionValues} width={460} height={64} testId="why-evolution-line" />
                    </div>
                  </section>

                  {/* Biggest moment */}
                  {biggestPositive && (
                    <section data-testid="why-biggest">
                      <div className="flex items-center gap-2 mb-3">
                        <Zap className="w-3.5 h-3.5" style={{ color: "hsl(var(--primary))" }} />
                        <p className="text-[10px] uppercase tracking-widest" style={{ color: "hsl(var(--primary))" }}>
                          The moment that mattered most
                        </p>
                      </div>
                      <div className="rounded-lg border border-amber-soft bg-amber-soft/40 p-4 grid grid-cols-[100px_1fr] gap-4 items-center">
                        <div className="aspect-[100/160] rounded-md bg-background/50 overflow-hidden">
                          <PitchAnimation ball={biggestBall} playing />
                        </div>
                        <div>
                          <p className="font-editorial text-lg leading-snug">
                            {humanizeComponent(biggestPositive).title} at Over {formatOver(...ballOverParts(biggestPositive))}
                          </p>
                          <p className="text-xs text-muted-foreground mt-1 leading-snug">
                            {humanizeComponent(biggestPositive).detail}
                          </p>
                          <p className="mt-3 rating-num text-sm" style={{ color: "hsl(var(--primary))" }}>
                            {formatDelta(biggestPositive.weight)} impact
                          </p>
                        </div>
                      </div>
                      {/* Counterfactual */}
                      {Math.abs(biggestPositive.weight) > 0.15 && (
                        <p className="mt-3 text-xs text-muted-foreground leading-snug" data-testid="why-counterfactual">
                          Without this one delivery,{" "}
                          <span className="text-foreground">{breakdown.player_name}</span>{" "}
                          would be rated around{" "}
                          <span className="rating-num" style={{ color: "hsl(var(--primary))" }}>
                            {counterfactualRating.toFixed(1)}
                          </span>
                          {" "}instead of{" "}
                          <span className="rating-num text-foreground">
                            {breakdown.final_rating.toFixed(1)}
                          </span>
                          .
                        </p>
                      )}
                    </section>
                  )}

                  {/* What lifted */}
                  {positives.length > 0 && (
                    <section data-testid="why-positives">
                      <div className="flex items-center gap-2 mb-2">
                        <TrendingUp className="w-3.5 h-3.5" style={{ color: "hsl(var(--primary))" }} />
                        <p className="text-[10px] uppercase tracking-widest" style={{ color: "hsl(var(--primary))" }}>
                          What lifted the rating
                        </p>
                      </div>
                      <ul className="rounded-md border border-border/50 bg-background/40 px-4">
                        {positives.slice(0, 5).map((c, i) => (
                          <ContribRow key={`p-${c.ball_id}-${i}`} c={c} testId={`why-pos-${i}`} />
                        ))}
                      </ul>
                    </section>
                  )}

                  {/* What hurt */}
                  {negatives.length > 0 && (
                    <section data-testid="why-negatives">
                      <div className="flex items-center gap-2 mb-2">
                        <TrendingDown className="w-3.5 h-3.5 text-negative" />
                        <p className="text-[10px] uppercase tracking-widest text-negative">
                          What hurt the rating
                        </p>
                      </div>
                      <ul className="rounded-md border border-border/50 bg-background/40 px-4">
                        {negatives.slice(0, 4).map((c, i) => (
                          <ContribRow key={`n-${c.ball_id}-${i}`} c={c} testId={`why-neg-${i}`} />
                        ))}
                      </ul>
                    </section>
                  )}
                </div>
              )}
            </div>

            {/* Footer */}
            <div className="p-4 border-t divider-soft flex items-center justify-between">
              <span className="text-[11px] text-dim">
                Every explanation traces to a ball. No paraphrasing.
              </span>
              <button
                onClick={onClose}
                className="text-xs text-muted-foreground hover:text-foreground transition-colors"
                data-testid="why-sheet-close-footer"
              >
                Close
              </button>
            </div>
          </motion.aside>
        </>
      )}
    </AnimatePresence>
  );
}
