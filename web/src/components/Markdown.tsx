import { useMemo } from "react";
import { renderMarkdown } from "../lib/markdown";

// Renders notes.md / flashcards.md as readable prose rather than a raw <pre>
// dump. The HTML is sanitised in lib/markdown.ts before it gets here — see the
// note there on why this input is untrusted despite being our own output.
//
// The .md rules live in index.css, not here. They used to be a `markdownStyles`
// template string exported from this file, which was imported nowhere and
// injected into no <style> tag, so every generated note rendered with browser
// default typography. Putting them back as a string would also have hard-coded
// light hex into the reading sheet, which is the one place that has to
// re-theme. On custom properties they follow whatever ground they land on.
export default function Markdown({ source }: { source: string }) {
  const html = useMemo(() => renderMarkdown(source), [source]);
  return <div className="md" dangerouslySetInnerHTML={{ __html: html }} />;
}
