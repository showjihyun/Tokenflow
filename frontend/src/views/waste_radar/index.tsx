import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import {
  AlertTriangle,
  Check,
  Cpu,
  FileText,
  Package,
  Radar,
  Repeat,
  Sparkles,
  X,
} from "lucide-react";
import { api, type WasteKind, type WastePattern, type WasteSeverity } from "../../api/client";
import { Badge } from "../../components/Badge";
import { Button } from "../../components/Button";
import { Card, CardBody, CardHeader } from "../../components/Card";
import { EmptyState } from "../../components/EmptyState";
import { ErrorState } from "../../components/ErrorState";
import { fmt } from "../../lib/fmt";
import "./WasteRadar.css";

const SEVERITY: Record<WasteSeverity, { fg: string; bg: string; label: string; badge: "danger" | "warn" | "haiku" }> = {
  high: { fg: "var(--red)", bg: "var(--red-w)", label: "High", badge: "danger" },
  med: { fg: "var(--amber)", bg: "var(--amber-w)", label: "Medium", badge: "warn" },
  low: { fg: "var(--blue)", bg: "var(--blue-w)", label: "Low", badge: "haiku" },
};

function iconFor(kind: WasteKind) {
  switch (kind) {
    case "big-file-load":
      return FileText;
    case "repeat-question":
      return Repeat;
    case "wrong-model":
      return Package;
    case "context-bloat":
      return Cpu;
    case "tool-loop":
    default:
      return AlertTriangle;
  }
}

export function WasteRadar() {
  const qc = useQueryClient();
  const [appliedPreview, setAppliedPreview] = useState<{
    wasteId: string;
    outcome: string;
    preview: { path: string; title: string; diff: string } | null;
  } | null>(null);
  const { data: wastes, isLoading, isError, refetch } = useQuery({
    queryKey: ["wastes", "active"],
    queryFn: () => api.listWastes("active"),
    refetchInterval: 15_000,
  });
  const session = useQuery({
    queryKey: ["session-current"],
    queryFn: () => api.currentSession(),
  });
  const scan = useMutation({
    // Prefer session-scoped scan when we have an active session; only fall back to
    // the 24h cross-session sweep when there's nothing to scan.
    mutationFn: () =>
      session.data?.active && session.data.id
        ? api.scanWastes(session.data.id)
        : api.sweepWastes(),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["wastes"] }),
  });
  const dismiss = useMutation({
    mutationFn: (id: string) => api.dismissWaste(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["wastes"] }),
  });
  const apply = useMutation({
    mutationFn: (id: string) => api.applyWaste(id),
    onSuccess: (result, wasteId) => {
      setAppliedPreview({ wasteId, outcome: result.outcome, preview: result.preview });
      qc.invalidateQueries({ queryKey: ["wastes"] });
      qc.invalidateQueries({ queryKey: ["routing-rules"] });
    },
  });
  const confirmApply = useMutation({
    mutationFn: (id: string) => api.confirmWasteFix(id),
  });

  const active = wastes ?? [];
  const totalTokens = active.reduce((s, w) => s + w.save_tokens, 0);
  const totalUSD = active.reduce((s, w) => s + w.save_usd, 0);
  const bySev = {
    high: active.filter((w) => w.severity === "high").length,
    med: active.filter((w) => w.severity === "med").length,
    low: active.filter((w) => w.severity === "low").length,
  };

  return (
    <div className="page">
      <div className="page-header">
        <div>
          <h1 className="page-title">Waste Radar</h1>
          <p className="page-sub">불필요한 토큰 소비 패턴과 최적화 제안</p>
        </div>
        <div className="hstack">
          <Button variant="ghost" size="sm" onClick={() => scan.mutate()} disabled={scan.isPending}>
            <Sparkles size={13} strokeWidth={1.8} /> {scan.isPending ? "Scanning…" : "Scan now"}
          </Button>
        </div>
      </div>

      <div className="waste-summary">
        <div className="waste-summary-main">
          <div className="waste-summary-label">Potential savings</div>
          <div className="waste-summary-value">{fmt.usd(totalUSD)}</div>
          <div style={{ fontSize: 12, color: "var(--fg-2)", marginTop: 4 }}>
            · {fmt.k(totalTokens)} tokens · {active.length}건 활성
          </div>
        </div>
        <SummaryCounter label="High severity" value={bySev.high} color="var(--red)" />
        <SummaryCounter label="Medium" value={bySev.med} color="var(--amber)" />
        <SummaryCounter label="Low" value={bySev.low} color="var(--blue)" />
      </div>

      {isLoading && <div className="view-placeholder">Loading waste patterns…</div>}

      {isError && <ErrorState variant="generic" onRetry={() => refetch()} />}

      {appliedPreview && (
        <Card>
          <CardHeader
            title={appliedPreview.preview?.title ?? "Fix applied"}
            icon={<Check size={13} strokeWidth={1.6} />}
            sub={appliedPreview.outcome}
            action={
              <div className="hstack">
                {appliedPreview.preview?.path === "CLAUDE.md" && (
                  <Button
                    variant="primary"
                    size="sm"
                    onClick={() => confirmApply.mutate(appliedPreview.wasteId)}
                    disabled={confirmApply.isPending}
                  >
                    <Check size={12} strokeWidth={1.8} />{" "}
                    {confirmApply.isPending ? "Applying" : "Apply to CLAUDE.md"}
                  </Button>
                )}
                <Button variant="ghost" size="sm" onClick={() => setAppliedPreview(null)}>
                  <X size={12} strokeWidth={1.8} /> Close
                </Button>
              </div>
            }
          />
          <CardBody>
            {confirmApply.data && (
              <div className="waste-preview-result">
                {confirmApply.data.applied
                  ? `Applied to ${confirmApply.data.path}`
                  : `No file change: ${confirmApply.data.reason ?? "not applicable"}`}
              </div>
            )}
            {confirmApply.isError && (
              <div className="waste-preview-error">{(confirmApply.error as Error).message}</div>
            )}
            {appliedPreview.preview ? (
              <>
                <div className="waste-preview-path">{appliedPreview.preview.path}</div>
                <pre className="waste-preview-diff">{appliedPreview.preview.diff}</pre>
              </>
            ) : (
              <div className="view-placeholder">No preview was generated for this fix.</div>
            )}
          </CardBody>
        </Card>
      )}

      {!isLoading && !isError && active.length === 0 && (
        <EmptyState
          icon={<Radar size={20} strokeWidth={1.6} />}
          title="All clean"
          description='No active waste patterns. Start Claude Code or run "Scan now" to re-check.'
        />
      )}

      <div className="vstack" style={{ gap: 12 }}>
        {active.map((w) => (
          <WasteCardRow
            key={w.id}
            waste={w}
            onDismiss={() => dismiss.mutate(w.id)}
            onApply={() => apply.mutate(w.id)}
            busy={dismiss.isPending || apply.isPending}
          />
        ))}
      </div>
    </div>
  );
}

function SummaryCounter({ label, value, color }: { label: string; value: number; color: string }) {
  return (
    <div>
      <div className="waste-summary-label">{label}</div>
      <div className="waste-summary-value" style={{ color }}>
        {value}
      </div>
    </div>
  );
}

function WasteCardRow({
  waste,
  onDismiss,
  onApply,
  busy,
}: {
  waste: WastePattern;
  onDismiss: () => void;
  onApply: () => void;
  busy: boolean;
}) {
  const sev = SEVERITY[waste.severity];
  const Icon = iconFor(waste.kind);
  return (
    <div
      className="waste-card"
      style={{
        ["--severity-fg" as string]: sev.fg,
        ["--severity-bg" as string]: sev.bg,
      }}
    >
      <div className="waste-head">
        <div className="waste-icon">
          <Icon size={16} strokeWidth={1.8} />
        </div>
        <div style={{ flex: 1 }}>
          <h3 className="waste-title">{waste.title}</h3>
          <div className="waste-meta">{waste.meta}</div>
        </div>
        <Badge kind={sev.badge}>{sev.label}</Badge>
      </div>
      <div className="waste-body" dangerouslySetInnerHTML={{ __html: waste.body_html }} />
      <div className="waste-impact">
        <span>
          Est. savings: <b>{fmt.k(waste.save_tokens)} tokens</b>
        </span>
        <span className="sep">·</span>
        <span>
          <b>{fmt.usd(waste.save_usd)}</b>
        </span>
        <span className="sep">·</span>
        <span>
          Sessions: <span style={{ color: "var(--fg-0)" }}>{waste.sessions}</span>
        </span>
      </div>
      <div className="waste-actions">
        <Button variant="primary" size="sm" onClick={onApply} disabled={busy}>
          <Check size={12} strokeWidth={1.8} /> Apply fix
        </Button>
        <Button variant="ghost" size="sm" onClick={onDismiss} disabled={busy} style={{ marginLeft: "auto" }}>
          <X size={12} strokeWidth={1.8} /> Dismiss
        </Button>
      </div>
    </div>
  );
}
