import { describe, expect, it } from "vitest";
import { parseFlashcards } from "./flashcards";

/**
 * The flashcard agent writes `## <question> #flashcard`, a blank line, the
 * answer, then a `---` rule. This parser turns that into the flip cards on the
 * session page. A malformed block should cost one card, never the whole tab.
 */

const REAL = `## What is the attention mechanism? #flashcard

It lets a model weigh every token when producing each output token.

---

## What are queries, keys and values? #flashcard

Three learned projections of each token embedding.
`;

describe("parseFlashcards", () => {
  it("parses the real agent output format", () => {
    const cards = parseFlashcards(REAL);
    expect(cards).toHaveLength(2);
    expect(cards[0].q).toBe("What is the attention mechanism?");
    expect(cards[0].a).toBe("It lets a model weigh every token when producing each output token.");
    expect(cards[1].q).toBe("What are queries, keys and values?");
  });

  it("strips the #flashcard marker from the question", () => {
    const [card] = parseFlashcards("## Q here #flashcard\n\nA here");
    expect(card.q).toBe("Q here");
    expect(card.q).not.toContain("#flashcard");
  });

  it("is case-insensitive about the marker", () => {
    const [card] = parseFlashcards("## Q here #FlashCard\n\nA here");
    expect(card.q).toBe("Q here");
  });

  it("works without the marker at all", () => {
    const [card] = parseFlashcards("## Q here\n\nA here");
    expect(card.q).toBe("Q here");
  });

  it("keeps a multi-paragraph answer whole", () => {
    const [card] = parseFlashcards("## Q\n\nFirst para.\n\nSecond para.");
    expect(card.a).toBe("First para.\n\nSecond para.");
  });

  it("handles any heading level", () => {
    expect(parseFlashcards("### Q\n\nA")[0].q).toBe("Q");
  });

  it("tolerates leading whitespace before the heading", () => {
    expect(parseFlashcards("   ## Q\n\nA")[0].q).toBe("Q");
  });

  describe("malformed input costs one card, not the tab", () => {
    it("returns nothing for empty input", () => {
      expect(parseFlashcards("")).toEqual([]);
    });

    it("skips a block with no heading", () => {
      expect(parseFlashcards("just prose with no heading")).toEqual([]);
    });

    it("skips a heading with no answer", () => {
      expect(parseFlashcards("## Q with nothing after it")).toEqual([]);
    });

    it("skips an empty heading", () => {
      expect(parseFlashcards("## \n\nAn answer")).toEqual([]);
    });

    it("keeps the good cards and drops only the bad one", () => {
      const md = "## Good\n\nAnswer\n\n---\n\nno heading here\n\n---\n\n## Also good\n\nAnswer";
      const cards = parseFlashcards(md);
      expect(cards.map((c) => c.q)).toEqual(["Good", "Also good"]);
    });

    it("ignores trailing separators", () => {
      expect(parseFlashcards("## Q\n\nA\n\n---\n")).toHaveLength(1);
    });

    it("does not treat a --- inside an answer's fenced block as a separator boundary it cannot recover from", () => {
      // A horizontal rule on its own line does split blocks; the point is that
      // the surviving halves are still handled rather than throwing.
      expect(() => parseFlashcards("## Q\n\nA\n---\nmore")).not.toThrow();
    });
  });
});
