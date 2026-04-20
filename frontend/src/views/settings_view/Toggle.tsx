interface ToggleProps {
  on: boolean;
  onChange: (on: boolean) => void;
  ariaLabel?: string;
}

export function Toggle({ on, onChange, ariaLabel }: ToggleProps) {
  return (
    <button
      onClick={() => onChange(!on)}
      aria-label={ariaLabel}
      aria-pressed={on}
      style={{
        width: 32,
        height: 18,
        borderRadius: 9,
        background: on ? "var(--amber)" : "var(--bg-3)",
        position: "relative",
        transition: "background 0.15s",
        border: "1px solid var(--border-subtle)",
      }}
    >
      <div
        style={{
          position: "absolute",
          top: 1,
          left: on ? 15 : 1,
          width: 14,
          height: 14,
          borderRadius: "50%",
          background: on ? "oklch(0.18 0.02 62)" : "var(--fg-2)",
          transition: "left 0.15s",
        }}
      />
    </button>
  );
}
