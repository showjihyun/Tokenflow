import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AlertTriangle, ArrowRight, Check, X } from "lucide-react";
import { api } from "../../api/client";
import { Button } from "../../components/Button";
import "./Onboarding.css";

interface OnboardingProps {
  onClose: () => void;
}

const STEPS = ["Hook", "API key", "Import", "Done"] as const;

export function Onboarding({ onClose }: OnboardingProps) {
  const qc = useQueryClient();
  const { data: status, refetch } = useQuery({
    queryKey: ["onboarding-status"],
    queryFn: () => api.onboardingStatus(),
  });
  const [step, setStep] = useState(0);
  const [apiKeyDraft, setApiKeyDraft] = useState("");

  const install = useMutation({
    mutationFn: () => api.installHook(false),
    onSuccess: () => refetch(),
  });
  const saveKey = useMutation({
    mutationFn: (k: string) => api.setApiKey(k),
    onSuccess: () => {
      setApiKeyDraft("");
      qc.invalidateQueries({ queryKey: ["api-key-status"] });
      refetch();
    },
  });
  const complete = useMutation({
    mutationFn: () => api.onboardingComplete(),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["onboarding-status"] });
      onClose();
    },
  });

  if (!status) {
    return (
      <div className="onboarding-overlay">
        <div className="onboarding-card">
          <div className="onboarding-body">Loading…</div>
        </div>
      </div>
    );
  }

  const hookInstalled = status.hook.status === "installed";
  // Every step is skippable — onboarding is guidance, not a gate.
  const canAdvance = !install.isPending && !saveKey.isPending;

  return (
    <div className="onboarding-overlay">
      <div className="onboarding-card">
        <div className="onboarding-header">
          <div className="onboarding-brand">
            <div className="mark" />
            <div>
              <h1 className="onboarding-title">Welcome to Token Flow</h1>
              <div style={{ color: "var(--fg-3)", fontSize: 11.5, fontFamily: "var(--font-mono)" }}>
                {STEPS[step]} · {step + 1} / {STEPS.length}
              </div>
            </div>
          </div>
          <div className="onboarding-stepper">
            {STEPS.map((_, i) => (
              <div key={i} className={`dot ${i === step ? "active" : i < step ? "done" : ""}`} />
            ))}
          </div>
        </div>

        <div className="onboarding-body">
          {step === 0 && (
            <>
              <h2 className="onboarding-step-title">Install the hook in Claude Code</h2>
              <p className="onboarding-step-sub">
                Token Flow listens to Claude Code's hook events to track your usage. We'll add entries
                to <code>{status.hook.settings_path}</code> and back up the current file first.
              </p>
              <div className="onboarding-status-row" data-tone={hookInstalled ? "ok" : "warn"}>
                {hookInstalled ? (
                  <Check size={14} strokeWidth={1.8} color="var(--green)" />
                ) : (
                  <AlertTriangle size={14} strokeWidth={1.8} color="var(--amber)" />
                )}
                <div>
                  <div>status: <b>{status.hook.status}</b></div>
                  <div className="onboarding-step-sub" style={{ marginTop: 4 }}>
                    installed: {status.hook.installed_events.length
                      ? status.hook.installed_events.join(", ")
                      : "(none)"}
                    <br />
                    missing: {status.hook.missing_events.length
                      ? status.hook.missing_events.join(", ")
                      : "(none)"}
                  </div>
                </div>
              </div>
              {!hookInstalled && (
                <Button
                  variant="primary"
                  size="sm"
                  onClick={() => install.mutate()}
                  disabled={install.isPending}
                  style={{ marginTop: 12 }}
                >
                  {install.isPending ? "Installing…" : "Install hook"}
                </Button>
              )}
            </>
          )}

          {step === 1 && (
            <>
              <h2 className="onboarding-step-title">Add your Claude API key (optional)</h2>
              <p className="onboarding-step-sub">
                Only needed for AI Coach + LLM better-prompt. You can add or change it later in Settings.
                Stored in <code>~/.tokenflow/secret.json</code> with 0600 permissions.
              </p>
              {status.api_key_configured ? (
                <div className="onboarding-status-row" data-tone="ok">
                  <Check size={14} strokeWidth={1.8} color="var(--green)" /> key configured
                </div>
              ) : (
                <div style={{ display: "flex", gap: 8 }}>
                  <div className="settings-input onboarding-input" style={{ flex: 1 }}>
                    <span className="settings-input-prefix">sk-</span>
                    <input
                      type="password"
                      placeholder="paste API key (or Skip)"
                      value={apiKeyDraft}
                      onChange={(e) => setApiKeyDraft(e.target.value)}
                    />
                  </div>
                  <Button
                    variant="primary"
                    size="sm"
                    onClick={() => saveKey.mutate(apiKeyDraft)}
                    disabled={saveKey.isPending || apiKeyDraft.length < 8}
                  >
                    Save
                  </Button>
                </div>
              )}
            </>
          )}

          {step === 2 && (
            <>
              <h2 className="onboarding-step-title">Import past data from ccprophet (optional)</h2>
              <p className="onboarding-step-sub">
                Token Flow shares the V1–V5 schema with ccprophet so we can import existing session history.
              </p>
              <div
                className="onboarding-status-row"
                data-tone={status.ccprophet.exists ? "ok" : "warn"}
              >
                {status.ccprophet.exists ? (
                  <Check size={14} strokeWidth={1.8} color="var(--green)" />
                ) : (
                  <X size={14} strokeWidth={1.8} color="var(--fg-3)" />
                )}
                <div>
                  <div>ccprophet DB: {status.ccprophet.exists ? "found" : "not found"}</div>
                  <div className="onboarding-step-sub" style={{ marginTop: 4 }}>
                    <code>{status.ccprophet.candidate_path}</code>
                  </div>
                </div>
              </div>
              {status.ccprophet.exists && (
                <p className="onboarding-step-sub" style={{ marginTop: 12 }}>
                  Run <code>tokenflow import --from-ccprophet {status.ccprophet.candidate_path}</code> in
                  a terminal to import.
                </p>
              )}
            </>
          )}

          {step === 3 && (
            <>
              <h2 className="onboarding-step-title">You're all set 🎉</h2>
              <p className="onboarding-step-sub">
                Start a Claude Code session — Live Monitor will activate as soon as the first event arrives.
                You can re-run this onboarding from Settings later.
              </p>
            </>
          )}
        </div>

        <div className="onboarding-footer">
          <div className="hstack" style={{ gap: 8 }}>
            <Button
              variant="ghost"
              size="sm"
              onClick={() => setStep(Math.max(0, step - 1))}
              disabled={step === 0}
            >
              Back
            </Button>
            <Button
              variant="ghost"
              size="sm"
              onClick={() => complete.mutate()}
              disabled={complete.isPending}
              title="Finish onboarding now and go to Live Monitor"
            >
              Skip all
            </Button>
          </div>
          {step < STEPS.length - 1 ? (
            <Button
              variant="primary"
              size="sm"
              onClick={() => setStep(step + 1)}
              disabled={!canAdvance}
            >
              {step === 0 && !hookInstalled ? "Skip" : "Next"} <ArrowRight size={12} strokeWidth={1.8} />
            </Button>
          ) : (
            <Button
              variant="primary"
              size="sm"
              onClick={() => complete.mutate()}
              disabled={complete.isPending}
            >
              Go to Live Monitor <ArrowRight size={12} strokeWidth={1.8} />
            </Button>
          )}
        </div>
      </div>
    </div>
  );
}
