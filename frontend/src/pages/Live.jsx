import { useEffect, useState } from "react";
import { fetchMatches, fetchMatch, fetchMatchState, fetchMoments } from "@/lib/api";
import MatchHeader from "@/components/live/MatchHeader";
import NarrationLine from "@/components/live/NarrationLine";
import MomentumChart from "@/components/live/MomentumChart";
import ImpactBoard from "@/components/live/ImpactBoard";
import MomentCard from "@/components/live/MomentCard";
import { Link } from "react-router-dom";

/**
 * Live page — the hero surface.
 * M2: static, loads full match state at once. Replay ticker (SSE) arrives in M3.
 */
function buildStaticNarration(match, state, moments) {
  if (!match || !state) return "PitchWise is watching.";
  const top = state.top_impact?.[0];
  const turningPoint = moments?.find((m) => m.type === "match_turning_point");
  if (turningPoint && top) {
    return `${top.player_name} tops the impact board at ${top.rating.toFixed(1)}. The 20th over — five sixes in five balls — was the highest-pressure sequence of the innings.`;
  }
  if (top) {
    return `${top.player_name} is leading this innings at ${top.rating.toFixed(1)} impact.`;
  }
  return "PitchWise is watching.";
}

export default function Live() {
  const [match, setMatch] = useState(null);
  const [state, setState] = useState(null);
  const [moments, setMoments] = useState([]);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    (async () => {
      try {
        const featured = await fetchMatches({ featured: true });
        if (!featured.length) { setLoading(false); return; }
        const matchId = featured[0].match_id;
        const [m, s, mm] = await Promise.all([
          fetchMatch(matchId),
          fetchMatchState(matchId),
          fetchMoments(matchId, 6),
        ]);
        setMatch(m);
        setState(s);
        setMoments(mm);
      } catch (e) {
        setError(e.message || "Failed to load match");
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  if (loading) {
    return (
      <div className="max-w-[1400px] mx-auto px-6 py-16 text-dim text-sm" data-testid="live-loading">
        Loading match…
      </div>
    );
  }

  if (error) {
    return (
      <div className="max-w-[1400px] mx-auto px-6 py-10" data-testid="live-error">
        <div className="p-4 rounded-md border border-destructive/40 bg-negative-soft text-sm">{error}</div>
      </div>
    );
  }

  if (!match) {
    return (
      <div className="max-w-[1400px] mx-auto px-6 py-16" data-testid="live-empty">
        <h1 className="font-editorial text-3xl mb-2">No live match right now.</h1>
        <p className="text-muted-foreground">Try the <Link to="/time-machine" className="underline underline-offset-4" style={{ color: "hsl(var(--primary))" }}>Time Machine</Link>.</p>
      </div>
    );
  }

  const topMoment = moments?.[0] ?? state?.latest_moment ?? null;
  const narration = buildStaticNarration(match, state, moments);

  return (
    <div className="max-w-[1400px] mx-auto px-6 py-8" data-testid="live-page">
      <MatchHeader match={match} currentOver={state?.current_over} currentBall={state?.current_ball} />

      <div className="mt-6">
        <NarrationLine text={narration} />
      </div>

      <div className="mt-4">
        <MomentumChart
          momentum={state?.momentum || []}
          moments={moments}
          teamShort={match.team_short}
        />
      </div>

      <div className="mt-10">
        <ImpactBoard rows={state?.top_impact || []} />
      </div>

      <div className="mt-10 grid grid-cols-1 md:grid-cols-3 gap-4" data-testid="live-moments-strip">
        <div className="md:col-span-2">
          <div className="mb-3">
            <p className="text-[10px] uppercase tracking-widest text-dim">Moment of the match</p>
            <p className="font-editorial text-lg leading-tight">The ball that changed everything</p>
          </div>
          <MomentCard moment={topMoment} />
        </div>

        <div>
          <div className="mb-3">
            <p className="text-[10px] uppercase tracking-widest text-dim">Also decisive</p>
            <p className="font-editorial text-lg leading-tight">Other key moments</p>
          </div>
          <div className="flex flex-col gap-3">
            {(moments || []).slice(1, 4).map((m) => (
              <MomentCard key={m.ball_id} moment={m} />
            ))}
            {(!moments || moments.length <= 1) && (
              <div className="rounded-lg border border-border/50 bg-card/40 p-5 text-dim text-sm">
                No other key moments yet.
              </div>
            )}
          </div>
        </div>
      </div>

      <footer className="mt-16 pt-6 border-t divider-soft text-xs text-dim flex items-center justify-between">
        <span>Powered by the PitchWise impact engine · adapter v0.1 (placeholder)</span>
        <Link to="/time-machine" className="underline underline-offset-4 hover:text-foreground" data-testid="footer-time-machine-link">
          Browse Time Machine →
        </Link>
      </footer>
    </div>
  );
}
