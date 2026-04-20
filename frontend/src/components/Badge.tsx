import type { ReactNode } from "react";
import "./Badge.css";

export type BadgeKind =
  | "opus"
  | "sonnet"
  | "haiku"
  | "good"
  | "warn"
  | "danger"
  | "neutral";

interface BadgeProps {
  kind: BadgeKind;
  children: ReactNode;
  dot?: boolean;
}

export function Badge({ kind, children, dot = true }: BadgeProps) {
  return (
    <span className={`badge ${kind}`}>
      {dot && <span className="dot" />}
      {children}
    </span>
  );
}
