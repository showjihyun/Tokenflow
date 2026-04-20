interface HBarProps {
  value: number;
  max: number;
  color?: string;
  height?: number;
}

export function HBar({ value, max, color = "var(--amber)", height = 6 }: HBarProps) {
  const pct = Math.min(1, Math.max(0, value / max));
  return (
    <div
      style={{
        flex: 1,
        height,
        background: "var(--bg-3)",
        borderRadius: height / 2,
        overflow: "hidden",
      }}
    >
      <div
        style={{
          width: `${pct * 100}%`,
          height: "100%",
          background: color,
          borderRadius: height / 2,
          transition: "width 0.2s",
        }}
      />
    </div>
  );
}
