import { useState, type ReactNode } from "react";
import { AlertTriangle, ExternalLink, RefreshCw } from "lucide-react";
import "./ErrorState.css";

/**
 * SPEC §10.4 error taxonomy maps to these variants. Each variant carries its
 * own default copy + affordance so callers only pass a variant (and optional
 * retry) instead of wiring title/hint/CTA individually in every view.
 *
 * `generic` is the fall-through for unmapped failures (network, 5xx, unknown).
 */
export type ErrorVariant =
  | "api_key_invalid"
  | "rate_limit"
  | "upstream_5xx"
  | "hook_disconnected"
  | "db_unavailable"
  | "disk_full"
  | "generic";

interface VariantCopy {
  title: string;
  hint: string;
  cta?: string;
}

const VARIANT_COPY: Record<ErrorVariant, VariantCopy> = {
  api_key_invalid: {
    title: "API key rejected",
    hint: "Settings 에서 Anthropic 키를 재확인해 주세요.",
    cta: "Settings 이동",
  },
  rate_limit: {
    title: "Rate limited",
    hint: "요청이 몰렸어요. 잠시 후 다시 시도해 주세요.",
    cta: "재시도",
  },
  upstream_5xx: {
    title: "Anthropic service issue",
    hint: "업스트림이 응답하지 않습니다.",
    cta: "재시도",
  },
  hook_disconnected: {
    title: "Hook 연결 없음",
    hint: "Settings → Onboarding 에서 tokenflow-hook 재설치가 필요합니다.",
    cta: "Onboarding",
  },
  db_unavailable: {
    title: "DB unavailable",
    hint: "DuckDB 파일 잠금 중 — 자동 재시도합니다.",
  },
  disk_full: {
    title: "Disk almost full",
    hint: "Vacuum 으로 DB 를 정리해 주세요.",
    cta: "Vacuum",
  },
  generic: {
    title: "뭔가 잘못됐어요",
    hint: "잠시 후 다시 시도해 주세요.",
    cta: "재시도",
  },
};

// 5s client-side throttle prevents rage-click storms while still letting the
// user recover quickly from transient failures. Matches the plan-eng-review
// decision for TanStack Query refetch semantics.
const RETRY_THROTTLE_MS = 5_000;

interface ErrorStateProps {
  variant?: ErrorVariant;
  /** Override the default title for unusual cases. */
  title?: string;
  /** Additional free-form hint appended after the variant copy. */
  detail?: ReactNode;
  /** Called when the user clicks the CTA. No-op renders no button. */
  onRetry?: () => void;
  /** Override the default CTA label. */
  retryLabel?: string;
  /** Compact variant: hides icon, smaller padding. For inline use inside cards. */
  compact?: boolean;
}

export function ErrorState({
  variant = "generic",
  title,
  detail,
  onRetry,
  retryLabel,
  compact = false,
}: ErrorStateProps) {
  const copy = VARIANT_COPY[variant];
  const [throttledUntil, setThrottledUntil] = useState(0);
  const disabled = Date.now() < throttledUntil;

  const handleClick = () => {
    if (disabled) return;
    onRetry?.();
    setThrottledUntil(Date.now() + RETRY_THROTTLE_MS);
  };

  // role="alert" + aria-live="assertive": SR announces immediately when the
  // ErrorState mounts. This is the right level for a primary error — empty
  // states use the gentler polite/status combo.
  return (
    <div className={`error-state ${compact ? "compact" : ""}`} role="alert" aria-live="assertive">
      {!compact && (
        <div className="error-state-icon" aria-hidden>
          <AlertTriangle size={28} strokeWidth={1.6} />
        </div>
      )}
      <div className="error-state-body">
        <div className="error-state-title">{title ?? copy.title}</div>
        <div className="error-state-hint">
          {copy.hint}
          {detail ? <> · {detail}</> : null}
        </div>
      </div>
      {onRetry && copy.cta && (
        <button
          type="button"
          className="error-state-cta"
          onClick={handleClick}
          disabled={disabled}
          aria-label={retryLabel ?? copy.cta}
        >
          {variant === "api_key_invalid" || variant === "hook_disconnected" ? (
            <ExternalLink size={14} strokeWidth={1.6} />
          ) : (
            <RefreshCw size={14} strokeWidth={1.6} />
          )}
          {retryLabel ?? copy.cta}
        </button>
      )}
    </div>
  );
}
