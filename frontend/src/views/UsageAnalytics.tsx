import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Cpu, LineChart, TrendingUp } from "lucide-react";
import { api, type Range } from "../api/client";
import { Card, CardBody, CardHeader } from "../components/Card";
import { EmptyState } from "../components/EmptyState";
import { KPI } from "../components/KPI";
import { AreaChart } from "../components/charts/AreaChart";
import { CostRing } from "../components/charts/CostRing";
import { Heatmap } from "../components/charts/Heatmap";
import "../components/charts/chart.css";
import "../views/live_monitor/LiveMonitor.css";
import { fmt } from "../lib/fmt";
import { queryKeys, queryStaleTime } from "../lib/queryKeys";

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
  const [project, setProject] = useState<string>("");
  const projectRange = range === "30d" || range === "90d" || range === "all" ? "30d" : "7d";

  const projects = useQuery({
    queryKey: queryKeys.projects(projectRange),
    queryFn: () => api.projects(projectRange),
    staleTime: queryStaleTime.analytics,
  });
  const projectParam = project || undefined;
  const overview = useQuery({
    queryKey: queryKeys.analyticsOverview(range, project),
    queryFn: () => api.analyticsOverview(range, 4, projectParam),
    staleTime: queryStaleTime.analytics,
  });
  const kpi = overview.data?.kpi;
  const daily = overview.data?.daily;
  const heat = overview.data?.heatmap;
  const cost = overview.data?.cost;
  const topWastes = overview.data?.topWastes ?? [];

  const totalTokens = kpi?.totalTokens ?? 0;
  const totalCost = kpi?.totalCost ?? 0;
  const avgMin = kpi?.avgSessionMinutes ?? 0;
  const perSession = kpi?.costPerSession ?? 0;

  const everythingEmpty = useMemo(
    () => totalTokens === 0 && (daily?.series ?? []).every((s) => s.data.every((d) => d === 0)),
    [totalTokens, daily],
  );

  return (
    <div className="page">
      <div className="page-header">
        <div>
          <h1 className="page-title">Usage Analytics</h1>
          <p className="page-sub">일/주/월별 토큰 사용 패턴 분석</p>
        </div>
        <div className="hstack">
          <select
            className="analytics-project-select"
            value={project}
            onChange={(e) => setProject(e.target.value)}
            aria-label="Project filter"
          >
            <option value="">All projects</option>
            {(projects.data ?? []).map((p) => (
              <option key={p.name} value={p.name}>
                {p.name}
              </option>
            ))}
          </select>
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
      </div>

      {everythingEmpty && (
        <div style={{ marginBottom: 16 }}>
          <EmptyState
            icon={<LineChart size={20} strokeWidth={1.6} />}
            title="No usage data in this range"
            description={<>Start Claude Code or run <code>tokenflow import --from-ccprophet &lt;db&gt;</code> to populate.</>}
          />
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
            {daily ? (
              <AreaChart
                width={820}
                height={260}
                labels={daily.labels}
                series={daily.series.map((s) => ({ color: s.color, data: s.data }))}
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
            {cost ? (
              <CostRing total={cost.total} parts={cost.parts} />
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
            sub={range.toUpperCase()}
          />
          <CardBody>
            {topWastes.length === 0 ? (
              <EmptyState compact title="No waste patterns in this range" />
            ) : (
              <div className="vstack" style={{ gap: 10 }}>
                {topWastes.map((waste) => (
                  <div key={waste.id} className="settings-toggle-row">
                    <div>
                      <div style={{ fontSize: 13, fontWeight: 600 }}>{waste.title}</div>
                      <div className="sub">
                        {waste.kind} · {waste.severity} · {waste.meta}
                      </div>
                    </div>
                    <div style={{ textAlign: "right", fontSize: 12 }}>
                      <div>{fmt.k(waste.save_tokens)} tk</div>
                      <div className="sub">{fmt.usd(waste.save_usd)}</div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </CardBody>
        </Card>

        <Card>
          <CardHeader
            title="Activity Heatmap"
            icon={<LineChart size={13} strokeWidth={1.6} />}
            sub={`${range.toUpperCase()} × 24h`}
          />
          <CardBody>
            {heat ? (
              <Heatmap grid={heat.grid} color="var(--amber)" />
            ) : (
              <div style={{ color: "var(--fg-3)" }}>Loading…</div>
            )}
          </CardBody>
        </Card>
      </div>
    </div>
  );
}
