import { Monitor, LineChart, Radar, MessageSquare, Waypoints, Settings as SettingsIcon, HelpCircle } from "lucide-react";
import type { ViewKey } from "../App";
import "./Sidebar.css";

interface NavItem {
  key: ViewKey;
  label: string;
  Icon: typeof Monitor;
}

const WORKSPACE: NavItem[] = [
  { key: "live", label: "Live Monitor", Icon: Monitor },
  { key: "analytics", label: "Analytics", Icon: LineChart },
  { key: "waste", label: "Waste Radar", Icon: Radar },
  { key: "coach", label: "AI Coach", Icon: MessageSquare },
  { key: "replay", label: "Session Replay", Icon: Waypoints },
];

interface SidebarProps {
  active: ViewKey;
  onSelect: (key: ViewKey) => void;
}

export function Sidebar({ active, onSelect }: SidebarProps) {
  return (
    <aside className="sidebar">
      <div className="brand">
        <div className="brand-mark" />
        <div className="brand-name">
          Token<span className="brand-dot">⌁</span>Flow
        </div>
      </div>

      <nav className="nav" role="navigation">
        <div className="nav-group-label">Workspace</div>
        {WORKSPACE.map(({ key, label, Icon }) => (
          <button
            key={key}
            className={`nav-item ${active === key ? "active" : ""}`}
            onClick={() => onSelect(key)}
            aria-current={active === key ? "page" : undefined}
          >
            <Icon size={15} strokeWidth={1.6} />
            <span>{label}</span>
          </button>
        ))}

        <div className="nav-group-label">Account</div>
        <button
          className={`nav-item ${active === "settings" ? "active" : ""}`}
          onClick={() => onSelect("settings")}
        >
          <SettingsIcon size={15} strokeWidth={1.6} />
          <span>Settings</span>
        </button>
        <button className="nav-item">
          <HelpCircle size={15} strokeWidth={1.6} />
          <span>Docs</span>
        </button>
      </nav>

      <div className="sidebar-footer">
        <div className="budget-mini">
          <div className="budget-mini-head">
            <span>Monthly</span>
            <span className="mono dim">—</span>
          </div>
          <div className="budget-mini-bar">
            <div className="budget-mini-fill" style={{ width: "0%" }} />
          </div>
          <div className="budget-mini-foot">
            <span>$0.00</span>
            <span>/ $150</span>
          </div>
        </div>
      </div>
    </aside>
  );
}
