import "@testing-library/jest-dom/vitest";
import { afterEach } from "vitest";
import { cleanup } from "@testing-library/react";

// Unmount anything the previous test rendered.
afterEach(() => {
  cleanup();
});
