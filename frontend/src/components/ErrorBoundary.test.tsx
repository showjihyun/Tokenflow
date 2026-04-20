import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import { ErrorBoundary } from "./ErrorBoundary";

// Render-time throw so componentDidCatch fires.
function Boom({ message = "kaboom" }: { message?: string }): never {
  throw new Error(message);
}

function Ok() {
  return <p>healthy</p>;
}

describe("<ErrorBoundary>", () => {
  it("renders children when they don't throw", () => {
    render(
      <ErrorBoundary>
        <Ok />
      </ErrorBoundary>,
    );
    expect(screen.getByText("healthy")).toBeInTheDocument();
  });

  it("renders fallback with error details when a child throws", () => {
    render(
      <ErrorBoundary label="Test View">
        <Boom message="oh no" />
      </ErrorBoundary>,
    );
    expect(screen.getByText(/Something broke/i)).toBeInTheDocument();
    expect(screen.getByText(/Test View/i)).toBeInTheDocument();
    expect(screen.getByText(/oh no/)).toBeInTheDocument();
  });

  it("Retry clears the error so the next render can recover", async () => {
    // useReducer trick: the child decides whether to throw based on a ref
    // we flip between renders via a state-based wrapper.
    let shouldThrow = true;
    function Toggle(): JSX.Element {
      if (shouldThrow) throw new Error("boom");
      return <p>recovered</p>;
    }
    const { rerender } = render(
      <ErrorBoundary>
        <Toggle />
      </ErrorBoundary>,
    );
    expect(screen.getByText(/Something broke/i)).toBeInTheDocument();

    shouldThrow = false;
    await userEvent.click(screen.getByRole("button", { name: /retry/i }));
    // After retry, ErrorBoundary clears its state and re-renders children; but the
    // children tree is the same instance — we have to force a new render.
    rerender(
      <ErrorBoundary>
        <Toggle />
      </ErrorBoundary>,
    );
    expect(screen.getByText("recovered")).toBeInTheDocument();
  });
});
