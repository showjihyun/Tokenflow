import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Package } from "lucide-react";
import { api, type LLMModel, type SettingsResponse } from "../../api/client";
import { Card, CardBody, CardHeader } from "../../components/Card";

interface Option {
  value: LLMModel;
  name: string;
  tagline: string;
}

const MODELS: Option[] = [
  {
    value: "claude-sonnet-4-6",
    name: "Sonnet 4.6",
    tagline: "빠르고 저렴 · 대부분의 코칭/재작성에 충분",
  },
  {
    value: "claude-opus-4-7",
    name: "Opus 4.7",
    tagline: "깊은 추론 · 아키텍처·복잡한 디버깅에 권장",
  },
];

export function LlmModelCard({ settings }: { settings: SettingsResponse }) {
  const qc = useQueryClient();
  const current = settings.tweaks.llm_model;

  const save = useMutation({
    mutationFn: (next: LLMModel) => api.patchTweaks({ llm_model: next }),
    onSuccess: (data) => qc.setQueryData(["settings"], data),
  });

  return (
    <Card>
      <CardHeader
        title="LLM 모델"
        icon={<Package size={13} strokeWidth={1.6} />}
        sub="AI Coach + LLM better-prompt"
      />
      <CardBody>
        <div className="settings-help" style={{ marginBottom: 10 }}>
          AI Coach 와 Better prompt LLM 모드 모두에서 사용할 모델입니다. 기본값은 Sonnet 4.6.
        </div>
        <div className="settings-radio">
          {MODELS.map((m) => (
            <button
              key={m.value}
              className={current === m.value ? "active" : ""}
              onClick={() => save.mutate(m.value)}
              disabled={save.isPending || current === m.value}
            >
              <span className="name">{m.name}</span>
              <span className="desc">{m.tagline}</span>
            </button>
          ))}
        </div>
      </CardBody>
    </Card>
  );
}
