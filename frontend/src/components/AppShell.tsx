import type { ReactNode } from "react";

interface AppShellProps {
  sidebar: ReactNode;
  topbar: ReactNode;
  children: ReactNode;
  density?: "compact" | "normal" | "roomy";
  sidebarPos?: "left" | "right";
  chartStyle?: "bold" | "minimal" | "outlined";
}

export function AppShell({
  sidebar,
  topbar,
  children,
  density = "normal",
  sidebarPos = "left",
  chartStyle = "bold",
}: AppShellProps) {
  return (
    <div
      className="app"
      data-density={density}
      data-sidebar={sidebarPos}
      data-chart={chartStyle}
    >
      {sidebar}
      {topbar}
      <main className="main">{children}</main>
    </div>
  );
}
