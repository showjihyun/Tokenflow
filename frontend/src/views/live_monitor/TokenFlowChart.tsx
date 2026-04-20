import { LineChart } from "lucide-react";
import { Card, CardBody, CardHeader } from "../../components/Card";
import { AreaChart } from "../../components/charts/AreaChart";
import { useSSE } from "../../hooks/useSSE";
import type { FlowResponse } from "../../types";

const LEGEND = [
  { label: "Opus", color: "var(--violet)" },
  { label: "Sonnet", color: "var(--amber)" },
  { label: "Haiku", color: "var(--blue)" },
  { label: "Cache hit", color: "var(--green)" },
];

export function TokenFlowChart() {
  const { events, status } = useSSE<FlowResponse>({
    url: "/api/sessions/current/flow/stream?window=60m",
    event: "flow",
    bufferSize: 1,
  });
  const data = events[0];

  return (
    <Card>
      <CardHeader
        title="Token Flow - Last 60 minutes"
        icon={<LineChart size={13} strokeWidth={1.6} />}
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
        {data ? (
          <AreaChart
            width={800}
            height={220}
            labels={data.labels}
            series={data.series.map((s) => ({ color: s.color, data: s.data }))}
          />
        ) : (
          <div style={{ height: 220, color: "var(--fg-3)", textAlign: "center", paddingTop: 90 }}>
            {status === "closed" ? "Flow stream disconnected" : "Loading flow..."}
          </div>
        )}
      </CardBody>
    </Card>
  );
}
