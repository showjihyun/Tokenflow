import { useQuery } from "@tanstack/react-query";
import { ArrowRight, Package } from "lucide-react";
import { api } from "../../api/client";
import { Button, IconButton } from "../../components/Button";
import { Card, CardBody, CardHeader } from "../../components/Card";
import { HBar } from "../../components/charts/HBar";
import { Sparkline } from "../../components/charts/Sparkline";
import { fmt } from "../../lib/fmt";
import { queryKeys, queryStaleTime } from "../../lib/queryKeys";

const TREND_COLOR: Record<string, string> = {
  up: "var(--red)",
  down: "var(--green)",
  flat: "var(--blue)",
};
const EMPTY_TREND = [0, 0, 0, 0, 0, 0, 0];

export function ProjectsTable() {
  const { data } = useQuery({
    queryKey: queryKeys.projects("7d"),
    queryFn: () => api.projects("7d"),
    staleTime: queryStaleTime.analytics,
  });

  return (
    <Card>
      <CardHeader
        title="By Project · This week"
        icon={<Package size={13} strokeWidth={1.6} />}
        action={
          <Button variant="ghost" size="sm">
            All projects <ArrowRight size={12} strokeWidth={1.8} />
          </Button>
        }
      />
      <CardBody flush>
        <table className="lm-tbl">
          <thead>
            <tr>
              <th>Project</th>
              <th style={{ textAlign: "right" }}>Tokens</th>
              <th style={{ textAlign: "right" }}>Cost</th>
              <th style={{ textAlign: "right" }}>Sessions</th>
              <th>Waste</th>
              <th>Trend (7d)</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {(data ?? []).map((p) => {
              const wasteColor =
                p.waste > 0.2 ? "var(--red)" : p.waste > 0.1 ? "var(--amber)" : "var(--green)";
              return (
                <tr key={p.name}>
                  <td>
                    <div className="project-cell">
                      <div
                        className="project-dot"
                        style={{ background: TREND_COLOR[p.trend] ?? "var(--fg-3)" }}
                      />
                      <span className="mono" style={{ color: "var(--fg-0)" }}>
                        {p.name}
                      </span>
                    </div>
                  </td>
                  <td className="num">{fmt.k(p.tokens)}</td>
                  <td className="num">{fmt.usd(p.cost)}</td>
                  <td className="num">
                    <span className="muted">{p.sessions}</span>
                  </td>
                  <td>
                    <div className="waste-cell">
                      <HBar value={p.waste} max={0.35} color={wasteColor} />
                      <span
                        className="mono tnum"
                        style={{
                          fontSize: 11,
                          minWidth: 36,
                          textAlign: "right",
                          color: "var(--fg-2)",
                        }}
                      >
                        {(p.waste * 100).toFixed(0)}%
                      </span>
                    </div>
                  </td>
                  <td>
                    <Sparkline
                      data={p.trendData ?? EMPTY_TREND}
                      color={p.trend === "up" ? "var(--red)" : p.trend === "down" ? "var(--green)" : "var(--blue)"}
                      width={80}
                      height={24}
                    />
                  </td>
                  <td style={{ textAlign: "right" }}>
                    <IconButton ariaLabel={`Open ${p.name}`}>
                      <ArrowRight size={13} strokeWidth={1.8} />
                    </IconButton>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </CardBody>
    </Card>
  );
}
