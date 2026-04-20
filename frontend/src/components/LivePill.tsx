import "./LivePill.css";

interface LivePillProps {
  children: React.ReactNode;
  tone?: "green" | "amber" | "red";
}

export function LivePill({ children, tone = "green" }: LivePillProps) {
  return (
    <span className="live-pill" data-tone={tone}>
      <span className="live-dot" />
      {children}
    </span>
  );
}
