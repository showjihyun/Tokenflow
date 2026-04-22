import { useQuery } from "@tanstack/react-query";
import { api } from "../../api/client";
import { KPI } from "../../components/KPI";
import { fmt } from "../../lib/fmt";
import { queryKeys, queryStaleTime } from "../../lib/queryKeys";

export function KPIRow() {
  const { data } = useQuery({
    queryKey: queryKeys.kpiSummary("today"),
    queryFn: () => api.kpiSummary("today"),
    staleTime: queryStaleTime.short,
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
  // FINDING-002: the old 4-in-1 ``penalty X · waste X / model X / ctx X``
  // crowd-string wrapped awkwardly in the KPI card. Keep one single-line
  // summary; the detailed breakdown lives in the existing kpi-detail-grid
  // (shown on hover/focus via the KPI component's detail slot).
  const efficiencySub = efficiencyAttr
    ? `−${efficiencyAttr.penalty.total.toFixed(1)} pts total penalty`
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
        // Real trailing-7-day series from /kpi/summary. Empty or all-zero
        // arrays are treated as "no data" — spark stays hidden rather than
        // render a flat baseline that reads like a trend.
        spark={data.waste.series && data.waste.series.some((v) => v > 0) ? data.waste.series : undefined}
        sparkColor="var(--red)"
      />
    </div>
  );
}
