interface Point {
  label: string;
  score: number;
}

interface Props {
  points: Point[];
}

export default function ScoreChart({ points }: Props) {
  if (points.length === 0) {
    return <p className="muted">No scored stations yet — your progress will appear here.</p>;
  }

  const w = 560;
  const h = 180;
  const pad = { t: 16, r: 16, b: 36, l: 36 };
  const innerW = w - pad.l - pad.r;
  const innerH = h - pad.t - pad.b;
  const maxY = 100;
  const xs = points.map((_, i) => pad.l + (points.length === 1 ? innerW / 2 : (i / (points.length - 1)) * innerW));
  const ys = points.map((p) => pad.t + innerH - (p.score / maxY) * innerH);
  const line = xs.map((x, i) => `${i === 0 ? "M" : "L"}${x},${ys[i]}`).join(" ");
  const area = `${line} L${xs[xs.length - 1]},${pad.t + innerH} L${xs[0]},${pad.t + innerH} Z`;

  return (
    <svg className="score-chart" viewBox={`0 0 ${w} ${h}`} role="img" aria-label="Score progression">
      {[0, 25, 50, 75, 100].map((tick) => {
        const y = pad.t + innerH - (tick / maxY) * innerH;
        return (
          <g key={tick}>
            <line x1={pad.l} x2={w - pad.r} y1={y} y2={y} className="chart-grid" />
            <text x={pad.l - 8} y={y + 4} className="chart-label" textAnchor="end">
              {tick}
            </text>
          </g>
        );
      })}
      <path d={area} className="chart-area" />
      <path d={line} className="chart-line" fill="none" />
      {xs.map((x, i) => (
        <g key={`${points[i].label}-${i}`}>
          <circle cx={x} cy={ys[i]} r={4.5} className="chart-dot" />
          <text x={x} y={h - 10} className="chart-label" textAnchor="middle">
            {points[i].label}
          </text>
        </g>
      ))}
    </svg>
  );
}
