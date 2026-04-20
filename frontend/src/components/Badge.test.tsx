import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { Badge } from "./Badge";

describe("<Badge>", () => {
  it("renders children inside a span with the kind class", () => {
    const { container } = render(<Badge kind="opus">Opus 4</Badge>);
    const badge = container.querySelector(".badge");
    expect(badge).toBeInTheDocument();
    expect(badge?.classList.contains("opus")).toBe(true);
    expect(screen.getByText("Opus 4")).toBeInTheDocument();
  });

  it("includes the indicator dot by default", () => {
    const { container } = render(<Badge kind="sonnet">Sonnet</Badge>);
    expect(container.querySelector(".badge .dot")).not.toBeNull();
  });

  it("hides the dot when dot={false}", () => {
    const { container } = render(
      <Badge kind="haiku" dot={false}>
        Haiku
      </Badge>,
    );
    expect(container.querySelector(".badge .dot")).toBeNull();
  });

  it.each(["opus", "sonnet", "haiku", "good", "warn", "danger", "neutral"] as const)(
    "accepts kind=%s",
    (kind) => {
      const { container } = render(<Badge kind={kind}>x</Badge>);
      expect(container.querySelector(`.badge.${kind}`)).not.toBeNull();
    },
  );
});
