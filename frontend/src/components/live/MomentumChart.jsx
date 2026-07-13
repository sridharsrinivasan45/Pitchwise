import {
  Area, AreaChart, ResponsiveContainer, XAxis, YAxis,
  ReferenceDot, ReferenceLine, Tooltip, Label,
} from "recharts";

function ChartTooltip({ teamShort }) {
  return ({ active, payload }) => {
    if (!active || !payload || !payload.length) return null;
    const p = payload[0].payload;
    return (
      <div className="glass rounded-md px-3 py-2 border border-border/60 text-xs">
        <div className="rating-num text-foreground">Over {p.label}</div>
        <div className="text-dim">
          {teamShort[0]} WP{" "}
          <span className="rating-num" style={{ color: "hsl(var(--primary))" }}>
            {p.wp}%
          </span>
        </div>
      </div>
    );
  };
}

function LiveHeadShape(props) {
  return (
    <g>
      <circle cx={props.cx} cy={props.cy} r={11} fill="hsla(38, 92%, 55%, 0.25)">
        <animate attributeName="r" values="7;14;7" dur="1.4s" repeatCount="indefinite" />
        <animate attributeName="opacity" values="0.6;0;0.6" dur="1.4s" repeatCount="indefinite" />
      </circle>
      <circle cx={props.cx} cy={props.cy} r={5} fill="hsl(38, 92%, 55%)" stroke="hsl(220, 15%, 6%)" strokeWidth={2} />
    </g>
  );
}

/**
 * Momentum chart — win probability for team1 across the innings.
 * Full width, ~280px tall. Dots on flagged moments.
 * Non-interactive in M2 (no on-click); tap-jump wires in M3+.
 */
export default function MomentumChart({ momentum = [], moments = [], teamShort = [], live = false }) {
  if (!momentum.length) {
    return (
      <div className="h-[280px] w-full rounded-lg border border-border/50 bg-card/40 flex items-center justify-center text-dim text-sm">
        Momentum will appear once the match starts.
      </div>
    );
  }

  const data = momentum.map((m, i) => {
    // Innings from canonical ball_id `<match>-i<inn>-o<over>.<ball>`
    const idMatch = /-i(\d+)-/.exec(m.ball_id || "");
    const innings = idMatch ? parseInt(idMatch[1], 10) : 1;
    return {
      idx: i,
      wp: Math.round(m.wp * 100),
      label: `${(m.over ?? 0) + 1}.${m.ball}`,
      innings,
    };
  });

  // Find every innings boundary index (first ball of innings 2, and 3 if super over)
  const inningsBreaks = [];
  for (let i = 1; i < data.length; i++) {
    if (data[i].innings !== data[i - 1].innings) inningsBreaks.push(i);
  }

  const momentByBallId = new Map(moments.map((m) => [m.ball_id, m]));
  const dotPoints = momentum
    .map((m, i) => {
      const mm = momentByBallId.get(m.ball_id);
      if (!mm) return null;
      return { idx: i, wp: Math.round(m.wp * 100), type: mm.type };
    })
    .filter(Boolean);

  const lastIdx = data.length - 1;
  const lastWp = data[lastIdx]?.wp;

  return (
    <div className="w-full" data-testid="momentum-chart">
      <div className="flex items-center justify-between mb-3">
        <div>
          <p className="text-[10px] uppercase tracking-widest text-dim">Momentum</p>
          <p className="font-editorial text-lg leading-tight">Win probability, ball by ball</p>
        </div>
        <p className="text-xs text-dim rating-num">
          {teamShort[0]} chase · {momentum.length} balls
        </p>
      </div>

      <div className="h-[260px] w-full">
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart data={data} margin={{ top: 10, right: 10, bottom: 0, left: -20 }}>
            <defs>
              <linearGradient id="wpFill" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="hsl(38, 92%, 55%)" stopOpacity={0.35} />
                <stop offset="100%" stopColor="hsl(38, 92%, 55%)" stopOpacity={0.02} />
              </linearGradient>
            </defs>
            <XAxis dataKey="idx" hide />
            <YAxis
              domain={[0, 100]}
              tick={{ fill: "hsla(220,8%,55%,1)", fontSize: 10, fontFamily: "JetBrains Mono" }}
              axisLine={false}
              tickLine={false}
              tickCount={5}
            />
            <Tooltip
              cursor={{ stroke: "hsla(38,92%,55%,0.4)", strokeWidth: 1 }}
              content={ChartTooltip({ teamShort })}
            />
            {inningsBreaks.map((idx, n) => (
              <ReferenceLine
                key={`inn-brk-${idx}`}
                x={idx}
                stroke="hsla(220, 8%, 60%, 0.55)"
                strokeDasharray="4 4"
                strokeWidth={1}
                ifOverflow="visible"
              >
                <Label
                  value={n === 0 ? "Innings break" : "Super over"}
                  position="top"
                  fill="hsla(220, 8%, 65%, 0.9)"
                  fontSize={10}
                  fontFamily="JetBrains Mono"
                  offset={6}
                />
              </ReferenceLine>
            ))}
            <Area
              type="monotone"
              dataKey="wp"
              stroke="hsl(38, 92%, 55%)"
              strokeWidth={1.75}
              fill="url(#wpFill)"
              isAnimationActive={!live}
              animationDuration={live ? 200 : 800}
              activeDot={{ r: 4, fill: "hsl(38, 92%, 55%)", stroke: "hsl(220, 15%, 6%)", strokeWidth: 2 }}
            />
            {dotPoints.map((d) => (
              <ReferenceDot
                key={d.idx}
                x={d.idx}
                y={d.wp}
                r={4}
                fill={d.type === "match_turning_point" ? "hsl(38, 92%, 55%)" : "hsla(340, 65%, 60%, 0.9)"}
                stroke="hsl(220, 15%, 6%)"
                strokeWidth={2}
              />
            ))}
            {live && lastWp != null && (
              <ReferenceDot
                x={lastIdx}
                y={lastWp}
                r={6}
                fill="hsl(38, 92%, 55%)"
                stroke="hsl(220, 15%, 6%)"
                strokeWidth={2}
                isFront
                shape={LiveHeadShape}
              />
            )}
          </AreaChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
