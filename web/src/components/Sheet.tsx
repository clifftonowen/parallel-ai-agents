import { radius, space } from "../theme";

/** A light reading surface inside the dark app.
 *
 *  The app is dark; the material it generates is not. Notes arrive carrying
 *  images the pipeline hotlinked from the open web, which have white grounds
 *  and would punch holes in a dark page, and the PDFs beside them are white
 *  pages by definition. So generated material is shown on paper, framed like a
 *  document on a desk.
 *
 *  Deliberately NOT used for flashcards or the video. Flashcards are an
 *  interactive control surface, and a light interactive panel in a dark app is
 *  the single most likely thing to read as a mode bug rather than a design
 *  choice. The rule is: this wraps things you read, not things you operate.
 *
 *  The frame is a separate element from the sheet on purpose. `.sheet`
 *  re-declares the palette on itself, so its own border would go light too,
 *  and the document-on-a-desk read would collapse into an unframed white slab.
 */
export default function Sheet({ children }: { children: React.ReactNode }) {
  return (
    <div style={frame}>
      <div className="sheet" style={paper}>
        {children}
      </div>
    </div>
  );
}

const frame: React.CSSProperties = {
  border: "1px solid var(--color-divider)",
  borderRadius: radius.lg,
  background: "var(--color-bg-deep)",
  padding: space.xs,
  overflow: "hidden",
};

const paper: React.CSSProperties = {
  borderRadius: radius.md,
  // Generous margin, because the point is that it reads as a sheet of paper
  // rather than as a white box someone forgot to restyle.
  padding: `${space.xl}px ${space.section}px`,
};
