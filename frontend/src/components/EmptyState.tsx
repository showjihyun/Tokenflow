import type { ReactNode } from "react";
import "./EmptyState.css";

interface EmptyStateProps {
  icon?: ReactNode;
  title: ReactNode;
  description?: ReactNode;
  /** Optional action button rendered to the right. */
  action?: ReactNode;
  compact?: boolean;
}

// role="status" + aria-live="polite": this is a non-error info state; SR should
// mention it but without interrupting the user (contrast with ErrorState's
// assertive alert). Matches SPEC §10.6 accessibility requirements.
export function EmptyState({ icon, title, description, action, compact = false }: EmptyStateProps) {
  return (
    <div className={`empty-state ${compact ? "compact" : ""}`} role="status" aria-live="polite">
      {icon && (
        <div className="empty-state-icon" aria-hidden>
          {icon}
        </div>
      )}
      <div className="empty-state-body">
        <div className="empty-state-title">{title}</div>
        {description && <div className="empty-state-description">{description}</div>}
      </div>
      {action && <div className="empty-state-action">{action}</div>}
    </div>
  );
}
