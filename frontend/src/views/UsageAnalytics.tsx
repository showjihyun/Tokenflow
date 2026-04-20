import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Cpu, LineChart, TrendingUp } from "lucide-react";
import { api, type Range } from "../api/client";
import { Card, CardBody, CardHeader } from "../components/Card";
import { KPI } from "../components/KPI";
import { AreaChart } from "../components/charts/AreaChart";
import { CostRing } from "../components/charts/CostRing";
import { Heatmap } from "../components/charts/Heatmap";
import "../components/charts/chart.css";
import "../views/live_monitor/LiveMonitor.css";
import { fmt } from "../lib/fmt";

const RANGES: { key: Range; label: string }[] = [
  { key: "24h", label: "24H" },
  { key: "7d", label: "7D" },
  { key: "30d", label: "30D" },
  { key: "90d", label: "90D" },
  { key: "all", label: "All" },
];

const LEGEND = [
  { label: "Opus", color: "var(--violet)" },
  { label: "Sonnet", color: "var(--amber)" },
  { label: "Haiku", color: "var(--blue)" },
];

export function UsageAnalytics() {
  const [range, setRange] = useState<Range>("7d");

  const kpi = useQuery({ queryKey: ["analytics-kpi", range], queryFn: () => api.analyticsKpi(range) });
  const daily = useQuery({ queryKey: ["analytics-daily", range], queryFn: () => api.analyticsDaily(range) });
  const heat = useQuery({ queryKey: ["analytics-heatmap", range], queryFn: () => api.analyticsHeatmap(range) });
  const cost = useQuery({ queryKey: ["analytics-cost", range], queryFn: () => api.analyticsCostBreakdown(range) });

  const totalTokens = kpi.data?.totalTokens ?? 0;
  const totalCost = kpi.data?.totalCost ?? 0;
  const avgMin = kpi.data?.avgSessionMinutes ?? 0;
  const perSession = kpi.data?.costPerSession ?? 0;

  const everythingEmpty = useMemo(
    () => totalTokens === 0 && (daily.data?.series ?? []).every((s) => s.data.every((d) => d === 0)),
    [totalTokens, daily.data],
  );

  return (
    <div className="page">
      <div className="page-header">
        <div>
          <h1 className="page-title">Usage Analytics</h1>
          <p className="page-sub">일/주/월별 토큰 사용 패턴 분석</p>
        </div>
        <div className="range-picker">
          {RANGES.map((r) => (
            <button
              key={r.key}
              className={range === r.key ? "active" : ""}
              onClick={() => setRange(r.key)}
            >
              {r.label}
            </button>
          ))}
        </div>
      </div>

      {everythingEmpty && (
        <div className="view-placeholder" style={{ marginBottom: 16 }}>
          No usage data in this range. Start Claude Code or <code>tokenflow import --from-ccprophet &lt;db&gt;</code> to populate.
        </div>
      )}

      <div className="kpi-grid">
        <KPI label="Total tokens" value={fmt.k(totalTokens)} delta="" accent="var(--blue)" />
        <KPI label="Total cost" value={fmt.usd(totalCost)} delta="" accent="var(--green)" />
        <KPI label="Avg session length" value={avgMin.toFixed(1)} unit=" min" delta="" accent="var(--amber)" />
        <KPI label="Cost per session" value={fmt.usd(perSession)} delta="" accent="var(--violet)" />
      </div>

      <div className="row row-21">
        <Card>
          <CardHeader
            title="Daily Usage"
            icon={<LineChart size={13} strokeWidth={1.6} />}
            sub={range.toUpperCase()}
            action={
              <div className="chart-legend">
                {LEGEND.map((l) => (
                  <span key={l.label}>
                    <span className="sw" style={{ background: l.color }} />
                    {l.label}
                  </span>
                ))}
              </div>
            }
          />
          <CardBody>
            {daily.data ? (
              <AreaChart
                width={820}
                height={260}
                labels={daily.data.labels}
                series={daily.data.series.map((s) => ({ color: s.color, data: s.data }))}
              />
            ) : (
              <div style={{ height: 260, color: "var(--fg-3)", textAlign: "center", paddingTop: 110 }}>
                Loading…
              </div>
            )}
          </CardBody>
        </Card>

        <Card>
          <CardHeader
            title="Cost Breakdown"
            icon={<Cpu size={13} strokeWidth={1.6} />}
            sub={range.toUpperCase()}
          />
          <CardBody>
            {cost.data ? (
              <CostRing total={cost.data.total} parts={cost.data.parts} />
            ) : (
              <div style={{ color: "var(--fg-3)" }}>Loading…</div>
            )}
          </CardBody>
        </Card>
      </div>

      <div className="row row-12">
        <Card>
          <CardHeader
            title="Top Waste Patterns"
            icon={<TrendingUp size={13} strokeWidth={1.6} />}
            sub="Phase E"
          />
          <CardBody>
            <div className="view-placeholder">
              Waste pattern detection ships in Phase E.
            </div>
          </CardBody>
        </Card>

        <Card>
          <CardHeader
            title="Activity Heatmap"
            icon={<LineChart size={13} strokeWidth={1.6} />}
            sub={`${range.toUpperCase()} × 24h`}
          />
          <CardBody>
            {heat.data ? (
              <Heatmap grid={heat.data.grid} color="var(--amber)" />
            ) : (
              <div style={{ color: "var(--fg-3)" }}>Loading…</div>
            )}
          </CardBody>
        </Card>
      </div>
    </div>
  );
}
