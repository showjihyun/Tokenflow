interface HeatmapProps {
  grid: number[][];
  color?: string;
}

const DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];

export function Heatmap({ grid, color = "var(--amber)" }: HeatmapProps) {
  const hours = Array.from({ length: 24 }, (_, i) => i);

  return (
    <div style={{ fontFamily: "var(--font-mono)" }}>
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "32px repeat(24, 1fr)",
          gap: 2,
          fontSize: 9,
          color: "var(--fg-3)",
        }}
      >
        <div />
        {hours.map((h) => (
          <div key={h} style={{ textAlign: "center" }}>
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

function Row({ day, data, color }: { day: string; data: number[]; color: string }) {
  return (
    <>
      <div style={{ textAlign: "right", paddingRight: 4, alignSelf: "center" }}>{day}</div>
      {Array.from({ length: 24 }, (_, h) => {
        const v = data[h] ?? 0;
        return (
          <div
            key={h}
            title={`${day} ${h}:00 · ${Math.round(v * 100)}%`}
            style={{
              aspectRatio: "1",
              borderRadius: 2,
              background:
                v > 0.05
                  ? `color-mix(in oklch, ${color} ${Math.round(v * 100)}%, var(--bg-2))`
                  : "var(--bg-2)",
              border: "1px solid var(--border-subtle)",
            }}
          />
        );
      })}
    </>
  );
}
