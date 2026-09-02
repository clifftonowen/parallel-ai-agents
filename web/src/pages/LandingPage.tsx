import { Link } from "react-router-dom";
import PlateNumber from "../components/PlateNumber";
import { CONTACT_EMAIL, DEMO, DEMO_RUN_ID, REPO_URL } from "../api/demo";
import {
  c, display, displaySmall, eyebrow, font, hairline, headingWeight, layout,
  muted, mutedFaint, size, space,
} from "../theme";

/**
 * The front door.
 *
 * `/` used to be the composer, which meant a visitor's first screen was a
 * Generate button they could not press. This says what the project is before
 * offering to spend money on anyone's behalf.
 *
 * It leads with the measurement rather than the product, because the
 * measurement is the point: this is a UROP about where parallelising a
 * heterogeneous pipeline helps, and the study-materials app is the workload it
 * is measured on. It also leads with the result that complicates the headline
 * — Amdahl's law drowning the effect on a full run — since a benchmark page
 * that shows only its best number is advertising, not a finding.
 */
export default function LandingPage() {
  return (
    <main style={page}>
      {/* ── Masthead ─────────────────────────────────────────────────────── */}
      <header style={masthead}>
        <span style={eyebrow}>
          SUTD undergraduate research · supervised by Prof Oka Kurniawan
        </span>
        <h1 style={heading}>
          Three orchestrators, one multi-agent pipeline
        </h1>
        <div className="standfirst" style={standfirst}>
          <p style={{ margin: 0 }}>
            One topic goes in. Four agents turn it into lecture notes,
            flashcards, a narrated video and printable PDFs. All four need the
            notes first, so they start together the moment those are done.
          </p>
          <p style={{ margin: `${space.md}px 0 0` }}>
            Three orchestrators run that same pipeline: a thread pool, pure{" "}
            <code style={code}>asyncio</code>, and a Google ADK agent graph.
            Same work each time, so the framework is the only thing being
            measured.
          </p>
        </div>
      </header>

      {/* ── The finding ──────────────────────────────────────────────────── */}
      <section style={section} aria-labelledby="finding">
        <span style={eyebrow}>The result</span>
        <h2 id="finding" style={sectionHeading}>
          Where asyncio actually wins
        </h2>

        <div style={figureRow}>
          <figure style={figure}>
            <PlateNumber value="1.44×" fontSize={58} />
            <figcaption style={figCaption}>
              faster on <strong style={strong}>phase 2</strong>, the parallel
              fan-out. It is the only phase where the two arms do anything
              differently.
            </figcaption>
          </figure>
          <figure style={figure}>
            <PlateNumber value="1.18×" fontSize={58} />
            <figcaption style={figCaption}>
              faster end to end with video switched off. Phases 1 and 3 are
              sequential in both arms and landed within a few percent of each
              other, so the gain is coming from where it should.
            </figcaption>
          </figure>
        </div>

        <blockquote style={pullQuote}>
          <p style={{ margin: 0 }}>
            On a <em>full</em> run asyncio measured 0.96×, which is no better
            than threads. Concurrency was not the problem. Video assembly is
            single-threaded ffmpeg and takes{" "}
            <strong style={strong}>76 to 81% of wall time</strong>, so
            parallelising the LLM stages could only ever affect the remaining
            fifth. That was too small to see.
          </p>
          <footer style={quoteFooter}>
            That is Amdahl's law. Dropping the video stage is what isolates the
            part this project is actually about.
          </footer>
        </blockquote>

        <p style={caveat}>
          One run per arm, so 1.18× is indicative rather than something I
          would quote with confidence. The rest of the caveats, including the
          fact that the two arms made a different number of LLM calls, are on
          the benchmark page and in the repository.
        </p>
      </section>

      {/* ── The pipeline ─────────────────────────────────────────────────── */}
      <section style={section} aria-labelledby="pipeline">
        <span style={eyebrow}>The workload</span>
        <h2 id="pipeline" style={sectionHeading}>Where the parallelism is</h2>
        <p style={prose}>
          Everything downstream needs the notes, so phase 1 is sequential no
          matter what. Phase 2 is the fan-out, and it is the only place an
          orchestrator has anything to decide.
        </p>

        <div style={diagram} role="img" aria-label={DIAGRAM_ALT}>
          <div style={stage}>
            <span style={stageLabel}>Phase 1 · sequential</span>
            <div style={{ ...node, ...nodeLead }}>Notes</div>
          </div>

          <div style={arrow} aria-hidden="true">↓</div>

          <div style={stage}>
            <span style={stageLabel}>Phase 2 · parallel</span>
            <div style={fanOut}>
              {["Flashcards", "Video", "Notes PDF"].map((n) => (
                <div key={n} style={node}>{n}</div>
              ))}
            </div>
          </div>

          <div style={arrow} aria-hidden="true">↓</div>

          <div style={stage}>
            <span style={stageLabel}>Phase 3 · sequential</span>
            <div style={node}>Flashcards PDF</div>
          </div>
        </div>
      </section>

      {/* ── Ways in ──────────────────────────────────────────────────────── */}
      <section style={section} aria-labelledby="look">
        <span style={eyebrow}>Have a look</span>
        <h2 id="look" style={sectionHeading}>Where to start</h2>

        <div style={cardRow}>
          <article className="card elev-sm" style={card}>
            <div className="card-kicker">Measurement</div>
            <div className="card-title">The benchmark</div>
            <p className="card-body">
              Per-phase wall clock and token counts for each orchestrator, with
              the caveats sitting next to the numbers they apply to.
            </p>
            <Link to="/benchmark" className="btn btn-primary" style={cardBtn}>
              See the numbers
            </Link>
          </article>

          <article className="card elev-sm" style={card}>
            <div className="card-kicker">Output</div>
            <div className="card-title">A finished session</div>
            <p className="card-body">
              Notes, flashcards, a narrated video and PDFs from one run on
              binary search. Nothing has been tidied up afterwards.
            </p>
            {/* Without the demo fixture there is no one session to open, so
                this goes to the list. `/session/` with an empty id is a route
                that renders nothing. */}
            <Link
              to={DEMO ? `/session/${DEMO_RUN_ID}` : "/library"}
              className="btn btn-secondary"
              style={cardBtn}
            >
              {DEMO ? "Open the session" : "Browse the library"}
            </Link>
          </article>

          <article className="card elev-sm" style={card}>
            <div className="card-kicker">Source</div>
            <div className="card-title">The code</div>
            <p className="card-body">
              Three orchestrators, the profiling harness, and the FastAPI
              backend behind them. Python for now, with a Rust port under
              consideration.
            </p>
            <a
              href={REPO_URL}
              target="_blank"
              rel="noreferrer"
              className="btn btn-secondary"
              style={cardBtn}
            >
              Read it on GitHub
            </a>
          </article>
        </div>
      </section>

      {/* ── What is and is not live ──────────────────────────────────────── */}
      <section style={{ ...section, borderBottom: "none" }} aria-labelledby="live">
        <span style={eyebrow}>{DEMO ? "About this build" : "Before you start one"}</span>
        <h2 id="live" style={sectionHeading}>
          {DEMO ? "There is no backend behind this" : "Runs are granted by hand"}
        </h2>
        <p style={prose}>
          {DEMO ? (
            <>
              This site is static files. A run takes ten to thirty minutes and
              needs ffmpeg, pandoc and a headless browser, none of which a
              static host can give it. The session and the numbers above came
              out of runs I did on my own machine, and they are built into the
              page.
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

const DIAGRAM_ALT =
  "Pipeline: phase 1 generates notes sequentially; phase 2 runs flashcards, " +
  "video and the notes PDF in parallel; phase 3 renders the flashcards PDF.";

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
  maxWidth: "18ch",
};

/** Type only. The two-column treatment — what a broadsheet does with a
 *  standfirst, and the only place in this app that uses columns — is the
 *  `.standfirst` class in index.css, because it needs a media query: below
 *  roughly 700px two columns leave four words a line. An inline style cannot
 *  carry one. */
const standfirst: React.CSSProperties = {
  fontSize: size.lead,
  lineHeight: 1.55,
  color: c.ink,
};

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

const figureRow: React.CSSProperties = {
  display: "flex",
  flexWrap: "wrap",
  gap: space.section,
  margin: `${space.base}px 0 ${space.xl}px`,
};

const figure: React.CSSProperties = {
  margin: 0,
  flex: "1 1 260px",
  minWidth: 0,
};

const figCaption: React.CSSProperties = {
  marginTop: space.sm,
  fontSize: size.small,
  lineHeight: 1.5,
  color: muted,
  maxWidth: "34ch",
};

const strong: React.CSSProperties = { color: c.ink, fontWeight: headingWeight };

/** The counter-argument, given the weight of a pull quote rather than a
 *  footnote. It is the more interesting half of the result. */
const pullQuote: React.CSSProperties = {
  margin: `0 0 ${space.base}px`,
  padding: `${space.md}px 0 ${space.md}px ${space.base}px`,
  borderLeft: `3px solid ${c.flag}`,
  fontSize: size.lead,
  lineHeight: 1.5,
  color: c.ink,
  maxWidth: layout.measure,
};

const quoteFooter: React.CSSProperties = {
  marginTop: space.sm,
  fontSize: size.small,
  fontStyle: "italic",
  color: muted,
};

const caveat: React.CSSProperties = {
  fontSize: size.small,
  lineHeight: 1.55,
  color: mutedFaint,
  maxWidth: layout.measure,
  margin: 0,
};

const diagram: React.CSSProperties = {
  marginTop: space.base,
  padding: space.base,
  border: hairline,
  background: c.paperCard,
  maxWidth: 620,
};

const stage: React.CSSProperties = { display: "block" };

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

const cardRow: React.CSSProperties = {
  display: "grid",
  gridTemplateColumns: "repeat(auto-fit, minmax(230px, 1fr))",
  gap: space.base,
  marginTop: space.base,
};

const card: React.CSSProperties = {
  display: "flex",
  flexDirection: "column",
  gap: space.sm,
};

const cardBtn: React.CSSProperties = {
  textDecoration: "none",
  marginTop: "auto",
  alignSelf: "flex-start",
};

const code: React.CSSProperties = {
  fontFamily: font.mono,
  fontSize: "0.88em",
};

const link: React.CSSProperties = {
  color: c.reagentDeep,
  textDecorationThickness: "1px",
  textUnderlineOffset: "2px",
};
