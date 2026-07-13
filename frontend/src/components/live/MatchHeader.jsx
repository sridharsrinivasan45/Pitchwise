import { formatOver } from "@/lib/format";

/**
 * Match header — the score is always the visual hero.
 * Layout:
 *   Mobile   : meta chip, team vs team, venue, then a compact score row
 *   Desktop  : meta chip + team vs team on the left, score panel on the right
 */
export default function MatchHeader({ match, currentOver, currentBall }) {
  if (!match) return null;
  const [home, away] = match.team_short || ["", ""];
  return (
    <header
      className="flex flex-col md:flex-row md:items-end md:justify-between gap-4 md:gap-6 pb-6 border-b divider-soft"
      data-testid="match-header"
    >
      {/* Left: meta + team names + venue */}
      <div className="min-w-0">
        <div className="flex items-center gap-2 mb-2 flex-wrap">
          <span
            className="text-[10px] uppercase tracking-widest px-2 py-0.5 rounded-sm bg-amber-soft border border-amber-soft"
            style={{ color: "hsl(var(--primary))" }}
          >
            {match.status === "live" ? "Live" : "Time Machine"}
          </span>
          <span className="rating-num text-xs text-dim">{match.season} · {match.date}</span>
          {match.curation_title && (
            <>
              <span className="text-dim" aria-hidden="true">·</span>
              <span className="text-xs text-muted-foreground truncate">{match.curation_title}</span>
            </>
          )}
        </div>
        <div className="flex items-baseline gap-3 flex-wrap">
          <span className="font-editorial text-4xl md:text-5xl leading-none tracking-tight">{home}</span>
          <span className="text-dim rating-num text-sm">vs</span>
          <span className="font-editorial text-4xl md:text-5xl leading-none tracking-tight">{away}</span>
        </div>
        {match.venue && (
          <div className="text-dim text-xs mt-2 truncate">{match.venue}</div>
        )}
      </div>

      {/* Right: score / progress panel */}
      <div className="flex flex-row md:flex-col md:items-end items-baseline justify-between md:justify-end gap-2 md:gap-1 pt-3 md:pt-0 border-t md:border-t-0 divider-soft">
        <div className="flex flex-col md:items-end">
          <span className="rating-num text-[10px] uppercase tracking-widest text-dim">Score</span>
          <span className="rating-num text-xl md:text-lg font-medium leading-tight">{match.final_score}</span>
          <span className="text-positive text-xs">{match.result_summary}</span>
        </div>
        <span className="rating-num text-xs md:text-sm text-muted-foreground md:mt-1 whitespace-nowrap">
          Over {formatOver(currentOver, currentBall)} · {match.ball_count} balls
        </span>
      </div>
    </header>
  );
}
