import { useQuery } from "@tanstack/react-query";
import { api } from "../../api/client";
import { queryStaleTime } from "../../lib/queryKeys";
import { ApiKeyCard } from "./ApiKeyCard";
import { BetterPromptCard } from "./BetterPromptCard";
import { BudgetCard } from "./BudgetCard";
import { DataCard } from "./DataCard";
import { LlmModelCard } from "./LlmModelCard";
import { NotificationsCard } from "./NotificationsCard";
import { RoutingRulesCard } from "./RoutingRulesCard";
import "./Settings.css";

export function Settings() {
  const { data } = useQuery({
    queryKey: ["settings"],
    queryFn: () => api.getSettings(),
    staleTime: queryStaleTime.config,
  });

  if (!data) {
    return (
      <div className="page">
        <div className="page-header">
          <div>
            <h1 className="page-title">Settings</h1>
            <p className="page-sub">loading…</p>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="page" style={{ maxWidth: 900 }}>
      <div className="page-header">
        <div>
          <h1 className="page-title">Settings</h1>
          <p className="page-sub">예산 · 라우팅 · 알림 · LLM 모델 · Better prompt · API 키</p>
        </div>
      </div>

      <div className="vstack" style={{ gap: 16 }}>
        <BudgetCard settings={data} />
        <LlmModelCard settings={data} />
        <BetterPromptCard settings={data} />
        <RoutingRulesCard />
        <NotificationsCard />
        <ApiKeyCard />
        <DataCard />
      </div>
    </div>
  );
}
