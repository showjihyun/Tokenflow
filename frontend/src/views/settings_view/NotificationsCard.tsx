import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Bell } from "lucide-react";
import { useMemo, useState } from "react";
import { api } from "../../api/client";
import { Button } from "../../components/Button";
import { Card, CardBody, CardHeader } from "../../components/Card";
import { Toggle } from "./Toggle";

const LABELS: Record<string, string> = {
  waste_high: "High-severity waste",
  budget_threshold: "Budget threshold",
  context_saturation: "Context over 85%",
  opus_overuse: "Opus overuse",
  api_error: "API error",
  daily_report: "Daily report",
  weekly_summary: "Weekly summary",
  session_summary: "Session summary",
};

function notificationSupport() {
  if (!("Notification" in window)) {
    return { supported: false, permission: "unsupported" as const };
  }
  return { supported: true, permission: Notification.permission };
}

export function NotificationsCard() {
  const qc = useQueryClient();
  const [permission, setPermission] = useState(notificationSupport().permission);
  const support = useMemo(notificationSupport, []);
  const { data, isLoading } = useQuery({
    queryKey: ["notifications"],
    queryFn: () => api.listNotifications(),
  });

  const patch = useMutation({
    mutationFn: ({ key, enabled, channel }: { key: string; enabled?: boolean; channel?: "in_app" | "system" }) =>
      api.patchNotification(key, { enabled, channel }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["notifications"] }),
  });

  const requestPermission = async () => {
    if (!support.supported) return;
    const next = await Notification.requestPermission();
    setPermission(next);
  };

  const systemReady = support.supported && permission === "granted";

  return (
    <Card>
      <CardHeader
        title="Notifications"
        icon={<Bell size={13} strokeWidth={1.6} />}
        action={
          support.supported && permission !== "granted" ? (
            <Button size="sm" variant="ghost" onClick={requestPermission}>
              Grant permission
            </Button>
          ) : null
        }
      />
      <CardBody>
        {isLoading && <div className="view-placeholder">Loading...</div>}
        {!support.supported && (
          <div className="view-placeholder">System notifications are not supported in this browser.</div>
        )}
        <div className="vstack" style={{ gap: 8 }}>
          {(data ?? []).map((pref) => (
            <div key={pref.key} className="settings-toggle-row">
              <span style={{ fontSize: 13 }}>{LABELS[pref.key] ?? pref.key}</span>
              <div className="hstack" style={{ gap: 8 }}>
                <Button
                  size="sm"
                  variant={pref.channel === "system" ? "primary" : "ghost"}
                  disabled={!systemReady}
                  onClick={() => patch.mutate({ key: pref.key, channel: "system" })}
                  title={systemReady ? "Use system notification" : "Grant system notification permission first"}
                >
                  System
                </Button>
                <Button
                  size="sm"
                  variant={pref.channel === "in_app" ? "primary" : "ghost"}
                  onClick={() => patch.mutate({ key: pref.key, channel: "in_app" })}
                >
                  In-app
                </Button>
                <Toggle
                  on={pref.enabled}
                  onChange={(enabled) => patch.mutate({ key: pref.key, enabled })}
                  ariaLabel={`Notification ${pref.key}`}
                />
              </div>
            </div>
          ))}
        </div>
      </CardBody>
    </Card>
  );
}
