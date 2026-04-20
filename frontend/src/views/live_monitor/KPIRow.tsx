import { useQuery } from "@tanstack/react-query";
import { api } from "../../api/client";
import { KPI } from "../../components/KPI";
import { fmt } from "../../lib/fmt";

export function KPIRow() {
  const { data } = useQuery({ queryKey: ["kpi-summary", "today"], queryFn: () => api.kpiSummary("today") });

  if (!data) {
    return (
      <div className="kpi-grid">
        {Array.from({ length: 4 }).map((_, i) => (
          <div key={i} className="kpi" style={{ opacity: 0.4 }}>
            <div className="kpi-accent-bar" />
            <div className="kpi-label">Loading</div>
            <div className="kpi-value">—</div>
          </div>
        ))}
      </div>
    );
  }

  return (
    <div className="kpi-grid">
      <KPI
        label="현재 세션 Tokens"
        value={fmt.k(data.currentSession.tokens)}
        delta={data.currentSession.delta}
        deltaDir="up"
        accent="var(--amber)"
      />
      <KPI
        label="Today · Total"
        value={fmt.k(data.today.tokens)}
        delta={fmt.delta(data.today.delta)}
        deltaDir={data.today.delta >= 0 ? "up" : "down"}
        sub={fmt.usd(data.today.cost)}
        accent="var(--blue)"
        spark={data.today.series}
        sparkColor="var(--blue)"
      />
      <KPI
        label="Efficiency Score"
        value={data.efficiency.score}
        unit="/100"
        delta={`+${data.efficiency.delta} pts`}
        deltaDir="down"
        accent="var(--green)"
        spark={data.efficiency.series}
        sparkColor="var(--green)"
      />
      <KPI
        label="Wasted Tokens"
        value={fmt.k(data.waste.tokens)}
        delta={fmt.delta(data.waste.delta)}
        deltaDir={data.waste.delta >= 0 ? "up" : "down"}
        sub={`${data.waste.pct.toFixed(1)}%`}
        accent="var(--red)"
        spark={[0.9, 0.8, 0.7, 0.6, 0.5, 0.4, 0.3]}
        sparkColor="var(--red)"
      />
    </div>
  );
}
