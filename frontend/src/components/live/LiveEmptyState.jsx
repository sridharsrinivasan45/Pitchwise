import { Link } from "react-router-dom";
import { ArrowRight, Clock3, Compass } from "lucide-react";

/**
 * Elegant empty state for /live when no match has been selected yet.
 * Renders:
 *   - a "Choose a Match" hero
 *   - a "Continue last viewed" card (only if lastMatch preview is available)
 *   - a "Browse Time Machine" primary CTA
 * No hardcoded match ids anywhere.
 */
export default function LiveEmptyState({ lastMatch }) {
  return (
    <div className="max-w-[900px] mx-auto px-6 py-16 md:py-24 text-center" data-testid="live-empty">
      <p className="text-dim text-[11px] uppercase tracking-widest mb-3">Live replay</p>
      <h1 className="font-editorial text-4xl sm:text-5xl md:text-6xl leading-[1.05] mb-4">
        Choose a Match
      </h1>
      <p className="text-muted-foreground max-w-xl mx-auto mb-12 leading-relaxed">
        Pick a game and PitchWise will replay every ball with live-evolving
        ratings, momentum, and explainable impact for every player on the field.
      </p>

      <div className={`grid gap-4 mx-auto ${lastMatch ? "grid-cols-1 md:grid-cols-2 max-w-[720px]" : "grid-cols-1 max-w-[420px]"}`}>
        {lastMatch && (
          <Link
            to={`/?match_id=${lastMatch.match_id}`}
            data-testid="continue-last-match"
            className="group rounded-xl border border-amber-soft bg-card p-6 flex flex-col justify-between min-h-[180px] text-left hover:bg-secondary/40 transition-colors"
          >
            <div>
              <div className="flex items-center gap-2 text-[10px] uppercase tracking-widest text-dim">
                <Clock3 className="w-3 h-3" style={{ color: "hsl(var(--primary))" }} aria-hidden="true" />
                <span style={{ color: "hsl(var(--primary))" }}>Continue where you left off</span>
              </div>
              <h2 className="mt-3 font-editorial text-2xl leading-tight">
                {lastMatch.curation_title
                  || (lastMatch.team_short?.length ? lastMatch.team_short.join(" vs ") : "Last match")}
              </h2>
              <p className="mt-1 text-xs text-dim rating-num">
                {[lastMatch.season, lastMatch.date, lastMatch.venue?.split(",")[0]]
                  .filter(Boolean)
                  .join(" · ")}
              </p>
            </div>
            <div className="mt-6 flex items-center justify-between">
              <span className="text-xs text-muted-foreground">
                {lastMatch.result_summary || "Resume replay"}
              </span>
              <ArrowRight className="w-4 h-4 text-muted-foreground group-hover:text-foreground transition-colors" aria-hidden="true" />
            </div>
          </Link>
        )}

        <Link
          to="/time-machine"
          data-testid="browse-time-machine"
          className={`group rounded-xl border ${
            lastMatch ? "border-border/60" : "border-amber-soft"
          } bg-card p-6 flex flex-col justify-between min-h-[180px] text-left hover:bg-secondary/40 transition-colors`}
        >
          <div>
            <div className="flex items-center gap-2 text-[10px] uppercase tracking-widest text-dim">
              <Compass className="w-3 h-3" style={{ color: "hsl(var(--primary))" }} aria-hidden="true" />
              <span style={{ color: "hsl(var(--primary))" }}>Browse Time Machine</span>
            </div>
            <h2 className="mt-3 font-editorial text-2xl leading-tight">
              Every IPL match, replayable.
            </h2>
            <p className="mt-1 text-xs text-dim rating-num">
              Search 19 seasons of ball-by-ball history
            </p>
          </div>
          <div className="mt-6 flex items-center justify-between">
            <span className="text-xs text-muted-foreground">Open the archive</span>
            <ArrowRight className="w-4 h-4 text-muted-foreground group-hover:text-foreground transition-colors" aria-hidden="true" />
          </div>
        </Link>
      </div>

      <p className="mt-14 text-[11px] text-dim">
        Every rating on PitchWise is traceable to a specific ball. Nothing is invented.
      </p>
    </div>
  );
}
