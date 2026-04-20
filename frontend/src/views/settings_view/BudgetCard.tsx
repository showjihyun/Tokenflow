import { useEffect, useState } from "react";
import { TrendingUp } from "lucide-react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { api, type SettingsResponse } from "../../api/client";
import { Button } from "../../components/Button";
import { Card, CardBody, CardHeader } from "../../components/Card";
import { Toggle } from "./Toggle";

const THRESHOLDS: [pct: number, color: string][] = [
  [50, "var(--green)"],
  [75, "var(--amber)"],
  [90, "var(--red)"],
];

export function BudgetCard({ settings }: { settings: SettingsResponse }) {
  const qc = useQueryClient();
  const [limit, setLimit] = useState(settings.budget.monthly_budget_usd);
  const [enabled, setEnabled] = useState<Record<number, boolean>>({
    50: settings.budget.alert_thresholds_pct.includes(50),
    75: settings.budget.alert_thresholds_pct.includes(75),
    90: settings.budget.alert_thresholds_pct.includes(90),
  });
  const [hardBlock, setHardBlock] = useState(settings.budget.hard_block);

  useEffect(() => {
    setLimit(settings.budget.monthly_budget_usd);
    setEnabled({
      50: settings.budget.alert_thresholds_pct.includes(50),
      75: settings.budget.alert_thresholds_pct.includes(75),
      90: settings.budget.alert_thresholds_pct.includes(90),
    });
    setHardBlock(settings.budget.hard_block);
  }, [settings]);

  const save = useMutation({
    mutationFn: () =>
      api.putBudget({
        monthly_budget_usd: limit,
        alert_thresholds_pct: Object.entries(enabled).filter(([, v]) => v).map(([k]) => Number(k)),
        hard_block: hardBlock,
      }),
    onSuccess: (data) => qc.setQueryData(["settings"], data),
  });

  return (
    <Card>
      <CardHeader title="Monthly budget" icon={<TrendingUp size={13} strokeWidth={1.6} />} />
      <CardBody>
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 24 }}>
          <div>
            <div className="settings-label">
              Hard limit
              <span className="settings-badge-v2">hard block · v2</span>
            </div>
            <div className="settings-input">
              <span className="settings-input-prefix">$</span>
              <input
                type="number"
                value={limit}
                min={0}
                step={10}
                onChange={(e) => setLimit(Number(e.target.value))}
              />
            </div>
            <div className="settings-help">v1 은 알림만. 하드 차단은 v2 에서 지원.</div>
            <label className="settings-toggle-row" style={{ marginTop: 10 }}>
              <span style={{ fontSize: 13 }}>Enable hard block (stored for v2)</span>
              <Toggle on={hardBlock} onChange={setHardBlock} ariaLabel="Hard block" />
            </label>
          </div>
          <div>
            <div className="settings-label">Alert thresholds</div>
            <div className="vstack" style={{ gap: 6 }}>
              {THRESHOLDS.map(([pct, c]) => (
                <div key={pct} className="settings-toggle-row">
                  <span style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 12 }}>
                    <span style={{ width: 6, height: 6, borderRadius: "50%", background: c }} />
                    {pct}% 도달 시 알림
                  </span>
                  <Toggle
                    on={!!enabled[pct]}
                    onChange={(v) => setEnabled({ ...enabled, [pct]: v })}
                    ariaLabel={`Alert at ${pct}%`}
                  />
                </div>
              ))}
            </div>
          </div>
        </div>
        <div style={{ display: "flex", justifyContent: "flex-end", marginTop: 16 }}>
          <Button variant="primary" size="sm" onClick={() => save.mutate()} disabled={save.isPending}>
            {save.isPending ? "Saving…" : "Save budget"}
          </Button>
        </div>
      </CardBody>
    </Card>
  );
}
