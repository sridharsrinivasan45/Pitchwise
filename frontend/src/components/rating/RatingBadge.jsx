import { motion } from "framer-motion";
import { formatDelta, deltaColorClass, ratingTone } from "@/lib/format";

/**
 * Reusable rating tile. Tappable across the product (invokes onExplain in later milestones).
 * sizes: sm (compact), md (default), lg (hero)
 */
export default function RatingBadge({
  rating,
  delta = 0,
  size = "md",
  onExplain,
  testId,
  showDelta = true,
}) {
  const tone = ratingTone(rating);
  const dims = {
    sm: { num: "text-lg", pad: "px-2 py-1", delta: "text-[10px]", minW: "min-w-[64px]" },
    md: { num: "text-3xl", pad: "px-3 py-2", delta: "text-xs", minW: "min-w-[88px]" },
    lg: { num: "text-5xl", pad: "px-4 py-3", delta: "text-sm", minW: "min-w-[128px]" },
  }[size];

  const toneRing = {
    hot: "ring-1 ring-inset ring-amber-soft bg-amber-soft",
    warm: "ring-1 ring-inset ring-border/60",
    neutral: "ring-1 ring-inset ring-border/40",
    cold: "ring-1 ring-inset ring-border/30 opacity-90",
  }[tone];

  const numColor = tone === "hot" ? "" : "text-foreground";

  const clickable = !!onExplain;

  return (
    <button
      type="button"
      disabled={!clickable}
      onClick={clickable ? onExplain : undefined}
      data-testid={testId || "rating-badge"}
      className={`group inline-flex items-center justify-center gap-2 rounded-md ${dims.pad} ${dims.minW} ${toneRing} bg-card transition-transform ${
        clickable ? "hover:-translate-y-0.5 cursor-pointer" : "cursor-default"
      }`}
      style={tone === "hot" ? { color: "hsl(var(--primary))" } : {}}
    >
      <motion.span
        key={rating}
        initial={{ opacity: 0, y: -4 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.25 }}
        className={`rating-num font-semibold leading-none ${dims.num} ${numColor}`}
      >
        {rating != null ? rating.toFixed(1) : "—"}
      </motion.span>
      {showDelta && (
        <span className={`rating-num ${dims.delta} ${deltaColorClass(delta)} leading-none`}>
          {formatDelta(delta)}
        </span>
      )}
    </button>
  );
}
