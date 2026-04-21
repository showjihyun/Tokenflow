import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { FileText, Play, Search, Sparkles } from "lucide-react";
import { api, type ReplayEvent, type SessionSummary } from "../../api/client";
import { Badge } from "../../components/Badge";
import { Button } from "../../components/Button";
import { EmptyState } from "../../components/EmptyState";
import { useTweaks } from "../../lib/tweaksStore";
import { fmt } from "../../lib/fmt";
import { Toggle } from "../settings_view/Toggle";
import "./Replay.css";

function modelBadgeKind(model: string | null): "opus" | "sonnet" | "haiku" | "neutral" {
  if (!model) return "neutral";
  const m = model.toLowerCase();
  if (m.includes("opus")) return "opus";
  if (m.includes("haiku")) return "haiku";
  if (m.includes("sonnet")) return "sonnet";
  return "neutral";
}

export function SessionReplay() {
  const qc = useQueryClient();
  const betterMode = useTweaks((s) => s.tweaks.better_prompt_mode);
  const [query, setQuery] = useState("");
  const [onlyWaste, setOnlyWaste] = useState(false);
  const [includePaused, setIncludePaused] = useState(false);
  const [activeSession, setActiveSession] = useState<string | null>(null);
  const [activeIdx, setActiveIdx] = useState<number>(0);

  const sessionsQuery = useQuery({
    queryKey: ["sessions", "list", query, onlyWaste],
    queryFn: () => api.listSessions({ q: query || undefined, has_waste: onlyWaste, limit: 50 }),
  });
  const replayQuery = useQuery({
    queryKey: ["sessions", activeSession, "replay", includePaused],
    queryFn: () => (activeSession ? api.sessionReplay(activeSession, includePaused) : Promise.resolve(null)),
    enabled: !!activeSession,
  });

  const betterPrompt = useMutation({
    mutationFn: ({ idx, mode, wasteReason }: { idx: number; mode: "static" | "llm"; wasteReason?: string }) =>
      api.betterPrompt(activeSession!, idx, mode, wasteReason),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["better-prompt", activeSession, activeIdx] }),
  });

  useEffect(() => {
    if (!activeSession && sessionsQuery.data && sessionsQuery.data.length > 0) {
      setActiveSession(sessionsQuery.data[0]!.id);
    }
  }, [activeSession, sessionsQuery.data]);

  const sessions = sessionsQuery.data ?? [];
  const replay = replayQuery.data;
  const activeEvent: ReplayEvent | null =
    replay && replay.events[activeIdx] ? replay.events[activeIdx] : null;

  return (
    <div className="page">
      <div className="page-header">
        <div>
          <h1 className="page-title">Session Replay</h1>
          <p className="page-sub">
            {replay
              ? `${replay.summary.messages} messages · ${fmt.k(replay.summary.tokens)} tokens · ${fmt.usd(replay.summary.cost)}`
              : "세션을 선택하세요"}
          </p>
        </div>
        <div className="hstack" style={{ gap: 12 }}>
          <label style={{ fontSize: 12, color: "var(--fg-2)", display: "flex", alignItems: "center", gap: 8 }}>
            Include paused
            <Toggle
              on={includePaused}
              onChange={(next) => {
                setIncludePaused(next);
                setActiveIdx(0);
              }}
              ariaLabel="Include paused transcript messages"
            />
          </label>
          <Button variant="ghost" size="sm" disabled title="Playback · v1.1">
            <Play size={12} strokeWidth={1.8} /> Playback
          </Button>
        </div>
      </div>

      <div className="replay-wrap">
        <div className="replay-col">
          <div className="replay-col-head">
            <div className="replay-search">
              <Search size={13} strokeWidth={1.6} />
              <input
                placeholder="search query…"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
              />
            </div>
            <label style={{ fontSize: 11.5, color: "var(--fg-2)", display: "flex", alignItems: "center", gap: 6 }}>
              <input
                type="checkbox"
                checked={onlyWaste}
                onChange={(e) => setOnlyWaste(e.target.checked)}
              />
              with waste only
            </label>
          </div>
          <div className="replay-session-list">
            {sessions.map((s) => (
              <SessionRow
                key={s.id}
                session={s}
                active={s.id === activeSession}
                onClick={() => {
                  setActiveSession(s.id);
                  setActiveIdx(0);
                }}
              />
            ))}
            {sessions.length === 0 && (
              <div style={{ margin: 12 }}>
                <EmptyState compact title="No sessions match" description="Clear filters or broaden the time range." />
              </div>
            )}
          </div>
        </div>

        <div className="replay-col">
          {!replay || replay.events.length === 0 ? (
            <div style={{ margin: 16 }}>
              <EmptyState
                title="No session selected"
                description="Pick a session from the left panel — or start Claude Code and this fills in as tokens flow."
              />
            </div>
          ) : (
            <>
              <ScrubBars events={replay.events} activeIdx={activeIdx} onPick={setActiveIdx} />
              <div className="replay-timeline">
                {replay.events.map((e) => (
                  <div
                    key={e.id}
                    className={`replay-row ${e.idx === activeIdx ? "active" : ""}`}
                    onClick={() => setActiveIdx(e.idx)}
                  >
                    <span className="t">{e.t}</span>
                    <span className="q">
                      {e.role === "assistant" ? "↩ " : "→ "}
                      {e.preview || "(no preview)"}
                    </span>
                    <span className="tk">
                      <span className="up">↑{fmt.k(e.tokens_in)}</span>{" "}
                      <span className="dn">↓{fmt.k(e.tokens_out)}</span>
                    </span>
                    <span className="tk">{fmt.usd(e.cost_usd)}</span>
                  </div>
                ))}
              </div>
            </>
          )}
        </div>

        <div className="replay-col replay-detail">
          {activeEvent ? (
            <>
              <div className="replay-detail-section">
                <div className="replay-detail-label">
                  Message #{activeEvent.idx + 1} · {activeEvent.t}
                </div>
                <div style={{ fontSize: 13, color: "var(--fg-0)", marginBottom: 8 }}>
                  {activeEvent.preview || "(no preview)"}
                </div>
                <div className="hstack" style={{ gap: 6 }}>
                  <Badge kind={modelBadgeKind(activeEvent.model)}>
                    {activeEvent.model || activeEvent.role}
                  </Badge>
                </div>
              </div>

              <div className="replay-detail-section">
                <div className="replay-detail-label">Token breakdown</div>
                <div className="vstack" style={{ gap: 6, fontSize: 12 }}>
                  <div className="hstack spread">
                    <span className="muted">Input</span>
                    <span className="mono tnum">{fmt.k(activeEvent.tokens_in)}</span>
                  </div>
                  <div className="hstack spread">
                    <span className="muted">Output</span>
                    <span className="mono tnum">{fmt.k(activeEvent.tokens_out)}</span>
                  </div>
                  <div className="hstack spread">
                    <span className="muted">Cache read</span>
                    <span className="mono tnum dim">{fmt.k(activeEvent.cache_read)}</span>
                  </div>
                  <hr className="hr" />
                  <div className="hstack spread" style={{ fontWeight: 500 }}>
                    <span>Total cost</span>
                    <span className="mono tnum">{fmt.usd(activeEvent.cost_usd)}</span>
                  </div>
                </div>
              </div>

              <div className="replay-detail-section">
                <div className="replay-detail-label">
                  Better prompt · {betterMode.toUpperCase()}
                </div>
                {betterPrompt.data ? (
                  <>
                    <div className="replay-detail-box">{betterPrompt.data.suggested_text}</div>
                    <div style={{ fontSize: 11, color: "var(--fg-3)", marginTop: 4 }}>
                      est save {fmt.k(betterPrompt.data.est_save_tokens)} tokens
                      {betterPrompt.data.cached ? " · cached" : ""}
                    </div>
                    <Button
                      size="sm"
                      style={{ width: "100%", justifyContent: "center", marginTop: 8 }}
                      onClick={() => {
                        void navigator.clipboard.writeText(betterPrompt.data!.suggested_text);
                      }}
                    >
                      <FileText size={12} strokeWidth={1.8} /> Copy
                    </Button>
                  </>
                ) : (
                  <Button
                    size="sm"
                    variant="primary"
                    style={{ width: "100%", justifyContent: "center" }}
                    onClick={() =>
                      betterPrompt.mutate({
                        idx: activeEvent.idx,
                        mode: betterMode,
                      })
                    }
                    disabled={betterPrompt.isPending}
                  >
                    <Sparkles size={12} strokeWidth={1.8} />{" "}
                    {betterPrompt.isPending ? "Generating…" : "Suggest"}
                  </Button>
                )}
                {betterPrompt.isError && (
                  <div style={{ color: "var(--red)", fontSize: 11, marginTop: 6 }}>
                    {(betterPrompt.error as Error).message}
                  </div>
                )}
              </div>
            </>
          ) : (
            <div style={{ margin: 16 }}>
              <EmptyState compact title="No message selected" description="Click a row in the timeline to inspect tokens, model, and cost." />
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function SessionRow({
  session,
  active,
  onClick,
}: {
  session: SessionSummary;
  active: boolean;
  onClick: () => void;
}) {
  return (
    <div
      className={`replay-session-row ${active ? "active" : ""}`}
      onClick={onClick}
    >
      <div className="replay-session-proj">{session.project}</div>
      <div className="replay-session-meta">
        <span>{session.started_at ? new Date(session.started_at).toLocaleString() : ""}</span>
      </div>
      <div className="replay-session-meta" style={{ marginTop: 2 }}>
        <span>{fmt.k(session.tokens)} tokens</span>
        <span>·</span>
        <span>{fmt.usd(session.cost)}</span>
        {session.wastes > 0 && (
          <>
            <span>·</span>
            <span style={{ color: "var(--red)" }}>{session.wastes} waste</span>
          </>
        )}
      </div>
    </div>
  );
}

function ScrubBars({
  events,
  activeIdx,
  onPick,
}: {
  events: ReplayEvent[];
  activeIdx: number;
  onPick: (idx: number) => void;
}) {
  const max = Math.max(1, ...events.map((e) => e.tokens_in + e.tokens_out));
  return (
    <div className="replay-scrub">
      <div className="replay-scrub-bars">
        {events.map((e) => {
          const pct = ((e.tokens_in + e.tokens_out) / max) * 100;
          const kind = modelBadgeKind(e.model);
          const color =
            kind === "opus" ? "var(--violet)" :
            kind === "sonnet" ? "var(--amber)" :
            kind === "haiku" ? "var(--blue)" : "var(--fg-3)";
          return (
            <button
              key={e.id}
              type="button"
              className="replay-scrub-bar"
              onClick={() => onPick(e.idx)}
              title={`${e.t} — ${fmt.k(e.tokens_in + e.tokens_out)} tokens`}
              aria-label={`message ${e.idx + 1}`}
            >
              <div
                className="fill"
                style={{
                  height: `${pct}%`,
                  background: color,
                  opacity: activeIdx === e.idx ? 1 : 0.55,
                }}
              />
            </button>
          );
        })}
      </div>
    </div>
  );
}
