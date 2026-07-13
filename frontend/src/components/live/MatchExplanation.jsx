import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import { api } from "@/lib/api";

/**
 * MatchExplanation — PitchWise's translation layer, rendered in the UI.
 *
 * Renders three levels of engine-grounded prose:
 *   1. Match Verdict   (why the match ended the way it did)
 *   2. Turning Point   (the biggest single-over WPA swing)
 *   3. Player summary  (per top-6 impact-board player)
 *
 * Everything comes from GET /api/matches/{id}/narration. Sentences are
 * template-first and LLM-polished on the backend; this component does no
 * rewriting of its own.
 */
export default function MatchExplanation({ matchId }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (!matchId) return;
    let cancelled = false;
    setLoading(true);
    setError(null);
    api.get(`/matches/${matchId}/narration`)
      .then((r) => { if (!cancelled) setData(r.data); })
      .catch((e) => {
        if (!cancelled) setError(e?.response?.status === 404 ? "No explanation available." : (e.message || "Failed"));
      })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [matchId]);

  if (loading) {
    return (
      <section className="rounded-xl border border-border/50 bg-card/40 p-6" data-testid="match-explanation-loading">
        <p className="text-[10px] uppercase tracking-widest text-dim mb-2">Match verdict</p>
        <p className="text-dim text-sm">Reading the engine…</p>
      </section>
    );
  }

  if (error || !data) {
    return null; // silent — never show broken narration
  }

  const { verdict, turning_point, players } = data;

  return (
    <section
      className="rounded-xl border border-amber-soft bg-card/40 p-6 md:p-8"
      data-testid="match-explanation"
    >
      {/* Verdict */}
      <div className="mb-6" data-testid="match-verdict">
        <p className="text-[10px] uppercase tracking-widest text-dim mb-2"
          style={{ color: "hsl(var(--primary))" }}>
          Match verdict
        </p>
        <motion.h2
          initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.4 }}
          className="font-editorial text-2xl md:text-3xl leading-snug"
        >
          {verdict.polished || verdict.sentence}
        </motion.h2>
      </div>

      {/* Turning point */}
      {turning_point && (
        <div className="mb-6 pl-4 border-l-2 border-border/60" data-testid="turning-point">
          <p className="text-[10px] uppercase tracking-widest text-dim mb-2">Turning point</p>
          <p className="text-base leading-relaxed text-foreground/90">
            {turning_point.polished || turning_point.sentence}
          </p>
        </div>
      )}

      {/* Players */}
      {players?.length > 0 && (
        <div data-testid="player-explanations">
          <p className="text-[10px] uppercase tracking-widest text-dim mb-3">
            Why each player rated the way they did
          </p>
          <ul className="space-y-2.5">
            {players.map((p, i) => (
              <li
                key={p.evidence?.player_id || i}
                data-testid={`player-explanation-${p.evidence?.player_id || i}`}
                className="flex items-start gap-3 text-sm leading-relaxed text-foreground/90"
              >
                <span className="mt-1 h-1.5 w-1.5 rounded-full shrink-0"
                  style={{ background: "hsl(var(--primary))" }} />
                <span>{p.polished || p.sentence}</span>
              </li>
            ))}
          </ul>
        </div>
      )}

      <p className="mt-6 text-[11px] text-dim">
        Every sentence above is a rendering of engine-computed evidence. No opinions, no drama.
      </p>
    </section>
  );
}
