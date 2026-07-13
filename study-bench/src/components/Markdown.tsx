import { useMemo } from "react";
import { marked } from "marked";
import { c, font } from "../theme";

// Renders notes.md / flashcards.md as readable prose rather than a raw <pre> dump.
// marked handles the parsing; the styling below is scoped via a wrapper class so it
// reads like a page from the worksheet, not a generic markdown blob.

marked.setOptions({ gfm: true, breaks: false });

export default function Markdown({ source }: { source: string }) {
  const html = useMemo(() => marked.parse(source) as string, [source]);
  return (
    <div className="md" style={wrap} dangerouslySetInnerHTML={{ __html: html }} />
  );
}

const wrap: React.CSSProperties = {
  fontFamily: font.body,
  fontSize: 15,
  lineHeight: 1.72,
  color: c.ink,
};

// One scoped style block for the rendered markup. Kept here so Markdown owns its look.
export const markdownStyles = `
  .md h1, .md h2, .md h3 { font-family: ${font.display}; font-weight: 600; line-height: 1.15; color: ${c.ink}; }
  .md h1 { font-size: 30px; margin: 0 0 12px; }
  .md h2 { font-size: 22px; margin: 26px 0 8px; padding-bottom: 6px; border-bottom: 1px solid ${c.ruleSoft}; }
  .md h3 { font-size: 17px; margin: 20px 0 6px; }
  .md p { margin: 0 0 12px; }
  .md ul, .md ol { margin: 0 0 12px; padding-left: 22px; }
  .md li { margin: 3px 0; }
  .md strong { font-weight: 700; color: ${c.ink}; }
  .md em { color: ${c.inkSoft}; }
  .md a { color: ${c.reagent}; text-decoration: underline; text-underline-offset: 2px; }
  .md code { font-family: ${font.mono}; font-size: 13px; background: ${c.paperDeep}; padding: 1px 5px; }
  .md pre { font-family: ${font.mono}; font-size: 13px; background: ${c.paperDeep}; padding: 12px; overflow-x: auto; margin: 0 0 12px; }
  .md pre code { background: none; padding: 0; }
  .md img { max-width: 100%; height: auto; border: 1px solid ${c.rule}; margin: 6px 0; display: block; }
  .md blockquote { margin: 0 0 12px; padding-left: 14px; border-left: 3px solid ${c.reagent}; color: ${c.inkSoft}; }
  .md hr { border: none; border-top: 1px solid ${c.rule}; margin: 22px 0; }
`;
