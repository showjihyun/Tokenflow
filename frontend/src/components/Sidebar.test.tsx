import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";
import { Sidebar } from "./Sidebar";

function renderAt(path: string) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <Sidebar />
    </MemoryRouter>,
  );
}

describe("<Sidebar>", () => {
  it("renders NavLinks pointing at the canonical routes", () => {
    renderAt("/live");
    const cases: [string, string][] = [
      ["Live Monitor", "/live"],
      ["Analytics", "/analytics"],
      ["Waste Radar", "/waste"],
      ["AI Coach", "/coach"],
      ["Session Replay", "/replay"],
      ["Settings", "/settings"],
    ];
    for (const [label, href] of cases) {
      const link = screen.getByRole("link", { name: new RegExp(label, "i") });
      expect(link.getAttribute("href")).toBe(href);
    }
  });

  it("marks the current route with the 'active' class and aria-current", () => {
    renderAt("/analytics");
    const active = screen.getByRole("link", { name: /analytics/i });
    expect(active.className).toMatch(/\bactive\b/);
    expect(active.getAttribute("aria-current")).toBe("page");
  });

  it("does not mark inactive links as current", () => {
    renderAt("/analytics");
    const inactive = screen.getByRole("link", { name: /live monitor/i });
    expect(inactive.className).not.toMatch(/\bactive\b/);
    expect(inactive.getAttribute("aria-current")).not.toBe("page");
  });

  it("renders the Docs link as an external anchor (not a router link)", () => {
    renderAt("/live");
    const docs = screen.getByRole("link", { name: /documentation/i });
    expect(docs.getAttribute("href")).toMatch(/^https?:\/\//);
    expect(docs.getAttribute("target")).toBe("_blank");
  });
});
