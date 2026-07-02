import { useCallback, useEffect, useRef, useState } from "react";
import { API_BASE } from "@/lib/api";

/**
 * useMatchStream — consumes the SSE replay of a match ball-by-ball.
 *
 * Behavior:
 *  - Auto-connects on mount and streams from `from_ball`.
 *  - Updates state per tick; keeps last state on pause; resumes seamlessly.
 *  - Speed change closes/reopens the stream from the current cursor.
 *
 * Returned API:
 *  { meta, state, currentBall, narration, playing, speed, seq, progress,
 *    completed, play, pause, setSpeed, restart, seekToBall }
 */
export default function useMatchStream(matchId, { autoPlay = true, initialSpeed = 1 } = {}) {
  const [meta, setMeta] = useState(null);
  const [seq, setSeq] = useState(-1);
  const [state, setState] = useState(null);
  const [currentBall, setCurrentBall] = useState(null);
  const [narration, setNarration] = useState(null);
  const [playing, setPlaying] = useState(false);
  const [speed, setSpeedInner] = useState(initialSpeed);
  const [completed, setCompleted] = useState(false);

  const esRef = useRef(null);
  const seqRef = useRef(-1);

  const closeStream = useCallback(() => {
    if (esRef.current) {
      esRef.current.close();
      esRef.current = null;
    }
  }, []);

  const openStream = useCallback((fromBall, useSpeed) => {
    if (!matchId) return;
    closeStream();
    const url = `${API_BASE}/matches/${matchId}/stream?from_ball=${fromBall}&speed=${useSpeed}`;
    const es = new EventSource(url);
    esRef.current = es;
    setPlaying(true);
    setCompleted(false);

    es.addEventListener("meta", (e) => {
      try { setMeta(JSON.parse(e.data)); } catch { /* ignore */ }
    });

    es.addEventListener("tick", (e) => {
      try {
        const payload = JSON.parse(e.data);
        seqRef.current = payload.seq;
        setSeq(payload.seq);
        setCurrentBall(payload.ball);
        setState(payload.state);
        setNarration(payload.narration);
      } catch { /* ignore malformed */ }
    });

    es.addEventListener("end", () => {
      setPlaying(false);
      setCompleted(true);
      closeStream();
    });

    es.onerror = () => {
      // Browser closes ES on error; treat as pause. Consumer can resume.
      setPlaying(false);
      closeStream();
    };
  }, [matchId, closeStream]);

  // Autoplay on mount / matchId change
  useEffect(() => {
    if (!matchId) return;
    seqRef.current = -1;
    setSeq(-1);
    setState(null);
    setCurrentBall(null);
    setNarration(null);
    setCompleted(false);
    if (autoPlay) openStream(0, initialSpeed);
    return () => closeStream();
  }, [matchId]);

  const play = useCallback(() => {
    if (playing || completed) return;
    const from = Math.max(0, seqRef.current + 1);
    openStream(from, speed);
  }, [playing, completed, openStream, speed]);

  const pause = useCallback(() => {
    closeStream();
    setPlaying(false);
  }, [closeStream]);

  const setSpeed = useCallback((newSpeed) => {
    setSpeedInner(newSpeed);
    if (playing) {
      const from = Math.max(0, seqRef.current + 1);
      openStream(from, newSpeed);
    }
  }, [playing, openStream]);

  const restart = useCallback(() => {
    seqRef.current = -1;
    setSeq(-1);
    setState(null);
    setCurrentBall(null);
    setNarration(null);
    setCompleted(false);
    openStream(0, speed);
  }, [openStream, speed]);

  const seekToBall = useCallback((targetBall) => {
    // targetBall is the seq index (0-based).
    seqRef.current = Math.max(-1, targetBall - 1);
    setSeq(seqRef.current);
    openStream(targetBall, speed);
  }, [openStream, speed]);

  const total = meta?.total_balls || 0;
  const progress = total > 0 ? Math.min(1, Math.max(0, (seq + 1) / total)) : 0;

  return {
    meta, state, currentBall, narration,
    playing, speed, seq, progress, completed,
    total,
    play, pause, setSpeed, restart, seekToBall,
  };
}
