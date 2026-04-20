import { fmt } from "../../lib/fmt";

interface Series {
  color: string;
  data: number[];
  key?: string;
}

interface AreaChartProps {
  series: Series[];
  width?: number;
  height?: number;
  labels?: string[];
}

export function AreaChart({ series, width = 800, height = 220, labels = [] }: AreaChartProps) {
  if (series.length === 0 || series[0]!.data.length === 0) return null;
  const padX = 40;
  const padY = 20;
  const W = width - padX * 2;
  const H = height - padY * 2;
  const N = series[0]!.data.length;

  // Stack values per column.
  const stacked: { base: number; top: number }[][] = [];
  for (let i = 0; i < N; i++) {
    let sum = 0;
    const col: { base: number; top: number }[] = [];
    for (const s of series) {
      const prev = sum;
      sum += s.data[i] ?? 0;
      col.push({ base: prev, top: sum });
    }
    stacked.push(col);
  }

  const maxY = Math.max(1, ...stacked.map((col) => col[col.length - 1]!.top));
  const x = (i: number) => padX + (i / (N - 1)) * W;
  const y = (v: number) => padY + H - (v / maxY) * H;

  const areas = series.map((s, si) => {
    const top = stacked.map((col, i) => `${x(i)},${y(col[si]!.top)}`);
    const bot = stacked
      .map((col, i) => `${x(i)},${y(col[si]!.base)}`)
      .reverse();
    return (
      <path
        key={si}
        d={`M${top.join(" L")} L${bot.join(" L")} Z`}
        fill={s.color}
        opacity={0.75}
        className="chart-fill"
      />
    );
  });

  const yTicks = 4;
  const yLines = Array.from({ length: yTicks + 1 }, (_, i) => {
    const v = (maxY / yTicks) * i;
    return { v, yy: y(v), i };
  });

  return (
    <svg
      width="100%"
      viewBox={`0 0 ${width} ${height}`}
      className="chart-svg"
      role="img"
      aria-label="Token flow area chart"
    >
      {yLines.map((l) => (
        <g key={l.i}>
          <line
            x1={padX}
            x2={width - padX}
            y1={l.yy}
            y2={l.yy}
            stroke="var(--border-subtle)"
            strokeDasharray={l.i === 0 ? undefined : "2 3"}
          />
          <text
            x={padX - 8}
            y={l.yy + 3}
            textAnchor="end"
            fill="var(--fg-3)"
            fontSize={10}
            fontFamily="var(--font-mono)"
          >
            {fmt.k(l.v)}
          </text>
        </g>
      ))}
      {areas}
      {labels.map((lb, i) => (
        <text
          key={i}
          x={x(i)}
          y={height - 4}
          textAnchor="middle"
          fill="var(--fg-3)"
          fontSize={10}
          fontFamily="var(--font-mono)"
        >
          {lb}
        </text>
      ))}
    </svg>
  );
}
