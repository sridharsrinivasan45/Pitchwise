import { formatOver } from "@/lib/format";

export default function MatchHeader({ match, currentOver, currentBall }) {
  if (!match) return null;
  const [home, away] = match.team_short || ["", ""];
  return (
    <header className="flex flex-wrap items-end justify-between gap-6 pb-6 border-b divider-soft" data-testid="match-header">
      <div>
        <div className="flex items-center gap-2 mb-2">
          <span className="text-[10px] uppercase tracking-widest px-2 py-0.5 rounded-sm bg-amber-soft border border-amber-soft"
            style={{ color: "hsl(var(--primary))" }}>
            {match.status === "live" ? "Live" : "Time Machine"}
          </span>
          <span className="rating-num text-xs text-dim">{match.season} · {match.date}</span>
          {match.curation_title && (
            <>
              <span className="text-dim">·</span>
              <span className="text-xs text-muted-foreground">{match.curation_title}</span>
            </>
          )}
        </div>
        <div className="flex items-baseline gap-3">
          <span className="font-editorial text-4xl md:text-5xl leading-none tracking-tight">{home}</span>
          <span className="text-dim rating-num text-sm">vs</span>
          <span className="font-editorial text-4xl md:text-5xl leading-none tracking-tight">{away}</span>
        </div>
        <div className="text-dim text-xs mt-2">{match.venue}</div>
      </div>

      <div className="flex flex-col items-start md:items-end gap-1">
        <span className="rating-num text-sm text-muted-foreground">
          Over {formatOver(currentOver, currentBall)} · {match.ball_count} balls
        </span>
        <span className="rating-num text-lg font-medium">{match.final_score}</span>
        <span className="text-positive text-xs">{match.result_summary}</span>
      </div>
    </header>
  );
}
