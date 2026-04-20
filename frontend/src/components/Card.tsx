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
}
export function CardHeader({ title, icon, sub, action }: CardHeaderProps) {
  return (
    <div className="card-header">
      <div className="card-title">
        {icon}
        {title}
      </div>
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
