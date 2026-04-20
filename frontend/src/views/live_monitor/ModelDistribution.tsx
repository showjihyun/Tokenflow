import { useQuery } from "@tanstack/react-query";
import { Package } from "lucide-react";
import { api } from "../../api/client";
import { Badge } from "../../components/Badge";
import { Card, CardBody, CardHeader } from "../../components/Card";
import { fmt } from "../../lib/fmt";

export function ModelDistribution() {
  const { data } = useQuery({ queryKey: ["kpi-models"], queryFn: () => api.kpiModels() });
  const { data: budget } = useQuery({ queryKey: ["kpi-budget"], queryFn: () => api.kpiBudget() });

  return (
    <Card>
      <CardHeader
        title="Model Distribution"
        icon={<Package size={13} strokeWidth={1.6} />}
        sub="Today"
      />
      <CardBody>
        <div className="lm-model-bar">
          {(data ?? []).map((m) => (
            <div
              key={m.key}
              style={{ width: `${m.share * 100}%`, background: `var(--m-${m.key})` }}
            />
          ))}
        </div>
        <div className="vstack" style={{ gap: 10 }}>
          {(data ?? []).map((m) => (
            <div key={m.key} className="lm-model-row">
              <Badge kind={m.key}>{m.name}</Badge>
              <div className="hstack" style={{ gap: 12 }}>
                <span className="mono dim" style={{ fontSize: 11.5 }}>
                  {fmt.k(m.tokens)}
                </span>
                <span
                  className="mono"
                  style={{ fontSize: 12, color: "var(--fg-0)", minWidth: 56, textAlign: "right" }}
                >
                  {fmt.usd(m.cost)}
                </span>
              </div>
            </div>
          ))}
          <hr className="hr" />
          <div className="lm-model-row">
            <span className="muted" style={{ fontSize: 12 }}>
              Opus 의존도
            </span>
            {budget && (
              <Badge kind={budget.opusShare > 0.15 ? "warn" : "good"}>
                {Math.round(budget.opusShare * 100)}% · 권장 15%↓
              </Badge>
            )}
          </div>
        </div>
      </CardBody>
    </Card>
  );
}
