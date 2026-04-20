import type { ButtonHTMLAttributes, ReactNode } from "react";
import "./Button.css";

type Variant = "primary" | "default" | "ghost";
type Size = "sm" | "md";

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant;
  size?: Size;
  children: ReactNode;
}

export function Button({
  variant = "default",
  size = "md",
  className = "",
  children,
  ...rest
}: ButtonProps) {
  const cls = ["btn", variant !== "default" ? variant : "", size === "sm" ? "sm" : "", className]
    .filter(Boolean)
    .join(" ");
  return (
    <button className={cls} {...rest}>
      {children}
    </button>
  );
}

interface IconButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  children: ReactNode;
  ariaLabel: string;
}
export function IconButton({ children, ariaLabel, className = "", ...rest }: IconButtonProps) {
  return (
    <button className={`icon-btn ${className}`} aria-label={ariaLabel} {...rest}>
      {children}
    </button>
  );
}
