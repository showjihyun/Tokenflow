import { useState } from "react";
import { AlertTriangle, Check, Key, Trash2 } from "lucide-react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../../api/client";
import { Button } from "../../components/Button";
import { Card, CardBody, CardHeader } from "../../components/Card";

export function ApiKeyCard() {
  const qc = useQueryClient();
  const [draft, setDraft] = useState("");
  const { data } = useQuery({ queryKey: ["api-key-status"], queryFn: () => api.apiKeyStatus() });
  const configured = data?.configured ?? false;
  const valid = data?.valid ?? false;
  const showForm = !configured || !valid;

  const save = useMutation({
    mutationFn: (key: string) => api.setApiKey(key),
    onSuccess: () => {
      setDraft("");
      qc.invalidateQueries({ queryKey: ["api-key-status"] });
    },
  });
  const del = useMutation({
    mutationFn: () => api.deleteApiKey(),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["api-key-status"] }),
  });

  return (
    <Card>
      <CardHeader title="Claude API key" icon={<Key size={13} strokeWidth={1.6} />} />
      <CardBody>
        <div className="settings-help" style={{ marginBottom: 10 }}>
          AI Coach · LLM better prompt 에 필요합니다.{" "}
          {data?.backend === "keyring" ? (
            <>키는 OS 자격증명 저장소 (Windows Credential Manager / macOS Keychain / Secret Service) 에 저장됩니다.</>
          ) : (
            <>키는 <code>~/.tokenflow/secret.json</code> 에 0600 권한으로 저장됩니다 (keyring backend 없음).</>
          )}
        </div>
        {configured && valid && (
          <div className="settings-toggle-row">
            <span style={{ display: "flex", alignItems: "center", gap: 8, color: "var(--green)" }}>
              <Check size={14} strokeWidth={1.8} /> configured · {data?.backend}
            </span>
            <Button variant="ghost" size="sm" onClick={() => del.mutate()} disabled={del.isPending}>
              <Trash2 size={12} strokeWidth={1.8} /> Remove
            </Button>
          </div>
        )}
        {configured && !valid && (
          <div
            className="settings-toggle-row"
            style={{
              borderColor: "color-mix(in oklch, var(--red) 35%, transparent)",
              marginBottom: 8,
            }}
          >
            <span style={{ display: "flex", alignItems: "center", gap: 8, color: "var(--red)" }}>
              <AlertTriangle size={14} strokeWidth={1.8} /> secret.json is invalid ({data?.error ?? "unknown error"})
            </span>
            <Button variant="ghost" size="sm" onClick={() => del.mutate()} disabled={del.isPending}>
              <Trash2 size={12} strokeWidth={1.8} /> Delete file
            </Button>
          </div>
        )}
        {showForm && (
          <div style={{ display: "flex", gap: 8 }}>
            <div className="settings-input" style={{ flex: 1 }}>
              <span className="settings-input-prefix">sk-</span>
              <input
                type="password"
                placeholder={configured ? "re-enter API key" : "paste your Anthropic API key"}
                value={draft}
                onChange={(e) => setDraft(e.target.value)}
                autoComplete="off"
              />
            </div>
            <Button
              variant="primary"
              size="sm"
              onClick={() => save.mutate(draft)}
              disabled={save.isPending || draft.length < 8}
            >
              Save key
            </Button>
          </div>
        )}
      </CardBody>
    </Card>
  );
}
