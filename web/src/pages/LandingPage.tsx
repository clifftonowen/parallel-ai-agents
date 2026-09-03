import { Link } from "react-router-dom";
import { CONTACT_EMAIL, DEMO, DEMO_RUN_ID, REPO_URL } from "../api/demo";
import {
  c, display, displaySmall, eyebrow, font, hairline, headingWeight, layout,
  muted, mutedFaint, size, space,
} from "../theme";

/**
 * The front door.
 *
 * It used to lead with a benchmark figure, which was aimed at the wrong reader
 * even while that figure looked good: somebody who wants study material does
 * not care which executor produced it. Worse, the figure did not survive being
 * measured properly. So this page is about what the thing makes, and the
 * research it came out of has its own page, where the numbers are reported
 * including the ones that went the wrong way.
 */
export default function LandingPage() {
  return (
    <main style={page}>
      {/* ── What it makes ────────────────────────────────────────────────── */}
      <header style={masthead}>
        <span style={eyebrow}>
          SUTD undergraduate research · supervised by Prof Oka Kurniawan
        </span>
        <h1 style={heading}>One topic in. A full study set out.</h1>
        <p style={standfirst}>
          Give it something you need to learn. Four agents go and build the
          material: structured notes, flashcards you can revise from, a narrated
          video, and PDFs to print. They work at the same time, so the set
          arrives together rather than one piece at a time.
        </p>

        <div style={ctaRow}>
          {DEMO ? (
            <Link to={`/session/${DEMO_RUN_ID}`} className="btn btn-primary" style={btn}>
              See one it made
            </Link>
          ) : (
            <Link to="/new" className="btn btn-primary" style={btn}>
              Make one
            </Link>
          )}
          <Link to="/benchmark" className="btn btn-secondary" style={btn}>
            The measurements
          </Link>
        </div>
      </header>

      {/* ── The four outputs ─────────────────────────────────────────────── */}
      <section style={section} aria-labelledby="outputs">
        <span style={eyebrow}>What arrives</span>
        <h2 id="outputs" style={sectionHeading}>Four things, from one prompt</h2>

        <div style={cardRow}>
          {OUTPUTS.map((o) => (
            <article key={o.name} className="card elev-sm" style={card}>
              <div className="card-kicker">{o.file}</div>
              <div className="card-title">{o.name}</div>
              <p className="card-body">{o.what}</p>
            </article>
          ))}
        </div>

        <p style={note}>
          The notes carry images the pipeline finds for itself. The video is real
          narration over slides written for the topic, not a slideshow with
          subtitles.
        </p>
      </section>

      {/* ── How it works ─────────────────────────────────────────────────── */}
      <section style={section} aria-labelledby="pipeline">
        <span style={eyebrow}>How it works</span>
        <h2 id="pipeline" style={sectionHeading}>Notes first, then everything at once</h2>
        <p style={prose}>
          Everything else needs the notes, so those come first. After that the
          remaining agents have nothing left to wait for and run together.
        </p>

        <div style={diagram} role="img" aria-label={DIAGRAM_ALT}>
          <div>
            <span style={stageLabel}>First, on its own</span>
            <div style={{ ...node, ...nodeLead }}>Notes</div>
          </div>

          <div style={arrow} aria-hidden="true">↓</div>

          <div>
            <span style={stageLabel}>Then, together</span>
            <div style={fanOut}>
              {["Flashcards", "Video", "Notes PDF"].map((n) => (
                <div key={n} style={node}>{n}</div>
              ))}
            </div>
          </div>

          <div style={arrow} aria-hidden="true">↓</div>

          <div>
            <span style={stageLabel}>Last, once flashcards exist</span>
            <div style={node}>Flashcards PDF</div>
          </div>
        </div>
      </section>

      {/* ── The research ─────────────────────────────────────────────────── */}
      <section style={section} aria-labelledby="research">
        <span style={eyebrow}>Why it exists</span>
        <h2 id="research" style={sectionHeading}>It was built to measure something</h2>
        <p style={prose}>
          The question was whether running those agents in parallel actually
          helps, and if so which concurrency model to use. The app is the
          workload the question gets asked of.
        </p>
        <p style={prose}>
          The answer turned out better than the one expected. Choosing between
          concurrency models made no measurable difference at this scale. Almost
          all of the time was going somewhere nobody had looked, and fixing that
          was worth about seventeen times, mostly for a reason that has nothing
          to do with parallelism at all.
        </p>
        <Link to="/benchmark" className="btn btn-secondary" style={btn}>
          Read what was measured
        </Link>
      </section>

      {/* ── What this build can do ───────────────────────────────────────── */}
      <section style={{ ...section, borderBottom: "none" }} aria-labelledby="live">
        <span style={eyebrow}>{DEMO ? "About this build" : "Before you start one"}</span>
        <h2 id="live" style={sectionHeading}>
          {DEMO ? "There is no backend behind this" : "Runs are granted by hand"}
        </h2>
        <p style={prose}>
          {DEMO ? (
            <>
              This site is static files. A run takes ten to thirty minutes and
              needs ffmpeg, pandoc and a headless browser, none of which a static
              host can give it. The session and the numbers here came out of runs
              on my own machine and are built into the page.
            </>
          ) : (
            <>
              Every run calls the Anthropic and OpenAI APIs, and those calls come
              off my own credits. So an account by itself does not let you start
              one. Sign up and ask, and I will turn it on for you.
            </>
          )}
        </p>
        <p style={prose}>
          Want to see it generate something live?{" "}
          {CONTACT_EMAIL ? (
            <a href={`mailto:${CONTACT_EMAIL}`} style={link}>Get in touch</a>
          ) : (
            <a href={REPO_URL} target="_blank" rel="noreferrer" style={link}>
              Say so on the repository
            </a>
          )}{" "}
          and I'll set it up.
        </p>
      </section>
    </main>
  );
}

const OUTPUTS = [
  {
    name: "Notes",
    file: "notes.md",
    what: "The topic broken into sections, with the key ideas, worked examples and diagrams found along the way.",
  },
  {
    name: "Flashcards",
    file: "flashcards.md",
    what: "Question and answer pairs drawn from the notes, in a format Anki and Obsidian both read.",
  },
  {
    name: "Video",
    file: "study_video.mp4",
    what: "Slides written for the topic, narrated end to end, for when reading is not what you want.",
  },
  {
    name: "PDFs",
    file: "notes.pdf",
    what: "Both the notes and the flashcards typeset for printing, via pandoc.",
  },
];

const DIAGRAM_ALT =
  "Notes are generated first. Flashcards, the video and the notes PDF then run " +
  "together. The flashcards PDF follows once the flashcards exist.";

// ── styles ──────────────────────────────────────────────────────────────────

const page: React.CSSProperties = { maxWidth: layout.shell };

const masthead: React.CSSProperties = {
  paddingBottom: space.section,
  borderBottom: `2px solid ${c.ink}`,
};

const heading: React.CSSProperties = {
  fontFamily: font.display,
  fontWeight: headingWeight,
  fontSize: display,
  lineHeight: 1.04,
  letterSpacing: "-0.015em",
  margin: `${space.sm}px 0 ${space.base}px`,
  maxWidth: "16ch",
};

const standfirst: React.CSSProperties = {
  fontSize: size.lead,
  lineHeight: 1.55,
  color: c.ink,
  maxWidth: layout.measure,
  margin: 0,
};

const ctaRow: React.CSSProperties = {
  display: "flex",
  flexWrap: "wrap",
  gap: space.md,
  marginTop: space.xl,
};

const btn: React.CSSProperties = { textDecoration: "none" };

const section: React.CSSProperties = {
  paddingTop: space.section,
  paddingBottom: space.section,
  borderBottom: hairline,
};

const sectionHeading: React.CSSProperties = {
  fontFamily: font.display,
  fontWeight: headingWeight,
  fontSize: displaySmall,
  lineHeight: 1.15,
  margin: `${space.xs}px 0 ${space.base}px`,
  maxWidth: "24ch",
};

const prose: React.CSSProperties = {
  fontSize: size.body,
  lineHeight: 1.6,
  color: muted,
  maxWidth: layout.measure,
  margin: `0 0 ${space.md}px`,
};

const note: React.CSSProperties = {
  fontSize: size.small,
  fontStyle: "italic",
  color: mutedFaint,
  maxWidth: layout.measure,
  marginTop: space.base,
};

const cardRow: React.CSSProperties = {
  display: "grid",
  gridTemplateColumns: "repeat(auto-fit, minmax(210px, 1fr))",
  gap: space.base,
  marginTop: space.base,
};

const card: React.CSSProperties = {
  display: "flex",
  flexDirection: "column",
  gap: space.sm,
};

const diagram: React.CSSProperties = {
  marginTop: space.base,
  padding: space.base,
  border: hairline,
  background: c.paperCard,
  maxWidth: 620,
};

const stageLabel: React.CSSProperties = {
  ...eyebrow,
  display: "block",
  marginBottom: space.xs,
};

const node: React.CSSProperties = {
  border: `1px solid ${c.ink}`,
  background: c.paper,
  padding: `${space.sm}px ${space.md}px`,
  fontSize: size.small,
  fontWeight: headingWeight,
  textAlign: "center",
};

const nodeLead: React.CSSProperties = {
  borderColor: c.reagent,
  color: c.reagentDeep,
};

const fanOut: React.CSSProperties = {
  display: "grid",
  gridTemplateColumns: "repeat(auto-fit, minmax(120px, 1fr))",
  gap: space.sm,
};

const arrow: React.CSSProperties = {
  textAlign: "center",
  color: c.inkFaint,
  padding: `${space.sm}px 0`,
  fontSize: size.body,
};

const link: React.CSSProperties = {
  color: c.reagentDeep,
  textDecorationThickness: "1px",
  textUnderlineOffset: "2px",
};
