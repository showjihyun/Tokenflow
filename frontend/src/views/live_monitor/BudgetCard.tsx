import { useQuery } from "@tanstack/react-query";
import { TrendingUp, AlertTriangle } from "lucide-react";
import { api } from "../../api/client";
import { Card, CardBody, CardHeader } from "../../components/Card";
import { fmt } from "../../lib/fmt";

export function BudgetCard() {
  const { data } = useQuery({ queryKey: ["kpi-budget"], queryFn: () => api.kpiBudget() });

  if (!data) {
    return (
      <Card>
        <CardHeader title="Monthly Budget" icon={<TrendingUp size={13} strokeWidth={1.6} />} sub="—" />
        <CardBody>Loading…</CardBody>
      </Card>
    );
  }

  const spentPct = Math.min(1, data.spent / data.month);
  const forecastPct = Math.min(1, data.forecast / data.month);
  const forecastOver = data.forecast > data.month;

  return (
    <Card>
      <CardHeader
        title="Monthly Budget"
        icon={<TrendingUp size={13} strokeWidth={1.6} />}
        sub={new Date().toLocaleString("en-US", { month: "short", year: "numeric" })}
      />
      <CardBody>
        <div style={{ display: "flex", alignItems: "baseline", gap: 8, marginBottom: 4 }}>
          <span className="mono" style={{ fontSize: 26, fontWeight: 600 }}>
            {fmt.usd(data.spent)}
          </span>
          <span className="dim" style={{ fontSize: 13 }}>
            / {fmt.usd(data.month)}
          </span>
        </div>
        <div className="dim" style={{ fontSize: 11.5, marginBottom: 14 }}>
          {data.daysLeft}일 남음 · 일평균 {fmt.usd(data.dailyAvg)}
        </div>

        <div className="lm-budget-track">
          <div className="lm-budget-fill" style={{ width: `${spentPct * 100}%` }} />
          <div
            className="lm-budget-forecast"
            style={{
              left: `${spentPct * 100}%`,
              width: `${Math.max(0, (forecastPct - spentPct) * 100)}%`,
            }}
          />
          <div className="lm-budget-limit" />
        </div>
        <div className="lm-budget-marks">
          <span>Spent {Math.round(spentPct * 100)}%</span>
          <span>Forecast {Math.round(forecastPct * 100)}%</span>
          <span>Limit {fmt.usd(data.month)}</span>
        </div>

        {forecastOver && (
          <div className="lm-budget-alert">
            <AlertTriangle size={14} strokeWidth={1.8} />
            <div className="body">
              이 속도면 월말 <b style={{ color: "var(--amber)" }}>{fmt.usd(data.forecast)}</b> 도달 예상.
              <br />
              <span className="dim" style={{ fontSize: 11 }}>
                Opus → Sonnet 전환 시 절감 가능.
              </span>
            </div>
          </div>
        )}
      </CardBody>
    </Card>
  );
}
