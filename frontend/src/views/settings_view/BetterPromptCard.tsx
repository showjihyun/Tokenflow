import { Sparkles } from "lucide-react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { api, type SettingsResponse } from "../../api/client";
import { Card, CardBody, CardHeader } from "../../components/Card";
import { useTweaks, type BetterPromptMode } from "../../lib/tweaksStore";

export function BetterPromptCard({ settings }: { settings: SettingsResponse }) {
  const qc = useQueryClient();
  const mode = settings.tweaks.better_prompt_mode as BetterPromptMode;
  const setTweak = useTweaks((s) => s.setTweak);

  const save = useMutation({
    mutationFn: (next: BetterPromptMode) => api.patchTweaks({ better_prompt_mode: next }),
    onSuccess: (data) => qc.setQueryData(["settings"], data),
  });

  const set = (next: BetterPromptMode) => {
    setTweak("better_prompt_mode", next);
    save.mutate(next);
  };

  return (
    <Card>
      <CardHeader title="Better prompt mode" icon={<Sparkles size={13} strokeWidth={1.6} />} />
      <CardBody>
        <div className="settings-radio">
          <button className={mode === "static" ? "active" : ""} onClick={() => set("static")}>
            <span className="name">Static templates</span>
            <span className="desc">Instant · free · deterministic · 5 patterns</span>
          </button>
          <button className={mode === "llm" ? "active" : ""} onClick={() => set("llm")}>
            <span className="name">LLM rewrite (Sonnet 4.6)</span>
            <span className="desc">1–3s · ~$0.01/query · context-aware</span>
          </button>
        </div>
      </CardBody>
    </Card>
  );
}
