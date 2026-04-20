import { useQuery } from "@tanstack/react-query";
import { FileText, Pause } from "lucide-react";
import { api } from "../../api/client";
import { Button } from "../../components/Button";
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
  const { data: session } = useQuery({
    queryKey: ["session-current"],
    queryFn: () => api.currentSession(),
  });

  return (
    <div className="page">
      <div className="page-header">
        <div>
          <h1 className="page-title">Live Monitor</h1>
          <p className="page-sub">
            실시간 세션{" "}
            {session && (
              <span className="mono dim">
                · {session.id} · {session.project}
              </span>
            )}
          </p>
        </div>
        <div className="hstack">
          <Button variant="ghost" size="sm">
            <Pause size={13} strokeWidth={1.8} /> Pause tracking
          </Button>
          <Button size="sm">
            <FileText size={13} strokeWidth={1.8} /> Export session
          </Button>
        </div>
      </div>

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
