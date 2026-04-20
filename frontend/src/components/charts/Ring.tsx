interface RingProps {
  value: number;
  max?: number;
  size?: number;
  stroke?: number;
  color?: string;
  track?: string;
}

export function Ring({
  value,
  max = 100,
  size = 120,
  stroke = 10,
  color = "var(--amber)",
  track = "var(--bg-3)",
}: RingProps) {
  const r = (size - stroke) / 2;
  const c = 2 * Math.PI * r;
  const pct = Math.min(1, value / max);
  return (
    <svg width={size} height={size} role="img" aria-label={`${Math.round(pct * 100)} percent`}>
      <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke={track} strokeWidth={stroke} />
      <circle
        cx={size / 2}
        cy={size / 2}
        r={r}
        fill="none"
        stroke={color}
        strokeWidth={stroke}
        strokeDasharray={c}
        strokeDashoffset={c * (1 - pct)}
        strokeLinecap="round"
        transform={`rotate(-90 ${size / 2} ${size / 2})`}
      />
    </svg>
  );
}
