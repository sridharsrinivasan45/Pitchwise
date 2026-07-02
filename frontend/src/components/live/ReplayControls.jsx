import { Play, Pause, RotateCcw, FastForward } from "lucide-react";
import { formatOver } from "@/lib/format";

const SPEEDS = [0.5, 1, 2, 4];

/**
 * Cinematic replay controls: play/pause, speed chips, progress ribbon.
 * Sits above the momentum chart so users always know they're in replay mode.
 */
export default function ReplayControls({
  playing, completed, speed, progress, seq, total,
  currentOver, currentBall,
  onPlay, onPause, onSetSpeed, onRestart, onSkipToDeath,
}) {
  return (
    <div className="rounded-lg border border-border/60 bg-card/60 px-4 py-3 flex flex-wrap items-center gap-4" data-testid="replay-controls">
      <button
        type="button"
        onClick={completed ? onRestart : (playing ? onPause : onPlay)}
        data-testid="replay-play-pause"
        className="h-10 w-10 rounded-full flex items-center justify-center transition-transform active:scale-95"
        style={{ background: "hsl(var(--primary))", color: "hsl(var(--primary-foreground))" }}
        aria-label={playing ? "Pause" : (completed ? "Restart" : "Play")}
      >
        {completed ? <RotateCcw className="w-4 h-4" /> : (playing ? <Pause className="w-4 h-4" /> : <Play className="w-4 h-4 ml-0.5" />)}
      </button>

      <div className="flex flex-col min-w-[180px]">
        <div className="flex items-center gap-2">
          <span className="text-[10px] uppercase tracking-widest text-dim">
            {completed ? "Complete" : playing ? "Replaying" : "Paused"}
          </span>
          <span className="rating-num text-xs text-muted-foreground">
            Ball {Math.max(0, seq + 1)} / {total || "—"}
          </span>
        </div>
        <div className="mt-1 h-1.5 rounded-full bg-secondary overflow-hidden">
          <div
            className="h-full transition-all duration-300"
            style={{ width: `${progress * 100}%`, background: "hsl(var(--primary))" }}
            data-testid="replay-progress"
          />
        </div>
        <span className="mt-1 rating-num text-[11px] text-dim">
          Over {formatOver(currentOver, currentBall)}
        </span>
      </div>

      <div className="flex items-center gap-1 ml-auto">
        <span className="text-[10px] uppercase tracking-widest text-dim mr-2">Speed</span>
        {SPEEDS.map((s) => (
          <button
            key={s}
            onClick={() => onSetSpeed(s)}
            data-testid={`replay-speed-${s}x`}
            className={`px-2.5 py-1 rounded-md rating-num text-xs transition-colors ${
              speed === s
                ? "text-foreground bg-secondary border border-amber-soft"
                : "text-dim hover:text-foreground hover:bg-secondary/50"
            }`}
          >
            {s}×
          </button>
        ))}
      </div>

      <button
        type="button"
        onClick={onSkipToDeath}
        data-testid="replay-skip-death"
        className="flex items-center gap-1 px-3 py-1.5 rounded-md border border-border/60 text-xs text-muted-foreground hover:text-foreground hover:border-amber-soft transition-colors"
      >
        <FastForward className="w-3 h-3" />
        Skip to the finish
      </button>
    </div>
  );
}
