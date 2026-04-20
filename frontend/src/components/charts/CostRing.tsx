import { Ring } from "./Ring";
import { fmt } from "../../lib/fmt";

interface Part {
  label: string;
  value: number;
  color: string;
}

interface CostRingProps {
  total: number;
  parts: Part[];
}

export function CostRing({ total, parts }: CostRingProps) {
  const max = Math.max(total, 0.0001);
  return (
    <div className="lm-ring-wrap" style={{ marginBottom: 16 }}>
      <div className="lm-ring-center">
        <Ring value={total ? 100 : 0} size={120} stroke={12} color="var(--amber)" />
        <div className="lm-ring-text">
          <div className="lm-ring-pct">{fmt.usd(total)}</div>
          <div className="lm-ring-lbl">spent</div>
        </div>
      </div>
      <div style={{ display: "flex", flexDirection: "column", gap: 8, flex: 1 }}>
        {parts.map((p) => (
          <div key={p.label}>
            <div className="hstack spread" style={{ fontSize: 11.5, marginBottom: 3 }}>
              <span style={{ color: "var(--fg-1)" }}>{p.label}</span>
              <span className="mono tnum" style={{ color: "var(--fg-0)" }}>
                {fmt.usd(p.value)}
              </span>
            </div>
            <div
              style={{
                height: 4,
                background: "var(--bg-3)",
                borderRadius: 2,
                overflow: "hidden",
              }}
            >
              <div
                style={{
                  width: `${(p.value / max) * 100}%`,
                  height: "100%",
                  background: p.color,
                }}
              />
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
