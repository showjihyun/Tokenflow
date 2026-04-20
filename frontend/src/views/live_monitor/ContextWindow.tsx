import { useQuery } from "@tanstack/react-query";
import { Cpu } from "lucide-react";
import { api } from "../../api/client";
import { Card, CardBody, CardHeader } from "../../components/Card";
import { Ring } from "../../components/charts/Ring";
import { fmt } from "../../lib/fmt";

export function ContextWindow() {
  const { data } = useQuery({
    queryKey: ["session-current"],
    queryFn: () => api.currentSession(),
    refetchInterval: 5_000,
  });

  if (!data) {
    return (
      <Card>
        <CardHeader
          title="Context Window"
          icon={<Cpu size={13} strokeWidth={1.6} />}
          sub="— / —"
        />
        <CardBody>Loading…</CardBody>
      </Card>
    );
  }

  const pct = data.contextWindow > 0 ? data.contextUsed / data.contextWindow : 0;
  const color = pct > 0.85 ? "var(--red)" : pct > 0.65 ? "var(--amber)" : "var(--green)";

  return (
    <Card>
      <CardHeader
        title="Context Window"
        icon={<Cpu size={13} strokeWidth={1.6} />}
        sub={`${fmt.k(data.contextUsed)} / ${fmt.k(data.contextWindow)}`}
      />
      <CardBody className="vstack" >
        <div className="lm-ring-wrap">
          <div className="lm-ring-center">
            <Ring value={pct * 100} size={118} stroke={10} color={color} />
            <div className="lm-ring-text">
              <div className="lm-ring-pct">{(pct * 100).toFixed(1)}%</div>
              <div className="lm-ring-lbl">saturation</div>
            </div>
          </div>
          <div className="lm-ring-info">
            <div className="lbl">Recommended</div>
            <div
              style={{
                color: pct > 0.7 ? "var(--amber)" : "var(--green)",
                fontSize: 13,
                fontWeight: 500,
                marginTop: 2,
              }}
            >
              {pct > 0.7 ? "⚡ /compact 권장" : "✓ Healthy"}
            </div>
            <div className="sub" style={{ marginTop: 6 }}>
              Input: {fmt.k(data.tokens.input)}
            </div>
            <div className="sub">Output: {fmt.k(data.tokens.output)}</div>
            <div className="sub">Cache: {fmt.k(data.tokens.cacheRead)}</div>
          </div>
        </div>
        <div className="lm-tip">
          💡 <span style={{ color: "var(--fg-0)" }}>Pro tip:</span> 컨텍스트가 70% 를 넘으면 응답 품질이 평균 18% 떨어져요. <code>/compact</code> 로 정리하세요.
        </div>
      </CardBody>
    </Card>
  );
}
