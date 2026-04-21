import { useMutation, useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { FileText, Pause } from "lucide-react";
import { api } from "../../api/client";
import { Button } from "../../components/Button";
import { ErrorState } from "../../components/ErrorState";
import { errorVariantFrom } from "../../lib/errorMapping";
import { queryKeys, queryStaleTime } from "../../lib/queryKeys";
import "../../components/charts/chart.css";
import "./LiveMonitor.css";

import { ActivityTicker } from "./ActivityTicker";
import { BudgetCard } from "./BudgetCard";
import { ContextWindow } from "./ContextWindow";
import { KPIRow } from "./KPIRow";
import { ModelDistribution } from "./ModelDistribution";
import { ProjectsTable } from "./ProjectsTable";
import { TokenFlowChart } from "./TokenFlowChart";

export function LiveMonitor() {
  const [paused, setPaused] = useState(false);
  const { data: session, isError, error, refetch } = useQuery({
    queryKey: queryKeys.sessionCurrent,
    queryFn: () => api.currentSession(),
    staleTime: queryStaleTime.live,
  });
  const pauseMutation = useMutation({
    mutationFn: (next: boolean) => api.pauseIngestion(next),
    onSuccess: (data) => setPaused(data.paused),
  });

  const exportMutation = useMutation({
    mutationFn: async () => {
      if (!session?.id) return;
      const payload = await api.exportSession(session.id);
      const blob = new Blob([JSON.stringify(payload, null, 2)], { type: "application/json" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `tokenflow-${session.id}.json`;
      a.click();
      URL.revokeObjectURL(url);
    },
  });

  return (
    <div className="page">
      <div className="page-header">
        <div>
          <h1 className="page-title">Live Monitor</h1>
          <p className="page-sub">
            실시간 세션{" "}
            {session?.id && (
              <span className="mono dim">
                · {session.id} · {session.project}
              </span>
            )}
          </p>
        </div>
        <div className="hstack">
          <Button variant="ghost" size="sm" onClick={() => pauseMutation.mutate(!paused)}>
            <Pause size={13} strokeWidth={1.8} /> {paused ? "Resume tracking" : "Pause tracking"}
          </Button>
          <Button size="sm" onClick={() => exportMutation.mutate()} disabled={!session?.id}>
            <FileText size={13} strokeWidth={1.8} /> Export session
          </Button>
        </div>
      </div>

      {isError && (
        <ErrorState
          variant={errorVariantFrom(error)}
          detail={error instanceof Error ? error.message : undefined}
          onRetry={() => refetch()}
        />
      )}

      <KPIRow />

      <div className="row row-21">
        <TokenFlowChart />
        <ContextWindow />
      </div>

      <div className="row row-3">
        <ModelDistribution />
        <BudgetCard />
        <ActivityTicker />
      </div>

      <div className="row">
        <ProjectsTable />
      </div>
    </div>
  );
}

