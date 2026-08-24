import { marked } from "marked";
import DOMPurify from "dompurify";

marked.setOptions({ gfm: true, breaks: false });

/** Markdown to sanitised HTML.
 *
 *  This markdown is NOT trusted, despite being "our own" output. The notes
 *  agent has web_search and image_search tools (src/agents/base_agent.py), so
 *  text from arbitrary third-party pages reaches the model and can reach its
 *  output. marked passes raw HTML straight through — its `sanitize` option was
 *  removed in v5 — and the result goes into dangerouslySetInnerHTML, so a
 *  scraped page carrying `<img onerror=...>` would be an indirect-injection
 *  route to stored XSS against whoever opens those notes.
 *
 *  Sanitising at the render boundary rather than at generation time is
 *  deliberate: this is the one place the HTML is actually injected, so no later
 *  caller can bypass it.
 */
export function renderMarkdown(source: string): string {
  return DOMPurify.sanitize(marked.parse(source) as string, {
    USE_PROFILES: { html: true },
    // Markdown never needs these, and they are the usual pivots.
    FORBID_TAGS: ["style", "form", "input", "button", "iframe", "object", "embed"],
    FORBID_ATTR: ["style", "srcset", "formaction"],
  });
}
