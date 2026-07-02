import { useEffect, useState } from "react";
import { fetchMatches, fetchMatch } from "@/lib/api";
import { Link } from "react-router-dom";

export default function Live() {
  const [featured, setFeatured] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    (async () => {
      try {
        const matches = await fetchMatches({ featured: true });
        if (matches.length > 0) {
          const full = await fetchMatch(matches[0].match_id);
          setFeatured(full);
        }
      } catch (e) {
        setError(e.message || "Failed to load match");
      }
    })();
  }, []);

  return (
    <div className="max-w-[1400px] mx-auto px-6 py-10" data-testid="live-page">
      <div className="mb-10">
        <p className="text-dim text-[11px] uppercase tracking-widest mb-3">Featured</p>
        <h1 className="font-editorial text-5xl md:text-6xl leading-none mb-4">
          Cricket, explained.
        </h1>
        <p className="text-muted-foreground max-w-xl">
          Every rating on PitchWise is traceable to the ball that earned it. Live impact ratings,
          historical parallels, and an AI analyst that speaks cricket.
        </p>
      </div>

      {error && (
        <div className="p-4 rounded-md border border-destructive/40 bg-negative-soft text-sm" data-testid="live-error">
          {error}
        </div>
      )}

      {featured && (
        <section data-testid="featured-match-card"
          className="rounded-xl border border-border/60 bg-card p-6 md:p-8 flex flex-col md:flex-row md:items-end md:justify-between gap-6">
          <div>
            <div className="flex items-center gap-2 mb-3">
              <span className="text-[10px] uppercase tracking-widest px-2 py-0.5 rounded-sm bg-amber-soft border border-amber-soft" style={{ color: 'hsl(var(--primary))' }}>
                Time Machine
              </span>
              <span className="text-dim rating-num text-xs">{featured.season} · {featured.date}</span>
            </div>
            <h2 className="font-editorial text-3xl md:text-4xl leading-tight mb-2" data-testid="featured-title">
              {featured.curation_title}
            </h2>
            <p className="text-muted-foreground max-w-lg">{featured.curation_hook}</p>
            <div className="mt-4 flex items-center gap-4 text-sm">
              <span className="rating-num">{featured.team_short?.join("  vs  ")}</span>
              <span className="text-dim">·</span>
              <span className="text-dim">{featured.venue}</span>
            </div>
          </div>
          <div className="flex flex-col items-start md:items-end gap-3">
            <span className="rating-num text-xs text-dim">{featured.ball_count} balls indexed</span>
            <span className="rating-num text-sm">{featured.final_score}</span>
            <span className="text-positive text-sm">{featured.result_summary}</span>
            <Link to="/time-machine" data-testid="open-time-machine-link"
              className="mt-2 inline-flex items-center gap-2 px-4 py-2 rounded-md bg-primary text-primary-foreground text-sm font-medium hover:opacity-90 transition-opacity">
              Open Time Machine →
            </Link>
          </div>
        </section>
      )}

      <section className="mt-16 grid grid-cols-1 md:grid-cols-3 gap-6" data-testid="live-teasers">
        {[
          ["Live Pulse", "Momentum, ratings, moments — updating ball by ball."],
          ["Explainable Ratings", "Tap any number. See the balls that earned it."],
          ["Innings DNA", "Shareable fingerprint of every innings."],
        ].map(([title, body]) => (
          <div key={title} className="rounded-lg border border-border/50 bg-card/60 p-5">
            <div className="text-[10px] uppercase tracking-widest text-dim mb-3">Coming online</div>
            <h3 className="font-editorial text-xl mb-2">{title}</h3>
            <p className="text-muted-foreground text-sm">{body}</p>
          </div>
        ))}
      </section>
    </div>
  );
}
