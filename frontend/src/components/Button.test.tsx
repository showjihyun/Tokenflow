import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { Button, IconButton } from "./Button";

describe("<Button>", () => {
  it("renders children and forwards click", async () => {
    const onClick = vi.fn();
    render(<Button onClick={onClick}>Save</Button>);
    const btn = screen.getByRole("button", { name: /save/i });
    expect(btn).toHaveClass("btn");
    await userEvent.click(btn);
    expect(onClick).toHaveBeenCalledOnce();
  });

  it("applies variant + size classes", () => {
    render(
      <Button variant="primary" size="sm">
        Go
      </Button>,
    );
    const btn = screen.getByRole("button", { name: /go/i });
    expect(btn).toHaveClass("primary");
    expect(btn).toHaveClass("sm");
  });

  it("respects disabled", async () => {
    const onClick = vi.fn();
    render(
      <Button disabled onClick={onClick}>
        off
      </Button>,
    );
    await userEvent.click(screen.getByRole("button"));
    expect(onClick).not.toHaveBeenCalled();
  });
});

describe("<IconButton>", () => {
  it("requires an aria-label that becomes the accessible name", () => {
    render(
      <IconButton ariaLabel="dismiss waste">
        <svg />
      </IconButton>,
    );
    expect(screen.getByRole("button", { name: "dismiss waste" })).toBeInTheDocument();
  });
});
