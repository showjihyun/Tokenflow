import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Database, Import, RotateCw } from "lucide-react";
import { useState } from "react";
import { api } from "../../api/client";
import { Button } from "../../components/Button";
import { Card, CardBody, CardHeader } from "../../components/Card";
import { queryStaleTime } from "../../lib/queryKeys";

export function DataCard() {
  const qc = useQueryClient();
  const [importPath, setImportPath] = useState("");
  const [jobId, setJobId] = useState<string | null>(null);

  const backups = useQuery({
    queryKey: ["system-backups"],
    queryFn: () => api.listBackups(),
    staleTime: queryStaleTime.config,
  });
  const job = useQuery({
    queryKey: ["import-ccprophet", jobId],
    queryFn: () => api.importCcprophetStatus(jobId!),
    enabled: !!jobId,
    staleTime: queryStaleTime.live,
    refetchInterval: (query) => {
      const state = query.state.data?.state;
      return state === "queued" || state === "running" ? 1000 : false;
    },
  });

  const vacuum = useMutation({
    mutationFn: () => api.vacuum(),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["system-backups"] }),
  });
  const importJob = useMutation({
    mutationFn: (path: string) => api.importCcprophet(path),
    onSuccess: (data) => setJobId(data.job_id),
  });

  const latestBackup = backups.data?.[0];
  const imported = job.data?.imported ?? 0;
  const skipped = job.data?.skipped ?? 0;
  const errors = job.data?.errors ?? [];

  return (
    <Card>
      <CardHeader title="Data" icon={<Database size={13} strokeWidth={1.6} />} />
      <CardBody>
        <div className="vstack" style={{ gap: 12 }}>
          <div className="settings-toggle-row">
            <div>
              <div style={{ fontSize: 13, fontWeight: 600 }}>Vacuum database</div>
              <div className="settings-help" style={{ marginTop: 3 }}>
                Runs 180-day retention, creates a backup, then compacts DuckDB.
              </div>
              {vacuum.data && (
                <div className="settings-help" style={{ marginTop: 3 }}>
                  {formatBytes(vacuum.data.before_bytes)} to {formatBytes(vacuum.data.after_bytes)} · rolled{" "}
                  {vacuum.data.retention.rolled_messages} messages
                </div>
              )}
            </div>
            <Button size="sm" variant="ghost" onClick={() => vacuum.mutate()} disabled={vacuum.isPending}>
              <RotateCw size={12} strokeWidth={1.8} /> {vacuum.isPending ? "Running" : "Vacuum"}
            </Button>
          </div>

          <div>
            <div className="settings-label">Import from ccprophet</div>
            <div style={{ display: "flex", gap: 8 }}>
              <div className="settings-input" style={{ flex: 1 }}>
                <input
                  placeholder="C:\\Users\\you\\.claude-prophet\\events.duckdb"
                  value={importPath}
                  onChange={(e) => setImportPath(e.target.value)}
                />
              </div>
              <Button
                size="sm"
                variant="primary"
                onClick={() => importJob.mutate(importPath)}
                disabled={importJob.isPending || importPath.trim().length === 0}
              >
                <Import size={12} strokeWidth={1.8} /> Import
              </Button>
            </div>
            {job.data && (
              <div className="settings-help">
                Job {job.data.state} · imported {imported} · skipped {skipped}
                {errors.length > 0 ? ` · ${errors.length} errors` : ""}
              </div>
            )}
            {importJob.isError && (
              <div className="settings-help" style={{ color: "var(--red)" }}>
                {(importJob.error as Error).message}
              </div>
            )}
          </div>

          <div>
            <div className="settings-label">Recent backups</div>
            {latestBackup ? (
              <div className="settings-toggle-row">
                <div>
                  <div style={{ fontSize: 13, fontWeight: 600 }}>{latestBackup.name}</div>
                  <div className="settings-help" style={{ marginTop: 3 }}>
                    {formatBytes(latestBackup.bytes)} · {new Date(latestBackup.mtime).toLocaleString()}
                  </div>
                </div>
                <span className="mono dim" style={{ fontSize: 11 }}>
                  {backups.data?.length ?? 0} total
                </span>
              </div>
            ) : (
              <div className="view-placeholder">No backups yet.</div>
            )}
          </div>
        </div>
      </CardBody>
    </Card>
  );
}

function formatBytes(bytes: number) {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}
