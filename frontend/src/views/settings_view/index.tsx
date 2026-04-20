import { useQuery } from "@tanstack/react-query";
import { api } from "../../api/client";
import { ApiKeyCard } from "./ApiKeyCard";
import { BetterPromptCard } from "./BetterPromptCard";
import { BudgetCard } from "./BudgetCard";
import { NotificationsCard } from "./NotificationsCard";
import { RoutingRulesCard } from "./RoutingRulesCard";
import "./Settings.css";

export function Settings() {
  const { data } = useQuery({ queryKey: ["settings"], queryFn: () => api.getSettings() });

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
          <p className="page-sub">예산 · 라우팅 · 알림 · Better prompt · API 키</p>
        </div>
      </div>

      <div className="vstack" style={{ gap: 16 }}>
        <BudgetCard settings={data} />
        <RoutingRulesCard />
        <NotificationsCard />
        <BetterPromptCard settings={data} />
        <ApiKeyCard />
      </div>
    </div>
  );
}
