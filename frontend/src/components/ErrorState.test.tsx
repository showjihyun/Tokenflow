import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { ErrorState } from "./ErrorState";

describe("<ErrorState>", () => {
  it("renders variant default copy with role=alert for SR announcement", () => {
    render(<ErrorState variant="api_key_invalid" />);
    const alert = screen.getByRole("alert");
    expect(alert).toHaveTextContent(/API key rejected/);
    expect(alert).toHaveTextContent(/Settings/);
  });

  it("fires retry callback on CTA click", async () => {
    const onRetry = vi.fn();
    render(<ErrorState variant="generic" onRetry={onRetry} />);
    const cta = screen.getByRole("button", { name: /재시도/ });
    await userEvent.click(cta);
    expect(onRetry).toHaveBeenCalledOnce();
  });

  it("hides CTA when onRetry is absent", () => {
    render(<ErrorState variant="db_unavailable" />);
    expect(screen.queryByRole("button")).toBeNull();
  });

  it("throttles the CTA for 5s after one click to kill rage-click storms", async () => {
    const onRetry = vi.fn();
    const user = userEvent.setup();
    render(<ErrorState variant="generic" onRetry={onRetry} />);
    const cta = screen.getByRole("button", { name: /재시도/ });
    await user.click(cta);
    expect(onRetry).toHaveBeenCalledOnce();
    // Second immediate click: button is disabled, no further call.
    await user.click(cta);
    expect(onRetry).toHaveBeenCalledOnce();
    expect(cta).toBeDisabled();
  });

  it("supports a custom title + detail without losing variant copy", () => {
    render(
      <ErrorState variant="rate_limit" title="Custom title" detail="Retry-After 30s" />,
    );
    const alert = screen.getByRole("alert");
    expect(alert).toHaveTextContent("Custom title");
    expect(alert).toHaveTextContent(/Retry-After 30s/);
    // Variant hint still present, just composed with the detail.
    expect(alert).toHaveTextContent(/잠시 후/);
  });
});
