import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Bell } from "lucide-react";
import { api } from "../../api/client";
import { Card, CardBody, CardHeader } from "../../components/Card";
import { Toggle } from "./Toggle";

const LABELS: Record<string, string> = {
  waste_high: "High-severity waste 감지 시",
  context_saturation: "컨텍스트 85% 초과",
  opus_overuse: "Opus 과사용 감지",
  daily_report: "일일 리포트 (매일 오전 9시)",
  weekly_summary: "주간 요약 (일요일 밤)",
  session_summary: "세션 종료 시 효율 점수",
};

export function NotificationsCard() {
  const qc = useQueryClient();
  const { data, isLoading } = useQuery({
    queryKey: ["notifications"],
    queryFn: () => api.listNotifications(),
  });

  const patch = useMutation({
    mutationFn: ({ key, enabled }: { key: string; enabled: boolean }) =>
      api.patchNotification(key, { enabled }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["notifications"] }),
  });

  return (
    <Card>
      <CardHeader title="Notifications" icon={<Bell size={13} strokeWidth={1.6} />} />
      <CardBody>
        {isLoading && <div className="view-placeholder">Loading…</div>}
        <div className="vstack" style={{ gap: 8 }}>
          {(data ?? []).map((pref) => (
            <div key={pref.key} className="settings-toggle-row">
              <span style={{ fontSize: 13 }}>{LABELS[pref.key] ?? pref.key}</span>
              <Toggle
                on={pref.enabled}
                onChange={(enabled) => patch.mutate({ key: pref.key, enabled })}
                ariaLabel={`Notification ${pref.key}`}
              />
            </div>
          ))}
        </div>
      </CardBody>
    </Card>
  );
}
