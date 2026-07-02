import { formatOver, momentTypeLabel } from "@/lib/format";
import { Flame, Circle } from "lucide-react";

/**
 * The current top moment (or latest_moment). Shows type, over.ball, narrative.
 * In M4+ this becomes a jump-in-time trigger for the momentum chart + WhySheet.
 */
export default function MomentCard({ moment, onExplain }) {
  if (!moment) {
    return (
      <div className="rounded-lg border border-border/50 bg-card/40 p-6 text-dim text-sm" data-testid="moment-card-empty">
        No key moments yet.
      </div>
    );
  }

  const isTurning = moment.type === "match_turning_point";
  const clickable = !!onExplain;

  const Wrapper = clickable ? "button" : "article";

  return (
    <Wrapper
      data-testid="moment-card"
      onClick={clickable ? () => onExplain(moment) : undefined}
      className={`w-full text-left rounded-lg border p-5 bg-card transition-colors ${
        isTurning ? "border-amber-soft" : "border-border/60"
      } ${clickable ? "hover:border-amber-soft cursor-pointer" : ""}`}
    >
      <div className="flex items-center gap-2 mb-3">
        {isTurning ? (
          <Flame className="w-3.5 h-3.5" style={{ color: "hsl(var(--primary))" }} />
        ) : (
          <Circle className="w-3.5 h-3.5 text-dim" />
        )}
        <span
          className="text-[10px] uppercase tracking-widest"
          style={isTurning ? { color: "hsl(var(--primary))" } : {}}
        >
          {momentTypeLabel(moment.type)}
        </span>
        <span className="text-dim">·</span>
        <span className="rating-num text-xs text-dim">
          Over {formatOver(moment.over, moment.ball)}
        </span>
        <span className="ml-auto rating-num text-xs">
          Impact <span className={isTurning ? "" : "text-foreground"} style={isTurning ? { color: "hsl(var(--primary))" } : {}}>
            {moment.impact_score.toFixed(1)}
          </span>
        </span>
      </div>

      <p className="font-editorial text-xl leading-snug">{moment.narrative}</p>

      <div className="mt-4 flex items-center justify-between">
        <span className="text-xs text-dim">
          {clickable ? "Tap to see why this moment mattered" : "Why did this moment matter?"}
        </span>
      </div>
    </Wrapper>
  );
}
