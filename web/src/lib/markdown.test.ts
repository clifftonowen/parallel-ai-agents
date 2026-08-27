import { describe, expect, it } from "vitest";
import { renderMarkdown } from "./markdown";

/**
 * These are security tests, not formatting tests.
 *
 * The markdown reaching this function is NOT trusted: the notes agent has
 * web_search and image_search tools, so text from arbitrary third-party pages
 * reaches the model and can reach its output. The result goes into
 * dangerouslySetInnerHTML, so anything that survives sanitising executes in the
 * reader's session.
 */
describe("renderMarkdown: sanitising", () => {
  it("strips script tags", () => {
    const html = renderMarkdown("# Notes\n\n<script>alert(1)</script>");
    expect(html).not.toContain("<script");
    expect(html).toContain("<h1>Notes</h1>");
  });

  it("strips inline event handlers but keeps the element", () => {
    const html = renderMarkdown('<img src=x onerror="alert(1)">');
    expect(html).not.toContain("onerror");
    expect(html).toContain("<img");
  });

  it("strips svg onload", () => {
    expect(renderMarkdown('<svg onload="alert(1)"></svg>')).not.toContain("onload");
  });

  it("strips javascript: hrefs but keeps the link text", () => {
    const html = renderMarkdown("[click me](javascript:alert(1))");
    expect(html).not.toContain("javascript:");
    expect(html).toContain("click me");
  });

  it.each([
    ["iframe", '<iframe src="https://evil.example"></iframe>'],
    ["object", '<object data="evil.swf"></object>'],
    ["embed", '<embed src="evil.swf">'],
    ["form", '<form action="https://evil.example"><input name="x"></form>'],
    ["style", "<style>body{display:none}</style>"],
  ])("removes %s", (_name, source) => {
    const html = renderMarkdown(source);
    expect(html).not.toMatch(/<(iframe|object|embed|form|input|style)/);
  });

  it("strips style attributes, which can hide or reposition content", () => {
    const html = renderMarkdown('<p style="position:fixed;inset:0">covering</p>');
    expect(html).not.toContain("style=");
  });

  it("survives a payload split across markdown constructs", () => {
    const html = renderMarkdown("**bold**<script>alert(1)</script>*em*");
    expect(html).not.toContain("<script");
    expect(html).toContain("<strong>bold</strong>");
  });

  it("does not execute anything when the output is inserted into a document", () => {
    // The real failure mode: not "does the string contain <script>" but "does
    // anything run once this is in the DOM".
    (window as unknown as { __pwned?: number }).__pwned = undefined;
    const host = document.createElement("div");
    host.innerHTML = renderMarkdown(
      '<img src=x onerror="window.__pwned=1"><script>window.__pwned=2</script>'
    );
    document.body.appendChild(host);
    expect((window as unknown as { __pwned?: number }).__pwned).toBeUndefined();
    host.remove();
  });
});

describe("renderMarkdown: legitimate content survives", () => {
  it("renders headings, emphasis, code and lists", () => {
    const html = renderMarkdown("# Title\n\n**bold** and `code`\n\n- one\n- two");
    expect(html).toContain("<h1>Title</h1>");
    expect(html).toContain("<strong>bold</strong>");
    expect(html).toContain("<code>code</code>");
    expect(html).toContain("<li>one</li>");
  });

  it("keeps ordinary links with their href intact", () => {
    const html = renderMarkdown("[example](https://example.com)");
    expect(html).toContain('href="https://example.com"');
  });

  it("keeps images, which the notes rely on for diagrams", () => {
    const html = renderMarkdown("![diagram](https://example.com/d.png)");
    expect(html).toContain("<img");
    expect(html).toContain("https://example.com/d.png");
  });

  it("keeps data: image URIs, which is how embedded diagrams arrive", () => {
    const html = renderMarkdown("![d](data:image/png;base64,iVBORw0KGgo=)");
    expect(html).toContain("data:image/png");
  });

  it("keeps tables, which gfm mode enables", () => {
    const html = renderMarkdown("| a | b |\n|---|---|\n| 1 | 2 |");
    expect(html).toContain("<table>");
  });

  it("handles empty input without throwing", () => {
    expect(renderMarkdown("")).toBe("");
  });
});
