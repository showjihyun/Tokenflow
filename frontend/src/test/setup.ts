import "@testing-library/jest-dom/vitest";
import { afterEach, beforeAll, afterAll, vi } from "vitest";
import { cleanup } from "@testing-library/react";

const originalConsoleError = console.error;

beforeAll(() => {
  vi.spyOn(console, "error").mockImplementation((...args: unknown[]) => {
    const text = args.map(String).join(" ");
    if (text.includes("oh no") || text.includes("boom")) return;
    originalConsoleError(...args);
  });
  window.addEventListener("error", (event) => {
    if (event.message.includes("oh no") || event.message.includes("boom")) {
      event.preventDefault();
    }
  });
});

afterAll(() => {
  vi.restoreAllMocks();
});

// Unmount anything the previous test rendered.
afterEach(() => {
  cleanup();
});
