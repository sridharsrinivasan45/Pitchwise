import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { LineChart, Line, ResponsiveContainer, Tooltip, YAxis, XAxis } from "recharts";
import { fetchPlayerProfile } from "@/lib/api";
import RatingBadge from "@/components/rating/RatingBadge";

export default function PlayerProfile() {
  const { id } = useParams();
  const nav = useNavigate();
  const [profile, setProfile] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    setLoading(true);
    fetchPlayerProfile(id)
      .then(setProfile)
      .catch((e) => setError(e.response?.status === 404 ? "Player not found" : e.message))
      .finally(() => setLoading(false));
  }, [id]);

  if (loading) return <div className="max-w-[1400px] mx-auto px-6 py-16 text-dim text-sm" data-testid="player-loading">Loading profile…</div>;
  if (error) return <div className="max-w-[1400px] mx-auto px-6 py-10" data-testid="player-error"><div className="p-4 rounded-md border border-destructive/40 bg-negative-soft text-sm">{error}</div></div>;
  if (!profile) return null;

  const tl = (profile.timeline || []).map((t, i) => ({ i, rating: t.overall_rating, date: t.date, match_id: t.match_id }));

  return (
    <div className="max-w-[1400px] mx-auto px-6 py-10" data-testid="player-profile-page">
      <div className="mb-8 flex items-start gap-6 flex-wrap">
        <div className="flex-1 min-w-[280px]">
          <p className="text-dim text-[11px] uppercase tracking-widest mb-2">Player</p>
          <h1 className="font-editorial text-4xl md:text-5xl leading-tight mb-2">{profile.display_name}</h1>
          <p className="text-sm text-muted-foreground">
            <span className="rating-num">{profile.teams.join(" · ")}</span>
            <span className="text-dim"> · </span>
            <span className="rating-num">{profile.first_seen} → {profile.last_seen}</span>
          </p>
        </div>
        <div className="flex flex-col items-end gap-1">
          <p className="text-[10px] uppercase tracking-widest text-dim">Career rating (avg)</p>
          <RatingBadge rating={profile.career.avg_rating} delta={0} size="lg" showDelta={false} testId="player-career-rating" />
          <p className="text-xs text-dim rating-num">peak {profile.career.best_rating.toFixed(1)} · {profile.career.matches} matches</p>
        </div>
      </div>

      {/* Career stats */}
      <section className="grid grid-cols-2 md:grid-cols-5 gap-3 mb-10" data-testid="career-stats">
        {[
          ["Matches", profile.career.matches],
          ["Runs", profile.career.total_runs],
          ["Wickets", profile.career.total_wickets],
          ["Balls faced", profile.career.total_balls_faced],
          ["Balls bowled", profile.career.total_balls_bowled],
        ].map(([label, val]) => (
          <div key={label} className="rounded-lg border border-border/50 bg-card/60 p-4">
            <div className="text-[10px] uppercase tracking-widest text-dim mb-1">{label}</div>
            <div className="rating-num text-2xl font-medium">{val.toLocaleString()}</div>
          </div>
        ))}
      </section>

      {/* Rating timeline */}
      {tl.length > 1 && (
        <section className="mb-10" data-testid="rating-timeline">
          <div className="mb-3">
            <p className="text-[10px] uppercase tracking-widest text-dim">Rating timeline</p>
            <p className="font-editorial text-xl leading-tight">Every match, plotted</p>
          </div>
          <div className="rounded-lg border border-border/60 bg-card/60 p-4 h-[240px]">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={tl} margin={{ top: 10, right: 10, bottom: 0, left: -20 }}>
                <XAxis dataKey="i" hide />
                <YAxis domain={[0, 10]} tick={{ fill: "hsla(220,8%,55%,1)", fontSize: 10, fontFamily: "JetBrains Mono" }} axisLine={false} tickLine={false} tickCount={5} />
                <Tooltip content={({ active, payload }) => {
                  if (!active || !payload || !payload.length) return null;
                  const p = payload[0].payload;
                  return (
                    <div className="glass rounded-md px-3 py-2 border border-border/60 text-xs">
                      <div className="rating-num text-foreground">{p.date}</div>
                      <div className="text-dim">rating <span className="rating-num" style={{ color: "hsl(var(--primary))" }}>{p.rating}</span></div>
                    </div>
                  );
                }} />
                <Line type="monotone" dataKey="rating" stroke="hsl(38, 92%, 55%)" strokeWidth={1.5} dot={false} isAnimationActive={false} />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </section>
      )}

      {/* Best performances */}
      {profile.best_performances?.length > 0 && (
        <section className="mb-10" data-testid="best-performances">
          <div className="mb-3">
            <p className="text-[10px] uppercase tracking-widest text-dim">Best performances</p>
            <p className="font-editorial text-xl leading-tight">The innings that defined this career</p>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            {profile.best_performances.map((b) => (
              <button key={b.match_id} onClick={() => nav(`/?match_id=${b.match_id}`)}
                data-testid={`best-${b.match_id}`}
                className="text-left rounded-lg border border-border/60 bg-card p-4 flex items-center justify-between gap-4 hover:border-amber-soft transition-colors">
                <div className="min-w-0">
                  <div className="flex items-center gap-2 mb-1 text-[10px] uppercase tracking-widest text-dim rating-num">
                    <span>{b.season}</span><span>·</span><span>{b.date}</span><span>·</span><span>{b.teams}</span>
                  </div>
                  <p className="font-editorial text-base leading-tight">{b.curation_title || b.result_summary || "Match"}</p>
                  <p className="mt-1 text-xs text-dim rating-num">
                    {b.runs > 0 && `${b.runs}(${b.balls_faced})`}
                    {b.wickets > 0 && ` · ${b.wickets} wkts`}
                  </p>
                </div>
                <RatingBadge rating={b.overall_rating} delta={0} size="md" showDelta={false} />
              </button>
            ))}
          </div>
        </section>
      )}

      {/* Recent matches */}
      {profile.recent_matches?.length > 0 && (
        <section data-testid="recent-matches">
          <div className="mb-3">
            <p className="text-[10px] uppercase tracking-widest text-dim">Recent matches</p>
            <p className="font-editorial text-xl leading-tight">Last {profile.recent_matches.length}</p>
          </div>
          <ul className="rounded-lg border border-border/50 bg-card/60 divide-y divider-soft">
            {profile.recent_matches.map((r) => (
              <li key={r.match_id}
                onClick={() => nav(`/?match_id=${r.match_id}`)}
                data-testid={`recent-${r.match_id}`}
                className="p-4 flex items-center justify-between gap-4 hover:bg-secondary/30 cursor-pointer">
                <div>
                  <div className="text-xs text-dim rating-num">{r.date} · {r.teams}</div>
                  <div className="text-sm text-muted-foreground">{r.result_summary}</div>
                </div>
                <RatingBadge rating={r.overall_rating} delta={0} size="sm" showDelta={false} />
              </li>
            ))}
          </ul>
        </section>
      )}
    </div>
  );
}
