import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { EmptyState } from "./EmptyState";

describe("<EmptyState>", () => {
  it("renders title + description under role=status", () => {
    render(<EmptyState title="No sessions yet" description="Start a Claude Code session" />);
    const status = screen.getByRole("status");
    expect(status).toHaveTextContent("No sessions yet");
    expect(status).toHaveTextContent(/Start a Claude Code session/);
  });

  it("renders an action slot when provided", () => {
    render(
      <EmptyState
        title="Nothing here"
        action={<button type="button">Refresh</button>}
      />,
    );
    expect(screen.getByRole("button", { name: /refresh/i })).toBeInTheDocument();
  });
});
