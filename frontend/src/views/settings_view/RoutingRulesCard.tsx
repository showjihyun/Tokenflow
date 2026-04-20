import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Package, Plus, Trash2 } from "lucide-react";
import { api, type RoutingRule } from "../../api/client";
import { Badge } from "../../components/Badge";
import { Button, IconButton } from "../../components/Button";
import { Card, CardBody, CardHeader } from "../../components/Card";
import { Toggle } from "./Toggle";

const MODEL_OPTIONS = [
  { value: "claude-haiku-4-5", badge: "haiku" as const },
  { value: "claude-sonnet-4-6", badge: "sonnet" as const },
  { value: "claude-opus-4-7", badge: "opus" as const },
];

export function RoutingRulesCard() {
  const qc = useQueryClient();
  const [draftCondition, setDraftCondition] = useState("");
  const [draftModel, setDraftModel] = useState("claude-haiku-4-5");
  const { data, isLoading } = useQuery({ queryKey: ["routing-rules"], queryFn: () => api.listRoutingRules() });

  const invalidate = () => qc.invalidateQueries({ queryKey: ["routing-rules"] });

  const create = useMutation({
    mutationFn: () =>
      api.createRoutingRule({ condition_pattern: draftCondition, target_model: draftModel, enabled: true, priority: 100 }),
    onSuccess: () => {
      setDraftCondition("");
      invalidate();
    },
  });
  const del = useMutation({
    mutationFn: (id: string) => api.deleteRoutingRule(id),
    onSuccess: invalidate,
  });
  const toggle = useMutation({
    mutationFn: (rule: RoutingRule) =>
      api.updateRoutingRule(rule.id, {
        condition_pattern: rule.condition_pattern,
        target_model: rule.target_model,
        enabled: !rule.enabled,
        priority: rule.priority,
      }),
    onSuccess: invalidate,
  });

  return (
    <Card>
      <CardHeader title="Model routing rules" icon={<Package size={13} strokeWidth={1.6} />} />
      <CardBody>
        {isLoading && <div className="view-placeholder">Loading…</div>}

        <div className="vstack" style={{ gap: 8 }}>
          {(data ?? []).map((rule) => (
            <div key={rule.id} className="settings-toggle-row">
              <div style={{ display: "flex", alignItems: "center", gap: 10, flex: 1, minWidth: 0 }}>
                <span style={{ fontSize: 13, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                  {rule.condition_pattern}
                </span>
                <Badge kind={MODEL_OPTIONS.find((m) => m.value === rule.target_model)?.badge ?? "neutral"}>
                  {rule.target_model.replace("claude-", "")}
                </Badge>
              </div>
              <div className="hstack" style={{ gap: 8 }}>
                <Toggle on={rule.enabled} onChange={() => toggle.mutate(rule)} />
                <IconButton ariaLabel="Delete rule" onClick={() => del.mutate(rule.id)}>
                  <Trash2 size={12} strokeWidth={1.8} />
                </IconButton>
              </div>
            </div>
          ))}
          {(data ?? []).length === 0 && !isLoading && (
            <div className="view-placeholder">
              No rules yet. Waste Radar's "Apply fix" on wrong-model will create one automatically.
            </div>
          )}
        </div>

        <div style={{ display: "flex", gap: 8, marginTop: 12 }}>
          <div className="settings-input" style={{ flex: 1 }}>
            <input
              type="text"
              placeholder="condition (e.g. simple edits)"
              value={draftCondition}
              onChange={(e) => setDraftCondition(e.target.value)}
            />
          </div>
          <select
            value={draftModel}
            onChange={(e) => setDraftModel(e.target.value)}
            style={{
              background: "var(--bg-2)",
              color: "var(--fg-0)",
              border: "1px solid var(--border-default)",
              borderRadius: "var(--r-sm)",
              padding: "6px 10px",
              fontFamily: "var(--font-mono)",
              fontSize: 12,
            }}
          >
            {MODEL_OPTIONS.map((m) => (
              <option key={m.value} value={m.value}>
                {m.value}
              </option>
            ))}
          </select>
          <Button
            variant="primary"
            size="sm"
            onClick={() => create.mutate()}
            disabled={!draftCondition.trim() || create.isPending}
          >
            <Plus size={12} strokeWidth={1.8} /> Add rule
          </Button>
        </div>
      </CardBody>
    </Card>
  );
}
