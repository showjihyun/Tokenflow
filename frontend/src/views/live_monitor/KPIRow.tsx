import { useQuery } from "@tanstack/react-query";
import { api } from "../../api/client";
import { KPI } from "../../components/KPI";
import { fmt } from "../../lib/fmt";
import { queryKeys } from "../../lib/queryKeys";

export function KPIRow() {
  const { data } = useQuery({
    queryKey: queryKeys.kpiSummary("today"),
    queryFn: () => api.kpiSummary("today"),
    refetchInterval: 15_000,
  });

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

  const efficiencyAttr = data.efficiency.attribution;
  const efficiencySub = efficiencyAttr
    ? `penalty ${efficiencyAttr.penalty.total.toFixed(1)} · waste ${efficiencyAttr.penalty.waste.toFixed(1)} / model ${efficiencyAttr.penalty.opusMisuse.toFixed(1)} / ctx ${efficiencyAttr.penalty.contextBloat.toFixed(1)}`
    : undefined;
  const topWaste = data.waste.byKind?.[0];
  const wasteSub = topWaste
    ? `${data.waste.pct.toFixed(1)}% · top ${topWaste.kind} ${fmt.k(topWaste.tokens)}`
    : `${data.waste.pct.toFixed(1)}%`;
  const efficiencyDelta = data.efficiency.delta;
  const efficiencyDetail = efficiencyAttr ? (
    <div className="kpi-detail-grid">
      <div className="kpi-detail-cell">
        <div className="kpi-detail-label">Waste penalty</div>
        <div className="kpi-detail-value">{efficiencyAttr.penalty.waste.toFixed(1)}</div>
      </div>
      <div className="kpi-detail-cell">
        <div className="kpi-detail-label">Model penalty</div>
        <div className="kpi-detail-value">{efficiencyAttr.penalty.opusMisuse.toFixed(1)}</div>
      </div>
      <div className="kpi-detail-cell">
        <div className="kpi-detail-label">Context penalty</div>
        <div className="kpi-detail-value">{efficiencyAttr.penalty.contextBloat.toFixed(1)}</div>
      </div>
    </div>
  ) : undefined;

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
        delta={`${efficiencyDelta >= 0 ? "+" : ""}${efficiencyDelta} pts`}
        deltaDir={efficiencyDelta >= 0 ? "down" : "up"}
        sub={efficiencySub}
        accent="var(--green)"
        spark={data.efficiency.series}
        sparkColor="var(--green)"
        detail={efficiencyDetail}
      />
      <KPI
        label="Wasted Tokens"
        value={fmt.k(data.waste.tokens)}
        delta={fmt.delta(data.waste.delta)}
        deltaDir={data.waste.delta >= 0 ? "up" : "down"}
        sub={wasteSub}
        accent="var(--red)"
        spark={[0.9, 0.8, 0.7, 0.6, 0.5, 0.4, 0.3]}
        sparkColor="var(--red)"
      />
    </div>
  );
}
