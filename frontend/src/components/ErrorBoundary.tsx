import { Component, type ErrorInfo, type ReactNode } from "react";
import { AlertTriangle, RefreshCw } from "lucide-react";

interface Props {
  children: ReactNode;
  /** Short name of the boundary, shown in the fallback (e.g. view name). */
  label?: string;
}

interface State {
  error: Error | null;
  errorInfo: ErrorInfo | null;
}

/**
 * Catches render-time errors from descendants and renders a recovery UI.
 * Without this, any thrown Error from a view (missing field, TypeError on
 * unexpected API shape) takes down the whole app instead of just that view.
 */
export class ErrorBoundary extends Component<Props, State> {
  state: State = { error: null, errorInfo: null };

  static getDerivedStateFromError(error: Error): State {
    return { error, errorInfo: null };
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo): void {
    this.setState({ error, errorInfo });
    // Surface to the console so devs catch it in dev; in prod the fallback UI
    // still protects the rest of the app.
    // eslint-disable-next-line no-console
    console.error("[ErrorBoundary]", this.props.label ?? "", error, errorInfo);
  }

  render(): ReactNode {
    if (!this.state.error) return this.props.children;
    return (
      <div className="page">
        <div className="page-header">
          <div>
            <h1 className="page-title">Something broke</h1>
            <p className="page-sub">
              {this.props.label ? `in ${this.props.label}` : "in this view"} — the rest of
              the app is fine. You can retry below.
            </p>
          </div>
          <button
            className="btn primary sm"
            onClick={() => this.setState({ error: null, errorInfo: null })}
          >
            <RefreshCw size={13} strokeWidth={1.8} /> Retry
          </button>
        </div>
        <div
          style={{
            padding: 16,
            border: "1px solid color-mix(in oklch, var(--red) 35%, transparent)",
            borderRadius: "var(--r-md)",
            background: "var(--red-w)",
            color: "var(--fg-0)",
            display: "flex",
            gap: 12,
            alignItems: "flex-start",
          }}
        >
          <AlertTriangle size={18} strokeWidth={1.8} color="var(--red)" />
          <div style={{ flex: 1, fontSize: 13, lineHeight: 1.55 }}>
            <div style={{ fontWeight: 500, marginBottom: 4 }}>
              {this.state.error.name}: {this.state.error.message}
            </div>
            {this.state.errorInfo?.componentStack && (
              <pre
                style={{
                  margin: 0,
                  padding: 8,
                  background: "var(--bg-2)",
                  borderRadius: 6,
                  fontFamily: "var(--font-mono)",
                  fontSize: 11,
                  color: "var(--fg-2)",
                  whiteSpace: "pre-wrap",
                  overflowX: "auto",
                  maxHeight: 240,
                }}
              >
                {this.state.errorInfo.componentStack.trim()}
              </pre>
            )}
          </div>
        </div>
      </div>
    );
  }
}
