import { Monitor, LineChart, Radar, MessageSquare, Waypoints, Settings as SettingsIcon, HelpCircle } from "lucide-react";
import { NavLink } from "react-router-dom";
import "./Sidebar.css";

interface NavItem {
  to: string;
  label: string;
  Icon: typeof Monitor;
}

const WORKSPACE: NavItem[] = [
  { to: "/live", label: "Live Monitor", Icon: Monitor },
  { to: "/analytics", label: "Analytics", Icon: LineChart },
  { to: "/waste", label: "Waste Radar", Icon: Radar },
  { to: "/coach", label: "AI Coach", Icon: MessageSquare },
  { to: "/replay", label: "Session Replay", Icon: Waypoints },
];

export function Sidebar() {
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
        {WORKSPACE.map(({ to, label, Icon }) => (
          <NavLink
            key={to}
            to={to}
            className={({ isActive }) => `nav-item ${isActive ? "active" : ""}`}
          >
            <Icon size={15} strokeWidth={1.6} />
            <span>{label}</span>
          </NavLink>
        ))}

        <div className="nav-group-label">Account</div>
        <NavLink
          to="/settings"
          className={({ isActive }) => `nav-item ${isActive ? "active" : ""}`}
        >
          <SettingsIcon size={15} strokeWidth={1.6} />
          <span>Settings</span>
        </NavLink>
        <a
          className="nav-item"
          href="https://github.com/showjihyun/Tokenflow#readme"
          target="_blank"
          rel="noreferrer"
          aria-label="Open Token Flow documentation in a new tab"
        >
          <HelpCircle size={15} strokeWidth={1.6} />
          <span>Docs</span>
        </a>
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
