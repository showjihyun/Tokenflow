import { render } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { renderMarkdown } from "./markdown";

describe("renderMarkdown — safety", () => {
  it("escapes a raw HTML injection as text, never as DOM", () => {
    const { container } = render(<>{renderMarkdown("<img src=x onerror=alert(1)>")}</>);
    // Literal text stays literal — no real <img> element gets created.
    expect(container.querySelector("img")).toBeNull();
    expect(container.textContent).toContain("<img src=x onerror=alert(1)>");
  });

  it("never emits script tags for script-like markdown input", () => {
    const { container } = render(
      <>{renderMarkdown("run `<script>alert(1)</script>` to pwn")}</>,
    );
    expect(container.querySelector("script")).toBeNull();
    // Inline code wraps the raw text so it's safe but visible.
    const code = container.querySelector("code.md-inline-code");
    expect(code?.textContent).toBe("<script>alert(1)</script>");
  });
});

describe("renderMarkdown — formatting", () => {
  it("renders **bold** as <strong>", () => {
    const { container } = render(<>{renderMarkdown("hello **world**")}</>);
    expect(container.querySelector("strong")?.textContent).toBe("world");
  });

  it("renders *italic* as <em>", () => {
    const { container } = render(<>{renderMarkdown("*emphasis*")}</>);
    expect(container.querySelector("em")?.textContent).toBe("emphasis");
  });

  it("renders inline `code`", () => {
    const { container } = render(<>{renderMarkdown("use `grep`")}</>);
    const code = container.querySelector("code.md-inline-code");
    expect(code?.textContent).toBe("grep");
  });

  it("renders a fenced code block", () => {
    const md = "```\npython -m pip install\n```";
    const { container } = render(<>{renderMarkdown(md)}</>);
    const pre = container.querySelector("pre.md-code-block code");
    expect(pre?.textContent?.trim()).toBe("python -m pip install");
  });

  it("renders bullet lists", () => {
    const md = "- first\n- second";
    const { container } = render(<>{renderMarkdown(md)}</>);
    const items = container.querySelectorAll("ul.md-list li");
    expect(items).toHaveLength(2);
    expect(items[0]?.textContent).toBe("first");
    expect(items[1]?.textContent).toBe("second");
  });

  it("renders numbered lists", () => {
    const md = "1. alpha\n2. beta";
    const { container } = render(<>{renderMarkdown(md)}</>);
    const items = container.querySelectorAll("ol.md-list li");
    expect(items).toHaveLength(2);
    expect(items[0]?.textContent).toBe("alpha");
  });
});
