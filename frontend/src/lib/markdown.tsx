import type { ReactElement } from "react";

/**
 * Minimal, safe markdown renderer for LLM responses.
 * Supports: fenced code blocks, inline code, bold (**x**), italics (*x*),
 * bullet lists, numbered lists, paragraph breaks.
 * Escapes all literal text; never uses dangerouslySetInnerHTML.
 */
export function renderMarkdown(text: string): ReactElement {
  const parts = splitFences(text);
  return (
    <>
      {parts.map((p, i) =>
        p.kind === "code" ? (
          <pre key={i} className="md-code-block">
            <code>{p.text}</code>
          </pre>
        ) : (
          <Paragraphs key={i} text={p.text} />
        ),
      )}
    </>
  );
}

type Part = { kind: "text" | "code"; text: string };

function splitFences(s: string): Part[] {
  const parts: Part[] = [];
  const re = /```[^\n]*\n([\s\S]*?)```/g;
  let last = 0;
  let m: RegExpExecArray | null;
  while ((m = re.exec(s)) !== null) {
    if (m.index > last) parts.push({ kind: "text", text: s.slice(last, m.index) });
    parts.push({ kind: "code", text: m[1] ?? "" });
    last = re.lastIndex;
  }
  if (last < s.length) parts.push({ kind: "text", text: s.slice(last) });
  if (parts.length === 0) parts.push({ kind: "text", text: s });
  return parts;
}

function Paragraphs({ text }: { text: string }): ReactElement {
  const lines = text.split(/\n/);
  const blocks: { kind: "p" | "ul" | "ol"; items: string[] }[] = [];
  for (const raw of lines) {
    const line = raw;
    const trimmed = line.trim();
    if (!trimmed) {
      blocks.push({ kind: "p", items: [] });
      continue;
    }
    const bulletMatch = /^[-*]\s+(.+)$/.exec(trimmed);
    const numMatch = /^\d+\.\s+(.+)$/.exec(trimmed);
    if (bulletMatch) {
      const last = blocks[blocks.length - 1];
      if (last && last.kind === "ul") last.items.push(bulletMatch[1]!);
      else blocks.push({ kind: "ul", items: [bulletMatch[1]!] });
    } else if (numMatch) {
      const last = blocks[blocks.length - 1];
      if (last && last.kind === "ol") last.items.push(numMatch[1]!);
      else blocks.push({ kind: "ol", items: [numMatch[1]!] });
    } else {
      const last = blocks[blocks.length - 1];
      if (last && last.kind === "p") last.items.push(line);
      else blocks.push({ kind: "p", items: [line] });
    }
  }

  return (
    <>
      {blocks.map((b, i) => {
        if (b.kind === "ul") {
          return (
            <ul key={i} className="md-list">
              {b.items.map((item, j) => (
                <li key={j}>{renderInline(item)}</li>
              ))}
            </ul>
          );
        }
        if (b.kind === "ol") {
          return (
            <ol key={i} className="md-list">
              {b.items.map((item, j) => (
                <li key={j}>{renderInline(item)}</li>
              ))}
            </ol>
          );
        }
        if (b.items.length === 0) return null;
        return (
          <p key={i} className="md-p">
            {b.items.map((line, j) => (
              <span key={j}>
                {renderInline(line)}
                {j < b.items.length - 1 ? <br /> : null}
              </span>
            ))}
          </p>
        );
      })}
    </>
  );
}

// Inline: **bold**, *italic*, `code`. Nothing else — strict whitelist.
function renderInline(text: string): ReactElement[] {
  const tokens: ReactElement[] = [];
  const re = /(`[^`]+`|\*\*[^*]+\*\*|\*[^*]+\*)/g;
  let last = 0;
  let m: RegExpExecArray | null;
  let key = 0;
  while ((m = re.exec(text)) !== null) {
    if (m.index > last) tokens.push(<span key={key++}>{text.slice(last, m.index)}</span>);
    const tok = m[0];
    if (tok.startsWith("**")) {
      tokens.push(<strong key={key++}>{tok.slice(2, -2)}</strong>);
    } else if (tok.startsWith("*")) {
      tokens.push(<em key={key++}>{tok.slice(1, -1)}</em>);
    } else {
      tokens.push(
        <code key={key++} className="md-inline-code">
          {tok.slice(1, -1)}
        </code>,
      );
    }
    last = re.lastIndex;
  }
  if (last < text.length) tokens.push(<span key={key++}>{text.slice(last)}</span>);
  return tokens;
}
