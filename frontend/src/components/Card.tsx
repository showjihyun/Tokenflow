import type { ReactNode } from "react";
import "./Card.css";

interface CardProps {
  children: ReactNode;
  className?: string;
}
export function Card({ children, className = "" }: CardProps) {
  return <div className={`card ${className}`}>{children}</div>;
}

interface CardHeaderProps {
  title: ReactNode;
  icon?: ReactNode;
  sub?: ReactNode;
  action?: ReactNode;
  /**
   * Semantic heading level used for SR TOC. Defaults to h2 — cards are
   * page-level sections under the single <h1> page title. Pass "h3" for
   * nested cards (e.g., cards inside a subsection).
   */
  as?: "h2" | "h3";
}
export function CardHeader({ title, icon, sub, action, as: HeadingTag = "h2" }: CardHeaderProps) {
  return (
    <div className="card-header">
      <HeadingTag className="card-title">
        {icon}
        {title}
      </HeadingTag>
      {sub && <span className="card-sub mono">{sub}</span>}
      {action}
    </div>
  );
}

interface CardBodyProps {
  children: ReactNode;
  flush?: boolean;
  className?: string;
}
export function CardBody({ children, flush = false, className = "" }: CardBodyProps) {
  return <div className={`card-body ${flush ? "flush" : ""} ${className}`}>{children}</div>;
}
