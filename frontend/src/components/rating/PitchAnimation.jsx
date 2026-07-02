import { motion } from "framer-motion";

/**
 * Minimal SVG pitch diagram + ball/shot trajectory.
 * Deterministic geometry from the ball event — no invented data.
 *   - runs 6 → arc to boundary (angle varies by ball number)
 *   - runs 4 → shorter arc to nearer boundary
 *   - runs 1..3 → short arc into infield
 *   - dot → no arc, ball stops at the batter
 *   - wicket → line from bowler to stumps (no shot)
 */
export default function PitchAnimation({ ball, playing = true }) {
  if (!ball) return null;

  // Pitch coordinate system: 100x160 SVG viewBox (aerial view, batter at bottom)
  const cx = 50; // pitch center X
  const bowlerY = 20; // bowler end
  const batterY = 140; // striker end
  const stumpY = 152; // striker stumps (behind batter)

  const runs = ball.runs_batter ?? 0;
  const isWicket = !!ball.is_wicket;
  const ballIdx = ball.ball ?? 1;

  // Deterministic shot angle: alternate across balls so a full over shows variety
  // Angles measured from vertical, positive = toward off-side (right of batter for a right-hander)
  const angleTable = [-55, -30, 15, 45, -20, 30];
  const angle = angleTable[(ballIdx - 1) % angleTable.length];

  // Boundary radius
  const R = 78;
  const angleRad = (angle * Math.PI) / 180;
  const shotEnd = {
    x: cx + Math.sin(angleRad) * R,
    y: batterY - Math.cos(angleRad) * R,
  };
  const shortEnd = {
    x: cx + Math.sin(angleRad) * (R * 0.5),
    y: batterY - Math.cos(angleRad) * (R * 0.5),
  };
  const singleEnd = {
    x: cx + Math.sin(angleRad) * (R * 0.28),
    y: batterY - Math.cos(angleRad) * (R * 0.28),
  };

  const boundaryColor = "hsl(38, 92%, 55%)";
  const infieldColor = "hsla(220, 8%, 70%, 0.85)";

  return (
    <svg
      viewBox="0 0 100 160"
      className="w-full h-full"
      data-testid="pitch-animation"
      aria-hidden
    >
      {/* Field oval */}
      <ellipse cx={cx} cy={80} rx={48} ry={72} fill="hsla(155, 25%, 20%, 0.18)" stroke="hsla(220, 10%, 25%, 0.7)" strokeWidth="0.5" />

      {/* 30-yard circle */}
      <ellipse cx={cx} cy={80} rx={30} ry={48} fill="none" stroke="hsla(220, 10%, 30%, 0.5)" strokeWidth="0.35" strokeDasharray="2 2" />

      {/* Pitch strip */}
      <rect x={44} y={bowlerY} width={12} height={batterY - bowlerY} fill="hsla(40, 25%, 45%, 0.55)" rx={1} />

      {/* Stumps */}
      <line x1={cx - 3} y1={bowlerY - 3} x2={cx + 3} y2={bowlerY - 3} stroke="hsl(40, 30%, 90%)" strokeWidth="1" />
      <line x1={cx - 3} y1={stumpY} x2={cx + 3} y2={stumpY} stroke="hsl(40, 30%, 90%)" strokeWidth="1" />

      {/* Ball delivery trajectory — always shown */}
      <motion.line
        x1={cx} y1={bowlerY} x2={cx} y2={batterY}
        stroke="hsla(0, 0%, 92%, 0.75)"
        strokeWidth="0.7"
        strokeDasharray="2 1.5"
        initial={{ pathLength: 0 }}
        animate={playing ? { pathLength: 1 } : { pathLength: 1 }}
        transition={{ duration: 0.7, ease: "easeOut" }}
      />

      {/* Wicket = stumps hit */}
      {isWicket && (
        <>
          <motion.circle
            cx={cx} cy={stumpY} r={3}
            fill="none"
            stroke="hsl(0, 72%, 60%)"
            strokeWidth="1.2"
            initial={{ scale: 0, opacity: 0 }}
            animate={{ scale: 1, opacity: 1 }}
            transition={{ duration: 0.4, delay: 0.7 }}
          />
          <motion.line
            x1={cx - 4} y1={stumpY - 4} x2={cx + 4} y2={stumpY + 4}
            stroke="hsl(0, 72%, 60%)" strokeWidth="1.2"
            initial={{ pathLength: 0 }}
            animate={{ pathLength: 1 }}
            transition={{ duration: 0.35, delay: 0.8 }}
          />
        </>
      )}

      {/* Shot trajectory (skip if wicket or dot) */}
      {!isWicket && runs > 0 && (() => {
        const endPt = runs === 6 || runs === 4 ? shotEnd : (runs >= 2 ? shortEnd : singleEnd);
        const color = runs === 6 ? boundaryColor : (runs === 4 ? boundaryColor : infieldColor);
        return (
          <>
            <motion.line
              x1={cx} y1={batterY} x2={endPt.x} y2={endPt.y}
              stroke={color}
              strokeWidth={runs === 6 ? "1.4" : "1.0"}
              strokeLinecap="round"
              initial={{ pathLength: 0, opacity: 0 }}
              animate={{ pathLength: 1, opacity: 1 }}
              transition={{ duration: 0.55, delay: 0.65, ease: "easeOut" }}
            />
            <motion.circle
              cx={endPt.x} cy={endPt.y} r={runs === 6 ? 2.3 : 1.6}
              fill={color}
              initial={{ scale: 0, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              transition={{ duration: 0.25, delay: 1.15 }}
            />
            {runs === 6 && (
              <motion.text
                x={endPt.x} y={endPt.y - 3}
                textAnchor="middle"
                fill={color}
                fontSize="4.2"
                fontFamily="JetBrains Mono, monospace"
                fontWeight="600"
                initial={{ opacity: 0, y: -1 }}
                animate={{ opacity: 1, y: -3 }}
                transition={{ delay: 1.2, duration: 0.25 }}
              >6</motion.text>
            )}
          </>
        );
      })()}

      {/* Batter marker */}
      <circle cx={cx} cy={batterY} r={1.6} fill="hsl(40, 30%, 90%)" />
    </svg>
  );
}
