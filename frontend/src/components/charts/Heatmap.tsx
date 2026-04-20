import { memo, useMemo } from "react";

interface HeatmapProps {
  grid: number[][];
  color?: string;
}

const DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];
const HOURS = Array.from({ length: 24 }, (_, i) => i);

const outerStyle = { fontFamily: "var(--font-mono)" } as const;
const gridStyle = {
  display: "grid",
  gridTemplateColumns: "32px repeat(24, 1fr)",
  gap: 2,
  fontSize: 9,
  color: "var(--fg-3)",
} as const;
const hourLabelStyle = { textAlign: "center" } as const;
const dayLabelStyle = { textAlign: "right", paddingRight: 4, alignSelf: "center" } as const;
const cellBase = {
  aspectRatio: "1",
  borderRadius: 2,
  border: "1px solid var(--border-subtle)",
} as const;

export function Heatmap({ grid, color = "var(--amber)" }: HeatmapProps) {
  return (
    <div style={outerStyle}>
      <div style={gridStyle}>
        <div />
        {HOURS.map((h) => (
          <div key={h} style={hourLabelStyle}>
            {h % 3 === 0 ? h : ""}
          </div>
        ))}
        {DAYS.map((d, di) => (
          <Row key={d} day={d} data={grid[di] ?? []} color={color} />
        ))}
      </div>
    </div>
  );
}

const Row = memo(function Row({ day, data, color }: { day: string; data: number[]; color: string }) {
  // Pre-compute cell styles once per (data, color) tuple so every re-render doesn't
  // allocate 24 new style objects or run the color-mix string interpolation.
  const cells = useMemo(
    () =>
      HOURS.map((h) => {
        const v = data[h] ?? 0;
        const bg =
          v > 0.05
            ? `color-mix(in oklch, ${color} ${Math.round(v * 100)}%, var(--bg-2))`
            : "var(--bg-2)";
        return {
          h,
          title: `${day} ${h}:00 · ${Math.round(v * 100)}%`,
          style: { ...cellBase, background: bg },
        };
      }),
    [data, color, day],
  );

  return (
    <>
      <div style={dayLabelStyle}>{day}</div>
      {cells.map((c) => (
        <div key={c.h} title={c.title} style={c.style as React.CSSProperties} />
      ))}
    </>
  );
});
