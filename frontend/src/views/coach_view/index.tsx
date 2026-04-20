import { useEffect, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Plus, Send } from "lucide-react";
import { api, type CoachMessage } from "../../api/client";
import { Button, IconButton } from "../../components/Button";
import { fmt } from "../../lib/fmt";
import { renderMarkdown } from "../../lib/markdown";
import "./Coach.css";

export function AICoach() {
  const qc = useQueryClient();
  const [activeThread, setActiveThread] = useState<string | null>(null);
  const [draft, setDraft] = useState("");
  const bottomRef = useRef<HTMLDivElement | null>(null);

  const keyStatus = useQuery({ queryKey: ["api-key-status"], queryFn: () => api.apiKeyStatus() });
  const threads = useQuery({
    queryKey: ["coach-threads"],
    queryFn: () => api.listCoachThreads(),
  });
  const messages = useQuery({
    queryKey: ["coach-messages", activeThread],
    queryFn: () => (activeThread ? api.listCoachMessages(activeThread) : Promise.resolve([])),
    enabled: !!activeThread,
  });
  const suggestions = useQuery({
    queryKey: ["coach-suggestions"],
    queryFn: () => api.coachSuggestions(),
  });
  const session = useQuery({ queryKey: ["session-current"], queryFn: () => api.currentSession() });
  const budget = useQuery({ queryKey: ["kpi-budget"], queryFn: () => api.kpiBudget() });
  const wastes = useQuery({ queryKey: ["wastes", "active"], queryFn: () => api.listWastes("active") });
  const settings = useQuery({ queryKey: ["settings"], queryFn: () => api.getSettings() });

  useEffect(() => {
    if (!activeThread && threads.data && threads.data.length > 0) {
      setActiveThread(threads.data[0]!.id);
    }
  }, [activeThread, threads.data]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [messages.data]);

  const createThread = useMutation({
    mutationFn: (title?: string) => api.createCoachThread(title),
    onSuccess: (thread) => {
      qc.invalidateQueries({ queryKey: ["coach-threads"] });
      setActiveThread(thread.id);
    },
  });

  const sendMessage = useMutation({
    mutationFn: ({ threadId, content }: { threadId: string; content: string }) =>
      api.sendCoachMessage(threadId, content),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["coach-messages", activeThread] });
      qc.invalidateQueries({ queryKey: ["coach-threads"] });
    },
  });

  const onSend = () => {
    if (!draft.trim()) return;
    const content = draft.trim();
    setDraft("");

    if (!activeThread) {
      // Auto-create a thread with the first message as title
      createThread.mutate(content.slice(0, 40), {
        onSuccess: (thread) => {
          sendMessage.mutate({ threadId: thread.id, content });
        },
      });
    } else {
      sendMessage.mutate({ threadId: activeThread, content });
    }
  };

  if (!keyStatus.data?.configured) {
    return (
      <div className="page">
        <div className="page-header">
          <div>
            <h1 className="page-title">AI Coach</h1>
            <p className="page-sub">API 키 등록 필요</p>
          </div>
        </div>
        <div className="view-placeholder">
          Add your Claude API key in Settings to enable AI Coach.
        </div>
      </div>
    );
  }

  const activeThreadObj = threads.data?.find((t) => t.id === activeThread);
  const threadCost = activeThreadObj?.cost_usd_total ?? 0;
  const estTokens = Math.max(1, Math.ceil(draft.trim().length / 4));
  const estRate =
    settings.data?.llm.model === "claude-opus-4-7"
      ? { input: 15, output: 75 }
      : { input: 3, output: 15 };
  const estCost = draft.trim()
    ? (estTokens / 1_000_000) * estRate.input + (Math.ceil(estTokens * 0.8) / 1_000_000) * estRate.output
    : 0;

  return (
    <div className="page">
      <div className="page-header">
        <div>
          <h1 className="page-title">AI Coach</h1>
          <p className="page-sub">대화형 조언 · Sonnet 4.6 · 실시간 데이터 주입</p>
        </div>
        <div className="hstack">
          <span className="muted" style={{ fontSize: 12 }}>
            Thread cost: <span className="mono tnum">{fmt.usd(threadCost)}</span>
          </span>
        </div>
      </div>

      <div className="coach-wrap">
        {/* Threads */}
        <div className="coach-col">
          <div className="coach-col-head">
            <div className="coach-col-head-label">Threads</div>
            <IconButton ariaLabel="New thread" onClick={() => createThread.mutate("New thread")}>
              <Plus size={14} strokeWidth={1.8} />
            </IconButton>
          </div>
          <div className="coach-threads">
            {(threads.data ?? []).map((t) => (
              <div
                key={t.id}
                className={`coach-thread ${activeThread === t.id ? "active" : ""}`}
                onClick={() => setActiveThread(t.id)}
              >
                <div className="coach-thread-title">{t.title || "(untitled)"}</div>
                <div className="coach-thread-time">
                  {t.last_msg_at ? new Date(t.last_msg_at).toLocaleString() : ""}
                </div>
              </div>
            ))}
            {(threads.data ?? []).length === 0 && (
              <div className="view-placeholder" style={{ margin: 12 }}>
                No threads yet. Start a conversation.
              </div>
            )}
          </div>
        </div>

        {/* Chat */}
        <div className="coach-col">
          <div className="coach-chat-head">
            <div className="coach-avatar">TF</div>
            <div style={{ flex: 1 }}>
              <div style={{ fontSize: 13, fontWeight: 500 }}>TokenFlow Coach</div>
              <div style={{ fontSize: 11, color: "var(--fg-3)", fontFamily: "var(--font-mono)" }}>
                {settings.data?.llm.model === "claude-opus-4-7" ? "Opus 4.7" : "Sonnet 4.6"}
                {" · analyzing live usage"}
              </div>
            </div>
          </div>

          <div className="coach-messages">
            {(messages.data ?? []).map((m) => <ChatBubble key={m.id} msg={m} />)}
            {sendMessage.isPending && (
              <div className="msg ai">
                <div className="coach-avatar">TF</div>
                <div className="msg-bubble" style={{ color: "var(--fg-3)" }}>
                  …thinking
                </div>
              </div>
            )}
            {sendMessage.isError && (
              <div className="msg ai">
                <div className="msg-bubble" style={{ color: "var(--red)" }}>
                  Error: {(sendMessage.error as Error).message}
                </div>
              </div>
            )}
            <div ref={bottomRef} />
          </div>

          {(suggestions.data ?? []).length > 0 && (messages.data ?? []).length === 0 && (
            <div className="coach-suggestions">
              {(suggestions.data ?? []).map((s) => (
                <button key={s} className="coach-chip" onClick={() => setDraft(s)}>
                  {s}
                </button>
              ))}
            </div>
          )}

          <div className="coach-composer">
            <div className="coach-input-wrap">
              <textarea
                className="coach-input"
                placeholder="사용량·질문 효율에 대해 물어보세요…"
                rows={1}
                value={draft}
                onChange={(e) => setDraft(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter" && !e.shiftKey) {
                    e.preventDefault();
                    onSend();
                  }
                }}
              />
              <div className="coach-input-row">
                <span>
                  Enter 전송 · Shift+Enter 줄바꿈
                  {draft.trim() ? ` · Est. cost ${fmt.usd(estCost)}` : ""}
                </span>
                <Button variant="primary" size="sm" onClick={onSend} disabled={!draft.trim() || sendMessage.isPending}>
                  <Send size={12} strokeWidth={1.8} /> Send
                </Button>
              </div>
            </div>
          </div>
        </div>

        {/* Context */}
        <div className="coach-col coach-context">
          <div className="ctx-section">
            <div className="ctx-label">Current session</div>
            {session.data?.active ? (
              <>
                <div className="ctx-row"><span className="lbl">Project</span><span className="val">{session.data.project}</span></div>
                <div className="ctx-row"><span className="lbl">Model</span><span className="val">{session.data.model}</span></div>
                <div className="ctx-row"><span className="lbl">Tokens</span><span className="val">{fmt.k(session.data.tokens.input + session.data.tokens.output)}</span></div>
                <div className="ctx-row"><span className="lbl">Context</span><span className="val">{Math.round((session.data.contextUsed / session.data.contextWindow) * 100)}%</span></div>
                <div className="ctx-row"><span className="lbl">Cost</span><span className="val">{fmt.usd(session.data.costUSD)}</span></div>
              </>
            ) : (
              <div style={{ color: "var(--fg-3)", fontSize: 12 }}>no active session</div>
            )}
          </div>

          <div className="ctx-section">
            <div className="ctx-label">Budget</div>
            {budget.data && (
              <>
                <div className="ctx-row"><span className="lbl">Spent</span><span className="val">{fmt.usd(budget.data.spent)}</span></div>
                <div className="ctx-row"><span className="lbl">Forecast</span><span className="val">{fmt.usd(budget.data.forecast)}</span></div>
                <div className="ctx-row"><span className="lbl">Opus share</span><span className="val">{Math.round(budget.data.opusShare * 100)}%</span></div>
              </>
            )}
          </div>

          <div className="ctx-section">
            <div className="ctx-label">Waste observations</div>
            {(wastes.data ?? []).slice(0, 5).map((w) => (
              <div key={w.id} className="ctx-row">
                <span className="lbl">{w.kind}</span>
                <span className="val" style={{ color: w.severity === "high" ? "var(--red)" : w.severity === "med" ? "var(--amber)" : "var(--blue)" }}>
                  {w.severity}
                </span>
              </div>
            ))}
            {(wastes.data ?? []).length === 0 && (
              <div style={{ color: "var(--fg-3)", fontSize: 12 }}>clean</div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

function ChatBubble({ msg }: { msg: CoachMessage }) {
  const me = msg.role === "me";
  const body = me ? (
    <span style={{ whiteSpace: "pre-wrap" }}>{msg.content}</span>
  ) : (
    renderMarkdown(msg.content)
  );
  return (
    <div className={`msg ${me ? "me" : "ai"}`}>
      {!me && <div className="coach-avatar">TF</div>}
      <div>
        <div className="msg-bubble">{body}</div>
        <div className="msg-time" style={{ textAlign: me ? "right" : "left" }}>
          {msg.ts ? new Date(msg.ts).toLocaleTimeString() : ""}
          {msg.cost_usd ? ` · ${fmt.usd(msg.cost_usd)}` : ""}
        </div>
      </div>
    </div>
  );
}
