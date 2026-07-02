import { useEffect, useState } from "react";
import { fetchMatches } from "@/lib/api";

export default function TimeMachine() {
  const [matches, setMatches] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    (async () => {
      try {
        const m = await fetchMatches({ featured: true });
        setMatches(m);
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  return (
    <div className="max-w-[1400px] mx-auto px-6 py-10" data-testid="time-machine-page">
      <p className="text-dim text-[11px] uppercase tracking-widest mb-3">Time Machine</p>
      <h1 className="font-editorial text-4xl md:text-5xl leading-tight mb-3">
        Relive IPL classics with live-evolving ratings.
      </h1>
      <p className="text-muted-foreground max-w-2xl mb-10">
        Every match plays back ball by ball. Watch impact ratings tick, momentum shift,
        and the moments that quietly decided the outcome.
      </p>

      {loading && <div className="text-dim text-sm">Loading matches…</div>}

      <div className="grid grid-cols-1 md:grid-cols-2 gap-5" data-testid="time-machine-grid">
        {matches.map((m) => (
          <article key={m.match_id} data-testid={`match-card-${m.curation_slug}`}
            className="rounded-xl border border-border/60 bg-card p-6 hover:border-amber-soft transition-colors">
            <div className="flex items-center gap-2 mb-3">
              <span className="rating-num text-xs text-dim">{m.season}</span>
              <span className="text-dim">·</span>
              <span className="rating-num text-xs text-dim">{m.date}</span>
            </div>
            <h3 className="font-editorial text-2xl mb-2">{m.curation_title}</h3>
            <p className="text-muted-foreground text-sm mb-4">{m.curation_hook}</p>
            <div className="flex items-center justify-between">
              <span className="rating-num text-sm">{m.team_short?.join(" vs ")}</span>
              <span className="text-positive text-xs">{m.result_summary}</span>
            </div>
          </article>
        ))}
        {!loading && matches.length === 0 && (
          <div className="text-dim text-sm">More matches will appear here soon.</div>
        )}
      </div>
    </div>
  );
}
