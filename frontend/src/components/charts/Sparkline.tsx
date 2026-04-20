interface SparklineProps {
  data: number[];
  color?: string;
  width?: number;
  height?: number;
  fill?: boolean;
}

export function Sparkline({
  data,
  color = "var(--amber)",
  width = 80,
  height = 28,
  fill = true,
}: SparklineProps) {
  if (data.length < 2) return null;
  const max = Math.max(...data);
  const min = Math.min(...data);
  const r = max - min || 1;
  const pts = data.map((v, i) => {
    const x = (i / (data.length - 1)) * width;
    const y = height - ((v - min) / r) * (height - 4) - 2;
    return [x, y] as const;
  });
  const path = pts.map(([x, y], i) => `${i === 0 ? "M" : "L"}${x},${y}`).join(" ");
  const fillPath = `${path} L${width},${height} L0,${height} Z`;
  return (
    <svg
      width={width}
      height={height}
      className="chart-svg"
      role="img"
      aria-label="Sparkline trend"
    >
      {fill && <path d={fillPath} className="chart-fill" fill={color} opacity={0.15} />}
      <path
        d={path}
        className="chart-line"
        fill="none"
        stroke={color}
        strokeWidth={1.5}
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}
