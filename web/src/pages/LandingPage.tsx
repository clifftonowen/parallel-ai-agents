import { Link } from "react-router-dom";
import HeroPreview from "../components/HeroPreview";
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
        <h1 style={heading}>See how one topic becomes a study set.</h1>
        <p style={standfirst}>
          This research project turns a topic into notes, flashcards, a narrated
          video and printable PDFs. It writes the notes first, then uses them to
          make the rest. Explore a finished set below.
        </p>

        <div style={ctaRow}>
          {DEMO ? (
            <Link to={`/session/${DEMO_RUN_ID}`} className="btn btn-primary" style={btn}>
              Explore the sample set
            </Link>
          ) : (
            <Link to="/new" className="btn btn-primary" style={btn}>
              Start a study session
            </Link>
          )}
          <Link to="/benchmark" className="btn btn-secondary" style={btn}>
            See what the tests found
          </Link>
        </div>

        {/* The product is its own photography. This is the real notes.md from
            the bundled session, rendered by the same components the session
            viewer uses, so it cannot go stale the way a screenshot would. */}
        <div style={heroFrame}>
          <HeroPreview />
        </div>
      </header>

      {/* ── The four outputs ─────────────────────────────────────────────── */}
      <section style={section} aria-labelledby="outputs">
        <span style={eyebrow}>Study materials</span>
        <h2 id="outputs" style={sectionHeading}>What you get from a topic</h2>

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
          The notes include images found during research. The video pairs
          slides written for the topic with narration, rather than relying on
          subtitles.
        </p>
      </section>

      {/* ── How it works ─────────────────────────────────────────────────── */}
      <section style={section} aria-labelledby="pipeline">
        <span style={eyebrow}>How it works</span>
        <h2 id="pipeline" style={sectionHeading}>How the set comes together</h2>
        <p style={prose}>
          The notes give the other agents something to work from. Flashcards,
          the video and a printable notes PDF come next. The flashcards PDF
          follows once the cards are ready.
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
        <span style={eyebrow}>The research</span>
        <h2 id="research" style={sectionHeading}>What the experiments found</h2>
        <p style={prose}>
          I built this study tool to test whether running agents in parallel
          speeds up the work, and whether the way they are coordinated matters.
        </p>
        <p style={prose}>
          In repeated tests, the coordination method made no measurable
          difference at this scale. Video assembly took most of the time.
          Changing that step made it about 17 times faster, with most of the
          gain coming before any parallel work was added.
        </p>
        <Link to="/benchmark" className="btn btn-secondary" style={btn}>
          Read the results
        </Link>
      </section>

      {/* ── What this build can do ───────────────────────────────────────── */}
      <section style={{ ...section, borderBottom: "none" }} aria-labelledby="live">
        <span style={eyebrow}>{DEMO ? "About this demo" : "Before you start"}</span>
        <h2 id="live" style={sectionHeading}>
          {DEMO ? "Explore a finished session" : "Starting a run requires access"}
        </h2>
        <p style={prose}>
          {DEMO ? (
            <>
              This static demo includes a real finished session and benchmark
              results from runs on my machine. A new run takes 10 to 30 minutes
              and needs ffmpeg, pandoc and a headless browser, so it needs a
              separate study server.
            </>
          ) : (
            <>
              Each run uses my Anthropic and OpenAI API credits. You can create
              an account to save your sessions, then ask me for permission to
              generate new ones.
            </>
          )}
        </p>
        <p style={prose}>
          Want to see a new topic generated?{" "}
          {CONTACT_EMAIL ? (
            <a href={`mailto:${CONTACT_EMAIL}`} style={link}>Email me</a>
          ) : (
            <a href={REPO_URL} target="_blank" rel="noreferrer" style={link}>
              Visit the repository
            </a>
          )}{" "}
          to ask about a live demonstration.
        </p>
      </section>
    </main>
  );
}

const OUTPUTS = [
  {
    name: "Notes",
    file: "notes.md",
    what: "A clear explanation of the topic, with key ideas, worked examples and diagrams.",
  },
  {
    name: "Flashcards",
    file: "flashcards.md",
    what: "Questions and answers drawn from the notes, in a format Anki and Obsidian both read.",
  },
  {
    name: "Video",
    file: "study_video.mp4",
    what: "Topic-specific slides with narration, for when you would rather watch than read.",
  },
  {
    name: "PDFs",
    file: "notes.pdf",
    what: "Printable versions of the notes and flashcards, made with pandoc.",
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

const heroFrame: React.CSSProperties = {
  marginTop: space.section,
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
