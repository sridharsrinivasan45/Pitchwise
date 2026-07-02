/**
 * Tiny inline sparkline. No axes, no labels — just the shape of the trend.
 * Amber accent for rising, dim for flat/decline.
 */
export default function Sparkline({ values = [], width = 80, height = 22, testId }) {
  if (!values || values.length < 2) {
    return (
      <svg width={width} height={height} data-testid={testId} aria-hidden>
        <line x1="0" y1={height / 2} x2={width} y2={height / 2}
          stroke="hsla(220,8%,45%,0.4)" strokeWidth="1" strokeDasharray="2 3" />
      </svg>
    );
  }
  const min = Math.min(...values);
  const max = Math.max(...values);
  const range = Math.max(0.001, max - min);
  const step = width / (values.length - 1);
  const pts = values.map((v, i) => {
    const x = i * step;
    const y = height - ((v - min) / range) * (height - 4) - 2;
    return `${x.toFixed(2)},${y.toFixed(2)}`;
  });
  const path = `M ${pts.join(" L ")}`;
  const rising = values[values.length - 1] > values[0];
  const stroke = rising ? "hsl(var(--primary))" : "hsla(220,8%,60%,0.7)";
  const fill = rising ? "hsla(38,92%,55%,0.12)" : "hsla(220,8%,50%,0.06)";
  return (
    <svg width={width} height={height} data-testid={testId} aria-hidden>
      <path d={`${path} L ${width},${height} L 0,${height} Z`} fill={fill} />
      <path d={path} stroke={stroke} strokeWidth="1.5" fill="none" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}
