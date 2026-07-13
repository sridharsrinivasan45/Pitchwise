import { useEffect, useMemo, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { fetchMatch, fetchMoments, fetchSkipToDeath } from "@/lib/api";
import MatchHeader from "@/components/live/MatchHeader";
import NarrationLine from "@/components/live/NarrationLine";
import MomentumChart from "@/components/live/MomentumChart";
import ImpactBoard from "@/components/live/ImpactBoard";
import MomentCard from "@/components/live/MomentCard";
import ReplayControls from "@/components/live/ReplayControls";
import LiveEmptyState from "@/components/live/LiveEmptyState";
import WhySheet from "@/components/rating/WhySheet";
import useMatchStream from "@/hooks/useMatchStream";
import { readLastMatch, saveLastMatch } from "@/lib/lastMatch";

/**
 * Live page — cinematic replay of a match, ball-by-ball.
 * SSE-powered: state ticks per delivery, ratings animate, momentum extends.
 *
 * Match resolution:
 *   ?match_id=<id>   → replay that specific match (persisted as "last viewed")
 *   (no param)       → show the empty state (Choose a Match + Continue last)
 *
 * No hardcoded match ids. No featured fallback — every entry point is explicit.
 */
export default function Live() {
  const [params] = useSearchParams();
  const requestedMatchId = params.get("match_id");

  const [match, setMatch] = useState(null);
  const [moments, setMoments] = useState([]); // all-innings moments (for chart dots)
  const [skipTarget, setSkipTarget] = useState(null);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(false);
  const [lastMatch, setLastMatch] = useState(() => readLastMatch());

  useEffect(() => {
    let cancelled = false;

    // No match requested → show empty state, refresh last-viewed snapshot.
    if (!requestedMatchId) {
      setMatch(null);
      setMoments([]);
      setSkipTarget(null);
      setError(null);
      setLoading(false);
      setLastMatch(readLastMatch());
      return () => { cancelled = true; };
    }

    (async () => {
      setLoading(true);
      setError(null);
      setMatch(null);
      setMoments([]);
      setSkipTarget(null);
      try {
        const [m, mm, skip] = await Promise.all([
          fetchMatch(requestedMatchId),
          fetchMoments(requestedMatchId, 12),
          fetchSkipToDeath(requestedMatchId).catch(() => null),
        ]);
        if (cancelled) return;
        setMatch(m);
        setMoments(mm);
        setSkipTarget(skip?.skip_to_ball ?? null);
        saveLastMatch(m);       // persist for "Continue last viewed"
        setLastMatch(m);
      } catch (e) {
        if (cancelled) return;
        setError(
          e?.response?.status === 404
            ? "Match not found in the archive."
            : e.message || "Failed to load match"
        );
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => { cancelled = true; };
  }, [requestedMatchId]);

  const {
    state, currentBall, narration,
    playing, speed, seq, progress, completed, total,
    play, pause, setSpeed, restart, seekToBall,
  } = useMatchStream(match?.match_id, { autoPlay: true, initialSpeed: 1 });

  // Only show a moment dot on the chart if its ball has been reached in the replay.
  const visibleMoments = useMemo(() => {
    const idx = seq;
    if (idx < 0) return [];
    const reachedIds = new Set((state?.momentum || []).map((m) => m.ball_id));
    return moments.filter((m) => reachedIds.has(m.ball_id));
  }, [moments, state, seq]);

  const topMoment = state?.latest_moment || null;
  const otherMoments = visibleMoments
    .filter((m) => !topMoment || m.ball_id !== topMoment.ball_id)
    .slice(0, 3);

  const activePlayerId = currentBall?.batter_id || null;

  // WhySheet state — declared BEFORE early returns so hook order stays stable
  const [whyOpen, setWhyOpen] = useState(false);
  const [whyPlayer, setWhyPlayer] = useState(null);
  const [whyAtBall, setWhyAtBall] = useState(null);

  const openWhyForRow = (row) => {
    setWhyPlayer({
      player_id: row.player_id, player_name: row.player_name, team: row.team, role: row.role,
    });
    setWhyAtBall(state?.latest_ball_id || null);
    setWhyOpen(true);
  };

  const openWhyForMoment = (moment) => {
    if (!moment) return;
    // Prefer the actual attributed player from the moment doc.
    // For a wicket → bowler is the credited player.
    // For a boundary/turning point → batter is the credited player.
    const isWicket = moment.type === "wicket_key";
    const preferredId = isWicket ? moment.bowler_id : moment.batter_id;
    let target = null;
    if (preferredId) {
      target = (state?.top_impact || []).find((r) => r.player_id === preferredId);
      if (!target) {
        // Player is not currently in top 6 — construct a minimal row from the id
        target = { player_id: preferredId, player_name: preferredId, team: "", role: isWicket ? "bowler" : "batter" };
      }
    } else {
      // Legacy fallback: pick from impact board by role
      const impact = state?.top_impact || [];
      target = isWicket
        ? impact.find((r) => r.role === "bowler")
        : impact.find((r) => ["batter", "keeper", "allrounder"].includes(r.role)) || impact[0];
    }
    if (!target) return;
    setWhyPlayer({
      player_id: target.player_id, player_name: target.player_name, team: target.team, role: target.role,
    });
    setWhyAtBall(moment.ball_id);
    setWhyOpen(true);
  };

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
        <div className="p-4 rounded-md border border-destructive/40 bg-negative-soft text-sm mb-6">{error}</div>
        <LiveEmptyState lastMatch={lastMatch && lastMatch.match_id !== requestedMatchId ? lastMatch : null} />
      </div>
    );
  }

  if (!match) {
    return <LiveEmptyState lastMatch={lastMatch} />;
  }

  return (
    <div className="max-w-[1400px] mx-auto px-6 py-8" data-testid="live-page">
      <MatchHeader match={match} currentOver={state?.current_over} currentBall={state?.current_ball} />

      <div className="mt-6">
        <NarrationLine text={narration || "PitchWise is watching. Press play to begin the replay."} />
      </div>

      <div className="mt-2">
        <ReplayControls
          playing={playing}
          completed={completed}
          speed={speed}
          progress={progress}
          seq={seq}
          total={total || match.ball_count}
          currentOver={state?.current_over}
          currentBall={state?.current_ball}
          onPlay={play}
          onPause={pause}
          onSetSpeed={setSpeed}
          onRestart={restart}
          onSkipToDeath={skipTarget != null ? () => seekToBall(skipTarget) : null}
        />
      </div>

      <div className="mt-6">
        <MomentumChart
          momentum={state?.momentum || []}
          moments={visibleMoments}
          teamShort={match.team_short}
          live={playing}
        />
      </div>

      <div className="mt-10">
        <ImpactBoard rows={state?.top_impact || []} activePlayerId={activePlayerId} onExplain={openWhyForRow} />
      </div>

      <div className="mt-10 grid grid-cols-1 md:grid-cols-3 gap-4" data-testid="live-moments-strip">
        <div className="md:col-span-2">
          <div className="mb-3">
            <p className="text-[10px] uppercase tracking-widest text-dim">Moment of the match</p>
            <p className="font-editorial text-lg leading-tight">The ball that changed everything</p>
          </div>
          <MomentCard moment={topMoment} onExplain={openWhyForMoment} />
        </div>

        <div>
          <div className="mb-3">
            <p className="text-[10px] uppercase tracking-widest text-dim">Also decisive</p>
            <p className="font-editorial text-lg leading-tight">Other key moments so far</p>
          </div>
          <div className="flex flex-col gap-3">
            {otherMoments.map((m) => (
              <MomentCard key={m.ball_id} moment={m} onExplain={openWhyForMoment} />
            ))}
            {otherMoments.length === 0 && (
              <div className="rounded-lg border border-border/50 bg-card/40 p-5 text-dim text-sm">
                No other key moments yet.
              </div>
            )}
          </div>
        </div>
      </div>

      <WhySheet
        open={whyOpen}
        onClose={() => setWhyOpen(false)}
        matchId={match.match_id}
        playerId={whyPlayer?.player_id}
        atBallId={whyAtBall}
        seedRow={whyPlayer}
      />

      <footer className="mt-16 pt-6 border-t divider-soft text-xs text-dim flex items-center justify-between">
        <span>Powered by the PitchWise impact engine · adapter v0.1 (placeholder)</span>
        <Link to="/time-machine" className="underline underline-offset-4 hover:text-foreground" data-testid="footer-time-machine-link">
          Browse Time Machine →
        </Link>
      </footer>
    </div>
  );
}
