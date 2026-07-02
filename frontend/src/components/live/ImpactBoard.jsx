import { motion } from "framer-motion";
import RatingBadge from "@/components/rating/RatingBadge";
import Sparkline from "@/components/rating/Sparkline";

/**
 * Top impact ratings — the leaderboard of the match, right now.
 * Cards are tappable in later milestones (WhySheet).
 * M2: tap emits a callback but content is stubbed.
 */
export default function ImpactBoard({ rows = [], onExplain }) {
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

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {rows.slice(0, 6).map((r, i) => (
          <motion.article
            key={r.player_id}
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.35, delay: i * 0.05 }}
            data-testid={`impact-row-${r.player_id}`}
            className="rounded-lg border border-border/60 bg-card p-4 flex items-center justify-between gap-4"
          >
            <div className="min-w-0">
              <div className="flex items-center gap-2 mb-1">
                <span className="text-[10px] uppercase tracking-widest text-dim rating-num">
                  {r.team}
                </span>
                <span className="text-dim">·</span>
                <span className="text-[10px] uppercase tracking-widest text-dim">{r.role}</span>
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
        ))}
      </div>
    </section>
  );
}
