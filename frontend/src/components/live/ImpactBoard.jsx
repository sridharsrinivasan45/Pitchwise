import { motion, AnimatePresence } from "framer-motion";
import RatingBadge from "@/components/rating/RatingBadge";
import Sparkline from "@/components/rating/Sparkline";

/**
 * Top impact ratings — the leaderboard of the match, right now.
 * Uses Framer motion `layout` so cards reorder smoothly when ratings swap.
 */
export default function ImpactBoard({ rows = [], onExplain, activePlayerId = null }) {
  if (!rows.length) {
    return (
      <div className="rounded-lg border border-border/50 bg-card/40 p-6 text-dim text-sm">
        Impact ratings will appear as balls are bowled.
      </div>
    );
  }

  return (
    <section data-testid="impact-board">
      <div className="mb-4 flex items-baseline justify-between">
        <div>
          <p className="text-[10px] uppercase tracking-widest text-dim">Impact board</p>
          <p className="font-editorial text-lg leading-tight">Who&apos;s changing this match</p>
        </div>
        <p className="text-xs text-dim">Tap a rating to see why</p>
      </div>

      <motion.div layout className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <AnimatePresence initial={false}>
          {rows.slice(0, 6).map((r) => {
            const isActive = activePlayerId && r.player_id === activePlayerId;
            return (
              <motion.article
                key={r.player_id}
                layout
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -8 }}
                transition={{ type: "spring", stiffness: 260, damping: 26 }}
                data-testid={`impact-row-${r.player_id}`}
                className={`rounded-lg border p-4 flex items-center justify-between gap-4 ${
                  isActive
                    ? "border-amber-soft bg-card shadow-[0_0_0_1px_hsla(38,92%,55%,0.15)]"
                    : "border-border/60 bg-card"
                }`}
              >
                <div className="min-w-0">
                  <div className="flex items-center gap-2 mb-1">
                    <span className="text-[10px] uppercase tracking-widest text-dim rating-num">
                      {r.team}
                    </span>
                    <span className="text-dim">·</span>
                    <span className="text-[10px] uppercase tracking-widest text-dim">{r.role}</span>
                    {isActive && (
                      <span className="text-[9px] uppercase tracking-widest rating-num px-1.5 py-0.5 rounded-sm bg-amber-soft"
                        style={{ color: "hsl(var(--primary))" }}>
                        On strike
                      </span>
                    )}
                  </div>
                  <p className="font-editorial text-lg leading-tight truncate">{r.player_name}</p>
                  <div className="mt-2">
                    <Sparkline values={r.sparkline || []} width={100} height={20} testId={`sparkline-${r.player_id}`} />
                  </div>
                </div>
                <RatingBadge
                  rating={r.rating}
                  delta={r.delta}
                  size="md"
                  onExplain={onExplain ? () => onExplain(r) : undefined}
                  testId={`rating-${r.player_id}`}
                />
              </motion.article>
            );
          })}
        </AnimatePresence>
      </motion.div>
    </section>
  );
}
