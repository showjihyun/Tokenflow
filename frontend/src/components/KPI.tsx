import type { ReactNode } from "react";
import { ArrowDown, ArrowUp } from "lucide-react";
import { Sparkline } from "./charts/Sparkline";
import "./KPI.css";

interface KPIProps {
  label: ReactNode;
  value: ReactNode;
  unit?: string;
  delta?: string;
  deltaDir?: "up" | "down" | "flat";
  sub?: string;
  accent: string;
  spark?: number[];
  sparkColor?: string;
}

export function KPI({
  label,
  value,
  unit,
  delta,
  deltaDir = "flat",
  sub,
  accent,
  spark,
  sparkColor,
}: KPIProps) {
  return (
    <div className="kpi" style={{ "--kpi-accent": accent } as React.CSSProperties}>
      <div className="kpi-accent-bar" />
      <div className="kpi-label">{label}</div>
      <div className="kpi-value tnum mono">
        {value}
        {unit && <span className="unit">{unit}</span>}
      </div>
      {delta && (
        <div className={`kpi-delta ${deltaDir}`}>
          {deltaDir === "up" && <ArrowUp size={11} strokeWidth={1.8} />}
          {deltaDir === "down" && <ArrowDown size={11} strokeWidth={1.8} />}
          <span>{delta}</span>
          {sub && <span className="dim" style={{ marginLeft: 6 }}>· {sub}</span>}
        </div>
      )}
      {spark && (
        <div className="kpi-spark">
          <Sparkline data={spark} color={sparkColor ?? accent} width={80} height={28} />
        </div>
      )}
    </div>
  );
}
