export interface Card {
  q: string;
  a: string;
}

/** Split flashcards.md into question/answer pairs.
 *
 *  The agent writes `## <question> #flashcard`, a blank line, the answer, then
 *  a `---` rule. Anything that does not match that shape is skipped rather than
 *  rendered as a broken card, so a malformed block costs one card and not the
 *  whole tab.
 *
 *  Lives in its own module rather than beside the component so it can be tested
 *  without mounting React.
 */
export function parseFlashcards(md: string): Card[] {
  return md
    .split(/^\s*---\s*$/m)
    .map((block) => {
      const lines = block.trim().split("\n");
      const head = lines.findIndex((l) => l.trimStart().startsWith("##"));
      if (head === -1) return null;
      const q = lines[head]
        .replace(/^\s*#+\s*/, "")
        .replace(/#flashcard\s*$/i, "")
        .trim();
      const a = lines
        .slice(head + 1)
        .join("\n")
        .trim();
      if (!q || !a) return null;
      return { q, a };
    })
    .filter((x): x is Card => x !== null);
}
